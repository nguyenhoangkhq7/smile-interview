"""
test_upgraded_architecture.py — Verification suite for upgraded Module 2 (`skill_gap`):
1. Parallel LangGraph StateGraph (Fan-out / Fan-in speedup & determinism).
2. DSPy Signatures, Modules, Metrics, and LabeledFewShot artifact compilation.
3. Fact-based Static XAI Audit Report (`StaticGapAuditReport` JSON + GFM table).
4. FastAPI REST endpoints (`/health`, `/api/v1/skill-gap/analyze`, `/api/v1/skill-gap/report/{id}`)
   and 100% contract compatibility with Module 3 (`adaptive_questioning`).
"""

import time
from pathlib import Path
from fastapi.testclient import TestClient
import dspy
import pytest

from main import create_app
from src.adapters.config import AppConfig
from src.adapters.llm_client import DSPyLLMClient, LLMClient
from src.domain.enums import (
    QuestionStrategy,
    RichnessLabel,
    SemanticAlignment,
    SeniorityLevel,
    SkillType,
)
from src.domain.models import (
    ExtractedCVSkill,
    ExtractedJDSkill,
    JDParserOutput,
    JDRequirement,
    JobBlock,
    MatchResult,
    SpanMapping,
    SpanRichness,
)
from src.dspy_modules.compiler import (
    seed_default_compiled_artifacts,
    verify_gold_dataset_self_consistency,
)
from src.dspy_modules.dataset import (
    get_dspy_trainset_and_valset,
    get_gold_jd_requirement_examples,
    get_gold_job_extraction_examples,
    get_gold_span_mapping_examples,
    get_gold_span_richness_examples,
)
from src.dspy_modules.metrics import (
    jd_requirement_metric,
    job_extraction_metric,
    span_mapping_metric,
    span_richness_metric,
)
from src.pipeline.orchestrator import SkillGapOrchestrator
from src.services.proficiency_estimator import SpanAnalysisList
from src.services.resume_segmenter import JobBlockExtraction, SpanMappingExtraction


class SimulatedLatencyMockLLM(LLMClient):
    """Mock LLM with simulated 0.08s network latency per call to verify LangGraph parallel speedup."""

    def __init__(self, delay_sec: float = 0.08):
        self.delay_sec = delay_sec

    def complete(self, prompt: str, schema):
        time.sleep(self.delay_sec)
        name = schema.__name__
        if name == "JobBlockExtraction":
            return JobBlockExtraction(
                job_blocks=[
                    JobBlock(
                        job_id="job_1",
                        title="DevOps Engineer",
                        seniority_level=SeniorityLevel.MID,
                        start_date="2021-01",
                        end_date="2024-01",
                        raw_text="Worked on Kubernetes, Terraform, and Kafka in production.",
                    )
                ]
            )
        if name == "SpanMappingExtraction":
            return SpanMappingExtraction(
                span_mappings=[
                    SpanMapping(span="Vận hành Kubernetes production", job_id="job_1"),
                    SpanMapping(span="Viết Terraform IaC", job_id="job_1"),
                    SpanMapping(span="Xây dựng Kafka pipeline", job_id="job_1"),
                    SpanMapping(span="Kỹ năng khác: GCP, Photoshop", job_id="UNASSIGNED"),
                ]
            )
        if name == "JDParserOutput":
            return JDParserOutput(
                requirements=[
                    JDRequirement(
                        jd_skill_id="kubernetes",
                        required_level=4.5,
                        reasoning="Yêu cầu Senior/Lead K8s.",
                    ),
                    JDRequirement(
                        jd_skill_id="rabbitmq",
                        required_level=3.5,
                        reasoning="Yêu cầu Mid RabbitMQ.",
                    ),
                    JDRequirement(
                        jd_skill_id="gcp",
                        required_level=2.5,
                        reasoning="Nice-to-have GCP.",
                    ),
                    JDRequirement(
                        jd_skill_id="ui_ux",
                        required_level=2.0,
                        reasoning="Basic UI/UX.",
                    ),
                ]
            )
        if name == "SpanAnalysisList":
            return SpanAnalysisList(
                analyses=[
                    SpanRichness(
                        span="Vận hành Kubernetes production",
                        richness_label=RichnessLabel.RICH_CONTEXT,
                    ),
                    SpanRichness(
                        span="Viết Terraform IaC",
                        richness_label=RichnessLabel.RICH_CONTEXT,
                    ),
                    SpanRichness(
                        span="Xây dựng Kafka pipeline",
                        richness_label=RichnessLabel.RICH_CONTEXT,
                    ),
                ]
            )
        raise ValueError(f"Unexpected schema: {name}")


