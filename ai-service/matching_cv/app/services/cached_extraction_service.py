"""Resolve previously extracted skills for known CV/JD documents."""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, status

from matching_cv.app.schemas.unified_skill_extraction import UnifiedExtractFileResponse
from matching_cv.app.services.document_parser import DocumentParserService

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_CACHE_DIR = _PACKAGE_ROOT / "data/cache/stage6c3b/doc_extraction"
PAIR_CACHE_DIR = _PACKAGE_ROOT / "data/cache/stage6b3_live"
CANONICAL_MAPPING_PATH = _PACKAGE_ROOT / "docs/verification/stage6d2r/canonical_pair_label_mapping.json"
COHORT_MANIFEST_PATH = _PACKAGE_ROOT / "docs/verification/stage6c3a/cohort100_manifest.json"


class CachedExtractionService:
    """Parse documents and reuse extraction data when the input matches a known cohort."""

    def __init__(self) -> None:
        self._canonical_mapping: Optional[Dict[str, Any]] = None
        self._doc_hash_to_id: Optional[Dict[str, str]] = None

    def parse_document(self, file_bytes: bytes, filename: str) -> str:
        """Extract and normalize text for cache matching."""
        _, extension = os.path.splitext(filename.lower())
        if extension == ".pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(file_bytes))
                if reader.is_encrypted:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"PDF file '{filename}' is encrypted or password-protected.",
                    )
            except HTTPException:
                raise
            except Exception as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Malformed or unreadable PDF structure in '{filename}': {error}",
                ) from error

            raw_text, _ = DocumentParserService.extract_text_from_pdf(file_bytes)
        else:
            raw_text = DocumentParserService.extract_text_from_txt(file_bytes)

        clean_text = DocumentParserService.clean_extracted_text(raw_text)
        if not clean_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Extracted document text from '{filename}' is empty or unreadable.",
            )
        if len(clean_text) > 1_000_000:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Extracted document text from '{filename}' exceeds the 1 MB limit.",
            )
        return clean_text

    def _load_mapping(self) -> Tuple[Dict[str, Any], Dict[str, str]]:
        if self._canonical_mapping is None:
            if os.path.exists(CANONICAL_MAPPING_PATH):
                with open(CANONICAL_MAPPING_PATH, "r", encoding="utf-8") as file:
                    self._canonical_mapping = json.load(file).get("mapping", {})
            else:
                self._canonical_mapping = {}

            self._doc_hash_to_id = {}
            if os.path.exists(COHORT_MANIFEST_PATH):
                with open(COHORT_MANIFEST_PATH, "r", encoding="utf-8") as file:
                    manifest = json.load(file)
                for pair in manifest.get("pairs", []):
                    if pair.get("cv_text_sha256") and pair.get("cv_id"):
                        self._doc_hash_to_id[pair["cv_text_sha256"]] = pair["cv_id"]
                    if pair.get("jd_text_sha256") and pair.get("jd_id"):
                        self._doc_hash_to_id[pair["jd_text_sha256"]] = pair["jd_id"]

        return self._canonical_mapping, self._doc_hash_to_id or {}

    def resolve_cached_extraction(
        self,
        cv_text: str,
        jd_text: str,
        cv_filename: str,
        jd_filename: str,
    ) -> Tuple[Optional[UnifiedExtractFileResponse], Optional[str], Optional[str]]:
        """Return cached extraction, matching pair ID, and cache provenance when available."""
        mapping, hash_to_id = self._load_mapping()
        cv_hash = hashlib.sha256(cv_text.encode("utf-8")).hexdigest()
        jd_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()

        matched_pair_id = None
        for pair_id, pair in mapping.items():
            if (pair["cv_id"] in cv_filename and pair["jd_id"] in jd_filename) or (
                pair_id in cv_filename or pair_id in jd_filename
            ):
                matched_pair_id = pair_id
                break

        if matched_pair_id is None:
            cv_id = hash_to_id.get(cv_hash)
            jd_id = hash_to_id.get(jd_hash)
            if cv_id and jd_id:
                matched_pair_id = next(
                    (
                        pair_id
                        for pair_id, pair in mapping.items()
                        if pair["cv_id"] == cv_id and pair["jd_id"] == jd_id
                    ),
                    None,
                )

        if matched_pair_id:
            pair_path = os.path.join(PAIR_CACHE_DIR, f"{matched_pair_id}_extraction.json")
            if os.path.exists(pair_path):
                with open(pair_path, "r", encoding="utf-8") as file:
                    payload = json.load(file)
                return UnifiedExtractFileResponse.model_validate(payload), matched_pair_id, "CERTIFIED_CLEAN_COHORT"

        cv_id = hash_to_id.get(cv_hash) or (cv_filename.split(".")[0] if cv_filename.startswith("cv_") else None)
        jd_id = hash_to_id.get(jd_hash) or (jd_filename.split(".")[0] if jd_filename.startswith("jd_") else None)
        if not cv_id or not jd_id:
            return None, None, None

        cv_path = os.path.join(DOCUMENT_CACHE_DIR, f"{cv_id}.json")
        jd_path = os.path.join(DOCUMENT_CACHE_DIR, f"{jd_id}.json")
        if not (os.path.exists(cv_path) and os.path.exists(jd_path)):
            return None, None, None

        with open(cv_path, "r", encoding="utf-8") as file:
            cv_doc = json.load(file)
        with open(jd_path, "r", encoding="utf-8") as file:
            jd_doc = json.load(file)

        cv_exp = cv_doc.get("extracted_skills", {}).get("explicit", [])
        cv_imp = cv_doc.get("extracted_skills", {}).get("implicit", [])
        jd_exp = jd_doc.get("extracted_skills", {}).get("explicit", [])
        jd_imp = jd_doc.get("extracted_skills", {}).get("implicit", [])
        payload = {
            "run_id": f"cached_doc_{cv_id}_{jd_id}",
            "status": "completed",
            "cv": self._document_payload(cv_id, "CV", cv_hash, cv_text, cv_exp, cv_imp),
            "jd": self._document_payload(jd_id, "JD", jd_hash, jd_text, jd_exp, jd_imp),
        }
        return UnifiedExtractFileResponse.model_validate(payload), matched_pair_id, "CACHED_DOCUMENT_CORPUS"

    @staticmethod
    def _document_payload(
        document_id: str,
        document_type: str,
        text_hash: str,
        text: str,
        explicit_skills: list[dict[str, Any]],
        implicit_skills: list[dict[str, Any]],
    ) -> Dict[str, Any]:
        base = {
            "filename": f"{document_id}.txt",
            "document_type": document_type,
            "text_sha256": text_hash,
        }
        return {
            **base,
            "raw_text": text,
            "explicit": {
                **base,
                "stats": {"total_mentions": len(explicit_skills), "unique_skills": len(explicit_skills)},
                "skills": explicit_skills,
            },
            "implicit": {
                **base,
                "stats": {"total_inferences": len(implicit_skills), "unique_skills": len(implicit_skills)},
                "skills": implicit_skills,
            },
        }


cached_extraction_service = CachedExtractionService()
