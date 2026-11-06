import difflib
from typing import Dict, List, Optional, Set
from pydantic import ValidationError

from src.baselines.base import BaselineSkillResult
from src.baselines.llm.schemas import LLMZeroShotResponse


def validate_quote_in_text(quote: Optional[str], full_text: str, threshold: float = 0.85) -> bool:
    """
    Validates whether an evidence quote exists verbatim or with high fuzzy similarity in CV text.
    Reuses the sliding window logic from ResumeSegmenter._validate_quote_in_text.
    """
    if not quote or not quote.strip():
        return True  # If no quote was claimed, treat as neutral/valid
    q = quote.strip().lower()
    txt = full_text.lower()
    if q in txt:
        return True

    # Check sliding window fuzzy match
    q_len = len(q)
    if q_len > 10 and len(txt) >= q_len:
        step = max(1, q_len // 4)
        for i in range(0, len(txt) - q_len + 1, step):
            window = txt[i : i + q_len]
            if difflib.SequenceMatcher(None, q, window).ratio() >= threshold:
                return True
    return False


def parse_and_validate_response(
    response: LLMZeroShotResponse,
    expected_skill_ids: List[str],
    cv_text: str,
    baseline_name: str,
    fuzzy_threshold: float = 0.85,
) -> List[BaselineSkillResult]:
    """
    Validates the LLMZeroShotResponse against the expected JD skill requirements:
    1. Verifies that all expected skill IDs are evaluated.
    2. Verifies evidence quotes against cv_text, setting evidence_unverified flag if ungrounded.
    3. Transforms valid assessments into BaselineSkillResult matching the exact expected skill ordering.
    Raises ValueError if expected skills are missing.
    """
    assessment_map = {s.jd_skill_id: s for s in response.skills}
    missing_skills = [sid for sid in expected_skill_ids if sid not in assessment_map]

    if missing_skills:
        raise ValueError(
            f"LLM response missed {len(missing_skills)} required skill(s): {missing_skills}"
        )

    results: List[BaselineSkillResult] = []
    for sid in expected_skill_ids:
        assessment = assessment_map[sid]

        # Verify quote authenticity in raw CV text
        quote_verified = validate_quote_in_text(
            quote=assessment.evidence_quote,
            full_text=cv_text,
            threshold=fuzzy_threshold,
        )

        metadata: Dict[str, object] = {
            "baseline_name": baseline_name,
            "evidence_quote": assessment.evidence_quote,
            "reasoning": assessment.reasoning,
            "evidence_unverified": not quote_verified,
        }

        results.append(
            BaselineSkillResult(
                jd_skill_id=sid,
                semantic_alignment=assessment.semantic_alignment,
                required_proficiency=assessment.required_proficiency,
                candidate_proficiency=assessment.candidate_proficiency,
                gap_magnitude=assessment.gap_magnitude,
                priority=assessment.priority,
                metadata=metadata,
            )
        )

    return results
