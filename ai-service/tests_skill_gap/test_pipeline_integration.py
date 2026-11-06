"""
test_pipeline_integration.py — Kiểm tra orchestrator chạy đúng end-to-end.

Mock data Module 1 được định nghĩa trực tiếp trong file này (không dùng fixture file)
vì module 1 thực sẽ thay thế khi tích hợp thật.
"""
import pytest
from src.domain.enums import SemanticAlignment, SeniorityLevel, RichnessLabel
from src.domain.models import (
    JDRequirement, JDParserOutput, JobBlock, SpanMapping, SpanRichness,
    ExtractedCVSkill, ExtractedJDSkill, MatchResult,
)
from src.adapters.config import AppConfig
from src.pipeline.orchestrator import SkillGapOrchestrator
from src.services.resume_segmenter import JobBlockExtraction, SpanMappingExtraction
from src.services.proficiency_estimator import SpanAnalysisList

# ---------------------------------------------------------------------------
# Mock Module 1 output (inline — phản ánh format thực của SBERT + GNN output)
# Khi Module 1 thực được tích hợp, những giá trị này sẽ đến từ pipeline thật.
# ---------------------------------------------------------------------------

MOCK_CV_SKILLS = [
    {
        "skill_id": "kafka",
        "type": "implicit",
        "confidence": 0.85,
        "evidence_spans": [
            "Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày",
            "Kỹ năng: Kafka, RabbitMQ, Redis",
        ],
    },
    {
        "skill_id": "java",
        "type": "explicit",
        "confidence": 0.90,
        "evidence_spans": [
            "Lập trình backend bằng Java Spring Boot trong 2 năm",
            "Proficient in Java Core",
        ],
    },
    {
        "skill_id": "react",
        "type": "explicit",
        "confidence": 0.70,
        "evidence_spans": ["React, Vue, Angular"],
    },
]

MOCK_JD_SKILLS = [
    {
        "skill_id": "rabbitmq",
        "type": "explicit",
        "confidence": 0.95,
        "evidence_spans": ["3+ years of experience with RabbitMQ or similar message queue systems is required"],
    },
    {
        "skill_id": "java",
        "type": "explicit",
        "confidence": 0.99,
        "evidence_spans": ["Mạnh về Java, có khả năng tối ưu hóa performance"],
    },
    {
        "skill_id": "aws",
        "type": "explicit",
        "confidence": 0.88,
        "evidence_spans": ["Kinh nghiệm deploy trên AWS là một điểm cộng lớn"],
    },
]

MOCK_MATCH_RESULTS = [
    # rabbitmq ← kafka: PARTIAL (soft_match trong PARTIAL zone)
    {"jd_skill_id": "rabbitmq", "w_j": 0.25, "matched_cv_skill_id": "kafka",  "soft_match": 0.78},
    # java ← java: MATCH (exact)
    {"jd_skill_id": "java",     "w_j": 0.40, "matched_cv_skill_id": "java",   "soft_match": 1.0},
    # aws ← react: MISSING (soft_match below floor)
    {"jd_skill_id": "aws",      "w_j": 0.15, "matched_cv_skill_id": "react",  "soft_match": 0.1},
]


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockIntegrationLLM:
    def complete(self, prompt: str, schema):
        name = schema.__name__
        if name == "JobBlockExtraction":
            return JobBlockExtraction(job_blocks=[
                JobBlock(
                    job_id="job_1", title="Dev", seniority_level=SeniorityLevel.MID,
                    start_date="2020-01", end_date="2023-01", raw_text="did things",
                )
            ])
        elif name == "SpanMappingExtraction":
            return SpanMappingExtraction(span_mappings=[
                SpanMapping(span="Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày", job_id="job_1"),
                SpanMapping(span="Lập trình backend bằng Java Spring Boot trong 2 năm",              job_id="job_1"),
            ])
        elif name == "JDParserOutput":
            return JDParserOutput(requirements=[
                JDRequirement(jd_skill_id="rabbitmq", required_level=4.0, reasoning=""),
                JDRequirement(jd_skill_id="java",     required_level=3.0, reasoning=""),
                JDRequirement(jd_skill_id="aws",      required_level=2.0, reasoning=""),
            ])
        elif name == "SpanAnalysisList":
            return SpanAnalysisList(analyses=[
                SpanRichness(span="Xây dựng hệ thống message queue với Kafka phục vụ 1M event/ngày",
                             richness_label=RichnessLabel.RICH_CONTEXT, modifier_score=4.0),
                SpanRichness(span="Lập trình backend bằng Java Spring Boot trong 2 năm",
                             richness_label=RichnessLabel.RICH_CONTEXT, modifier_score=3.0),
            ])
        raise ValueError(f"Unknown schema: {name}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pipeline_integration():
    config = AppConfig()
    llm    = MockIntegrationLLM()
    orchestrator = SkillGapOrchestrator(llm_client=llm, config=config)

    cv_skills    = [ExtractedCVSkill(**s) for s in MOCK_CV_SKILLS]
    jd_skills    = [ExtractedJDSkill(**s) for s in MOCK_JD_SKILLS]
    match_results = [MatchResult(**m)     for m in MOCK_MATCH_RESULTS]

    results = orchestrator.run_pipeline(
        cv_text="mock cv",
        jd_text="mock jd",
        cv_skills=cv_skills,
        jd_skills=jd_skills,
        match_results=match_results,
    )

    assert len(results) == 3
    assert all(hasattr(r, "semantic_alignment") for r in results)
    assert any(r.jd_skill_id == "rabbitmq" for r in results)
    assert any(r.jd_skill_id == "java"     for r in results)
    assert any(r.jd_skill_id == "aws"      for r in results)

    # rabbitmq: soft_match=0.78 → PARTIAL zone [0.40, 0.85)
    rabbitmq_result = next(r for r in results if r.jd_skill_id == "rabbitmq")
    assert rabbitmq_result.semantic_alignment == SemanticAlignment.PARTIAL
    assert rabbitmq_result.is_substituted is True

    # java: soft_match=1.0 → MATCH
    java_result = next(r for r in results if r.jd_skill_id == "java")
    assert java_result.semantic_alignment == SemanticAlignment.MATCH

    # aws: soft_match=0.1 → MISSING
    aws_result = next(r for r in results if r.jd_skill_id == "aws")
    assert aws_result.semantic_alignment == SemanticAlignment.MISSING
