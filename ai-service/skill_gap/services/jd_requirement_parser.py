from typing import List, Optional
from skill_gap.domain.models import ExtractedJDSkill, JDRequirement, JDParserOutput
from skill_gap.adapters.config import AppConfig
from skill_gap.adapters.llm_client import LLMClient

class JDRequirementParser:
    """
    Service responsible for parsing JD requirements for specific extracted skills.
    Determines the Required Proficiency Level (P_JD on a 1.0 to 5.0 standardized scale)
    matching the Candidate Proficiency scale from Step C.
    """
    def __init__(self, llm_client: LLMClient, config: Optional[AppConfig] = None):
        self.llm_client = llm_client
        self.config = config or AppConfig()
        
    def parse(self, jd_text: str, jd_skills: List[ExtractedJDSkill]) -> JDParserOutput:
        """
        Parses JD text and skill evidence spans to determine required proficiency levels.
        """
        if not jd_skills:
            return JDParserOutput(requirements=[])
            
        skills_context = ""
        for skill in jd_skills:
            spans_str = "\n".join([f"  - {span}" for span in skill.evidence_spans])
            skills_context += f"Skill ID: {skill.skill_id}\nEvidence Spans:\n{spans_str}\n\n"
            
        prompt = f"""
You are an expert technical recruiter analyzing a Job Description (JD).
Your task is to determine the REQUIRED PROFICIENCY LEVEL (P_JD on a standardized 1.0 to 5.0 scale) for each specified skill.

NOTE ON SCOPE:
Skill importance (how critical the skill is to the role, w_j) is handled externally by a Graph Neural Network (GNN).
Your SOLE responsibility is to evaluate the DEPTH OF MASTERY (how proficient the candidate needs to be in this specific skill).

Standardized Proficiency Scale (1.0 - 5.0):
- 1.0 - 1.5: Basic Awareness / Familiarity ("có hiểu biết", "biết cơ bản", entry/intern level, 0-6 months)
- 2.0 - 2.5: Junior / Working Knowledge ("có kiến thức", 6-18 months experience, can execute standard tasks with guidance)
- 3.0 - 3.5: Mid-level / Solid Practical Experience ("nắm vững", "thành thạo", "solid experience", 18-36 months, independent)
- 4.0 - 4.5: Senior / Advanced Expertise ("chuyên sâu", "deep knowledge", "expert", 3-5+ years, system optimization, complex troubleshooting)
- 5.0: Lead / Master / Principal ("architectural experience", > 5 years, design, strategic leadership)

Hierarchical Inference Priority Rules:
1. Explicit Years of Experience: If an evidence span or the JD specifies required years (e.g. "3+ years with Kubernetes"), map directly to the scale (3 years -> 4.0).
2. Explicit Proficiency Descriptors: Look for depth modifiers in the evidence spans (e.g. "thành thạo / expert" -> 4.0, "có kinh nghiệm / solid" -> 3.0, "có hiểu biết / familiar" -> 2.0).
3. Role Seniority Inheritance: If a skill has neither years nor explicit modifiers, infer its required depth from the overall seniority of the role (e.g. A "DevOps Lead" role requires higher depth in primary skills than a "Junior DevOps" role).

JD Text:
{jd_text}

Skills to analyze:
{skills_context}

Return the required proficiency level and a concise reasoning for ALL provided Skill IDs exactly as requested in the schema.
"""
        try:
            return self.llm_client.complete(prompt, JDParserOutput)
        except Exception as e:
            # Graceful degradation on LLM failure
            fallback_reqs = [
                JDRequirement(
                    jd_skill_id=s.skill_id,
                    required_level=3.0,
                    reasoning=f"Graceful fallback due to LLM error: {str(e)}"
                )
                for s in jd_skills
            ]
            return JDParserOutput(
                requirements=fallback_reqs,
                degraded=True,
                flags=[f"llm_jd_parser_failed:{str(e)}"]
            )

