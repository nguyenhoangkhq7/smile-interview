"""Semantic embedding service using SBERT with L2 normalization, truncation detection, and stable provenance."""
import hashlib
import logging
import math
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from matching_cv.app.core.config import settings
from matching_cv.app.core.model_loader import ModelLoader, model_loader
from matching_cv.app.schemas.semantic_representation import EmbeddingRecord
from matching_cv.app.services.extraction_adapter import (
    AdaptedEvidenceItem,
    AdaptedRequirementItem,
    AdaptedSkillItem,
)

logger = logging.getLogger(__name__)


class SemanticEmbeddingService:
    """Service encoding text entities into SBERT semantic vectors with rigorous quality checks."""

    def __init__(
        self,
        loader: Optional[ModelLoader] = None,
        model_name: Optional[str] = None,
        revision: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self.loader = loader or model_loader
        self.model_name = model_name or settings.STAGE3_MODEL_NAME
        self.revision = revision or settings.STAGE3_MODEL_REVISION
        self.batch_size = batch_size or settings.STAGE3_BATCH_SIZE

    def _get_model(self) -> SentenceTransformer:
        return self.loader.get_model(self.model_name, revision=self.revision)

    def _get_tokenizer(self) -> Any:
        return self.loader.get_tokenizer(self.model_name, revision=self.revision)

    def _get_max_seq_length(self) -> int:
        return self.loader.get_max_seq_length(self.model_name, revision=self.revision)

    def _compute_vector_id(self, text_hash: str) -> str:
        """Generate content-based vector identifier tied to model revision and text hash."""
        rev_prefix = (self.revision or "default")[:8]
        return f"vec_{rev_prefix}_{text_hash[:16]}"

    def check_truncation(self, text: str) -> Tuple[bool, int, int]:
        """
        Check whether text exceeds max sequence length using the actual model tokenizer BEFORE inference.
        Returns (is_truncated, token_count, max_seq_length).
        """
        tokenizer = self._get_tokenizer()
        max_seq_length = self._get_max_seq_length()

        if tokenizer is None:
            approx_tokens = len(text.split())
            return approx_tokens > max_seq_length, approx_tokens, max_seq_length

        try:
            token_ids = tokenizer.encode(text, add_special_tokens=True, truncation=False)
            token_count = len(token_ids)
            is_truncated = token_count > max_seq_length
            return is_truncated, token_count, max_seq_length
        except Exception as exc:
            logger.warning(f"Tokenizer encoding error on text check: {exc}")
            approx = len(text.split())
            return approx > max_seq_length, approx, max_seq_length

    def segment_text(self, text: str) -> List[str]:
        """
        Split overlength text into segments each within max_seq_length tokens.
        Uses the model tokenizer if available, otherwise word-based splitting.
        """
        tokenizer = self._get_tokenizer()
        max_seq = self._get_max_seq_length()
        # Reserve special tokens ([CLS] and [SEP])
        chunk_tokens = max(10, max_seq - 2)

        if tokenizer is not None:
            try:
                token_ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
                if len(token_ids) <= max_seq:
                    return [text]
                chunks: List[str] = []
                for i in range(0, len(token_ids), chunk_tokens):
                    slice_ids = token_ids[i : i + chunk_tokens]
                    decoded = tokenizer.decode(slice_ids, skip_special_tokens=True).strip()
                    if decoded:
                        chunks.append(decoded)
                return chunks if chunks else [text]
            except Exception as exc:
                logger.warning(f"Error segmenting with tokenizer: {exc}. Falling back to word splitting.")

        # Fallback word-level chunking
        words = text.split()
        if len(words) <= chunk_tokens:
            return [text]
        chunks = []
        for i in range(0, len(words), chunk_tokens):
            chunk_str = " ".join(words[i : i + chunk_tokens]).strip()
            if chunk_str:
                chunks.append(chunk_str)
        return chunks if chunks else [text]

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        Batch encode texts into L2-normalized float32 vectors.
        Validates dimensions (768) and rejects NaN/Inf values.
        """
        if not texts:
            dim = settings.STAGE3_EMBEDDING_DIM
            return np.empty((0, dim), dtype=np.float32)

        model = self._get_model()

        # Batch encode with L2 normalization enabled
        embeddings_tensor = model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        # 1. Non-finite detection (NaN / Inf)
        if torch.isnan(embeddings_tensor).any():
            raise ValueError("Detected NaN in generated embedding vectors.")
        if torch.isinf(embeddings_tensor).any():
            raise ValueError("Detected Inf in generated embedding vectors.")

        # 2. Dimension validation
        expected_dim = settings.STAGE3_EMBEDDING_DIM
        actual_dim = embeddings_tensor.shape[1]
        if actual_dim != expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim} from {self.model_name}"
            )

        # 3. L2 normalization validation (vector norms must be ~1.0)
        norms = torch.linalg.norm(embeddings_tensor, dim=1)
        if not torch.allclose(norms, torch.ones_like(norms), atol=1e-3):
            # Enforce L2 normalization if not already exact
            embeddings_tensor = torch.nn.functional.normalize(embeddings_tensor, p=2, dim=1)

        return embeddings_tensor.cpu().numpy().astype(np.float32)

    def encode_unique_texts(self, texts: List[str]) -> Dict[str, np.ndarray]:
        """
        Deduplicate texts, batch-encode the unique set once, and map vectors back to text strings.
        Ensures identical texts across occurrences/skills do not trigger duplicate inference.
        """
        unique_texts = list(dict.fromkeys(texts))
        if not unique_texts:
            return {}
        vectors = self.encode_batch(unique_texts)
        return {text: vectors[idx] for idx, text in enumerate(unique_texts)}

    @staticmethod
    def _build_skill_metadata(skill: AdaptedSkillItem) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "category": skill.category,
            "kind": skill.kind,
            "basis": skill.basis,
            "confidence": skill.confidence,
            "sections": skill.sections,
            "legacy_id": getattr(skill, "legacy_id", skill.occurrence_id),
            "competency_granularity": getattr(skill, "granularity", None) or getattr(skill, "metadata", {}).get("competency_granularity", "atomic_skill"),
            "is_competency": getattr(skill, "metadata", {}).get("is_competency", getattr(skill, "kind", None) != "context"),
            "constituent_skill_ids": getattr(skill, "metadata", {}).get("constituent_skill_ids", []),
            "parent_compound_skill_ids": getattr(skill, "metadata", {}).get("parent_compound_skill_ids", []),
        }
        if skill.extraction_type == "implicit" and skill.raw_skill:
            raw = skill.raw_skill
            if hasattr(raw, "evidences") and raw.evidences:
                meta["inferred_evidences"] = [
                    e.model_dump() if hasattr(e, "model_dump") else e.dict() if hasattr(e, "dict") else str(e)
                    for e in raw.evidences
                ]
                first_ev = raw.evidences[0]
                if hasattr(first_ev, "reasoning"):
                    meta["reasoning"] = first_ev.reasoning
                if hasattr(first_ev, "llm_confidence_raw"):
                    meta["llm_confidence_raw"] = first_ev.llm_confidence_raw
        return meta

    def encode_skills(
        self,
        skills: List[AdaptedSkillItem],
        doc_type: Literal["CV", "JD"],
        source_identifier: str,
        definition_dict: Optional[Dict[str, str]] = None,
        include_vectors: bool = False,
        on_overlength: Literal["error", "reject", "segment"] = "error",
    ) -> Tuple[List[EmbeddingRecord], np.ndarray]:
        """
        Encode active skills into EmbeddingRecords and valid vector matrix.
        Separates occurrence ID from content vector ID and applies pre-inference truncation policies.
        """
        if not skills:
            return [], np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        records: List[EmbeddingRecord] = []
        texts_to_encode: List[str] = []

        for skill in skills:
            src_text, strategy = skill.get_embedding_input(definition_dict)
            is_trunc, token_cnt, max_seq = self.check_truncation(src_text)

            if is_trunc:
                if on_overlength == "error":
                    raise ValueError(
                        f"Skill text exceeds maximum sequence length ({token_cnt} > {max_seq}): '{src_text[:60]}...'"
                    )
                elif on_overlength == "reject":
                    text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
                    vec_id = self._compute_vector_id(text_hash)
                    records.append(
                        EmbeddingRecord(
                            occurrence_id=skill.occurrence_id,
                            vector_id=vec_id,
                            embedding_id=skill.occurrence_id,
                            document_type=doc_type,
                            source_identifier=source_identifier,
                            target_type="skill",
                            source_text=src_text,
                            associated_skill_ids=[skill.skill_id],
                            associated_skill_names=[skill.display_name],
                            extraction_type=skill.extraction_type,
                            model_id=self.model_name,
                            model_revision=self.revision,
                            embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                            construction_strategy=strategy,
                            text_hash=text_hash,
                            is_truncated=True,
                            truncation_status="rejected",
                            token_count=token_cnt,
                            max_seq_length=max_seq,
                            vector=None,
                            metadata=self._build_skill_metadata(skill),
                        )
                    )
                    continue
                elif on_overlength == "segment":
                    chunks = self.segment_text(src_text)
                    for c_idx, chunk_text in enumerate(chunks):
                        c_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                        c_vec_id = self._compute_vector_id(c_hash)
                        c_occ_id = f"{skill.occurrence_id}_chunk_{c_idx}"
                        texts_to_encode.append(chunk_text)
                        records.append(
                            EmbeddingRecord(
                                occurrence_id=c_occ_id,
                                vector_id=c_vec_id,
                                embedding_id=c_occ_id,
                                document_type=doc_type,
                                source_identifier=source_identifier,
                                target_type="skill",
                                source_text=chunk_text,
                                associated_skill_ids=[skill.skill_id],
                                associated_skill_names=[skill.display_name],
                                extraction_type=skill.extraction_type,
                                model_id=self.model_name,
                                model_revision=self.revision,
                                embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                                construction_strategy=strategy,
                                text_hash=c_hash,
                                is_truncated=True,
                                truncation_status="segmented",
                                segment_info={
                                    "parent_id": skill.occurrence_id,
                                    "chunk_index": c_idx,
                                    "total_chunks": len(chunks),
                                },
                                token_count=token_cnt,
                                max_seq_length=max_seq,
                                vector=None,
                                metadata=self._build_skill_metadata(skill),
                            )
                        )
                    continue

            # Standard non-truncated text
            text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
            vec_id = self._compute_vector_id(text_hash)
            texts_to_encode.append(src_text)
            records.append(
                EmbeddingRecord(
                    occurrence_id=skill.occurrence_id,
                    vector_id=vec_id,
                    embedding_id=skill.occurrence_id,
                    document_type=doc_type,
                    source_identifier=source_identifier,
                    target_type="skill",
                    source_text=src_text,
                    associated_skill_ids=[skill.skill_id],
                    associated_skill_names=[skill.display_name],
                    extraction_type=skill.extraction_type,
                    model_id=self.model_name,
                    model_revision=self.revision,
                    embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                    construction_strategy=strategy,
                    text_hash=text_hash,
                    is_truncated=False,
                    truncation_status="not_truncated",
                    token_count=token_cnt,
                    max_seq_length=max_seq,
                    vector=None,
                    metadata=self._build_skill_metadata(skill),
                )
            )

        # Batch encode unique texts and associate vectors
        text_vector_map = self.encode_unique_texts(texts_to_encode)
        valid_vec_list: List[np.ndarray] = []

        for r in records:
            if r.truncation_status != "rejected" and r.source_text in text_vector_map:
                vec = text_vector_map[r.source_text]
                valid_vec_list.append(vec)
                if include_vectors:
                    r.vector = vec.tolist()

        if valid_vec_list:
            vectors_array = np.vstack(valid_vec_list).astype(np.float32)
        else:
            vectors_array = np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        return records, vectors_array

    def encode_evidences(
        self,
        evidences: List[AdaptedEvidenceItem],
        include_vectors: bool = False,
        on_overlength: Literal["error", "reject", "segment"] = "error",
    ) -> Tuple[List[EmbeddingRecord], np.ndarray]:
        """
        Encode granular evidence occurrences into EmbeddingRecords and valid vector matrix.
        Preserves occurrence provenance while reusing vectors for identical text across occurrences.
        """
        if not evidences:
            return [], np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        records: List[EmbeddingRecord] = []
        texts_to_encode: List[str] = []

        for ev in evidences:
            src_text = ev.text
            is_trunc, token_cnt, max_seq = self.check_truncation(src_text)

            ext_type = (
                ev.extraction_type
                if ev.extraction_type in ("explicit", "implicit")
                else "explicit"
            )

            common_meta = {
                "section": ev.section,
                "start": ev.start,
                "end": ev.end,
                "offset_resolved": ev.offset_resolved,
                "verbatim_ok": ev.verbatim_ok,
                "basis": ev.basis,
                "reasoning": ev.reasoning,
                "llm_confidence_raw": ev.llm_confidence_raw,
                "evidences_meta": ev.evidences_meta,
            }

            if is_trunc:
                if on_overlength == "error":
                    raise ValueError(
                        f"Evidence text exceeds maximum sequence length ({token_cnt} > {max_seq}): '{src_text[:60]}...'"
                    )
                elif on_overlength == "reject":
                    text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
                    vec_id = self._compute_vector_id(text_hash)
                    records.append(
                        EmbeddingRecord(
                            occurrence_id=ev.occurrence_id,
                            vector_id=vec_id,
                            embedding_id=ev.occurrence_id,
                            document_type=ev.document_type,
                            source_identifier=ev.source_identifier,
                            target_type="cv_evidence" if ev.document_type == "CV" else "jd_requirement",
                            source_text=src_text,
                            associated_skill_ids=ev.associated_skill_ids,
                            associated_skill_names=ev.associated_skill_names,
                            extraction_type=ext_type,
                            model_id=self.model_name,
                            model_revision=self.revision,
                            embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                            construction_strategy=ev.construction_strategy,
                            text_hash=text_hash,
                            is_truncated=True,
                            truncation_status="rejected",
                            token_count=token_cnt,
                            max_seq_length=max_seq,
                            vector=None,
                            metadata=common_meta,
                        )
                    )
                    continue
                elif on_overlength == "segment":
                    chunks = self.segment_text(src_text)
                    for c_idx, chunk_text in enumerate(chunks):
                        c_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                        c_vec_id = self._compute_vector_id(c_hash)
                        c_occ_id = f"{ev.occurrence_id}_chunk_{c_idx}"
                        texts_to_encode.append(chunk_text)
                        records.append(
                            EmbeddingRecord(
                                occurrence_id=c_occ_id,
                                vector_id=c_vec_id,
                                embedding_id=c_occ_id,
                                document_type=ev.document_type,
                                source_identifier=ev.source_identifier,
                                target_type="cv_evidence" if ev.document_type == "CV" else "jd_requirement",
                                source_text=chunk_text,
                                associated_skill_ids=ev.associated_skill_ids,
                                associated_skill_names=ev.associated_skill_names,
                                extraction_type=ext_type,
                                model_id=self.model_name,
                                model_revision=self.revision,
                                embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                                construction_strategy=ev.construction_strategy,
                                text_hash=c_hash,
                                is_truncated=True,
                                truncation_status="segmented",
                                segment_info={
                                    "parent_id": ev.occurrence_id,
                                    "chunk_index": c_idx,
                                    "total_chunks": len(chunks),
                                },
                                token_count=token_cnt,
                                max_seq_length=max_seq,
                                vector=None,
                                metadata=common_meta,
                            )
                        )
                    continue

            # Standard non-truncated text
            text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
            vec_id = self._compute_vector_id(text_hash)
            texts_to_encode.append(src_text)
            records.append(
                EmbeddingRecord(
                    occurrence_id=ev.occurrence_id,
                    vector_id=vec_id,
                    embedding_id=ev.occurrence_id,
                    document_type=ev.document_type,
                    source_identifier=ev.source_identifier,
                    target_type="cv_evidence" if ev.document_type == "CV" else "jd_requirement",
                    source_text=src_text,
                    associated_skill_ids=ev.associated_skill_ids,
                    associated_skill_names=ev.associated_skill_names,
                    extraction_type=ext_type,
                    model_id=self.model_name,
                    model_revision=self.revision,
                    embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                    construction_strategy=ev.construction_strategy,
                    text_hash=text_hash,
                    is_truncated=False,
                    truncation_status="not_truncated",
                    token_count=token_cnt,
                    max_seq_length=max_seq,
                    vector=None,
                    metadata=common_meta,
                )
            )

        # Batch encode unique texts and associate vectors
        text_vector_map = self.encode_unique_texts(texts_to_encode)
        valid_vec_list: List[np.ndarray] = []

        for r in records:
            if r.truncation_status != "rejected" and r.source_text in text_vector_map:
                vec = text_vector_map[r.source_text]
                valid_vec_list.append(vec)
                if include_vectors:
                    r.vector = vec.tolist()

        if valid_vec_list:
            vectors_array = np.vstack(valid_vec_list).astype(np.float32)
        else:
            vectors_array = np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        return records, vectors_array

    def encode_requirements(
        self,
        requirements: List[AdaptedRequirementItem],
        include_vectors: bool = False,
        on_overlength: Literal["error", "reject", "segment"] = "error",
    ) -> Tuple[List[EmbeddingRecord], np.ndarray]:
        """
        Encode segmented JD requirements into EmbeddingRecords and valid vector matrix.
        Preserves span offsets and verified textual skill associations without tagging as 'explicit'.
        """
        if not requirements:
            return [], np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        records: List[EmbeddingRecord] = []
        texts_to_encode: List[str] = []

        for req in requirements:
            src_text = req.text
            is_trunc, token_cnt, max_seq = self.check_truncation(src_text)

            common_meta = {
                "section": req.section,
                "start": req.start,
                "end": req.end,
                "source_strategy": req.source_strategy,
                "associations_meta": getattr(req, "associations_meta", []),
            }

            if is_trunc:
                if on_overlength == "error":
                    raise ValueError(
                        f"Requirement text exceeds maximum sequence length ({token_cnt} > {max_seq}): '{src_text[:60]}...'"
                    )
                elif on_overlength == "reject":
                    text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
                    vec_id = self._compute_vector_id(text_hash)
                    records.append(
                        EmbeddingRecord(
                            occurrence_id=req.occurrence_id,
                            vector_id=vec_id,
                            embedding_id=req.occurrence_id,
                            document_type="JD",
                            source_identifier=req.source_identifier,
                            target_type="jd_requirement",
                            source_text=src_text,
                            associated_skill_ids=req.associated_skill_ids,
                            associated_skill_names=req.associated_skill_names,
                            extraction_type=None,  # Do not classify requirement as explicit/implicit
                            model_id=self.model_name,
                            model_revision=self.revision,
                            embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                            construction_strategy=req.source_strategy,
                            text_hash=text_hash,
                            is_truncated=True,
                            truncation_status="rejected",
                            token_count=token_cnt,
                            max_seq_length=max_seq,
                            vector=None,
                            metadata=common_meta,
                        )
                    )
                    continue
                elif on_overlength == "segment":
                    chunks = self.segment_text(src_text)
                    for c_idx, chunk_text in enumerate(chunks):
                        c_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                        c_vec_id = self._compute_vector_id(c_hash)
                        c_occ_id = f"{req.occurrence_id}_chunk_{c_idx}"
                        texts_to_encode.append(chunk_text)
                        records.append(
                            EmbeddingRecord(
                                occurrence_id=c_occ_id,
                                vector_id=c_vec_id,
                                embedding_id=c_occ_id,
                                document_type="JD",
                                source_identifier=req.source_identifier,
                                target_type="jd_requirement",
                                source_text=chunk_text,
                                associated_skill_ids=req.associated_skill_ids,
                                associated_skill_names=req.associated_skill_names,
                                extraction_type=None,
                                model_id=self.model_name,
                                model_revision=self.revision,
                                embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                                construction_strategy=req.source_strategy,
                                text_hash=c_hash,
                                is_truncated=True,
                                truncation_status="segmented",
                                segment_info={
                                    "parent_id": req.occurrence_id,
                                    "chunk_index": c_idx,
                                    "total_chunks": len(chunks),
                                },
                                token_count=token_cnt,
                                max_seq_length=max_seq,
                                vector=None,
                                metadata=common_meta,
                            )
                        )
                    continue

            # Standard non-truncated text
            text_hash = hashlib.sha256(src_text.encode("utf-8")).hexdigest()
            vec_id = self._compute_vector_id(text_hash)
            texts_to_encode.append(src_text)
            records.append(
                EmbeddingRecord(
                    occurrence_id=req.occurrence_id,
                    vector_id=vec_id,
                    embedding_id=req.occurrence_id,
                    document_type="JD",
                    source_identifier=req.source_identifier,
                    target_type="jd_requirement",
                    source_text=src_text,
                    associated_skill_ids=req.associated_skill_ids,
                    associated_skill_names=req.associated_skill_names,
                    extraction_type=None,
                    model_id=self.model_name,
                    model_revision=self.revision,
                    embedding_dim=settings.STAGE3_EMBEDDING_DIM,
                    construction_strategy=req.source_strategy,
                    text_hash=text_hash,
                    is_truncated=False,
                    truncation_status="not_truncated",
                    token_count=token_cnt,
                    max_seq_length=max_seq,
                    vector=None,
                    metadata=common_meta,
                )
            )

        # Batch encode unique texts and associate vectors
        text_vector_map = self.encode_unique_texts(texts_to_encode)
        valid_vec_list: List[np.ndarray] = []

        for r in records:
            if r.truncation_status != "rejected" and r.source_text in text_vector_map:
                vec = text_vector_map[r.source_text]
                valid_vec_list.append(vec)
                if include_vectors:
                    r.vector = vec.tolist()

        if valid_vec_list:
            vectors_array = np.vstack(valid_vec_list).astype(np.float32)
        else:
            vectors_array = np.empty((0, settings.STAGE3_EMBEDDING_DIM), dtype=np.float32)

        return records, vectors_array


semantic_embedding_service = SemanticEmbeddingService()
