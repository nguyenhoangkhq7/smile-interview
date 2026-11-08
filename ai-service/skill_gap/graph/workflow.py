"""
LangGraph StateGraph Orchestrator for Module 2 (Skill-Gap Detection).

Implements parallel Fan-out / Fan-in execution:
  START ---> [node_segment_cv] ---\
        ---> [node_parse_jd]   ----+--> [node_estimate_proficiencies (Parallel N skills)]
                                         --> [node_detect_gaps (Deterministic 0ms)]
                                         --> [node_build_audit_report (Fact-based XAI)]
                                         --> END
"""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple, TypedDict
import uuid

from langgraph.graph import END, START, StateGraph

from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    JDParserOutput,
    MatchResult,
    ProficiencyResult,
    SegmenterOutput,
    SkillGapResult,
)
from skill_gap.services.gap_detector import GapDetector
from skill_gap.services.jd_requirement_parser import JDRequirementParser
from skill_gap.services.proficiency_estimator import ProficiencyEstimator, ProficiencyEstimating
from skill_gap.services.report_generator import StaticGapAuditReport, generate_static_gap_report
from skill_gap.services.resume_segmenter import ResumeSegmenter


class SkillGapGraphState(TypedDict, total=False):
    """State schema passed through the compiled LangGraph StateGraph."""

    analysis_id: str
    cv_text: str
    jd_text: str
    cv_skills: List[ExtractedCVSkill]
    jd_skills: List[ExtractedJDSkill]
    match_results: List[MatchResult]

    # Parallel Fan-out intermediate outputs
    segment_output: SegmenterOutput
    jd_parser_output: JDParserOutput

    # Parallel Fan-in outputs
    proficiencies: List[ProficiencyResult]
    gap_results: List[SkillGapResult]
    audit_report: StaticGapAuditReport