def _build_sample_inputs():
    cv_skills = [
        ExtractedCVSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.98,
            evidence_spans=["Vận hành Kubernetes production"],
        ),
        ExtractedCVSkill(
            skill_id="terraform",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["Viết Terraform IaC"],
        ),
        ExtractedCVSkill(
            skill_id="kafka",
            type=SkillType.EXPLICIT,
            confidence=0.90,
            evidence_spans=["Xây dựng Kafka pipeline"],
        ),
        ExtractedCVSkill(
            skill_id="gcp",
            type=SkillType.EXPLICIT,
            confidence=0.75,
            evidence_spans=["Kỹ năng khác: GCP, Photoshop"],
        ),
    ]
    jd_skills = [
        ExtractedJDSkill(
            skill_id="kubernetes",
            type=SkillType.EXPLICIT,
            confidence=0.99,
            evidence_spans=["5+ years Kubernetes"],
        ),
        ExtractedJDSkill(
            skill_id="rabbitmq",
            type=SkillType.EXPLICIT,
            confidence=0.92,
            evidence_spans=["3+ years RabbitMQ"],
        ),
        ExtractedJDSkill(
            skill_id="gcp",
            type=SkillType.EXPLICIT,
            confidence=0.85,
            evidence_spans=["GCP is a plus"],
        ),
        ExtractedJDSkill(
            skill_id="ui_ux",
            type=SkillType.EXPLICIT,
            confidence=0.80,
            evidence_spans=["Basic UI/UX"],
        ),
    ]
    matches = [
        MatchResult(
            jd_skill_id="kubernetes",
            w_j=0.35,
            matched_cv_skill_id="kubernetes",
            soft_match=1.0,
        ),
        MatchResult(
            jd_skill_id="rabbitmq",
            w_j=0.25,
            matched_cv_skill_id="kafka",
            soft_match=0.75,
        ),
        MatchResult(
            jd_skill_id="gcp",
            w_j=0.20,
            matched_cv_skill_id="gcp",
            soft_match=1.0,
        ),
        MatchResult(
            jd_skill_id="ui_ux",
            w_j=0.20,
            matched_cv_skill_id="gcp",
            soft_match=0.20,
        ),
    ]
    return cv_skills, jd_skills, matches


def test_langgraph_parallel_speedup_and_static_report():
    """
    Verifies that:
    1. LangGraph StateGraph executes Fan-out (segment_cv // parse_jd) and parallel skill estimation
       significantly faster than sequential execution.
    2. Fact-based Static XAI Audit Report (`StaticGapAuditReport`) accurately diagnoses
       MATCH, PARTIAL, and MISSING skills using observable CV facts.
    """
    config = AppConfig(reference_date="2024-06-01")
    llm = SimulatedLatencyMockLLM(delay_sec=0.08)
    orchestrator = SkillGapOrchestrator(llm_client=llm, config=config, max_workers=4)

    cv_skills, jd_skills, matches = _build_sample_inputs()

    t0 = time.perf_counter()
    gap_results, report = orchestrator.run_pipeline_with_report(
        cv_text="DevOps Engineer worked on Kubernetes, Terraform, and Kafka in production.",
        jd_text="Need Senior K8s, Mid RabbitMQ, GCP, UI/UX.",
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        match_results=matches,
        analysis_id="test_audit_001",
    )
    elapsed = time.perf_counter() - t0

    # Sequential would take 6 LLM calls * 0.08s = 0.48s minimum.
    # Parallel Fan-out (max(2,1) calls) + Parallel 3 skills (1 wave) = 3 waves * 0.08s = ~0.24s.
    assert elapsed < 0.42
    assert len(gap_results) == 4
    assert report.analysis_id == "test_audit_001"
    assert report.total_jd_skills == 4
    assert report.matched_count == 2
    assert report.partial_count == 1
    assert report.missing_count == 1
    assert "Static Skill-Gap Audit Report" in report.markdown_summary
    assert "`kubernetes`" in report.markdown_summary
    assert "`COMPARE_SUBSTITUTE`" in report.markdown_summary
    assert "`LEARNING_AGILITY`" in report.markdown_summary


