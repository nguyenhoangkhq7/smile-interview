import pytest
from src.domain.enums import SkillType
from src.domain.models import ExtractedJDSkill, JDRequirement, JDParserOutput
from src.services.jd_requirement_parser import JDRequirementParser

class MockLLMClient:
    def __init__(self, expected_output: JDParserOutput):
        self.expected_output = expected_output
        self.call_count = 0
        
    def complete(self, prompt: str, schema):
        self.call_count += 1
        if schema.__name__ == "JDParserOutput":
            return self.expected_output
        raise ValueError("Unexpected schema requested")

def test_jd_requirement_parser():
    # Setup mock data
    mock_requirements = [
        JDRequirement(
            jd_skill_id="rabbitmq",
            required_level=4.0,
            reasoning="JD specifies 3+ years which maps to level 4.0"
        ),
        JDRequirement(
            jd_skill_id="aws",
            required_level=2.0,
            reasoning="JD says AWS is a plus, implying lower proficiency required."
        )
    ]
    
    mock_output = JDParserOutput(requirements=mock_requirements)
    mock_llm = MockLLMClient(expected_output=mock_output)
    
    parser = JDRequirementParser(llm_client=mock_llm)
    
    jd_skills = [
        ExtractedJDSkill(
            skill_id="rabbitmq",
            type=SkillType.EXPLICIT,
            confidence=0.95,
            evidence_spans=["3+ years of experience with RabbitMQ is required"]
        ),
        ExtractedJDSkill(
            skill_id="aws",
            type=SkillType.EXPLICIT,
            confidence=0.88,
            evidence_spans=["Experience with AWS is a big plus"]
        )
    ]
    
    result = parser.parse(jd_text="Dummy JD Text", jd_skills=jd_skills)
    
    assert mock_llm.call_count == 1
    assert len(result.requirements) == 2
    
    req1 = result.requirements[0]
    assert req1.jd_skill_id == "rabbitmq"
    assert req1.required_level == 4.0
    
    req2 = result.requirements[1]
    assert req2.jd_skill_id == "aws"
    assert req2.required_level == 2.0
    
def test_jd_requirement_parser_empty():
    mock_llm = MockLLMClient(expected_output=JDParserOutput(requirements=[]))
    parser = JDRequirementParser(llm_client=mock_llm)
    
    result = parser.parse(jd_text="Dummy JD Text", jd_skills=[])
    
    assert mock_llm.call_count == 0
    assert len(result.requirements) == 0
