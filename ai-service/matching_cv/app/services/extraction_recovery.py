"""Stage 6C.2: Extraction Reliability, Truncation Recovery, and Fail-Closed Guardrails."""
import contextvars
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from matching_cv.app.schemas.unified_skill_extraction import DocumentUnifiedResult, UnifiedExtractFileResponse

logger = logging.getLogger(__name__)

last_recovery_diag_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "last_recovery_diag_var", default=None
)

explicit_recovery_diag_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "explicit_recovery_diag_var", default=None
)

implicit_recovery_diag_var: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "implicit_recovery_diag_var", default=None
)

request_stage_context_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_stage_context_var", default=None
)


class ExtractionIntegrityError(Exception):
    """Raised when an extraction fails, is truncated beyond recovery, or silently drops mandatory skills."""
    pass


def clean_markdown_fences(text: str) -> str:
    """Strip markdown codeblock wrappers (```json ... ```)."""
    s = text.strip()
    if s.startswith("```json"):
        s = s[7:]
    elif s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


def attempt_json_truncation_recovery(
    raw_str: str,
    min_skills: int = 1,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Attempt to recover valid skill objects from an incomplete or truncated JSON response.

    Strategies:
    1. Direct parse (already valid JSON).
    2. Suffix bracket closure (trim broken tail after last valid `}` in `"skills"` array and close `]}`).
    3. Regex block salvage (extract all syntactically complete JSON objects representing skills).

    Returns:
        (recovered_dict, diagnostics_dict)
    """
    cleaned = clean_markdown_fences(raw_str)
    diagnostics = {
        "raw_length": len(raw_str),
        "cleaned_length": len(cleaned),
        "recovery_needed": False,
        "recovery_method": None,
        "salvaged_count": 0,
        "truncation_offset": None,
        "success": False,
    }

    # Strategy 1: Direct Parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and ("skills" in parsed or "explicit_skills" in parsed):
            skills = parsed.get("skills") or parsed.get("explicit_skills") or []
            diagnostics["success"] = True
            diagnostics["salvaged_count"] = len(skills)
            diagnostics["recovery_method"] = "direct_parse"
            return parsed, diagnostics
    except Exception as exc:
        diagnostics["direct_parse_error"] = str(exc)
        diagnostics["recovery_needed"] = True

    # Strategy 2: Backward scan for last complete object delimiter '}'
    # Look for skills array start
    array_match = re.search(r'["\'](?:skills|explicit_skills)["\']\s*:\s*\[', cleaned)
    if array_match:
        skills_start_idx = array_match.end()
        # Find last '}' after skills_start_idx
        last_brace_idx = cleaned.rfind("}")
        while last_brace_idx > skills_start_idx:
            candidate = cleaned[: last_brace_idx + 1].strip()
            # If candidate ends with comma, trim it
            if candidate.endswith(","):
                candidate = candidate[:-1].strip()
            # Append closing brackets
            candidate_json = candidate + "\n]}"
            # If the candidate didn't have opening '{', prefix it
            if not candidate_json.lstrip().startswith("{"):
                candidate_json = "{\n" + candidate_json
            try:
                candidate_parsed = json.loads(candidate_json)
                if isinstance(candidate_parsed, dict):
                    cand_skills = (
                        candidate_parsed.get("skills")
                        or candidate_parsed.get("explicit_skills")
                        or []
                    )
                    if len(cand_skills) >= min_skills:
                        diagnostics["success"] = True
                        diagnostics["salvaged_count"] = len(cand_skills)
                        diagnostics["truncation_offset"] = last_brace_idx
                        diagnostics["recovery_method"] = "suffix_bracket_closure"
                        logger.warning(
                            f"Successfully recovered {len(cand_skills)} skills via suffix bracket closure at offset {last_brace_idx}."
                        )
                        return candidate_parsed, diagnostics
            except Exception:
                pass
            # Try earlier brace
            last_brace_idx = cleaned.rfind("}", skills_start_idx, last_brace_idx)

    # Strategy 3: Regex Block Salvage
    # Find all independent skill objects matching key schema elements
    pattern = re.compile(
        r'\{\s*"(?:surface_form|mention)"\s*:\s*"(?:\\.|[^"\\])*"[^}]*\}',
        re.DOTALL,
    )
    salvaged_skills = []
    for match in pattern.finditer(cleaned):
        block_text = match.group(0)
        try:
            skill_obj = json.loads(block_text)
            if isinstance(skill_obj, dict) and ("surface_form" in skill_obj or "mention" in skill_obj):
                salvaged_skills.append(skill_obj)
        except Exception:
            continue

    if len(salvaged_skills) >= min_skills:
        diagnostics["success"] = True
        diagnostics["salvaged_count"] = len(salvaged_skills)
        diagnostics["recovery_method"] = "regex_block_salvage"
        logger.warning(
            f"Successfully salvaged {len(salvaged_skills)} skills via regex block extraction."
        )
        return {"skills": salvaged_skills}, diagnostics

    diagnostics["success"] = False
    diagnostics["recovery_method"] = "exhausted_unrecoverable"
    return None, diagnostics


def validate_extraction_integrity(
    doc_result: Optional[DocumentUnifiedResult],
    raw_text: str,
    document_type: str,
    min_chars_for_skill_requirement: int = 500,
) -> None:
    """
    Fail-closed validation enforcing that substantial documents must yield explicit skills.
    Prevents silent fallback to zero-skill graphs.
    """
    if doc_result is None:
        raise ExtractionIntegrityError(
            f"Extraction integrity failure: doc_result is None for {document_type} (text length: {len(raw_text)} chars)."
        )

    if doc_result.explicit is None:
        raise ExtractionIntegrityError(
            f"Extraction integrity failure: explicit extraction result is None for {document_type} (text length: {len(raw_text)} chars)."
        )

    explicit_skills = doc_result.explicit.skills or []
    if len(raw_text) >= min_chars_for_skill_requirement and len(explicit_skills) == 0:
        raise ExtractionIntegrityError(
            f"Extraction integrity failure: {document_type} contains {len(raw_text)} characters (>= {min_chars_for_skill_requirement}) "
            f"but yielded 0 explicit skills. Silent zero-skill graph construction is strictly prohibited."
        )


def validate_pipeline_extraction_response(
    response: UnifiedExtractFileResponse,
    require_cv: bool = True,
    require_jd: bool = True,
) -> None:
    """
    Enforces that a multi-document unified extraction response was 100% completed without errors.
    """
    if response.status != "completed":
        raise ExtractionIntegrityError(
            f"Extraction pipeline returned non-completed status '{response.status}' with errors: {response.errors}."
        )

    if response.errors:
        raise ExtractionIntegrityError(
            f"Extraction pipeline succeeded with unhandled errors: {response.errors}."
        )

    if require_cv:
        if response.cv is None or response.cv.explicit is None:
            raise ExtractionIntegrityError("Mandatory CV explicit extraction missing from pipeline response.")
        if len(response.cv.raw_text or "") >= 500 and len(response.cv.explicit.skills or []) == 0:
            raise ExtractionIntegrityError(
                f"CV document ({len(response.cv.raw_text or '')} chars) contains 0 explicit skills."
            )

    if require_jd:
        if response.jd is None or response.jd.explicit is None:
            raise ExtractionIntegrityError("Mandatory JD explicit extraction missing from pipeline response.")
        if len(response.jd.raw_text or "") >= 500 and len(response.jd.explicit.skills or []) == 0:
            raise ExtractionIntegrityError(
                f"JD document ({len(response.jd.raw_text or '')} chars) contains 0 explicit skills."
            )


def classify_extraction_status(
    doc_result: Optional[DocumentUnifiedResult],
    raw_text: str,
    document_type: str,
    errors: Optional[List[Any]] = None,
    recovery_diagnostics: Optional[Dict[str, Any]] = None,
    explicit_recovery_diag: Optional[Dict[str, Any]] = None,
    implicit_recovery_diag: Optional[Dict[str, Any]] = None,
    min_chars_for_skill_requirement: int = 500,
) -> Tuple[str, Dict[str, Any]]:
    """
    Classify document extraction into:
    - COMPLETE_VALIDATED: Explicit and implicit extractions complete, >= 1 skills, no recovery required, no errors.
    - RECOVERED_PARTIAL: Extraction salvaged via truncation recovery on either stage, requires quarantine.
    - FAILED_INTEGRITY: None explicit result, 0 skills on substantial document, or unhandled fatal errors.
    """
    audit = {
        "document_type": document_type,
        "text_length": len(raw_text),
        "explicit_skills_count": len(doc_result.explicit.skills) if (doc_result and doc_result.explicit) else 0,
        "recovery_applied": False,
        "explicit_recovery_applied": False,
        "implicit_recovery_applied": False,
        "classification": "FAILED_INTEGRITY",
        "reason": None,
    }

    if errors:
        audit["classification"] = "FAILED_INTEGRITY"
        audit["reason"] = f"Extraction recorded pipeline errors: {errors}"
        return "FAILED_INTEGRITY", audit

    if doc_result is None or doc_result.explicit is None:
        audit["classification"] = "FAILED_INTEGRITY"
        audit["reason"] = "Explicit extraction result is missing/None."
        return "FAILED_INTEGRITY", audit

    skills = doc_result.explicit.skills or []
    if len(raw_text) >= min_chars_for_skill_requirement and len(skills) == 0:
        audit["classification"] = "FAILED_INTEGRITY"
        audit["reason"] = f"Substantial document ({len(raw_text)} chars) yielded 0 explicit skills."
        return "FAILED_INTEGRITY", audit

    # Inspect independent stage recovery diagnostics (preventing stage overwriting)
    eff_explicit = (
        explicit_recovery_diag
        if explicit_recovery_diag is not None
        else explicit_recovery_diag_var.get()
    )
    eff_implicit = (
        implicit_recovery_diag
        if implicit_recovery_diag is not None
        else implicit_recovery_diag_var.get()
    )
    eff_fallback = (
        recovery_diagnostics
        if recovery_diagnostics is not None
        else last_recovery_diag_var.get()
    )

    explicit_salvaged = bool(eff_explicit and eff_explicit.get("recovery_needed"))
    implicit_salvaged = bool(eff_implicit and eff_implicit.get("recovery_needed"))
    fallback_salvaged = bool(eff_fallback and eff_fallback.get("recovery_needed"))

    # Fail-closed: If EITHER stage required truncation recovery, document MUST be RECOVERED_PARTIAL
    if explicit_salvaged or implicit_salvaged or fallback_salvaged:
        audit["recovery_applied"] = True
        audit["explicit_recovery_applied"] = explicit_salvaged
        audit["implicit_recovery_applied"] = implicit_salvaged
        audit["explicit_diagnostics"] = eff_explicit
        audit["implicit_diagnostics"] = eff_implicit
        audit["recovery_method"] = (
            (eff_explicit.get("recovery_method") if explicit_salvaged else None)
            or (eff_implicit.get("recovery_method") if implicit_salvaged else None)
            or (eff_fallback.get("recovery_method") if fallback_salvaged else None)
        )
        audit["salvaged_count"] = (
            (eff_explicit.get("salvaged_count", 0) if explicit_salvaged else 0)
            + (eff_implicit.get("salvaged_count", 0) if implicit_salvaged else 0)
            + (eff_fallback.get("salvaged_count", 0) if (not explicit_salvaged and not implicit_salvaged and fallback_salvaged) else 0)
        )
        audit["classification"] = "RECOVERED_PARTIAL"
        audit["reason"] = (
            f"Syntactically repaired from truncated stream "
            f"(explicit_salvaged={explicit_salvaged}, implicit_salvaged={implicit_salvaged}); "
            f"quarantined from clean benchmark."
        )
        return "RECOVERED_PARTIAL", audit

    # Fail-closed check: Any ungrounded evidences disqualify document from COMPLETE_VALIDATED
    has_ungrounded = any(
        any(not getattr(e, "verbatim_ok", True) or not getattr(e, "offset_resolved", True) for e in getattr(s, "evidences", []))
        for s in skills
    )
    if has_ungrounded:
        audit["classification"] = "RECOVERED_PARTIAL"
        audit["reason"] = "Extraction contains ungrounded skill evidences lacking verbatim character offsets; quarantined."
        return "RECOVERED_PARTIAL", audit

    audit["classification"] = "COMPLETE_VALIDATED"
    audit["reason"] = "Document extraction 100% complete and verified."
    return "COMPLETE_VALIDATED", audit