def test_dspy_compilation_and_metrics():
    """
    Verifies that DSPy LabeledFewShot compilation seeds all 4 module JSON artifacts
    with 4 Chain-of-Thought demonstrations each, and that all 21 gold examples
    achieve 1.0000 self-consistency across the 4 multi-component metrics.
    """
    import json

    paths = seed_default_compiled_artifacts(k=4)
    assert len(paths) == 4
    for p in paths.values():
        assert Path(p).exists()
        raw_json = json.loads(Path(p).read_text(encoding="utf-8"))
        predictor_state = next(iter(raw_json.values()))
        demos = predictor_state.get("demos", [])
        assert len(demos) == 4
        # Every compiled demo must include explicit Chain-of-Thought reasoning
        assert all("reasoning" in d and len(d["reasoning"]) > 20 for d in demos)

    client = DSPyLLMClient(api_key="dummy_key")
    assert client.is_compiled is True

    # Verify all 21 gold examples across the 4 datasets achieve 1.0 self-consistency
    consistency = verify_gold_dataset_self_consistency()
    assert consistency["job_extractor"]["count"] == 5
    assert consistency["job_extractor"]["mean_score"] == 1.0
    assert consistency["span_mapper"]["count"] == 5
    assert consistency["span_mapper"]["mean_score"] == 1.0
    assert consistency["jd_parser"]["count"] == 5
    assert consistency["jd_parser"]["mean_score"] == 1.0
    assert consistency["span_richness"]["count"] == 6
    assert consistency["span_richness"]["mean_score"] == 1.0

    # Verify train/val splitting helper
    splits = get_dspy_trainset_and_valset(train_ratio=0.8)
    assert len(splits["job_extractor"][0]) == 4
    assert len(splits["job_extractor"][1]) == 1


