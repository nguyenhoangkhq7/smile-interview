"""Data adapter extracting and structuring skills, evidences, and requirements from unified extraction responses."""
import hashlib
import logging
import re
from typing import NamedTuple, Any, Dict, List, Literal, Optional, Set, Tuple

from matching_cv.app.schemas.implicit_skill_extraction import (
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
)
from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.schemas.unified_skill_extraction import (
    DocumentUnifiedResult,
    DocumentValidationResult,
    DuplicateImplicitSkill,
    UnifiedExtractFileResponse,
)
from matching_cv.app.services.competency_granularity import (
    analyze_constituent_overlaps,
    classify_competency_granularity,
)
from matching_cv.app.services.section_tagger import find_section_spans
from matching_cv.app.services.unified_skill_service import normalize_skill_name

logger = logging.getLogger(__name__)


def build_term_pattern(term: str) -> re.Pattern:
    """
    Build a conservative regex pattern for technical skill matching that handles punctuation
    (e.g., C++, C#, .NET, Node.js, Spring Boot, REST API) and avoids substring false positives
    (e.g., C matching inside C++ or C#, Java matching inside JavaScript).
    """
    clean_term = term.strip()
    if not clean_term:
        return re.compile(r"(?!)")  # Never match empty string

    escaped = re.escape(clean_term)

    # Left boundary:
    # If starts with alphanumeric, cannot be preceded by alphanumeric
    if clean_term[0].isalnum():
        left = r"(?<![a-zA-Z0-9])"
    else:
        left = r"(?<!\S)"

    # Right boundary:
    if clean_term[-1].isalnum():
        # Special case: single-letter 'C' must not match 'C++' or 'C#'
        if clean_term.upper() == "C":
            right = r"(?![a-zA-Z0-9+#])"
        else:
            right = r"(?![a-zA-Z0-9])"
    else:
        # Ends with symbol (like ++ or #)
        right = r"(?![a-zA-Z0-9])"

    return re.compile(left + escaped + right, re.IGNORECASE)



def compute_document_namespace(
    doc_result: Optional[DocumentUnifiedResult],
    doc_type: str,
    run_id: Optional[str] = None,
) -> str:
    """
    Compute a deterministic collision-resistant document namespace.
    Prioritizes text_sha256, then filename hash, then run_id hash.
    Format: {doc_type.lower()}_{hash[:8]}
    """
    if doc_result:
        if getattr(doc_result, "text_sha256", None):
            return f"{doc_type.lower()}_{doc_result.text_sha256[:8]}"
        if getattr(doc_result, "filename", None):
            fn_hash = hashlib.sha256(doc_result.filename.encode("utf-8")).hexdigest()[:8]
            return f"{doc_type.lower()}_{fn_hash}"
    if run_id:
        r_hash = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
        return f"{doc_type.lower()}_{r_hash}"
    return doc_type.lower()


class ActiveSkillsResult(tuple):
    """2-tuple (active_skills, duplicate_audit) with attribute access for validation_diagnostics and effective_validation."""
    active_skills: List["AdaptedSkillItem"]
    duplicate_audit: List[DuplicateImplicitSkill]
    validation_diagnostics: Dict[str, Any]
    effective_validation: Optional[DocumentValidationResult]

    def __new__(
        cls,
        active_skills: List["AdaptedSkillItem"],
        duplicate_audit: List[DuplicateImplicitSkill],
        validation_diagnostics: Optional[Dict[str, Any]] = None,
        effective_validation: Optional[DocumentValidationResult] = None,
    ):
        instance = super().__new__(cls, (active_skills, duplicate_audit))
        instance.active_skills = active_skills
        instance.duplicate_audit = duplicate_audit
        instance.validation_diagnostics = validation_diagnostics or {}
        instance.effective_validation = effective_validation
        return instance