class SkillGapWorkflow:
    """
    LangGraph `StateGraph` orchestrating Module 2 (Skill-Gap Detection) with parallel execution.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: Optional[AppConfig] = None,
        estimator: Optional[ProficiencyEstimating] = None,
        segmenter: Optional[ResumeSegmenter] = None,
        jd_parser: Optional[JDRequirementParser] = None,
        gap_detector: Optional[GapDetector] = None,
        max_workers: int = 8,
    ) -> None:
        self.llm_client = llm_client
        self.config = config or AppConfig()
        self.segmenter = segmenter or ResumeSegmenter(self.llm_client, self.config)
        self.jd_parser = jd_parser or JDRequirementParser(self.llm_client, self.config)
        self.estimator = estimator or ProficiencyEstimator(self.llm_client, self.config)
        self.gap_detector = gap_detector or GapDetector(self.llm_client, self.config)
        self.max_workers = max_workers
        self.graph = self._build_langgraph()

    def _build_langgraph(self):
        builder = StateGraph(SkillGapGraphState)

        builder.add_node("segment_cv", self._node_segment_cv)
        builder.add_node("parse_jd", self._node_parse_jd)
        builder.add_node("estimate_proficiencies", self._node_estimate_proficiencies)
        builder.add_node("detect_gaps", self._node_detect_gaps)
        builder.add_node("build_audit_report", self._node_build_audit_report)

        # Fan-out: Run Step 1 (CV Segmentation) and Step 2 (JD Parsing) in parallel
        builder.add_edge(START, "segment_cv")
        builder.add_edge(START, "parse_jd")

        # Fan-in: Wait for both branches before running Step 3 (Proficiency Estimation)
        builder.add_edge(["segment_cv", "parse_jd"], "estimate_proficiencies")

        # Sequential deterministic post-processing (Step 4 & XAI Report)
        builder.add_edge("estimate_proficiencies", "detect_gaps")
        builder.add_edge("detect_gaps", "build_audit_report")
        builder.add_edge("build_audit_report", END)

        return builder.compile()

    def _filter_active_cv_skills(
        self,
        cv_skills: List[ExtractedCVSkill],
        match_results: List[MatchResult],
    ) -> List[ExtractedCVSkill]:
        """
        Target-Driven Active-Skill Pruning:
        Only retain CV skills that are matched to at least one JD skill with
        `soft_match >= floor_threshold`. Unreferenced CV skills or rejected MISSING
        matches (`soft_match < floor_threshold`) do not need span mapping or LLM richness analysis.
        """
        if not match_results:
            return cv_skills
        floor_tau = self.config.thresholds.floor_threshold
        active_ids = {
            m.matched_cv_skill_id
            for m in match_results
            if m.soft_match >= floor_tau and m.matched_cv_skill_id
        }
        return [s for s in cv_skills if s.skill_id in active_ids]

    def _node_segment_cv(self, state: SkillGapGraphState) -> SkillGapGraphState:
        print("[LangGraph] Nhánh song song 1A: Phân tách CV (Resume Segmenter)...")
        active_cv_skills = self._filter_active_cv_skills(
            state.get("cv_skills", []),
            state.get("match_results", []),
        )
        segment_output = self.segmenter.segment(
            cv_text=state["cv_text"],
            cv_skills=active_cv_skills,
        )
        return {"segment_output": segment_output}

    def _node_parse_jd(self, state: SkillGapGraphState) -> SkillGapGraphState:
        print("[LangGraph] Nhánh song song 1B: Đọc hiểu chuẩn yêu cầu JD (JD Requirement Parser)...")
        jd_parser_output = self.jd_parser.parse(
            jd_text=state["jd_text"],
            jd_skills=state.get("jd_skills", []),
        )
        return {"jd_parser_output": jd_parser_output}

    def _node_estimate_proficiencies(self, state: SkillGapGraphState) -> SkillGapGraphState:
        active_cv_skills = self._filter_active_cv_skills(
            state.get("cv_skills", []),
            state.get("match_results", []),
        )
        segment_output = state["segment_output"]
        print(
            f"[LangGraph] Bước 2 (Fan-in): Đo lường hàng loạt (Batch Deduplicated) {len(active_cv_skills)} kỹ năng ứng viên hoạt động..."
        )

        if not active_cv_skills:
            return {"proficiencies": []}

        # Use deduplicated single-call batch estimation if supported by estimator
        if hasattr(self.estimator, "estimate_batch"):
            proficiencies = self.estimator.estimate_batch(
                skills=active_cv_skills,
                mappings=segment_output.span_mappings,
                job_blocks=segment_output.job_blocks,
            )
            return {"proficiencies": proficiencies}

        def _estimate_single(skill: ExtractedCVSkill) -> ProficiencyResult:
            return self.estimator.estimate(
                skill=skill,
                mappings=segment_output.span_mappings,
                job_blocks=segment_output.job_blocks,
            )

        if len(active_cv_skills) == 1 or self.max_workers <= 1:
            proficiencies = [_estimate_single(s) for s in active_cv_skills]
        else:
            workers = min(self.max_workers, len(active_cv_skills))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                proficiencies = list(pool.map(_estimate_single, active_cv_skills))

        return {"proficiencies": proficiencies}

    def _node_detect_gaps(self, state: SkillGapGraphState) -> SkillGapGraphState:
        print("[LangGraph] Bước 3: Định lượng khoảng trống năng lực tất định (Gap Detector)...")
        segment_output = state["segment_output"]
        jd_parser_output = state["jd_parser_output"]
        proficiencies = state.get("proficiencies", [])

        upstream_degraded = bool(segment_output.degraded or jd_parser_output.degraded)
        upstream_flags = list(segment_output.flags) + list(jd_parser_output.flags)

        gap_results = self.gap_detector.detect(
            requirements=jd_parser_output.requirements,
            proficiencies=proficiencies,
            matches=state.get("match_results", []),
            cv_skills=state.get("cv_skills", []),
            job_blocks=segment_output.job_blocks,
            span_mappings=segment_output.span_mappings,
            upstream_degraded=upstream_degraded,
            upstream_flags=upstream_flags,
        )
        jd_spans = {skill.skill_id: skill.evidence_spans for skill in state.get("jd_skills", [])}
        for result in gap_results:
            result.jd_evidence_spans = list(jd_spans.get(result.jd_skill_id, []))
        return {"gap_results": gap_results}

    def _node_build_audit_report(self, state: SkillGapGraphState) -> SkillGapGraphState:
        print("[LangGraph] Bước 4: Tổng hợp Báo cáo Kiểm toán Chẩn đoán Tĩnh (Fact-based XAI Report)...")
        analysis_id = state.get("analysis_id") or str(uuid.uuid4())
        segment_output = state.get("segment_output")
        jd_parser_output = state["jd_parser_output"]
        proficiencies = state.get("proficiencies", [])
        gap_results = state.get("gap_results", [])
        matches = state.get("match_results", [])

        report = generate_static_gap_report(
            analysis_id=analysis_id,
            gap_results=gap_results,
            requirements=jd_parser_output.requirements,
            proficiencies=proficiencies,
            matches=matches,
            segment_output=segment_output,
            floor_threshold=self.config.thresholds.floor_threshold,
            identity_threshold=self.config.thresholds.identity_threshold,
        )
        return {"audit_report": report}

    def invoke(
        self,
        cv_text: str,
        jd_text: str,
        cv_skills: List[ExtractedCVSkill],
        jd_skills: List[ExtractedJDSkill],
        match_results: List[MatchResult],
        analysis_id: Optional[str] = None,
    ) -> Tuple[List[SkillGapResult], StaticGapAuditReport, SkillGapGraphState]:
        aid = analysis_id or str(uuid.uuid4())
        final_state: SkillGapGraphState = self.graph.invoke(
            {
                "analysis_id": aid,
                "cv_text": cv_text,
                "jd_text": jd_text,
                "cv_skills": list(cv_skills),
                "jd_skills": list(jd_skills),
                "match_results": list(match_results),
            }
        )
        return (
            final_state["gap_results"],
            final_state["audit_report"],
            final_state,
        )