def test_dspy_calibrated_metrics_adversarial_discrimination():
    """
    Verifies that the 4 multi-component metrics accurately penalize domain errors:
    1. `job_extraction_metric` rejects hallucinated quotes (0.0 when trace is present)
       and rewards same autonomy tier (Senior vs Lead -> 0.6) over wrong autonomy tier (Intern vs Lead -> 0.0).
    2. `span_mapping_metric` penalizes false attribution of UNASSIGNED global skill lists into a job block.
    3. `jd_requirement_metric` penalizes ordinal rank inversion (Nice-to-have > Must-have).
    4. `span_richness_metric` heavily penalizes false promotion of LIST_ONLY to RICH_CONTEXT (which corrupts c_evidence).
    """
    # 1. Job Extraction: Quote grounding & Seniority Autonomy
    ex_job = get_gold_job_extraction_examples()[0]
    hallucinated_blocks = [
        jb.model_copy(update={"raw_quote": "Completely fabricated quote not in CV at all xyz123", "raw_text": "Fake xyz"})
        for jb in ex_job.job_blocks
    ]
    # In BootstrapFewShot trace filtering mode (trace != None), hallucinated quotes must return 0.0
    assert job_extraction_metric(ex_job, dspy.Prediction(job_blocks=hallucinated_blocks), trace=True) == 0.0

    # Same autonomy tier (Senior vs Lead) > Wrong autonomy tier (Intern vs Lead)
    same_autonomy_blocks = [
        ex_job.job_blocks[0].model_copy(update={"seniority_level": SeniorityLevel.SENIOR}),
        ex_job.job_blocks[1],
    ]
    wrong_autonomy_blocks = [
        ex_job.job_blocks[0].model_copy(update={"seniority_level": SeniorityLevel.INTERN}),
        ex_job.job_blocks[1],
    ]
    score_same_autonomy = job_extraction_metric(ex_job, dspy.Prediction(job_blocks=same_autonomy_blocks))
    score_wrong_autonomy = job_extraction_metric(ex_job, dspy.Prediction(job_blocks=wrong_autonomy_blocks))
    assert 0.90 < score_same_autonomy < 1.0
    assert score_same_autonomy > score_wrong_autonomy

    # 2. Span Mapping: False attribution of UNASSIGNED span to job_1
    ex_map = get_gold_span_mapping_examples()[0]
    corrupted_mappings = [
        SpanMapping(span=m.span, job_id="job_1") for m in ex_map.span_mappings
    ]
    score_corrupted_unassigned = span_mapping_metric(ex_map, dspy.Prediction(span_mappings=corrupted_mappings))
    assert score_corrupted_unassigned < 0.65

    # 3. JD Requirement: Ordinal rank inversion penalty
    ex_jd = get_gold_jd_requirement_examples()[0]
    inverted_reqs = [
        JDRequirement(jd_skill_id="kubernetes", required_level=2.0, reasoning="Inverted nice to have"),
        JDRequirement(jd_skill_id="terraform", required_level=3.5, reasoning="Mid level requirement"),
        JDRequirement(jd_skill_id="gcp", required_level=4.5, reasoning="Inverted senior requirement"),
    ]
    score_inverted_jd = jd_requirement_metric(ex_jd, dspy.Prediction(requirements=inverted_reqs))
    assert score_inverted_jd < 0.60

    # 4. Span Richness: False promotion of LIST_ONLY -> RICH_CONTEXT vs AMBIGUOUS
    ex_rich = get_gold_span_richness_examples()[0]
    false_rich_pred = dspy.Prediction(
        analyses=[
            ex_rich.analyses[0],
            SpanRichness(span=ex_rich.analyses[1].span, richness_label=RichnessLabel.RICH_CONTEXT, modifier_score=4.0),
        ]
    )
    ambiguous_pred = dspy.Prediction(
        analyses=[
            ex_rich.analyses[0],
            SpanRichness(span=ex_rich.analyses[1].span, richness_label=RichnessLabel.AMBIGUOUS, modifier_score=None),
        ]
    )
    score_false_rich = span_richness_metric(ex_rich, false_rich_pred)
    score_ambiguous = span_richness_metric(ex_rich, ambiguous_pred)
    # AMBIGUOUS vs LIST_ONLY preserves c_evidence = 0.5, whereas false RICH_CONTEXT corrupts c_evidence to 1.0!
    assert score_ambiguous > score_false_rich


def test_fastapi_endpoints_and_module3_contract_interoperability():
    """
    Verifies FastAPI endpoints (`/health`, `/api/v1/skill-gap/analyze`, `/api/v1/skill-gap/report/{id}`)
    and validates that the returned `skills` payload can be passed directly into Module 3's
    `SkillGapInput` and `initialize_session_state` without any schema mismatch.
    """
    config = AppConfig(reference_date="2024-06-01")
    mock_llm = SimulatedLatencyMockLLM(delay_sec=0.0)
    app = create_app(llm_client=mock_llm, config=config)
    client = TestClient(app)

    # 1. Health check
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    # 2. POST /api/v1/skill-gap/analyze
    cv_skills, jd_skills, matches = _build_sample_inputs()
    payload = {
        "analysis_id": "api_session_01",
        "cv_text": "Worked on Kubernetes, Terraform, and Kafka in production.",
        "jd_text": "Senior K8s, RabbitMQ, GCP, UI/UX.",
        "cv_skills": [s.model_dump(mode="json") for s in cv_skills],
        "jd_skills": [s.model_dump(mode="json") for s in jd_skills],
        "match_results": [m.model_dump(mode="json") for m in matches],
    }
    analyze_res = client.post("/api/v1/skill-gap/analyze", json=payload)
    assert analyze_res.status_code == 200
    data = analyze_res.json()
    assert data["analysis_id"] == "api_session_01"
    assert data["total_skills"] == 4
    assert len(data["skills"]) == 4

    # 3. GET /api/v1/skill-gap/report/{analysis_id}
    report_res = client.get("/api/v1/skill-gap/report/api_session_01")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["analysis_id"] == "api_session_01"
    assert "Bảng Đối chiếu Định lượng Bằng chứng CV vs. Chuẩn JD" in report_data["markdown_summary"]

    # 4. Verify 100% direct interoperability with Module 3 (adaptive_questioning)
    import sys
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from adaptive_questioning.schemas.skill_gap_input import SkillGapInput
    from adaptive_questioning.core.router import initialize_session_state

    m3_inputs = [SkillGapInput.model_validate(item) for item in data["skills"]]
    session_state = initialize_session_state(skills_input=m3_inputs, session_id="m2_to_m3_test")
    assert session_state.total_initial_d == data["skills_requiring_probing"]
    assert session_state.active_skill_id is not None