class AdaptedSkillItem:
    """Internal normalized representation of an active skill (explicit or accepted implicit)."""

    def __init__(
        self,
        occurrence_id: str,
        skill_id: str,
        display_name: str,
        extraction_type: Literal["explicit", "implicit"],
        category: Optional[str] = None,
        kind: Optional[str] = None,
        basis: Optional[str] = None,
        confidence: Optional[float] = None,
        sections: Optional[List[str]] = None,
        raw_skill: Optional[Any] = None,
        legacy_id: Optional[str] = None,
        granularity: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.occurrence_id = occurrence_id
        self.skill_id = skill_id
        self.display_name = display_name
        self.extraction_type = extraction_type
        self.category = category
        self.kind = kind
        self.basis = basis
        self.confidence = confidence
        self.sections = sections or []
        self.raw_skill = raw_skill
        self.legacy_id = legacy_id or occurrence_id
        self.granularity = granularity or classify_competency_granularity(display_name, kind=kind, category=category)
        self.metadata = metadata or {}
        self.metadata.setdefault("competency_granularity", self.granularity)
        self.metadata.setdefault("is_competency", self.granularity in ("atomic_skill", "compound_competency"))

    def get_embedding_input(self, definition_dict: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
        """
        Return (text_to_encode, construction_strategy).
        Strategy A (default): 'skill_name'
        Strategy B (experimental): 'skill_name + definition' if trusted definition provided.
        """
        if definition_dict and self.display_name in definition_dict:
            definition = definition_dict[self.display_name].strip()
            return f"{self.display_name}: {definition}", "skill_name_and_definition"
        return self.display_name, "skill_name"


class AdaptedEvidenceOccurrence:
    """Internal granular occurrence of evidence in a document."""

    def __init__(
        self,
        occurrence_id: str,
        text: str,
        document_type: Literal["CV", "JD"],
        source_identifier: str,
        construction_strategy: str,
        extraction_type: Literal["explicit", "implicit"],
        section: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        offset_resolved: bool = False,
        verbatim_ok: bool = True,
        basis: Optional[str] = None,
        reasoning: Optional[str] = None,
        llm_confidence_raw: Optional[float] = None,
    ) -> None:
        self.occurrence_id = occurrence_id
        self.text = text
        self.document_type = document_type
        self.source_identifier = source_identifier
        self.construction_strategy = construction_strategy
        self.extraction_type = extraction_type
        self.section = section
        self.start = start
        self.end = end
        self.offset_resolved = offset_resolved
        self.verbatim_ok = verbatim_ok
        self.basis = basis
        self.reasoning = reasoning
        self.llm_confidence_raw = llm_confidence_raw
        self.associated_skill_ids: List[str] = []
        self.associated_skill_names: List[str] = []
        self.evidences_meta: List[Dict[str, Any]] = []

    def add_skill_association(
        self,
        skill_id: str,
        skill_name: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if skill_id not in self.associated_skill_ids:
            self.associated_skill_ids.append(skill_id)
        if skill_name not in self.associated_skill_names:
            self.associated_skill_names.append(skill_name)
        if meta:
            self.evidences_meta.append(meta)


# Backwards compatibility alias
AdaptedEvidenceItem = AdaptedEvidenceOccurrence


class AdaptedRequirementItem:
    """Internal structured requirement item segmented from JD with span offsets."""

    def __init__(
        self,
        occurrence_id: str,
        text: str,
        source_identifier: str,
        section: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        source_strategy: str = "raw_jd_text",
        associated_skill_ids: Optional[List[str]] = None,
        associated_skill_names: Optional[List[str]] = None,
        associations_meta: Optional[List[Dict[str, Any]]] = None,
        suppressed_associations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.occurrence_id = occurrence_id
        self.text = text
        self.source_identifier = source_identifier
        self.section = section
        self.start = start
        self.end = end
        self.source_strategy = source_strategy
        self.associated_skill_ids = associated_skill_ids or []
        self.associated_skill_names = associated_skill_names or []
        self.associations_meta = associations_meta or []
        self.suppressed_associations = suppressed_associations or []

    def add_skill_association(
        self,
        skill_id: str,
        skill_name: str,
        extraction_type: Literal["explicit", "implicit"] = "explicit",
        entity_kind: Optional[str] = "skill",
        association_method: Optional[str] = None,
        verification_status: Optional[str] = None,
        requirement_start: Optional[int] = None,
        requirement_end: Optional[int] = None,
        mention_start: Optional[int] = None,
        mention_end: Optional[int] = None,
        evidence_start: Optional[int] = None,
        evidence_end: Optional[int] = None,
        matched_surface_form: Optional[str] = None,
        evidence_reference: Optional[Dict[str, Any]] = None,
        source_document_id: Optional[str] = None,
        offset_resolved: Optional[bool] = None,
        verbatim_ok: Optional[bool] = None,
        basis: Optional[str] = None,
        reasoning: Optional[str] = None,
        confidence: Optional[float] = None,
        evidence_ref: Optional[Dict[str, Any]] = None,
    ) -> None:
        if skill_id not in self.associated_skill_ids:
            self.associated_skill_ids.append(skill_id)
        if skill_name not in self.associated_skill_names:
            self.associated_skill_names.append(skill_name)

        ev_ref = evidence_reference if evidence_reference is not None else (evidence_ref or {})

        canonical_map = {
            "verified_mention_span": "verified_mention_span",
            "verified_surface_form": "verified_surface_form",
            "surface_form_regex": "verified_surface_form",
            "span_overlap": "verified_mention_span",
            "sentence_evidence_supported": "sentence_evidence_supported",
            "evidence_sentence_match": "sentence_evidence_supported",
            "implicit_evidence_supported": "implicit_evidence_supported",
            "implicit_evidence_snippet_match": "implicit_evidence_supported",
            "implicit_inferred_from_match": "implicit_evidence_supported",
            "unresolved": "unresolved",
        }
        method = canonical_map.get(association_method, "sentence_evidence_supported") if association_method else None

        # Conservative defaults: require mention offsets for verified_mention_span
        if method == "verified_mention_span":
            if mention_start is None or mention_end is None:
                method = "sentence_evidence_supported"
                verification_status = "evidence_supported"
            else:
                verification_status = verification_status or "verified_mention"
        elif method is None:
            if mention_start is not None and mention_end is not None:
                method = "verified_mention_span"
                verification_status = verification_status or "verified_mention"
            else:
                method = "sentence_evidence_supported"
                verification_status = verification_status or "evidence_supported"
        else:
            if verification_status is None:
                if method == "verified_surface_form":
                    verification_status = "verified_surface"
                elif method == "implicit_evidence_supported":
                    verification_status = "implicit_inferred"
                else:
                    verification_status = "evidence_supported"

        ev_start = evidence_start or ev_ref.get("start") or ev_ref.get("snippet_start")
        ev_end = evidence_end or ev_ref.get("end") or ev_ref.get("snippet_end")

        meta = {
            "requirement_id": self.occurrence_id,
            "skill_id": skill_id,
            "skill_name": skill_name,
            "extraction_type": extraction_type,
            "entity_kind": entity_kind or "skill",
            "association_method": method,
            "verification_status": verification_status,
            "requirement_start": self.start if requirement_start is None else requirement_start,
            "requirement_end": self.end if requirement_end is None else requirement_end,
            "mention_start": mention_start,
            "mention_end": mention_end,
            "evidence_start": ev_start,
            "evidence_end": ev_end,
            "matched_surface_form": matched_surface_form,
            "evidence_reference": ev_ref,
            "source_document_id": self.source_identifier if source_document_id is None else source_document_id,
            "offset_resolved": (mention_start is not None and mention_end is not None) if offset_resolved is None else offset_resolved,
            "verbatim_ok": (verbatim_ok if verbatim_ok is not None else (extraction_type == "explicit")),
            "basis": basis,
            "reasoning": reasoning,
            "confidence": confidence,
        }

        # Deduplicate / upgrade association tier for the same skill_id
        existing_idx = None
        for i, m in enumerate(self.associations_meta):
            if m.get("skill_id") == skill_id:
                existing_idx = i
                break

        tier_rank = {
            "verified_mention_span": 1,
            "verified_surface_form": 2,
            "sentence_evidence_supported": 3,
            "implicit_evidence_supported": 4,
            "unresolved": 5,
        }

        if existing_idx is not None:
            curr_m = self.associations_meta[existing_idx]
            curr_rank = tier_rank.get(curr_m.get("association_method", ""), 99)
            new_rank = tier_rank.get(method, 99)
            if new_rank < curr_rank:
                self.associations_meta[existing_idx] = meta
        else:
            self.associations_meta.append(meta)


    def resolve_maximal_mention_spans(self, req_text: str) -> List[Dict[str, Any]]:
        """
        Deterministic post-matching resolution for overlapping skill mentions in this requirement.

        Rules (Section 4.2 and 4.5):
        1. Identifies containment: Candidate A is strictly contained inside Candidate B if:
           - Coordinates containment: (start_b <= start_a and end_a <= end_b and (end_a - start_a) < (end_b - start_b)), OR
           - Surface-form regex containment: sf_a is a token/word strictly matched inside sf_b via build_term_pattern(sf_a).
        2. Exception (Section 4.3): Compound coordinating phrases (e.g. 'React + TypeScript') must NOT suppress atomic skills.
        3. Suppresses Candidate A IF AND ONLY IF Candidate A has NO independent occurrence within req_text.
           An occurrence of sf_a is independent if it is NOT covered by any occurrence of sf_b in req_text.
        4. Preserves independent mentions elsewhere in req_text.
        5. Retains rejected candidate details in self.suppressed_associations and audit metadata.
        """
        meta_list = list(self.associations_meta)
        suppressed_in_this_req: List[Dict[str, Any]] = []
        kept_meta: List[Dict[str, Any]] = []

        def is_compound_phrase(term: str) -> bool:
            return bool(re.search(r"\s+(\+|\&|and|or)\s+", term, re.IGNORECASE))

        for i, meta_a in enumerate(meta_list):
            s_id_a = meta_a.get("skill_id")
            if not s_id_a:
                kept_meta.append(meta_a)
                continue

            sf_a = meta_a.get("matched_surface_form") or meta_a.get("skill_name") or s_id_a
            pat_a = build_term_pattern(sf_a)

            is_nested = False
            containing_meta = None

            for j, meta_b in enumerate(meta_list):
                if i == j:
                    continue
                s_id_b = meta_b.get("skill_id")
                if not s_id_b or s_id_a == s_id_b:
                    continue

                sf_b = meta_b.get("matched_surface_form") or meta_b.get("skill_name") or s_id_b

                # Section 4.3: Compound coordinating phrases cannot suppress atomic components
                if is_compound_phrase(sf_b):
                    continue

                # Check 1: Span coordinates containment if both have mention_start/end
                start_a = meta_a.get("mention_start")
                end_a = meta_a.get("mention_end")
                start_b = meta_b.get("mention_start")
                end_b = meta_b.get("mention_end")

                span_contained = False
                if start_a is not None and end_a is not None and start_b is not None and end_b is not None:
                    if start_b <= start_a and end_a <= end_b and (end_a - start_a) < (end_b - start_b):
                        span_contained = True

                # Check 2: Surface form regex or substring containment
                sf_contained = False
                clean_sf_a = sf_a.strip().casefold()
                clean_sf_b = sf_b.strip().casefold()
                if clean_sf_a != clean_sf_b and clean_sf_a in clean_sf_b:
                    sf_contained = True
                elif pat_a.search(sf_b):
                    sf_contained = True

                if span_contained or sf_contained:
                    # meta_a is contained inside meta_b!
                    # Now check: does sf_a appear independently elsewhere in req_text?
                    all_matches_a = list(pat_a.finditer(req_text))
                    pat_b = build_term_pattern(sf_b)
                    all_matches_b = list(pat_b.finditer(req_text))

                    # An occurrence of sf_a is independent if it is NOT covered by any occurrence of sf_b
                    has_independent = False
                    for ma in all_matches_a:
                        covered = False
                        for mb in all_matches_b:
                            if mb.start() <= ma.start() and ma.end() <= mb.end():
                                covered = True
                                break
                        if not covered:
                            has_independent = True
                            break

                    if not has_independent:
                        is_nested = True
                        containing_meta = meta_b
                        break

            if is_nested and containing_meta:
                suppression_record = {
                    "requirement_id": self.occurrence_id,
                    "candidate_skill_id": s_id_a,
                    "candidate_surface_form": sf_a,
                    "candidate_start": meta_a.get("mention_start"),
                    "candidate_end": meta_a.get("mention_end"),
                    "containing_skill_id": containing_meta.get("skill_id"),
                    "containing_surface_form": (
                        containing_meta.get("matched_surface_form") or containing_meta.get("skill_name")
                    ),
                    "suppression_reason": "nested_technical_name_without_independent_mention",
                    "source_strategy": meta_a.get("association_method", "verified_surface_form"),
                }
                suppressed_in_this_req.append(suppression_record)
                self.suppressed_associations.append(suppression_record)
            else:
                kept_meta.append(meta_a)

        # Update requirement state
        self.associations_meta = kept_meta
        self.associated_skill_ids = [m["skill_id"] for m in kept_meta if m.get("skill_id")]
        self.associated_skill_names = [m["skill_name"] for m in kept_meta if m.get("skill_name")]

        # If all associations were suppressed, ensure unresolved record is added
        if not self.associated_skill_ids:
            self.associations_meta.append({
                "requirement_id": self.occurrence_id,
                "skill_id": None,
                "skill_name": None,
                "extraction_type": "explicit",
                "entity_kind": "unresolved",
                "association_method": "unresolved",
                "verification_status": "unverified",
                "unresolved": True,
                "requirement_start": self.start,
                "requirement_end": self.end,
                "mention_start": None,
                "mention_end": None,
                "matched_surface_form": None,
                "offset_resolved": False,
                "verbatim_ok": False,
                "reason": "nested_candidates_suppressed_no_remaining_skills",
            })

        return suppressed_in_this_req


class ExtractionDataAdapter:
    """Adapter bridging UnifiedExtractFileResponse to SBERT embedding inputs with strict occurrence provenance."""

    @staticmethod
    def extract_active_skills(
        doc_result: Optional[DocumentUnifiedResult],
        auto_revalidate_implicit: bool = False,
        run_id: Optional[str] = None,
    ) -> ActiveSkillsResult:
        """
        Extract active explicit and accepted implicit skills for a document with collision-resistant occurrence IDs.
        Excludes rejected duplicate implicit skills and returns them separately for auditing.
        Implements strict 5-state machine (States A, B, C, D, E) for implicit validation safety:
        - State A: Validation completed with accepted skills -> preserve accepted skills, DO NOT revalidate.
        - State B: Validation completed with zero accepted skills -> preserve empty list, DO NOT revalidate, DO NOT resurrect rejected skills.
        - State C: Validation absent -> if auto_revalidate_implicit=True, run authoritative upstream deduplicate_explicit_implicit. If False, preserve empty.
        - State D: Validation failed or inconsistent -> preserve failure and diagnostics. If auto_revalidate_implicit=False, ZERO implicit accepted.
        - State E: No implicit skills were extracted -> preserve empty result.
        """
        if doc_result is None:
            return ActiveSkillsResult([], [], {
                "validation_origin": "not_applicable",
                "validation_status": "not_applicable",
                "revalidation_attempted": False,
                "revalidation_performed": False,
                "revalidation_reason": None,
                "accepted_implicit_count": 0,
                "duplicate_implicit_count": 0,
                "validation_errors": [],
            }, None)

        active_skills: List[AdaptedSkillItem] = []
        duplicate_audit: List[DuplicateImplicitSkill] = []
        doc_type = doc_result.document_type
        doc_ns = compute_document_namespace(doc_result, doc_type, run_id)

        raw_implicit_skills = (
            doc_result.implicit.skills
            if (doc_result.implicit and doc_result.implicit.skills)
            else []
        )
        has_raw_implicit = len(raw_implicit_skills) > 0
        val = doc_result.validation

        diag: Dict[str, Any] = {
            "validation_origin": "not_applicable",
            "validation_status": "not_applicable",
            "revalidation_attempted": False,
            "revalidation_performed": False,
            "revalidation_reason": None,
            "accepted_implicit_count": 0,
            "duplicate_implicit_count": 0,
            "validation_errors": [],
        }

        effective_val = val

        if not has_raw_implicit:
            # State E: No raw implicit skills were extracted
            diag["validation_origin"] = "not_applicable"
            diag["validation_status"] = getattr(val, "status", "not_applicable") if val else "not_applicable"
            if val is not None:
                val.validation_origin = "not_applicable"
        else:
            val_status = getattr(val, "status", None) if val else None

            if val_status == "failed":
                # State D: Validation explicitly failed upstream! NEVER PROMOTE TO COMPLETED!
                diag["validation_status"] = "failed"
                diag["validation_errors"].append("Upstream validation status is 'failed'.")
                if auto_revalidate_implicit:
                    diag["revalidation_attempted"] = True
                    try:
                        from matching_cv.app.services.unified_skill_service import deduplicate_explicit_implicit
                        new_val = deduplicate_explicit_implicit(doc_result.explicit, doc_result.implicit)
                        new_val.status = "completed"
                        new_val.validation_origin = "revalidated_after_failure"
                        doc_result.validation = new_val
                        effective_val = new_val
                        diag["revalidation_performed"] = True
                        diag["revalidation_reason"] = "authorized_revalidation_after_upstream_failure"
                        diag["validation_origin"] = "revalidated_after_failure"
                        diag["validation_status"] = "completed"
                    except Exception as e:
                        diag["validation_errors"].append(f"Revalidation error: {e}")
                else:
                    diag["validation_origin"] = "failed"
                    # Invariant: do NOT treat partial accepted list as authoritative
                    effective_val = DocumentValidationResult(
                        status="failed",
                        validation_origin="failed",
                        accepted_implicit_skills=[],
                        duplicate_implicit_skills=val.duplicate_implicit_skills if val else [],
                    )
            elif val_status == "completed":
                # State A & State B: Completed upstream validation.
                # Invariant: A completed validation (whether >0 accepted or 0 accepted) MUST NOT be revalidated.
                origin = "original" if len(val.accepted_implicit_skills) > 0 else "authoritative_empty"
                val.validation_origin = origin
                effective_val = val
                diag["validation_origin"] = origin
                diag["validation_status"] = "completed"
            elif val is not None and (len(val.accepted_implicit_skills) > 0 or len(val.duplicate_implicit_skills) > 0):
                # Outcomes exist without explicit completed status
                origin = "original" if len(val.accepted_implicit_skills) > 0 else "authoritative_empty"
                val.validation_origin = origin
                effective_val = val
                diag["validation_origin"] = origin
                diag["validation_status"] = "completed"
            else:
                # State C: Validation absent / missing
                diag["validation_origin"] = "missing"
                diag["validation_status"] = "missing"
                if auto_revalidate_implicit:
                    diag["revalidation_attempted"] = True
                    try:
                        from matching_cv.app.services.unified_skill_service import deduplicate_explicit_implicit
                        new_val = deduplicate_explicit_implicit(doc_result.explicit, doc_result.implicit)
                        new_val.status = "completed"
                        new_val.validation_origin = "revalidated"
                        doc_result.validation = new_val
                        effective_val = new_val
                        diag["revalidation_performed"] = True
                        diag["revalidation_reason"] = "authorized_revalidation_missing_validation"
                        diag["validation_origin"] = "revalidated"
                        diag["validation_status"] = "completed"
                    except Exception as e:
                        diag["validation_errors"].append(f"Revalidation error: {e}")
                else:
                    effective_val = DocumentValidationResult(
                        status="missing",
                        validation_origin="missing",
                        accepted_implicit_skills=[],
                        duplicate_implicit_skills=[],
                    )

        # 1. Process explicit skills with collision-resistant namespace
        if doc_result.explicit and doc_result.explicit.skills:
            for idx, exp in enumerate(doc_result.explicit.skills):
                # Filter out unsupported purely numeric tokens (e.g. standalone years '2000', '2007')
                # Legitimate technical skills containing version numbers (e.g. 'windows-98', 'python-3.12') are preserved
                if not any(c.isalpha() for c in exp.skill_id):
                    continue
                display_name = exp.surface_forms[0] if exp.surface_forms else exp.skill_id
                occ_id = f"occ_{doc_ns}_explicit_{exp.skill_id}_{idx}"
                legacy_id = f"occ_{doc_type.lower()}_skill_{exp.skill_id}_{idx}"
                active_skills.append(
                    AdaptedSkillItem(
                        occurrence_id=occ_id,
                        skill_id=exp.skill_id,
                        display_name=display_name,
                        extraction_type="explicit",
                        category=exp.category,
                        kind=exp.kind,
                        confidence=exp.confidence,
                        sections=exp.sections,
                        raw_skill=exp,
                        legacy_id=legacy_id,
                    )
                )

        # 2. Process accepted implicit skills with collision-resistant namespace
        if effective_val and effective_val.accepted_implicit_skills:
            for idx, imp in enumerate(effective_val.accepted_implicit_skills):
                if not any(c.isalpha() for c in imp.skill_id):
                    continue
                occ_id = f"occ_{doc_ns}_implicit_{imp.skill_id}_{idx}"
                legacy_id = f"occ_{doc_type.lower()}_skill_{imp.skill_id}_{idx}"
                active_skills.append(
                    AdaptedSkillItem(
                        occurrence_id=occ_id,
                        skill_id=imp.skill_id,
                        display_name=imp.label,
                        extraction_type="implicit",
                        category=imp.category,
                        kind=None,  # Do not invent kind for implicit skills
                        basis=imp.basis,
                        confidence=imp.confidence,  # Must remain None if uncalibrated
                        sections=[],
                        raw_skill=imp,
                        legacy_id=legacy_id,
                    )
                )

        # 3. Collect duplicate implicit skills for audit
        if effective_val and effective_val.duplicate_implicit_skills:
            duplicate_audit = list(effective_val.duplicate_implicit_skills)

        # 4. Analyze constituent overlaps and annotate granularity
        skill_dicts = [
            {
                "skill_id": s.skill_id,
                "occurrence_id": s.occurrence_id,
                "display_name": s.display_name,
                "kind": s.kind,
                "category": s.category,
                "granularity": s.granularity,
            }
            for s in active_skills
        ]
        overlap_map = analyze_constituent_overlaps(skill_dicts)
        for s in active_skills:
            info = overlap_map.get(s.skill_id) or overlap_map.get(s.occurrence_id) or {}
            s.metadata["constituent_skill_ids"] = info.get("constituent_skill_ids", [])
            s.metadata["parent_compound_skill_ids"] = info.get("parent_compound_skill_ids", [])
            s.metadata["competency_granularity"] = s.granularity
            s.metadata["is_competency"] = s.granularity in ("atomic_skill", "compound_competency")

        diag["accepted_implicit_count"] = len([s for s in active_skills if s.extraction_type == "implicit"])
        diag["duplicate_implicit_count"] = len(duplicate_audit)
        diag["rejected_implicit_count"] = len(getattr(effective_val, "rejected_implicit_skills", []))

        return ActiveSkillsResult(
            active_skills=active_skills,
            duplicate_audit=duplicate_audit,
            validation_diagnostics=diag,
            effective_validation=effective_val,
        )

    @staticmethod
    def extract_evidence_items(
        doc_result: Optional[DocumentUnifiedResult],
        doc_type: Literal["CV", "JD"],
        source_identifier: str,
        run_id: Optional[str] = None,
    ) -> List[AdaptedEvidenceOccurrence]:
        """
        Extract granular sentence-level evidence occurrences from explicit and accepted implicit skills.
        Preserves distinct document occurrences (different section/offsets) even when text is identical.
        When multiple skills reference the EXACT same occurrence span, associations are unified.
        """
        if doc_result is None:
            return []

        # Key for shared span deduplication: (norm_text, section, start, end, occurrence_hint)
        # Identical spans within the same sentence are merged, but distinct text occurrences remain separate
        occurrence_map: Dict[Tuple[str, Optional[str], Optional[int], Optional[int]], AdaptedEvidenceOccurrence] = {}
        unresolved_counter = 0

        # 1. Explicit skill evidences
        if doc_result.explicit and doc_result.explicit.skills:
            for skill in doc_result.explicit.skills:
                display_name = skill.surface_forms[0] if skill.surface_forms else skill.skill_id
                for ev in skill.evidences:
                    sent = (ev.sentence or "").strip()
                    if not sent:
                        continue
                    norm_text = re.sub(r"\s+", " ", sent).strip()

                    # Key preserves distinct occurrences
                    occ_key = (norm_text, ev.section, ev.start, ev.end)
                    if occ_key not in occurrence_map:
                        idx_part = f"{ev.start}_{ev.end}" if ev.start is not None else f"unres_{unresolved_counter}"
                        if ev.start is None:
                            unresolved_counter += 1
                        doc_ns = compute_document_namespace(doc_result, doc_type, run_id)
                        occ_id = f"occ_{doc_ns}_evidence_{idx_part}_{hashlib.sha256(norm_text.encode()).hexdigest()[:8]}"

                        occurrence_map[occ_key] = AdaptedEvidenceOccurrence(
                            occurrence_id=occ_id,
                            text=norm_text,
                            document_type=doc_type,
                            source_identifier=source_identifier,
                            construction_strategy="cv_evidence_sentence" if doc_type == "CV" else "jd_evidence_sentence",
                            extraction_type="explicit",
                            section=ev.section,
                            start=ev.start,
                            end=ev.end,
                            offset_resolved=ev.offset_resolved,
                            verbatim_ok=ev.verbatim_ok,
                        )

                    occurrence_map[occ_key].add_skill_association(
                        skill_id=skill.skill_id,
                        skill_name=display_name,
                        meta={
                            "surface_form": ev.surface_form,
                            "section": ev.section,
                            "start": ev.start,
                            "end": ev.end,
                            "kind": ev.kind,
                        },
                    )

        # 2. Accepted implicit skill evidences
        if doc_result.validation and doc_result.validation.accepted_implicit_skills:
            for imp in doc_result.validation.accepted_implicit_skills:
                for ev in imp.evidences:
                    if ev.snippets:
                        for snip in ev.snippets:
                            snip_text = (snip.text or "").strip()
                            if not snip_text:
                                continue
                            norm_text = re.sub(r"\s+", " ", snip_text).strip()
                            offset_ok = snip.start is not None and snip.end is not None

                            occ_key = (norm_text, snip.section, snip.start, snip.end)
                            if occ_key not in occurrence_map:
                                idx_part = f"{snip.start}_{snip.end}" if offset_ok else f"unres_{unresolved_counter}"
                                if not offset_ok:
                                    unresolved_counter += 1
                                doc_ns = compute_document_namespace(doc_result, doc_type, run_id)
                                occ_id = f"occ_{doc_ns}_evidence_{idx_part}_{hashlib.sha256(norm_text.encode()).hexdigest()[:8]}"

                                occurrence_map[occ_key] = AdaptedEvidenceOccurrence(
                                    occurrence_id=occ_id,
                                    text=norm_text,
                                    document_type=doc_type,
                                    source_identifier=source_identifier,
                                    construction_strategy="cv_evidence_snippet" if doc_type == "CV" else "jd_evidence_snippet",
                                    extraction_type="implicit",
                                    section=snip.section,
                                    start=snip.start,
                                    end=snip.end,
                                    offset_resolved=offset_ok,
                                    verbatim_ok=snip.verbatim_ok,
                                    basis=ev.basis,
                                    reasoning=ev.reasoning,
                                    llm_confidence_raw=ev.llm_confidence_raw,
                                )

                            occurrence_map[occ_key].add_skill_association(
                                skill_id=imp.skill_id,
                                skill_name=imp.label,
                                meta={
                                    "section": snip.section,
                                    "start": snip.start,
                                    "end": snip.end,
                                    "reasoning": ev.reasoning,
                                    "basis": ev.basis,
                                    "llm_confidence_raw": ev.llm_confidence_raw,
                                },
                            )
                    else:
                        raw_from = (ev.inferred_from_raw or "").strip()
                        if raw_from:
                            norm_text = re.sub(r"\s+", " ", raw_from).strip()
                            occ_key = (norm_text, None, None, None)
                            if occ_key not in occurrence_map:
                                doc_ns = compute_document_namespace(doc_result, doc_type, run_id)
                                occ_id = f"occ_{doc_ns}_evidence_fallback_{unresolved_counter}_{hashlib.sha256(norm_text.encode()).hexdigest()[:8]}"
                                unresolved_counter += 1
                                occurrence_map[occ_key] = AdaptedEvidenceOccurrence(
                                    occurrence_id=occ_id,
                                    text=norm_text,
                                    document_type=doc_type,
                                    source_identifier=source_identifier,
                                    construction_strategy="cv_evidence_raw_fallback" if doc_type == "CV" else "jd_evidence_raw_fallback",
                                    extraction_type="implicit",
                                    offset_resolved=False,
                                    verbatim_ok=False,
                                    basis=ev.basis,
                                    reasoning=ev.reasoning,
                                    llm_confidence_raw=ev.llm_confidence_raw,
                                )
                            occurrence_map[occ_key].add_skill_association(
                                skill_id=imp.skill_id,
                                skill_name=imp.label,
                                meta={
                                    "reasoning": ev.reasoning,
                                    "basis": ev.basis,
                                    "llm_confidence_raw": ev.llm_confidence_raw,
                                    "note": "fallback_from_inferred_from_raw",
                                },
                            )

        return list(occurrence_map.values())

    @staticmethod
    def segment_jd_requirements(
        jd_result: Optional[DocumentUnifiedResult],
        raw_jd_text: Optional[str],
        source_identifier: str,
    ) -> Tuple[List[AdaptedRequirementItem], Dict[str, Any]]:
        """
        Segment JD requirements into discrete sentences / bullet points with character spans.
        Associates requirements with skills following priority:
        1. Source-verified evidence offsets and span overlap.
        2. Verified explicit evidence sentence relationships.
        3. Conservative explicit surface-form matching with robust token boundaries.
        4. Accepted implicit skills supported by evidence snippets / reasoning.
        5. Explicitly marks unresolved requirements when supporting evidence is insufficient.
        """
        requirements: List[AdaptedRequirementItem] = []
        diagnostics: Dict[str, Any] = {}
        all_suppressed_mentions: List[Dict[str, Any]] = []

        if raw_jd_text and raw_jd_text.strip():
            diagnostics["jd_requirements_source"] = "raw_jd_text"
            spans = find_section_spans(raw_jd_text, "JD")
            req_spans = [
                s for s in spans if s.name in ("requirements", "qualifications", "responsibilities", "nice_to_have")
            ]

            target_sections: List[Tuple[int, int, str]] = []  # (start, end, section_name)
            if req_spans:
                for span in req_spans:
                    target_sections.append((span.start, span.end, span.name))
            else:
                target_sections.append((0, len(raw_jd_text), "general"))

            seen_lines: Set[str] = set()
            req_index = 0

            for sec_start, sec_end, sec_name in target_sections:
                chunk = raw_jd_text[sec_start:sec_end]
                curr_offset = sec_start

                for line in chunk.splitlines(keepends=True):
                    line_raw = line.rstrip("\r\n")
                    line_start = curr_offset
                    line_end = curr_offset + len(line_raw)
                    curr_offset += len(line)

                    cleaned = re.sub(r"^\s*[\*\-\•\+\d\.\)\(\]]+\s*", "", line_raw).strip()
                    # Filter out headers and trivial short lines
                    if len(cleaned) >= 15 and cleaned.casefold() not in seen_lines:
                        if not cleaned.endswith(":") and not cleaned.isupper():
                            seen_lines.add(cleaned.casefold())

                            doc_ns = compute_document_namespace(jd_result, "JD")
                            occ_id = f"occ_{doc_ns}_req_{req_index}_{line_start}_{line_end}"
                            req_index += 1

                            req_item = AdaptedRequirementItem(
                                occurrence_id=occ_id,
                                text=cleaned,
                                source_identifier=source_identifier,
                                section=sec_name,
                                start=line_start,
                                end=line_end,
                                source_strategy="raw_jd_text_line",
                            )

                            # Determine exact coordinate of cleaned text within line_raw
                            local_clean_idx = line_raw.find(cleaned) if cleaned in line_raw else 0
                            req_text_start = line_start + local_clean_idx
                            req_text_end = req_text_start + len(cleaned)

                            # Multi-skill association checking priority:
                            # 1. Explicit skills
                            if jd_result and jd_result.explicit and jd_result.explicit.skills:
                                for skill in jd_result.explicit.skills:
                                    s_id = skill.skill_id
                                    display_name = skill.surface_forms[0] if skill.surface_forms else s_id
                                    associated = False

                                    # LEVEL 1: Verified Mention Span
                                    for ev in skill.evidences:
                                        if ev.mention_start is not None and ev.mention_end is not None:
                                            # Mention span must fall inside requirement span
                                            if line_start <= ev.mention_start and ev.mention_end <= line_end:
                                                actual_mention = raw_jd_text[ev.mention_start:ev.mention_end]
                                                expected_sf = ev.surface_form or (skill.surface_forms[0] if skill.surface_forms else s_id)
                                                if (
                                                    actual_mention.strip().casefold() == expected_sf.strip().casefold()
                                                    or normalize_skill_name(actual_mention) == normalize_skill_name(expected_sf)
                                                ):
                                                    req_item.add_skill_association(
                                                        skill_id=s_id,
                                                        skill_name=display_name,
                                                        extraction_type="explicit",
                                                        entity_kind=ev.kind or skill.kind or "skill",
                                                        association_method="verified_mention_span",
                                                        verification_status="verified_mention",
                                                        requirement_start=line_start,
                                                        requirement_end=line_end,
                                                        mention_start=ev.mention_start,
                                                        mention_end=ev.mention_end,
                                                        matched_surface_form=actual_mention,
                                                        evidence_reference={
                                                            "start": ev.start,
                                                            "end": ev.end,
                                                            "section": ev.section,
                                                            "sentence": ev.sentence,
                                                        },
                                                        offset_resolved=True,
                                                        verbatim_ok=ev.verbatim_ok,
                                                    )
                                                    associated = True
                                                    break

                                    # LEVEL 2: Verified Local Surface Form Matching
                                    if not associated:
                                        candidate_sfs = list(skill.surface_forms or [])
                                        if s_id not in candidate_sfs:
                                            candidate_sfs.append(s_id)

                                        for sf in candidate_sfs:
                                            pat = build_term_pattern(sf)
                                            m = pat.search(cleaned)
                                            if m:
                                                loc_start = m.start()
                                                loc_end = m.end()
                                                matched_sf = m.group(0)
                                                abs_start = req_text_start + loc_start
                                                abs_end = req_text_start + loc_end
                                                if abs_end <= len(raw_jd_text) and raw_jd_text[abs_start:abs_end].casefold() == matched_sf.casefold():
                                                    req_item.add_skill_association(
                                                        skill_id=s_id,
                                                        skill_name=display_name,
                                                        extraction_type="explicit",
                                                        entity_kind=skill.kind or "skill",
                                                        association_method="verified_surface_form",
                                                        verification_status="verified_surface",
                                                        requirement_start=line_start,
                                                        requirement_end=line_end,
                                                        mention_start=abs_start,
                                                        mention_end=abs_end,
                                                        matched_surface_form=matched_sf,
                                                        evidence_reference={"matched_surface_form": sf},
                                                        offset_resolved=True,
                                                        verbatim_ok=True,
                                                    )
                                                    associated = True
                                                    break

                            # 2. Accepted implicit skills (LEVEL 4: Implicit Inference Support)
                            if jd_result and jd_result.validation and jd_result.validation.accepted_implicit_skills:
                                for imp in jd_result.validation.accepted_implicit_skills:
                                    imp_associated = False
                                    for ev in imp.evidences:
                                        for snip in (ev.snippets or []):
                                            if snip.start is not None and snip.end is not None and line_start <= snip.start and snip.end <= line_end:
                                                req_item.add_skill_association(
                                                    skill_id=imp.skill_id,
                                                    skill_name=imp.label,
                                                    extraction_type="implicit",
                                                    entity_kind=imp.category or "implicit_skill",
                                                    association_method="implicit_evidence_supported",
                                                    verification_status="implicit_inferred",
                                                    requirement_start=line_start,
                                                    requirement_end=line_end,
                                                    mention_start=None,
                                                    mention_end=None,
                                                    evidence_start=snip.start,
                                                    evidence_end=snip.end,
                                                    matched_surface_form=None,
                                                    evidence_reference={"snippet_start": snip.start, "snippet_end": snip.end, "text": snip.text},
                                                    basis=ev.basis,
                                                    reasoning=ev.reasoning,
                                                    confidence=ev.llm_confidence_raw,
                                                    offset_resolved=False,
                                                    verbatim_ok=False,
                                                )
                                                imp_associated = True
                                                break
                                            elif snip.text and snip.text.casefold() in cleaned.casefold():
                                                snip_loc = cleaned.casefold().find(snip.text.casefold())
                                                abs_snip_start = req_text_start + snip_loc if snip_loc != -1 else None
                                                abs_snip_end = abs_snip_start + len(snip.text) if abs_snip_start is not None else None
                                                req_item.add_skill_association(
                                                    skill_id=imp.skill_id,
                                                    skill_name=imp.label,
                                                    extraction_type="implicit",
                                                    entity_kind=imp.category or "implicit_skill",
                                                    association_method="implicit_evidence_supported",
                                                    verification_status="implicit_inferred",
                                                    requirement_start=line_start,
                                                    requirement_end=line_end,
                                                    mention_start=None,
                                                    mention_end=None,
                                                    evidence_start=abs_snip_start,
                                                    evidence_end=abs_snip_end,
                                                    matched_surface_form=None,
                                                    evidence_reference={"snippet_text": snip.text},
                                                    basis=ev.basis,
                                                    reasoning=ev.reasoning,
                                                    confidence=ev.llm_confidence_raw,
                                                    offset_resolved=False,
                                                    verbatim_ok=False,
                                                )
                                                imp_associated = True
                                                break
                                        if not imp_associated and ev.inferred_from_raw:
                                            raw_inf = ev.inferred_from_raw.strip().casefold()
                                            clean_lower = cleaned.casefold()
                                            if raw_inf in clean_lower or clean_lower in raw_inf:
                                                req_item.add_skill_association(
                                                    skill_id=imp.skill_id,
                                                    skill_name=imp.label,
                                                    extraction_type="implicit",
                                                    entity_kind=imp.category or "implicit_skill",
                                                    association_method="implicit_evidence_supported",
                                                    verification_status="implicit_inferred",
                                                    requirement_start=line_start,
                                                    requirement_end=line_end,
                                                    mention_start=None,
                                                    mention_end=None,
                                                    matched_surface_form=None,
                                                    evidence_reference={"inferred_from_raw": ev.inferred_from_raw},
                                                    basis=ev.basis,
                                                    reasoning=ev.reasoning,
                                                    confidence=ev.llm_confidence_raw,
                                                    offset_resolved=False,
                                                    verbatim_ok=False,
                                                )
                                                imp_associated = True
                                                break
                                        if imp_associated:
                                            break

                            # LEVEL 5: Unresolved
                            if not req_item.associated_skill_ids:
                                req_item.associations_meta.append({
                                    "requirement_id": req_item.occurrence_id,
                                    "skill_id": None,
                                    "skill_name": None,
                                    "extraction_type": "explicit",
                                    "entity_kind": "unresolved",
                                    "association_method": "unresolved",
                                    "verification_status": "unverified",
                                    "unresolved": True,
                                    "requirement_start": line_start,
                                    "requirement_end": line_end,
                                    "mention_start": None,
                                    "mention_end": None,
                                    "matched_surface_form": None,
                                    "offset_resolved": False,
                                    "verbatim_ok": False,
                                    "reason": "insufficient_supporting_evidence",
                                })

                            suppressed_records = req_item.resolve_maximal_mention_spans(cleaned)
                            for rec in suppressed_records:
                                rec["requirement_text"] = cleaned
                                all_suppressed_mentions.append(rec)

                            requirements.append(req_item)

            diagnostics["jd_requirements_count"] = len(requirements)
            diagnostics["suppressed_nested_mentions"] = all_suppressed_mentions
            diagnostics["nested_mentions_suppressed_count"] = len(all_suppressed_mentions)
            return requirements, diagnostics

        # Fallback when raw_jd_text is not provided
        diagnostics["jd_requirements_source"] = "extracted_evidences_fallback"
        diagnostics["limitation"] = (
            "Raw JD text was not provided. Requirements are constructed from distinct evidence sentences "
            "belonging to extracted JD skills. Sentences that do not contain recognized skills are omitted."
        )

        fallback_req_map: Dict[str, AdaptedRequirementItem] = {}
        req_index = 0

        # Step 1: Collect unique requirement sentences from all explicit evidences
        if jd_result and jd_result.explicit and jd_result.explicit.skills:
            for skill in jd_result.explicit.skills:
                display_name = skill.surface_forms[0] if skill.surface_forms else skill.skill_id
                for ev in skill.evidences:
                    sent = (ev.sentence or "").strip()
                    cleaned = re.sub(r"\s+", " ", sent).strip()
                    if len(cleaned) < 15:
                        continue
                    key = cleaned.casefold()
                    if key not in fallback_req_map:
                        occ_id = f"occ_jd_req_fallback_{req_index}_{ev.start}_{ev.end}"
                        req_index += 1
                        fallback_req_map[key] = AdaptedRequirementItem(
                            occurrence_id=occ_id,
                            text=cleaned,
                            source_identifier=source_identifier,
                            section=ev.section,
                            start=ev.start,
                            end=ev.end,
                            source_strategy="jd_evidence_sentence_fallback",
                        )
                    # Determine if surface form is present in sentence
                    sf = skill.surface_forms[0] if skill.surface_forms else skill.skill_id
                    has_sf = build_term_pattern(sf).search(cleaned)
                    fallback_req_map[key].add_skill_association(
                        skill_id=skill.skill_id,
                        skill_name=display_name,
                        extraction_type="explicit",
                        entity_kind=ev.kind or skill.kind or "skill",
                        association_method="verified_surface_form" if has_sf else "sentence_evidence_supported",
                        verification_status="verified_surface" if has_sf else "evidence_supported",
                        requirement_start=ev.start,
                        requirement_end=ev.end,
                        matched_surface_form=sf if has_sf else None,
                        evidence_reference={"start": ev.start, "end": ev.end, "section": ev.section, "sentence": ev.sentence},
                        offset_resolved=ev.offset_resolved,
                        verbatim_ok=ev.verbatim_ok,
                    )

        # Step 2: Also check other skills via surface form and accepted implicit skills
        for key, req_item in fallback_req_map.items():
            cleaned_text = req_item.text
            # Check other explicit skills
            if jd_result and jd_result.explicit and jd_result.explicit.skills:
                for skill in jd_result.explicit.skills:
                    if skill.skill_id not in req_item.associated_skill_ids:
                        display_name = skill.surface_forms[0] if skill.surface_forms else skill.skill_id
                        for sf in (skill.surface_forms or [skill.skill_id]):
                            pat = build_term_pattern(sf)
                            if pat.search(cleaned_text):
                                req_item.add_skill_association(
                                    skill_id=skill.skill_id,
                                    skill_name=display_name,
                                    extraction_type="explicit",
                                    association_method="surface_form_regex",
                                    evidence_ref={"matched_surface_form": sf},
                                )
                                break
            # Check implicit skills
            if jd_result and jd_result.validation and jd_result.validation.accepted_implicit_skills:
                for imp in jd_result.validation.accepted_implicit_skills:
                    if imp.skill_id not in req_item.associated_skill_ids:
                        for ev in imp.evidences:
                            matched = False
                            for snip in (ev.snippets or []):
                                if snip.text and snip.text.casefold() in cleaned_text.casefold():
                                    req_item.add_skill_association(
                                        skill_id=imp.skill_id,
                                        skill_name=imp.label,
                                        extraction_type="implicit",
                                        association_method="implicit_evidence_snippet_match",
                                        evidence_ref={"text": snip.text},
                                        basis=ev.basis,
                                        reasoning=ev.reasoning,
                                        confidence=ev.llm_confidence_raw,
                                    )
                                    matched = True
                                    break
                            if not matched and ev.inferred_from_raw:
                                if ev.inferred_from_raw.strip().casefold() in cleaned_text.casefold():
                                    req_item.add_skill_association(
                                        skill_id=imp.skill_id,
                                        skill_name=imp.label,
                                        extraction_type="implicit",
                                        association_method="implicit_inferred_from_match",
                                        evidence_ref={"inferred_from_raw": ev.inferred_from_raw},
                                        basis=ev.basis,
                                        reasoning=ev.reasoning,
                                        confidence=ev.llm_confidence_raw,
                                    )
                                    matched = True
                                    break
                            if matched:
                                break

        for key, req_item in fallback_req_map.items():
            suppressed_records = req_item.resolve_maximal_mention_spans(req_item.text)
            for rec in suppressed_records:
                rec["requirement_text"] = req_item.text
                all_suppressed_mentions.append(rec)

        requirements = list(fallback_req_map.values())
        diagnostics["jd_requirements_count"] = len(requirements)
        diagnostics["suppressed_nested_mentions"] = all_suppressed_mentions
        diagnostics["nested_mentions_suppressed_count"] = len(all_suppressed_mentions)
        return requirements, diagnostics
