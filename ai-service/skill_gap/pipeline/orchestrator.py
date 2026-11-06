from typing import List, Optional, Tuple
from skill_gap.domain.models import ExtractedCVSkill, ExtractedJDSkill, MatchResult, SkillGapResult
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient
from skill_gap.services.resume_segmenter import ResumeSegmenter
from skill_gap.services.jd_requirement_parser import JDRequirementParser
from skill_gap.services.proficiency_estimator import ProficiencyEstimator, ProficiencyEstimating
from skill_gap.services.gap_detector import GapDetector
from skill_gap.services.report_generator import StaticGapAuditReport
from skill_gap.graph.workflow import SkillGapWorkflow


class SkillGapOrchestrator:
    """
    End-to-End Pipeline orchestrating all steps of the Skill-Gap Detection module
    via a parallel LangGraph StateGraph (Fan-out CV Segmentation // JD Parsing +
    Parallel Proficiency Estimation + Deterministic Gap Detection + Fact-based XAI Report).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: AppConfig,
        estimator: Optional[ProficiencyEstimating] = None,
        max_workers: int = 8,
    ):
        self.llm_client = llm_client
        self.config = config

        # Initialize services
        self.segmenter = ResumeSegmenter(llm_client, config)
        self.jd_parser = JDRequirementParser(llm_client, config)
        self.estimator = estimator or ProficiencyEstimator(llm_client, config)
        self.gap_detector = GapDetector(llm_client, config)

        # Initialize LangGraph StateGraph workflow
        self.workflow = SkillGapWorkflow(
            llm_client=self.llm_client,
            config=self.config,
            estimator=self.estimator,
            segmenter=self.segmenter,
            jd_parser=self.jd_parser,
            gap_detector=self.gap_detector,
            max_workers=max_workers,
        )

    def run_pipeline(
        self,
        cv_text: str,
        jd_text: str,
        cv_skills: List[ExtractedCVSkill],
        jd_skills: List[ExtractedJDSkill],
        match_results: List[MatchResult],
    ) -> List[SkillGapResult]:
        """
        Execute the parallel LangGraph pipeline and return the list of SkillGapResult items.
        Preserves 100% backward compatibility with all existing tests, benchmarks, and Module 3 contracts.
        """
        gap_results, _, _ = self.workflow.invoke(
            cv_text=cv_text,
            jd_text=jd_text,
            cv_skills=cv_skills,
            jd_skills=jd_skills,
            match_results=match_results,
        )
        return gap_results

    def run_pipeline_with_report(
        self,
        cv_text: str,
        jd_text: str,
        cv_skills: List[ExtractedCVSkill],
        jd_skills: List[ExtractedJDSkill],
        match_results: List[MatchResult],
        analysis_id: Optional[str] = None,
    ) -> Tuple[List[SkillGapResult], StaticGapAuditReport]:
        """
        Execute the parallel LangGraph pipeline and return both the Module 3-compatible
        SkillGapResult list and the Fact-based Static XAI Audit Report.
        """
        gap_results, audit_report, _ = self.workflow.invoke(
            cv_text=cv_text,
            jd_text=jd_text,
            cv_skills=cv_skills,
            jd_skills=jd_skills,
            match_results=match_results,
            analysis_id=analysis_id,
        )
        return gap_results, audit_report