def test_three_llm_optimizations_fastpath_batch_and_schema():
    """
    Verifies the 3 LLM efficiency & schema optimizations:
    1. `SpanRichness.model_json_schema()` strips dead `modifier_score` from LLM prompts,
       and `GapDetector(config=...)` requires no `llm_client`.
    2. `ResumeSegmenter.segment()` skips Step 1b LLM call (`call_count == 1`) when all
       evidence spans are verbatim substrings of extracted `JobBlock.raw_text`.
    3. `ProficiencyEstimator.estimate_batch()` deduplicates shared spans across N skills
       into a single LLM call (`call_count == 1` instead of N).
    """
    from src.services.gap_detector import GapDetector
    from src.services.proficiency_estimator import ProficiencyEstimator
    from src.services.resume_segmenter import ResumeSegmenter

    # Optimization 1: Schema strips dead modifier_score & GapDetector needs no llm_client
    richness_schema = SpanRichness.model_json_schema()
    assert "modifier_score" not in richness_schema.get("properties", {})
    detector = GapDetector(config=AppConfig())
    assert detector.llm_client is None

    # Optimization 2: Deterministic Substring Fast-Path in ResumeSegmenter (0 LLM calls for Step 1b)
    class CountingSegmenterLLM(LLMClient):
        def __init__(self):
            self.calls = []

        def complete(self, prompt: str, schema):
            self.calls.append(schema.__name__)
            if schema.__name__ == "JobBlockExtraction":
                return JobBlockExtraction(
                    job_blocks=[
                        JobBlock(
                            job_id="job_1",
                            title="Senior Backend Engineer",
                            seniority_level=SeniorityLevel.SENIOR,
                            start_date="2021-01",
                            end_date="2024-01",
                            raw_quote="Senior Backend Engineer (2021-01 - 2024-01)",
                            raw_text="Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS.",
                        )
                    ]
                )
            raise AssertionError("Step 1b SpanMappingExtraction should NOT be called when spans match raw_text verbatim!")

    seg_llm = CountingSegmenterLLM()
    segmenter = ResumeSegmenter(llm_client=seg_llm)
    shared_span = "Xây dựng hệ thống thanh toán bằng Python FastAPI và PostgreSQL chịu tải 5,000 TPS."
    skills_sharing_span = [
        ExtractedCVSkill(skill_id="python", type=SkillType.EXPLICIT, confidence=0.98, evidence_spans=[shared_span]),
        ExtractedCVSkill(skill_id="fastapi", type=SkillType.EXPLICIT, confidence=0.95, evidence_spans=[shared_span]),
        ExtractedCVSkill(skill_id="postgresql", type=SkillType.EXPLICIT, confidence=0.92, evidence_spans=[shared_span]),
    ]
    seg_out = segmenter.segment(
        cv_text=f"Senior Backend Engineer (2021-01 - 2024-01)\n{shared_span}",
        cv_skills=skills_sharing_span,
    )
    assert seg_llm.calls == ["JobBlockExtraction"]
    assert len(seg_out.span_mappings) == 1
    assert seg_out.span_mappings[0].job_id == "job_1"

    # Optimization 3: Cross-skill deduplication & single-call batch estimation in ProficiencyEstimator
    class CountingEstimatorLLM(LLMClient):
        def __init__(self):
            self.call_count = 0

        def complete(self, prompt: str, schema):
            self.call_count += 1
            return SpanAnalysisList(
                analyses=[SpanRichness(span=shared_span, richness_label=RichnessLabel.RICH_CONTEXT)]
            )

    est_llm = CountingEstimatorLLM()
    estimator = ProficiencyEstimator(llm_client=est_llm, config=AppConfig(reference_date="2024-06-01"))
    prof_results = estimator.estimate_batch(
        skills=skills_sharing_span,
        mappings=seg_out.span_mappings,
        job_blocks=seg_out.job_blocks,
    )
    # 3 skills sharing the same span -> ONLY 1 LLM call total!
    assert est_llm.call_count == 1
    assert len(prof_results) == 3
    assert all(r.c_evidence == 1.0 for r in prof_results)


