from typing import List, Optional
from uuid import NAMESPACE_URL, uuid5
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
Extract concrete tasks with verbatim JD quotes into tasks. Optional/required describes importance, never proficiency. Prefer explicit task complexity over years; use seniority only as fallback. Do not invent tasks when the JD only names a skill.
Your responsibility is to evaluate the DEPTH OF MASTERY (how proficient the candidate needs to be in this specific skill).

Standardized Proficiency Scale (1.0 - 5.0):
- 1.0 - 1.5: Basic Awareness / Familiarity ("có hiểu biết", "biết cơ bản", entry/intern level, 0-6 months)
- 2.0 - 2.5: Junior / Working Knowledge ("có kiến thức", 6-18 months experience, can execute standard tasks with guidance)
- 3.0 - 3.5: Mid-level / Solid Practical Experience ("nắm vững", "thành thạo", "solid experience", 18-36 months, independent)
- 4.0 - 4.5: Senior / Advanced Expertise ("chuyên sâu", "deep knowledge", "expert", 3-5+ years, system optimization, complex troubleshooting)
- 5.0: Lead / Master / Principal ("architectural experience", > 5 years, design, strategic leadership)

Hierarchical Inference Priority Rules:
1. Explicit Task Complexity and Proficiency: Use observable responsibilities, autonomy and explicit expectations first.
2. Skill-specific Years: Use experience only if task/depth evidence is absent; mark the level INFERRED.
3. Role Seniority: Last fallback only. Optional/required and core/secondary status do not determine proficiency.

JD Text:
{jd_text}

Skills to analyze:
{skills_context}

Return the required proficiency level and a concise reasoning for ALL provided Skill IDs exactly as requested in the schema.
"""
        try:
            output = self.llm_client.complete(prompt, JDParserOutput)
            return self._validate_tasks(output, jd_text, jd_skills)
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


    @staticmethod
    def _validate_tasks(output, jd_text, jd_skills):
        expected = {skill.skill_id: skill for skill in jd_skills}
        if {req.jd_skill_id for req in output.requirements} != set(expected):
            raise ValueError("JD parser must cover every requested skill exactly once")
        if len(output.requirements) != len(expected):
            raise ValueError("Duplicate JD skill requirements")
        for req in output.requirements:
            for task in req.tasks:
                if not task.description.strip() or not task.evidence_spans or any(not span.strip() or span not in jd_text for span in task.evidence_spans):
                    raise ValueError("Task evidence must be grounded in the JD")
                key = f"{req.jd_skill_id}:{task.description}:{task.evidence_spans}"
                task.task_id = str(uuid5(NAMESPACE_URL, key))
        return output
