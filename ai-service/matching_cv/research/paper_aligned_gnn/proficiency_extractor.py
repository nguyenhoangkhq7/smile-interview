"""Proficiency Descriptor Extraction and Table 3 Numeric Mapping.

Reference:
Baghbanzadeh, A., & Wu, D. (2025). ICIT 2025.
- Section 3.2 & 3.4: POS-tagged modifiers mapped to numeric proficiency weights.
- Table 3 (Page 4): Explicit 9-level descriptor mapping (1, 3, 4, 5, 6, 7, 8, 9, 10).
- Tables 6 & 7 (Page 6): Sample resume/job tables containing 'Moderate', 'Familiar',
  'Some Knowledge', 'Some Skill', and '-' (missing).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from matching_cv.app.services.extraction_adapter import build_term_pattern
from matching_cv.research.paper_aligned_gnn.schemas import (
    EdgeWeightNormalization,
    ProficiencyRecord,
    ProficiencySide,
    SkillInputItem,
)

# ---------------------------------------------------------------------------
# PAPER_EXPLICIT: Table 3 (Page 4) exact mapping
# Note: Level 2 is omitted in Table 3 of the published paper.
# ---------------------------------------------------------------------------
PAPER_TABLE3_EXPLICIT_MAPPING: Dict[str, Tuple[float, str]] = {
    "basic": (1.0, "Basic"),
    "beginner": (3.0, "Beginner"),
    "intermediate": (4.0, "Intermediate"),
    "proficient": (5.0, "Proficient"),
    "skilled": (6.0, "Skilled"),
    "accomplished": (7.0, "Accomplished"),
    "experienced": (8.0, "Experienced"),
    "expert": (9.0, "Expert"),
    "strong": (10.0, "Strong"),
}

# Morphological / inflectional variants directly derived from Table 3 examples
# (e.g., Table 3 example "Strong expertise in Cybersecurity", "Proficiency in Python")
PAPER_TABLE3_MORPHOLOGICAL_VARIANTS: Dict[str, Tuple[float, str]] = {
    "proficiency": (5.0, "Proficient"),
    "expertise": (9.0, "Expert"),
}

# ---------------------------------------------------------------------------
# IMPLEMENTATION_ASSUMPTION: Descriptors used in Paper Tables 6 & 7 (Page 6)
# that were omitted from Table 3 (Page 4)
# ---------------------------------------------------------------------------
PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING: Dict[str, Tuple[float, str]] = {
    "some knowledge": (2.0, "Some Knowledge"),
    "some skill": (2.0, "Some Skill"),
    "familiar": (2.0, "Familiar"),
    "familiarity": (2.0, "Familiar"),
    "moderate": (4.0, "Moderate"),
}

CLAUSE_SPLIT_REGEX = re.compile(r"[.;,\n]|\b(?:and|but|while|whereas)\b", re.IGNORECASE)


def map_descriptor_to_proficiency(
    descriptor_text: Optional[str],
    side: ProficiencySide,
    allow_paper_table6_7_descriptors: bool = True,
    extraction_method: str = "explicit_modifier_field",
    provenance_sentence: Optional[str] = None,
) -> ProficiencyRecord:
    """
    Map a raw proficiency descriptor string to a structured ProficiencyRecord.
    Preserves missingness when descriptor is None, empty, '-', or unmapped.
    """
    if descriptor_text is None:
        return ProficiencyRecord(
            side=side,
            raw_descriptor=None,
            numeric_level=None,
            normalized_weight=None,
            is_missing=True,
            mapping_source="missing",
            extraction_method="missing",
            provenance_sentence=provenance_sentence,
            decision_class="PAPER_EXPLICIT",
        )

    cleaned = re.sub(r"\s+", " ", descriptor_text).strip()
    if not cleaned or cleaned in ("-", "—", "N/A", "n/a", "none", "None", "unknown"):
        return ProficiencyRecord(
            side=side,
            raw_descriptor=None,
            numeric_level=None,
            normalized_weight=None,
            is_missing=True,
            mapping_source="missing",
            extraction_method="missing",
            provenance_sentence=provenance_sentence,
            decision_class="PAPER_EXPLICIT",
        )

    lower = cleaned.casefold()

    # 1. Exact match in Table 3
    if lower in PAPER_TABLE3_EXPLICIT_MAPPING:
        val, canonical_desc = PAPER_TABLE3_EXPLICIT_MAPPING[lower]
        return ProficiencyRecord(
            side=side,
            raw_descriptor=canonical_desc,
            numeric_level=val,
            normalized_weight=round(val / 10.0, 4),
            is_missing=False,
            mapping_source="paper_table3_explicit",
            extraction_method=extraction_method,
            provenance_sentence=provenance_sentence,
            decision_class="PAPER_EXPLICIT",
        )

    # 2. Exact match in Table 6/7 supplemental descriptors (if enabled)
    if allow_paper_table6_7_descriptors and lower in PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING:
        val, canonical_desc = PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING[lower]
        return ProficiencyRecord(
            side=side,
            raw_descriptor=canonical_desc,
            numeric_level=val,
            normalized_weight=round(val / 10.0, 4),
            is_missing=False,
            mapping_source="paper_table6_7_assumption",
            extraction_method=extraction_method,
            provenance_sentence=provenance_sentence,
            decision_class="IMPLEMENTATION_ASSUMPTION",
        )

    # 3. Search token-bounded Table 3 descriptors inside a multi-word modifier phrase
    # (e.g., "Strong expertise" -> Strong (10.0), "Basic knowledge" -> Basic (1.0))
    best_match: Optional[Tuple[float, str, str, str]] = None
    for key, (val, canonical_desc) in sorted(
        PAPER_TABLE3_EXPLICIT_MAPPING.items(), key=lambda x: x[1][0], reverse=True
    ):
        if re.search(rf"\b{re.escape(key)}\b", lower):
            best_match = (val, canonical_desc, "paper_table3_explicit", "PAPER_EXPLICIT")
            break

    if best_match is None:
        for key, (val, canonical_desc) in sorted(
            PAPER_TABLE3_MORPHOLOGICAL_VARIANTS.items(), key=lambda x: x[1][0], reverse=True
        ):
            if re.search(rf"\b{re.escape(key)}\b", lower):
                best_match = (val, canonical_desc, "paper_table3_explicit", "PAPER_EXPLICIT")
                break

    if best_match is None and allow_paper_table6_7_descriptors:
        for key, (val, canonical_desc) in sorted(
            PAPER_TABLE6_7_SUPPLEMENTAL_MAPPING.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if re.search(rf"\b{re.escape(key)}\b", lower):
                best_match = (val, canonical_desc, "paper_table6_7_assumption", "IMPLEMENTATION_ASSUMPTION")
                break

    if best_match is not None:
        val, canonical_desc, map_src, dec_cls = best_match
        return ProficiencyRecord(
            side=side,
            raw_descriptor=canonical_desc,
            numeric_level=val,
            normalized_weight=round(val / 10.0, 4),
            is_missing=False,
            mapping_source=map_src,  # type: ignore[arg-type]
            extraction_method=extraction_method,
            provenance_sentence=provenance_sentence,
            decision_class=dec_cls,  # type: ignore[arg-type]
        )

    # Unrecognized modifier string -> do not invent a numeric proficiency level
    return ProficiencyRecord(
        side=side,
        raw_descriptor=cleaned,
        numeric_level=None,
        normalized_weight=None,
        is_missing=True,
        mapping_source="missing",
        extraction_method="missing",
        provenance_sentence=provenance_sentence,
        decision_class="PAPER_EXPLICIT",
    )


def _extract_clause_around_skill(sentence: str, skill_surface: str, window_chars: int = 48) -> str:
    """
    Extract the local clause or character window surrounding `skill_surface` inside `sentence`.
    Prevents cross-contaminating modifiers when two skills with different proficiency
    levels appear in the same sentence (e.g., 'Strong in Python and Basic in SQL').
    """
    if not sentence or not skill_surface:
        return sentence or ""

    pat = build_term_pattern(skill_surface)
    match = pat.search(sentence)
    if not match:
        # Fallback case-insensitive substring search
        idx = sentence.casefold().find(skill_surface.casefold())
        if idx == -1:
            return sentence
        m_start, m_end = idx, idx + len(skill_surface)
    else:
        m_start, m_end = match.start(), match.end()

    # Check if a clause boundary isolates the mention
    clauses: List[Tuple[int, int]] = []
    last_idx = 0
    for cm in CLAUSE_SPLIT_REGEX.finditer(sentence):
        clauses.append((last_idx, cm.start()))
        last_idx = cm.end()
    clauses.append((last_idx, len(sentence)))

    for c_start, c_end in clauses:
        if c_start <= m_start and m_end <= c_end:
            clause_str = sentence[c_start:c_end].strip()
            if clause_str:
                return clause_str

    w_start = max(0, m_start - window_chars)
    w_end = min(len(sentence), m_end + window_chars)
    return sentence[w_start:w_end]


def extract_skill_proficiency(
    skill_item: SkillInputItem,
    allow_paper_table6_7_descriptors: bool = True,
) -> ProficiencyRecord:
    """
    Extract proficiency for a CV or JD skill item without fabricating values:
    1. Explicit `proficiency_override` if set on the item.
    2. Explicit `modifier_text` if extracted upstream.
    3. Local clause/window search inside `evidence_sentences`.
    4. Otherwise returns missing ProficiencyRecord (`is_missing=True`, `numeric_level=None`).
    """
    side: ProficiencySide = (
        "CV_DEMONSTRATED" if skill_item.source_document == "CV" else "JD_REQUIRED"
    )
    first_sent = skill_item.evidence_sentences[0] if skill_item.evidence_sentences else None

    # 1. Explicit override
    if skill_item.proficiency_override is not None:
        return map_descriptor_to_proficiency(
            descriptor_text=skill_item.proficiency_override,
            side=side,
            allow_paper_table6_7_descriptors=allow_paper_table6_7_descriptors,
            extraction_method="provided_override",
            provenance_sentence=first_sent,
        )

    # 2. Upstream modifier_text field
    if skill_item.modifier_text and skill_item.modifier_text.strip():
        rec = map_descriptor_to_proficiency(
            descriptor_text=skill_item.modifier_text,
            side=side,
            allow_paper_table6_7_descriptors=allow_paper_table6_7_descriptors,
            extraction_method="explicit_modifier_field",
            provenance_sentence=first_sent,
        )
        if not rec.is_missing:
            return rec

    # 3. Context window search across verbatim evidence sentences
    best_record: Optional[ProficiencyRecord] = None
    for sent in skill_item.evidence_sentences:
        if not sent or not sent.strip():
            continue
        local_clause = _extract_clause_around_skill(sent, skill_item.surface_name)
        cand = map_descriptor_to_proficiency(
            descriptor_text=local_clause,
            side=side,
            allow_paper_table6_7_descriptors=allow_paper_table6_7_descriptors,
            extraction_method="context_window_regex",
            provenance_sentence=sent,
        )
        if not cand.is_missing and cand.numeric_level is not None:
            if best_record is None or (best_record.numeric_level or 0.0) < cand.numeric_level:
                best_record = cand

    if best_record is not None:
        return best_record

    # 4. Missing proficiency (do NOT invent or substitute cosine similarity)
    return ProficiencyRecord(
        side=side,
        raw_descriptor=None,
        numeric_level=None,
        normalized_weight=None,
        is_missing=True,
        mapping_source="missing",
        extraction_method="missing",
        provenance_sentence=first_sent,
        decision_class="PAPER_EXPLICIT",
    )


def compute_tensor_edge_weight(
    proficiency: ProficiencyRecord,
    normalization: EdgeWeightNormalization = "scaled_0_1",
    missing_tensor_weight: float = 0.0,
) -> float:
    """
    Convert a ProficiencyRecord into the scalar float used on the PyG edge tensor.
    Separates missingness (encoded via `missing_tensor_weight` and `edge_has_proficiency=False`)
    from grounded Table 3 weights.
    """
    if proficiency.is_missing or proficiency.numeric_level is None:
        return float(missing_tensor_weight)
    if normalization == "raw_table3":
        return float(proficiency.numeric_level)
    return round(float(proficiency.numeric_level) / 10.0, 4)