def test_six_pipeline_optimizations_end_to_end():
    """
    Verifies all 6 deep pipeline optimizations:
    1. `MISSING` skills (`soft_match < floor_threshold`) do NOT leak rejected SBERT top-1
       `matched_cv_skill_id`, `candidate_proficiency` (reset to 1.0), `cv_evidence_spans`, or `context_job`.
    2. `AMBIGUOUS` spans receive the configured 0.5 context density multiplier (between 1.0 and 0.3).
    3. Target-Driven Active-Skill Pruning skips unreferenced CV skills and rejected MISSING CV skills.
    4. Upstream `degraded` and `flags` from Step 1 / Step 2 propagate into `SkillGapResult`.
    5. Diagnostic flags (`recency_decay_warning`, `low_evidence_density`) surface in `SkillGapResult.flags`.
    6. `date_parser.merge_date_intervals` uses inclusive calendar-month set union matching `ProficiencyEstimator`.
    """
    import datetime
    from src.domain.models import ProficiencyResult
    from src.services.date_parser import merge_date_intervals
    from src.services.gap_detector import GapDetector
    from src.services.proficiency_estimator import ProficiencyEstimator

    config = AppConfig(reference_date="2024-06-01")

    # 1. Verify MISSING skill isolation & diagnostic flags in GapDetector
    detector = GapDetector(config=config)
    reqs = [
        JDRequirement(jd_skill_id="aws", required_level=4.0, reasoning="Senior AWS"),
        JDRequirement(jd_skill_id="linux", required_level=2.0, reasoning="Basic Linux"),
    ]
    profs = [
        # Candidate has 5.0 in Java, which SBERT falsely paired with AWS at soft_match=0.12
        ProficiencyResult(skill_id="java", proficiency=5.0, c_evidence=1.0, effective_months=60.0),
        # Candidate has stale keyword-only Linux from >3 years ago
        ProficiencyResult(
            skill_id="linux",
            proficiency=2.5,
            c_evidence=0.0,
            effective_months=12.0,
            recency_flag=True,
        ),
    ]
    matches = [
        MatchResult(jd_skill_id="aws", w_j=0.5, matched_cv_skill_id="java", soft_match=0.12),
        MatchResult(jd_skill_id="linux", w_j=0.5, matched_cv_skill_id="linux", soft_match=1.0),
    ]
    cv_skills = [
        ExtractedCVSkill(skill_id="java", type=SkillType.EXPLICIT, confidence=0.99, evidence_spans=["5 years Java"]),
        ExtractedCVSkill(skill_id="linux", type=SkillType.EXPLICIT, confidence=0.85, evidence_spans=["Skills: Linux"]),
    ]

    gaps = detector.detect(
        requirements=reqs,
        proficiencies=profs,
        matches=matches,
        cv_skills=cv_skills,
        upstream_degraded=True,
        upstream_flags=["jd_parser:fallback_warning"],
    )
    aws_gap = next(g for g in gaps if g.jd_skill_id == "aws")
    linux_gap = next(g for g in gaps if g.jd_skill_id == "linux")

    # Optimization 1: AWS is MISSING -> must NOT inherit Java's 5.0 proficiency or spans!
    assert aws_gap.semantic_alignment == SemanticAlignment.MISSING
    assert aws_gap.matched_cv_skill_id is None
    assert aws_gap.candidate_proficiency == 1.0
    assert aws_gap.cv_evidence_spans == []
    assert aws_gap.context_job is None

    # Optimization 4 & 5: Upstream flags + recency_decay_warning & low_evidence_density
    assert aws_gap.degraded is True
    assert "jd_parser:fallback_warning" in aws_gap.flags
    assert "recency_decay_warning" in linux_gap.flags
    assert "low_evidence_density" in linux_gap.flags

    # 2. Verify 3-Tier Context Density Multiplier (RICH=1.0 > AMBIGUOUS=0.5 > LIST_ONLY=0.3)
    job = JobBlock(
        job_id="j1",
        title="Mid Engineer",
        seniority_level=SeniorityLevel.MID,
        start_date="2023-01",
        end_date="2023-12",
        raw_text="Worked on Linux",
    )
    sk_amb = ExtractedCVSkill(skill_id="linux_amb", type=SkillType.EXPLICIT, confidence=0.8, evidence_spans=["Amb span"])
    sk_lst = ExtractedCVSkill(skill_id="linux_lst", type=SkillType.EXPLICIT, confidence=0.8, evidence_spans=["Lst span"])

    class AmbiguousVsListLLM(LLMClient):
        def complete(self, prompt: str, schema):
            return SpanAnalysisList(
                analyses=[
                    SpanRichness(span="Amb span", richness_label=RichnessLabel.AMBIGUOUS),
                    SpanRichness(span="Lst span", richness_label=RichnessLabel.LIST_ONLY),
                ]
            )

    est = ProficiencyEstimator(llm_client=AmbiguousVsListLLM(), config=config)
    res_amb = est.estimate(sk_amb, [SpanMapping(span="Amb span", job_id="j1")], [job])
    res_lst = est.estimate(sk_lst, [SpanMapping(span="Lst span", job_id="j1")], [job])
    # 12 months * 0.5 = 6.0m vs 12 months * 0.3 = 3.6m
    assert res_amb.effective_months == pytest.approx(6.0, abs=1e-6)
    assert res_lst.effective_months == pytest.approx(3.6, abs=1e-6)
    assert res_amb.proficiency > res_lst.proficiency

    # 6. Verify merge_date_intervals inclusive month union (18.0 distinct months for 2022-01..2022-12 U 2022-06..2023-06)
    intervals = [
        (datetime.date(2022, 1, 1), datetime.date(2022, 12, 1)),
        (datetime.date(2022, 6, 1), datetime.date(2023, 6, 1)),
    ]
    assert merge_date_intervals(intervals) == 18.0

    # 7. Verify Lightweight Year-Grounding & Natural Date Support in ResumeSegmenter
    jb_schema = JobBlock.model_json_schema()
    for legacy_field in ("raw_start_date", "raw_end_date", "raw_quote"):
        assert legacy_field not in jb_schema.get("properties", {})

    from src.services.resume_segmenter import ResumeSegmenter

    class NaturalDateLLM(LLMClient):
        def complete(self, prompt, schema):
            return JobBlockExtraction(
                job_blocks=[
                    JobBlock(
                        job_id="job_1",
                        title="Cloud Engineer",
                        seniority_level=SeniorityLevel.MID,
                        start_date="2020-03",
                        end_date="2022-09",
                        raw_text="Triển khai AWS.",
                    )
                ]
            )

    seg_clean = ResumeSegmenter(llm_client=NaturalDateLLM(), config=config).segment(
        cv_text="Làm việc từ Quý 1 năm 2020 đến Mùa thu năm 2022: Triển khai AWS.",
        cv_skills=[],
    )
    assert seg_clean.degraded is False
    assert seg_clean.flags == []

    class HallucinatedYearLLM(LLMClient):
        def complete(self, prompt, schema):
            return JobBlockExtraction(
                job_blocks=[
                    JobBlock(
                        job_id="job_1",
                        title="Cloud Engineer",
                        seniority_level=SeniorityLevel.MID,
                        start_date="2015-03",  # Year 2015 does NOT exist in cv_text!
                        end_date="2022-09",
                        raw_text="Triển khai AWS.",
                    )
                ]
            )

    seg_hallucinated = ResumeSegmenter(llm_client=HallucinatedYearLLM(), config=config).segment(
        cv_text="Làm việc từ Quý 1 năm 2020 đến Mùa thu năm 2022: Triển khai AWS.",
        cv_skills=[],
    )
    assert seg_hallucinated.degraded is True
    assert any("hallucinated_year:2015_not_in_cv" in fl for fl in seg_hallucinated.flags)
