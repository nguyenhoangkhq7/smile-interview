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

# ---------------------------------------------------------------------------
# PROJECT_ADAPTATION: Vietnamese Proficiency Descriptor Mapping
# Covers common Vietnamese CV/JD proficiency qualifiers so Vietnamese CVs
# (e.g., "Python (cơ bản, 3 tháng)" vs "Python (chuyên sâu, 6 năm)") are
# distinguished accurately even before or without Module 2.
# ---------------------------------------------------------------------------
VIETNAMESE_PROFICIENCY_MAPPING: Dict[str, Tuple[float, str]] = {
    "chuyên sâu": (9.0, "Expert"),
    "thành thục": (9.0, "Expert"),
    "chuyên gia": (9.0, "Expert"),
    "xuất sắc": (9.0, "Expert"),
    "nhiều kinh nghiệm": (8.0, "Experienced"),
    "dày dặn kinh nghiệm": (8.0, "Experienced"),
    "kinh nghiệm sâu": (8.0, "Experienced"),
    "sử dụng thành thạo": (7.0, "Accomplished"),
    "thành thạo": (7.0, "Accomplished"),
    "vững vàng": (7.0, "Accomplished"),
    "nắm vững": (6.0, "Skilled"),
    "sử dụng tốt": (6.0, "Skilled"),
    "có kinh nghiệm thực tế": (5.0, "Proficient"),
    "trung bình": (4.0, "Intermediate"),
    "biết sử dụng": (3.0, "Beginner"),
    "có kiến thức": (3.0, "Beginner"),
    "quen thuộc": (2.0, "Familiar"),
    "làm quen": (2.0, "Familiar"),
    "cơ bản": (1.0, "Basic"),
    "nhập môn": (1.0, "Basic"),
    "mới tìm hiểu": (1.0, "Basic"),
}

_EXPERIENCE_SECTIONS = frozenset({
    "experience",
    "work_experience",
    "work experience",
    "employment",
    "projects",
    "project",
    "professional_experience",
    "kinh_nghiem",
    "du_an",
})

_SKILLS_LIST_SECTIONS = frozenset({
    "skills",
    "technical_skills",
    "technical skills",
    "core_competencies",
    "summary",
    "ky_nang",
})

_JD_CORE_SECTIONS = frozenset({
    "requirements",
    "mandatory",
    "must_have",
    "qualifications",
    "responsibilities",
    "yeu_cau",
})

_JD_OPTIONAL_SECTIONS = frozenset({
    "bonus",
    "preferred",
    "nice_to_have",
    "plus",
    "uu_tien",
})

_RICH_ACTION_VERB_REGEX = re.compile(
    r"\b(?:built|designed|architected|deployed|implemented|optimized|developed|maintained|led|"
    r"spearheaded|migrated|engineered|scaled|managed|operated|automated|orchestrated|"
    r"xây dựng|thiết kế|triển khai|tối ưu|phát triển|vận hành|dẫn dắt|quản trị)\b",
    re.IGNORECASE,
)

