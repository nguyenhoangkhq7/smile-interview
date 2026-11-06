import pytest
from src.domain.enums import SeniorityLevel, SkillType
from src.domain.models import JobBlock, SpanMapping, ExtractedCVSkill, UNASSIGNED_JOB_ID
from src.services.resume_segmenter import ResumeSegmenter, JobBlockExtraction, SpanMappingExtraction

class MockLLMClient:
    def __init__(self, expected_job_blocks, expected_span_mappings):
        self.expected_job_blocks = expected_job_blocks
        self.expected_span_mappings = expected_span_mappings
        self.call_count = 0
        
    def complete(self, prompt: str, schema):
        self.call_count += 1
        if schema.__name__ == "JobBlockExtraction":
            return JobBlockExtraction(job_blocks=self.expected_job_blocks)
        elif schema.__name__ == "SpanMappingExtraction":
            return SpanMappingExtraction(span_mappings=self.expected_span_mappings)
        raise ValueError("Unexpected schema requested")

def test_resume_segmenter():
    # Setup mock data
    mock_jobs = [
        JobBlock(
            job_id="job_1", 
            title="Backend Developer", 
            seniority_level=SeniorityLevel.MID,
            start_date="2020-01", 
            end_date="2022-12",
            raw_text="Worked on Kafka."
        )
    ]
    
    mock_mappings = [
        SpanMapping(span="Worked on Kafka.", job_id="job_1"),
        SpanMapping(span="Skills: Java, Kafka", job_id=UNASSIGNED_JOB_ID)
    ]
    
    mock_llm = MockLLMClient(expected_job_blocks=mock_jobs, expected_span_mappings=mock_mappings)
    
    segmenter = ResumeSegmenter(llm_client=mock_llm)
    
    cv_skills = [
        ExtractedCVSkill(
            skill_id="kafka",
            type=SkillType.EXPLICIT,
            confidence=1.0,
            evidence_spans=["Worked on Kafka.", "Skills: Java, Kafka"]
        )
    ]
    
    output = segmenter.segment(cv_text="Dummy CV text", cv_skills=cv_skills)
    
    # Assertions
    assert mock_llm.call_count == 2
    assert len(output.job_blocks) == 1
    assert output.job_blocks[0].job_id == "job_1"
    
    assert len(output.span_mappings) == 2
    
    unassigned_spans = [m for m in output.span_mappings if m.job_id == UNASSIGNED_JOB_ID]
    assert len(unassigned_spans) == 1
    assert unassigned_spans[0].span == "Skills: Java, Kafka"
