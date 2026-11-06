import pytest
from skill_gap.domain.enums import SkillType, SeniorityLevel, RichnessLabel
from skill_gap.domain.models import ExtractedCVSkill, SpanMapping, JobBlock, SpanRichness, UNASSIGNED_JOB_ID
from skill_gap.adapters.config import AppConfig
from skill_gap.services.proficiency_estimator import ProficiencyEstimator, SpanAnalysisList

class MockLLMClient:
    def __init__(self, expected_output: SpanAnalysisList):
        self.expected_output = expected_output
        
    def complete(self, prompt: str, schema):
        return self.expected_output

def test_proficiency_estimator():
    config = AppConfig(reference_date="2024-06-01")
    
    mock_llm_output = SpanAnalysisList(
        analyses=[
            SpanRichness(
                span="Expert in Kafka",
                richness_label=RichnessLabel.RICH_CONTEXT,
                modifier_score=5.0
            )
        ]
    )
    
    llm = MockLLMClient(mock_llm_output)
    estimator = ProficiencyEstimator(llm_client=llm, config=config)
    
    skill = ExtractedCVSkill(
        skill_id="kafka",
        type=SkillType.EXPLICIT,
        confidence=0.9,
        evidence_spans=["Expert in Kafka"]
    )
    
    # 24 months (2022-01 to 2024-01), Mid level (mult 1.0), Rich context (mult 1.0)
    job_blocks = [
        JobBlock(
            job_id="job_1",
            title="Backend Dev",
            seniority_level=SeniorityLevel.MID,
            start_date="2022-01",
            end_date="2024-01",
            raw_text="Worked on Kafka"
        )
    ]
    
    mappings = [
        SpanMapping(span="Expert in Kafka", job_id="job_1")
    ]
    
    result = estimator.estimate(skill, mappings, job_blocks)
    
    assert result.skill_id == "kafka"
    # 25 inclusive effective months (Jan 2022 to Jan 2024) maps between 18 (3.0) and 36 (4.0):
    # 3.0 + (25 - 18) * (4.0 - 3.0) / 18 = 3.0 + 7/18 = 3.389
    assert result.proficiency == pytest.approx(3.389, 1e-2)
    assert result.c_evidence == 1.0
    assert result.recency_flag is False

def test_proficiency_estimator_unassigned():
    config = AppConfig()
    llm = MockLLMClient(SpanAnalysisList(analyses=[]))
    estimator = ProficiencyEstimator(llm_client=llm, config=config)
    
    skill = ExtractedCVSkill(
        skill_id="docker",
        type=SkillType.EXPLICIT,
        confidence=0.85,
        evidence_spans=["Docker, K8s, Git"]
    )
    
    mappings = [
        SpanMapping(span="Docker, K8s, Git", job_id=UNASSIGNED_JOB_ID)
    ]
    
    result = estimator.estimate(skill, mappings, job_blocks=[])
    
    # Unassigned baseline is 6 months -> Level 2.0 (Working knowledge)
    assert result.proficiency == 2.0
    # No rich context spans -> c_evidence is 0.0
    assert result.c_evidence == 0.0
