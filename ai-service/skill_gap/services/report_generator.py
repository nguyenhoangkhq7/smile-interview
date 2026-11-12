"""
Fact-Based Static XAI Audit Report Generator for Module 2 (Skill-Gap Detection).

Strictly adheres to the scientific boundary between Module 2 and Module 3:
- Module 2 (Static Fact-based Diagnosis): Explains competency gaps purely from observable
  CV evidence (`cv_evidence_spans`, `effective_months`, `c_evidence`, `recency_flag`,
  `substitution_factor`) compared against the JD benchmark (`required_proficiency`, `jd_reasoning`).
  Answers: "What concrete evidence is missing or insufficient in the CV?"
- Module 3 (Dynamic Hypothesis-based Probing): Inherits Module 2's static diagnosis as
  the starting observation (C_0) to abduce hidden competency hypotheses (A_0) during the interview.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from tabulate import tabulate

from skill_gap.domain.enums import SemanticAlignment, QuestionStrategy
from skill_gap.domain.models import (
    JDRequirement,
    MatchResult,
    ProficiencyResult,
    SegmenterOutput,
    SkillGapResult,
)


class StaticSkillAuditItem(BaseModel):
    """Fact-based static audit record for a single JD skill requirement."""

    jd_skill_id: str
    jd_skill_name: Optional[str] = None
    matched_cv_skill_name: Optional[str] = None
    matched_cv_skill_id: Optional[str] = None
    semantic_alignment: SemanticAlignment
    is_substituted: bool = False
    soft_match: float = Field(default=0.0, ge=0.0, le=1.0)
    substitution_factor: float = Field(default=0.0, ge=0.0, le=1.0)
    importance_weight: float = Field(default=0.0, ge=0.0, le=1.0, description="w_j from GNN")
    required_proficiency: float = Field(ge=1.0, le=5.0, description="P_JD")
    jd_reasoning: str = ""
    candidate_proficiency: float = Field(ge=1.0, le=5.0, description="P_CV")
    effective_candidate_proficiency: float = Field(
        default=0.0, description="s * P_CV after semantic transferability scaling"
    )
    effective_months: float = Field(default=0.0, ge=0.0)
    c_evidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ratio of RICH_CONTEXT project spans in [0, 1]"
    )
    recency_flag: bool = Field(
        default=False, description="True if skill was last practiced > recency_years_threshold ago"
    )
    gap_magnitude: float = Field(ge=0.0, le=1.0)
    severity: float = Field(ge=0.0, le=1.0)
    priority: float = Field(ge=0.0, le=1.0)
    suggested_strategy: QuestionStrategy
    context_job: Optional[str] = None
    cv_evidence_spans: List[str] = Field(default_factory=list)
    static_diagnosis: str = Field(
        description="Fact-based static explanation of what CV evidence is present or lacking compared to JD"
    )
    degraded: bool = False
    flags: List[str] = Field(default_factory=list)


class StaticGapAuditReport(BaseModel):
    """Complete Auditable Static Diagnosis Report (JSON + GitHub Flavored Markdown)."""

    analysis_id: str
    total_jd_skills: int
    matched_count: int
    partial_count: int
    missing_count: int
    skills_requiring_probing: int
    matching_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Overall GNN CV–JD compatibility on a 0–1 scale"
    )
    degraded: bool = False
    system_flags: List[str] = Field(default_factory=list)
    items: List[StaticSkillAuditItem] = Field(default_factory=list)
    markdown_summary: str = Field(
        description="Formatted GitHub Flavored Markdown table and per-skill static evidence audit"
    )


def _build_static_diagnosis(
    gap_res: SkillGapResult,
    prof: Optional[ProficiencyResult],
    req: Optional[JDRequirement],
    soft_match: float,
    substitution_factor: float,
) -> str:
    """
    Construct a 100% deterministic, fact-based static diagnosis explaining what evidence
    is observed or lacking in the CV relative to the JD requirement.
    """
    s_jd = gap_res.required_proficiency
    s_cv = gap_res.candidate_proficiency
    eff_months = prof.effective_months if prof else 0.0
    c_ev = prof.c_evidence if prof else 0.0
    recency = prof.recency_flag if prof else False

    if gap_res.semantic_alignment == SemanticAlignment.MISSING:
        return (
            f"Khuyết thiếu bằng chứng kỹ năng (MISSING): Độ tương đồng ngữ nghĩa đạt {soft_match:.2f} "
            f"(dưới ngưỡng sàn), CV không có bằng chứng hợp lệ cho '{gap_res.jd_skill_id}' "
            f"(JD yêu cầu s_jd = {s_jd:.1f}/5.0). Đề xuất chiến lược '{gap_res.suggested_strategy.value}' ở Module 3."
        )

    evidence_quality_str = (
        f"tỷ lệ bằng chứng dự án thực chiến c_evidence = {c_ev:.2f} "
        f"({'giàu ngữ cảnh dự án' if c_ev >= 0.5 else 'chủ yếu liệt kê từ khóa, thiếu mô tả dự án thực tế'})"
    )
    recency_str = (
        "; cảnh báo Recency Flag = True (kỹ năng đã quá hạn chưa thực hành gần đây)"
        if recency
        else ""
    )

    if gap_res.semantic_alignment == SemanticAlignment.PARTIAL:
        eff_level = substitution_factor * s_cv
        return (
            f"Bằng chứng kỹ năng thay thế tương đương (PARTIAL): CV không nêu trực tiếp '{gap_res.jd_skill_id}' "
            f"nhưng có kỹ năng gần gũi '{gap_res.matched_cv_skill_id}' (hệ số chuyển giao s = {substitution_factor:.2f}, "
            f"{eff_months:.1f} tháng kinh nghiệm hiệu dụng, {evidence_quality_str}{recency_str}). "
            f"Năng lực quy đổi đạt {eff_level:.2f}/5.0 so với yêu cầu JD s_jd = {s_jd:.1f}/5.0 "
            f"(gap = {gap_res.gap_magnitude:.3f}). Đề xuất chiến lược '{gap_res.suggested_strategy.value}'."
        )

    if gap_res.gap_magnitude <= 0.0:
        return (
            f"Đủ bằng chứng tĩnh trên CV (MATCH - Đạt chuẩn): Kỹ năng '{gap_res.jd_skill_id}' có "
            f"{eff_months:.1f} tháng kinh nghiệm hiệu dụng ({evidence_quality_str}{recency_str}), "
            f"đạt s_cv = {s_cv:.2f}/5.0 >= s_jd = {s_jd:.1f}/5.0 (gap = 0.000). "
            f"Đưa vào Context Anchors (chiến lược '{gap_res.suggested_strategy.value}')."
        )

    return (
        f"Thiếu hụt độ sâu bằng chứng trên CV (MATCH - Chưa đủ chuẩn JD): Kỹ năng '{gap_res.jd_skill_id}' "
        f"ghi nhận {eff_months:.1f} tháng kinh nghiệm hiệu dụng ({evidence_quality_str}{recency_str}), "
        f"đạt s_cv = {s_cv:.2f}/5.0 thấp hơn chuẩn JD s_jd = {s_jd:.1f}/5.0 "
        f"(gap = {gap_res.gap_magnitude:.3f}, priority = {gap_res.priority:.3f}). "
        f"Đề xuất chiến lược '{gap_res.suggested_strategy.value}' ở Module 3."
    )


def generate_static_gap_report(
    analysis_id: str,
    gap_results: List[SkillGapResult],
    requirements: List[JDRequirement],
    proficiencies: List[ProficiencyResult],
    matches: List[MatchResult],
    segment_output: Optional[SegmenterOutput] = None,
    floor_threshold: float = 0.40,
    identity_threshold: float = 0.85,
) -> StaticGapAuditReport:
    """
    Build the complete Fact-based Static XAI Audit Report (`StaticGapAuditReport`)
    from pipeline outputs.
    """
    req_map: Dict[str, JDRequirement] = {r.jd_skill_id: r for r in requirements}
    prof_map: Dict[str, ProficiencyResult] = {p.skill_id: p for p in proficiencies}
    match_map: Dict[str, MatchResult] = {m.jd_skill_id: m for m in matches}

    items: List[StaticSkillAuditItem] = []
    sys_flags: List[str] = []
    if segment_output and segment_output.flags:
        sys_flags.extend(segment_output.flags)

    for res in gap_results:
        req = req_map.get(res.jd_skill_id)
        prof = prof_map.get(res.matched_cv_skill_id) if res.matched_cv_skill_id else None
        match = match_map.get(res.jd_skill_id)

        soft_match = match.soft_match if match else 0.0
        w_j = match.w_j if match else 0.0

        if soft_match >= identity_threshold:
            sub_factor = 1.0
        elif soft_match < floor_threshold:
            sub_factor = 0.0
        else:
            sub_factor = soft_match

        eff_cand = (
            0.0
            if res.semantic_alignment == SemanticAlignment.MISSING
            else round(sub_factor * res.candidate_proficiency, 3)
        )

        diagnosis = _build_static_diagnosis(
            gap_res=res,
            prof=prof,
            req=req,
            soft_match=soft_match,
            substitution_factor=sub_factor,
        )

        items.append(
            StaticSkillAuditItem(
                jd_skill_id=res.jd_skill_id,
                jd_skill_name=res.jd_skill_name,
                matched_cv_skill_name=res.matched_cv_skill_name,
                matched_cv_skill_id=res.matched_cv_skill_id,
                semantic_alignment=res.semantic_alignment,
                is_substituted=res.is_substituted,
                soft_match=round(soft_match, 4),
                substitution_factor=round(sub_factor, 4),
                importance_weight=round(w_j, 4),
                required_proficiency=round(res.required_proficiency, 2),
                jd_reasoning=req.reasoning if req else "",
                candidate_proficiency=round(res.candidate_proficiency, 2),
                effective_candidate_proficiency=eff_cand,
                effective_months=round(prof.effective_months, 2) if prof else 0.0,
                c_evidence=round(prof.c_evidence, 3) if prof else 0.0,
                recency_flag=prof.recency_flag if prof else False,
                gap_magnitude=round(res.gap_magnitude, 4),
                severity=round(res.severity, 4),
                priority=round(res.priority, 4),
                suggested_strategy=res.suggested_strategy,
                context_job=res.context_job,
                cv_evidence_spans=list(res.cv_evidence_spans),
                static_diagnosis=diagnosis,
                degraded=res.degraded,
                flags=list(res.flags),
            )
        )

    matched_cnt = sum(1 for i in items if i.semantic_alignment == SemanticAlignment.MATCH)
    partial_cnt = sum(1 for i in items if i.semantic_alignment == SemanticAlignment.PARTIAL)
    missing_cnt = sum(1 for i in items if i.semantic_alignment == SemanticAlignment.MISSING)
    probing_cnt = sum(
        1 for i in items if i.suggested_strategy != QuestionStrategy.NONE and i.priority > 0.0
    )
    any_degraded = bool((segment_output and segment_output.degraded) or any(i.degraded for i in items))

    headers = [
        "Kỹ năng JD (`jd_skill_id`)",
        "Kỹ năng CV (`matched`)",
        "Alignment",
        "$w_j$",
        "$s_{jd}$ (Yêu cầu)",
        "$s_{cv}$ (Thực tế)",
        "Tháng HQ",
        "$c_{\\text{evidence}}$",
        "Gap",
        "Priority",
        "Chiến lược (Module 3)",
    ]
    rows = []
    for it in items:
        rows.append(
            [
                f"`{it.jd_skill_id}`",
                f"`{it.matched_cv_skill_id or 'None'}`",
                it.semantic_alignment.value,
                f"{it.importance_weight:.2f}",
                f"{it.required_proficiency:.2f}",
                f"**{it.candidate_proficiency:.2f}**",
                f"{it.effective_months:.1f}m",
                f"{it.c_evidence:.2f}",
                f"{it.gap_magnitude:.3f}",
                f"**{it.priority:.3f}**",
                f"`{it.suggested_strategy.value}`",
            ]
        )

    md_table = tabulate(rows, headers=headers, tablefmt="github")

    md_lines = [
        f"# Báo cáo Kiểm toán Chẩn đoán Tĩnh (Static Skill-Gap Audit Report - ID `{analysis_id}`)",
        "",
        f"- **Tổng số kỹ năng JD đánh giá**: {len(items)} "
        f"(`MATCH`: {matched_cnt}, `PARTIAL`: {partial_cnt}, `MISSING`: {missing_cnt})",
        f"- **Số kỹ năng cần chuyển sang Module 3 thăm dò động ($D$)**: {probing_cnt} / {len(items)}",
        f"- **Trạng thái Kiểm toán**: `{'DEGRADED' if any_degraded else 'CLEAN (100% DETERMINISTIC)'}`",
        "",
        "## 1. Bảng Đối chiếu Định lượng Bằng chứng CV vs. Chuẩn JD",
        "",
        md_table,
        "",
        "## 2. Chẩn đoán Tĩnh Chi tiết theo Bằng chứng (Fact-based Evidence Audit)",
        "",
    ]

    for it in items:
        md_lines.append(f"### Kỹ năng JD: `{it.jd_skill_id}` (Chiến lược: `{it.suggested_strategy.value}`)")
        md_lines.append(f"- **Chẩn đoán tĩnh**: {it.static_diagnosis}")
        if it.jd_reasoning:
            md_lines.append(f"- **Căn cứ chuẩn JD ($s_{{jd}} = {it.required_proficiency:.1f}$)**: {it.jd_reasoning}")
        if it.context_job:
            md_lines.append(f"- **Bối cảnh công việc trên CV**: {it.context_job}")
        if it.cv_evidence_spans:
            spans_joined = " | ".join(f'"{s}"' for s in it.cv_evidence_spans)
            md_lines.append(f"- **Trích dẫn nguyên văn từ CV (`cv_evidence_spans`)**: {spans_joined}")
        if it.recency_flag:
            md_lines.append("- **Cảnh báo thời gian (`recency_flag`)**: Kỹ năng đã lâu không sử dụng (> ngưỡng 3 năm).")
        md_lines.append("")

    return StaticGapAuditReport(
        analysis_id=analysis_id,
        total_jd_skills=len(items),
        matched_count=matched_cnt,
        partial_count=partial_cnt,
        missing_count=missing_cnt,
        skills_requiring_probing=probing_cnt,
        degraded=any_degraded,
        system_flags=sys_flags,
        items=items,
        markdown_summary="\n".join(md_lines),
    )