CLAUSE_SPLIT_REGEX = re.compile(r"[.;,\n]|\b(?:and|but|while|whereas)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# PROJECT_ADAPTATION: Years of Experience Heuristic Mapping
# Aligned with Dreyfus skill acquisition model & skill_gap standardized scale:
# - < 0.5 year (0 - 5 mos): 1.0 (Basic)
# - 0.5 - 0.9 year (6 - 11 mos): 3.0 (Beginner)
# - 1.0 - 2.9 years (Junior): 4.0 (Intermediate)
# - 3.0 - 4.9 years (Mid-level): 5.0 (Proficient)
# - 5.0 - 7.9 years (Senior): 8.0 (Experienced)
# - >= 8.0 years (Lead / Principal / Expert): 10.0 (Strong)
# ---------------------------------------------------------------------------
YEARS_PATTERN = re.compile(
    r"(?:over|at least|more than|khoảng|hơn|tối thiểu|tầm)?\s*"
    r"(\d+(?:\.\d+)?)(?:\s*(?:-|to|đến)\s*(\d+(?:\.\d+)?))?\s*(?:\+\s*)?"
    r"(?:years?|yrs?|năm)\b",
    re.IGNORECASE,
)
MONTHS_PATTERN = re.compile(
    r"(?:over|at least|more than|khoảng|hơn|tối thiểu|tầm)?\s*"
    r"(\d+(?:\.\d+)?)(?:\s*(?:-|to|đến)\s*(\d+(?:\.\d+)?))?\s*(?:\+\s*)?"
    r"(?:months?|mos?|tháng)\b",
    re.IGNORECASE,
)


def map_years_to_proficiency(
    text: str,
    side: ProficiencySide,
    extraction_method: str = "years_heuristic_mapping",
    provenance_sentence: Optional[str] = None,
) -> Optional[ProficiencyRecord]:
    """Map natural language years of experience expressions to Table 3 proficiency levels."""
    if not text:
        return None

    num_years: Optional[float] = None
    m_yr = YEARS_PATTERN.search(text)
    if m_yr:
        try:
            val1 = float(m_yr.group(1))
            val2 = float(m_yr.group(2)) if m_yr.group(2) else None
            num_years = (val1 + val2) / 2.0 if val2 is not None else val1
        except ValueError:
            num_years = None
    else:
        m_mo = MONTHS_PATTERN.search(text)
        if m_mo:
            try:
                val1 = float(m_mo.group(1))
                val2 = float(m_mo.group(2)) if m_mo.group(2) else None
                num_months = (val1 + val2) / 2.0 if val2 is not None else val1
                num_years = num_months / 12.0
            except ValueError:
                num_years = None

    if num_years is None:
        return None

    if num_years < 0.5:
        val, canonical_desc = 1.0, "Basic"
    elif num_years < 1.0:
        val, canonical_desc = 3.0, "Beginner"
    elif num_years < 3.0:
        val, canonical_desc = 4.0, "Intermediate"
    elif num_years < 5.0:
        val, canonical_desc = 5.0, "Proficient"
    elif num_years < 8.0:
        val, canonical_desc = 8.0, "Experienced"
    else:
        val, canonical_desc = 10.0, "Strong"

    return ProficiencyRecord(
        side=side,
        raw_descriptor=canonical_desc,
        numeric_level=val,
        normalized_weight=round(val / 10.0, 4),
        is_missing=False,
        mapping_source="years_heuristic_mapping",
        extraction_method=extraction_method,
        provenance_sentence=provenance_sentence,
        decision_class="PROJECT_ADAPTATION",
    )


def map_descriptor_to_proficiency(
    descriptor_text: Optional[str],
    side: ProficiencySide,
    allow_paper_table6_7_descriptors: bool = True,
    allow_years_heuristic: bool = True,
    allow_vietnamese_descriptors: bool = True,
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

    # 3B. Vietnamese proficiency descriptors (longest-phrase first)
    if allow_vietnamese_descriptors:
        for vn_key, (val, canonical_desc) in sorted(
            VIETNAMESE_PROFICIENCY_MAPPING.items(),
            key=lambda x: (len(x[0]), x[1][0]),
            reverse=True,
        ):
            if re.search(rf"(?<!\w){re.escape(vn_key)}(?!\w)", lower):
                return ProficiencyRecord(
                    side=side,
                    raw_descriptor=canonical_desc,
                    numeric_level=val,
                    normalized_weight=round(val / 10.0, 4),
                    is_missing=False,
                    mapping_source="vietnamese_descriptor_mapping",
                    extraction_method=extraction_method,
                    provenance_sentence=provenance_sentence,
                    decision_class="PROJECT_ADAPTATION",
                )

    # 4. Years of experience heuristic mapping (if enabled)
    if allow_years_heuristic:
        years_rec = map_years_to_proficiency(
            text=cleaned,
            side=side,
            extraction_method=extraction_method,
            provenance_sentence=provenance_sentence,
        )
        if years_rec is not None:
            return years_rec

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


def estimate_evidence_fallback_proficiency(
    skill_item: SkillInputItem,
    side: ProficiencySide,
) -> ProficiencyRecord:
    """
    Continuous, evidence-based proficiency fallback (Approach 2) for real CVs/JDs that omit
    explicit Table 3 modifiers ('Strong', 'Basic') or explicit years next to a skill mention.

    Maps structural signals already produced by Stage 2 (section placement, rich action context,
    evidence count, explicit vs. implicit) to a continuous level in [2.5, 7.5] (weight [0.25, 0.75])
    so edges never collapse to 0.0 while remaining strictly bounded below explicit Expert/Strong (8-10).
    """
    sents = [s.strip() for s in (skill_item.evidence_sentences or []) if s and s.strip()]
    first_sent = sents[0] if sents else None
    raw_sections = skill_item.metadata.get("sections", []) if isinstance(skill_item.metadata, dict) else []
    sections = {str(sec).strip().lower() for sec in raw_sections if sec}

    has_rich_sentence = any(
        len(sent) >= 35 and bool(_RICH_ACTION_VERB_REGEX.search(sent))
        for sent in sents
    )
    extra_evidence_count = max(0, len(sents) - 1)

    if side == "CV_DEMONSTRATED":
        if skill_item.extraction_type == "implicit":
            base_level = 3.5
        elif sections.intersection(_EXPERIENCE_SECTIONS) or has_rich_sentence:
            base_level = 5.5
        elif sections.intersection(_SKILLS_LIST_SECTIONS):
            base_level = 4.0
        else:
            base_level = 4.5
        level = min(7.5, base_level + 0.5 * min(4, extra_evidence_count))
    else:
        if sections.intersection(_JD_OPTIONAL_SECTIONS):
            base_level = 4.0
        elif sections.intersection(_JD_CORE_SECTIONS) or has_rich_sentence:
            base_level = 6.0
        else:
            base_level = 5.5
        level = min(7.5, base_level + 0.3 * min(3, extra_evidence_count))

    level = round(float(max(2.5, min(7.5, level))), 2)
    return ProficiencyRecord(
        side=side,
        raw_descriptor="EvidenceFallback",
        numeric_level=level,
        normalized_weight=round(level / 10.0, 4),
        is_missing=False,
        mapping_source="evidence_context_fallback",
        extraction_method="evidence_context_fallback",
        provenance_sentence=first_sent,
        decision_class="PROJECT_ADAPTATION",
    )


def build_module2_proficiency_record(
    proficiency_1_to_5: float,
    side: ProficiencySide,
    provenance_sentence: Optional[str] = None,
) -> ProficiencyRecord:
    """
    Convert a continuous Module 2 (skill_gap) proficiency score P in [1.0, 5.0]
    into a normalized GNN edge ProficiencyRecord on [0.2, 1.0] (numeric_level in [2.0, 10.0]).
    """
    clamped = max(1.0, min(5.0, float(proficiency_1_to_5)))
    weight = round(clamped / 5.0, 4)
    level = round(clamped * 2.0, 2)
    label_prefix = "Module2_P_CV" if side == "CV_DEMONSTRATED" else "Module2_P_JD"
    return ProficiencyRecord(
        side=side,
        raw_descriptor=f"{label_prefix}={clamped:.2f}",
        numeric_level=level,
        normalized_weight=weight,
        is_missing=False,
        mapping_source="module2_proficiency_estimator",
        extraction_method="module2_proficiency_estimator",
        provenance_sentence=provenance_sentence,
        decision_class="PROJECT_ADAPTATION",
    )


def extract_skill_proficiency(
    skill_item: SkillInputItem,
    allow_paper_table6_7_descriptors: bool = True,
    allow_years_heuristic: bool = True,
    allow_vietnamese_descriptors: bool = True,
    enable_evidence_fallback: bool = False,
) -> ProficiencyRecord:
    """
    Extract proficiency for a CV or JD skill item without fabricating values:
    1. Explicit `proficiency_override` if set on the item.
    2. Explicit `modifier_text` if extracted upstream.
    3. Local clause/window search inside `evidence_sentences` (Table 3, Table 6/7, Vietnamese, Years).
    4. Optional continuous evidence-based fallback (Approach 2) when `enable_evidence_fallback=True`.
    5. Otherwise returns missing ProficiencyRecord (`is_missing=True`, `numeric_level=None`).
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
            allow_years_heuristic=allow_years_heuristic,
            allow_vietnamese_descriptors=allow_vietnamese_descriptors,
            extraction_method="provided_override",
            provenance_sentence=first_sent,
        )

    # 2. Upstream modifier_text field
    if skill_item.modifier_text and skill_item.modifier_text.strip():
        rec = map_descriptor_to_proficiency(
            descriptor_text=skill_item.modifier_text,
            side=side,
            allow_paper_table6_7_descriptors=allow_paper_table6_7_descriptors,
            allow_years_heuristic=allow_years_heuristic,
            allow_vietnamese_descriptors=allow_vietnamese_descriptors,
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
            allow_years_heuristic=allow_years_heuristic,
            allow_vietnamese_descriptors=allow_vietnamese_descriptors,
            extraction_method="context_window_regex",
            provenance_sentence=sent,
        )
        if not cand.is_missing and cand.numeric_level is not None:
            if best_record is None or (best_record.numeric_level or 0.0) < cand.numeric_level:
                best_record = cand

    if best_record is not None:
        return best_record

    # 4. Continuous evidence-based fallback (Approach 2) when enabled for production inference
    if enable_evidence_fallback:
        return estimate_evidence_fallback_proficiency(skill_item, side=side)

    # 5. Missing proficiency (do NOT invent or substitute cosine similarity)
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
