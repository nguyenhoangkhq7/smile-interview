"""
Declarative DSPy Signatures for Module 2 (Skill-Gap Detection).
Covers the 3 genuine LLM tasks while preserving 100% deterministic math in GapDetector:
  1a. JobBlockExtractionSignature (ResumeSegmenter Step 1)
  1b. SpanMappingSignature (ResumeSegmenter Step 2)
  2.  JDRequirementSignature (JDRequirementParser)
  3.  SpanRichnessSignature (ProficiencyEstimator._analyze_span_richness)
"""

from typing import List
import dspy
from src.domain.models import JobBlock, SpanMapping, JDRequirement, SpanRichness


class JobBlockExtractionSignature(dspy.Signature):
    """
    You are an expert technical recruiter. Analyze the CV text and extract all actual work experience blocks into structured JobBlock items.

    Strict Extraction & Grounding Rules:
    1. Work Experience Only: Extract only real employment, internships, contract/freelance roles, or production work blocks. Do NOT extract university education, academic coursework, certifications, or standalone 'Skills / Kỹ năng' sections as JobBlocks (if the CV has no work experience, return an empty list []).
    2. Role Promotion Splitting: If a candidate held multiple distinct roles/titles with separate date ranges at the same company, extract each role as a separate JobBlock with a unique sequential job_id ('job_1', 'job_2', ...).
    3. ISO Date Normalization & Anti-Hallucination Year Grounding:
       - `start_date`: Convert the start date in the CV to ISO 'YYYY-MM' (if only a 4-digit year like '2019' is given, use '2019-01'). Never invent a year that does not appear in `cv_text`.
       - `end_date`: Convert the end date in the CV to ISO 'YYYY-MM'. If the job is ongoing ('Hiện tại', 'nay', 'present', 'current', 'now'), set `end_date` to null (None).
    4. Seniority Autonomy Calibration:
       - Classify `seniority_level` into one of: 'Intern', 'Junior', 'Mid', 'Senior', 'Lead', 'Unknown'.
       - Supervised roles ('Intern', 'Junior') represent guided/assisted execution; autonomous roles ('Mid', 'Senior', 'Lead') represent independent delivery, production ownership, or technical leadership.
    5. Verbatim Job Text (`raw_text`): Copy the responsibility sentences belonging to this job block from `cv_text`.
    """

    cv_text: str = dspy.InputField(
        desc="Raw resume / CV text (Vietnamese, English, or bilingual) to segment into discrete work experience JobBlocks"
    )
    job_blocks: List[JobBlock] = dspy.OutputField(
        desc="List of extracted JobBlock objects with unique job_id, title, seniority_level, ISO YYYY-MM start_date/end_date, and raw_text"
    )


class SpanMappingSignature(dspy.Signature):
    """
    Map each extracted skill evidence span from the CV to the exact `job_id` where that skill was practiced.

    Strict Attribution Rules:
    1. Complete Verbatim Coverage: Every single evidence span listed in `spans_context` MUST be returned in `span_mappings` with its `span` string preserved character-for-character (do not include the leading bullet prefix '- ').
    2. Job-Contextual Attribution: Assign a span to a `job_id` (e.g., 'job_1', 'job_2') ONLY if the span comes from that specific job block's responsibilities, achievements, or job-specific tech stack.
    3. UNASSIGNED Boundary Rule: If an evidence span comes from a general 'Skills / Kỹ năng khác' section, CV summary header, certifications list, or academic project not belonging to any extracted JobBlock in `jobs_context`, you MUST assign `job_id = 'UNASSIGNED'`. Never guess or force-map a general skill list into a work JobBlock.
    """

    jobs_context: str = dspy.InputField(
        desc="Formatted list of extracted JobBlocks with [job_id], title, ISO dates, and raw_text (or empty if no JobBlocks exist)"
    )
    spans_context: str = dspy.InputField(
        desc="Bulleted list of verbatim skill evidence spans extracted from the CV that must all be mapped"
    )
    span_mappings: List[SpanMapping] = dspy.OutputField(
        desc="List of SpanMapping items pairing every input span verbatim with its owning job_id or 'UNASSIGNED'"
    )


class JDRequirementSignature(dspy.Signature):
    """
    Determine the REQUIRED PROFICIENCY LEVEL (`required_level` P_JD on a standardized 1.0 to 5.0 scale) for each specified JD skill.

    Note on Scope:
    Skill importance weight (`w_j`) is computed externally by a Graph Neural Network (GNN). Your SOLE responsibility is to calibrate the required DEPTH OF MASTERY (`required_level` in [1.0, 5.0]) for each target skill ID.

    Standardized Proficiency Scale (1.0 - 5.0):
    - 1.0 - 1.5: Basic Awareness / Familiarity ('có hiểu biết', 'biết cơ bản', 'exposure to', entry/intern level, 0-6 months equivalent)
    - 2.0 - 2.5: Junior / Working Knowledge ('có kiến thức', 'nice-to-have / là một lợi thế / điểm cộng', 6-18 months equivalent, executes standard tasks with guidance)
    - 3.0 - 3.5: Mid-level / Solid Practical Experience ('nắm vững', 'thành thạo', 'solid / proficient experience', 18-36 months / 2-3 years equivalent, independent execution)
    - 4.0 - 4.5: Senior / Advanced Expertise ('chuyên sâu', 'deep knowledge', 'expert', 'tối ưu hóa hiệu năng / production scale', 3-5+ years equivalent, complex troubleshooting)
    - 5.0: Lead / Master / Principal ('architectural mastery', 'thiết kế kiến trúc tổng thể', >5 years equivalent, technical strategy & leadership)

    Hierarchical Inference Priority Rules (Apply in strict order 1 -> 2 -> 3):
    1. Explicit Years of Experience (Highest Priority): If the evidence span or JD explicitly states required years for the skill (e.g., '<1 year' -> 1.5-2.0, '1-2 years' -> 2.5, '2-3 years' -> 3.0-3.5, '3-4+ years' -> 4.0, '5+ years' -> 4.5-5.0), map directly to the corresponding milestone.
    2. Explicit Proficiency Descriptors (Second Priority): If no exact years are given for the skill, map explicit depth modifiers ('điểm cộng / plus / familiar' -> 2.0, 'có kinh nghiệm / working knowledge' -> 2.5-3.0, 'thành thạo / nắm vững / solid' -> 3.5, 'chuyên sâu / mạnh về / tối ưu hóa / expert' -> 4.0-4.5).
    3. Role Seniority Inheritance (Fallback Priority): If the skill has neither explicit years nor depth modifiers, infer its required depth from the overall JD role seniority and whether the skill is core/must-have vs. secondary.
    """

    jd_text: str = dspy.InputField(
        desc="Full Job Description (JD) text providing overall role seniority and context"
    )
    skills_context: str = dspy.InputField(
        desc="Target JD skill IDs and their verbatim extracted evidence spans from the JD"
    )
    requirements: List[JDRequirement] = dspy.OutputField(
        desc="List of JDRequirement objects covering every target jd_skill_id, with required_level in [1.0, 5.0] and concise rule-grounded reasoning"
    )


class SpanRichnessSignature(dspy.Signature):
    """
    Analyze each CV evidence span for a given candidate skill (or batch of skills) and classify its contextual richness into `RICH_CONTEXT`, `LIST_ONLY`, or `AMBIGUOUS`.

    Strict Classification Rubric:
    1. RICH_CONTEXT:
       - The span describes concrete project application, real engineering tasks, architectural actions, production scale/metrics, or specific problem-solving using the skill (e.g., 'Thiết kế và vận hành hạ tầng Kubernetes cho 50+ microservices', 'Xây dựng hệ thống event streaming với Kafka 2 năm').
    2. LIST_ONLY:
       - The span is merely a keyword list (e.g., 'Kỹ năng: Docker, Kubernetes, Helm', 'React, Vue, Angular') OR a generic, ungrounded self-claim without any project/task action (e.g., 'Proficient in Java Core', 'Thành thạo Python').
    3. AMBIGUOUS:
       - The span mentions the skill in a vague, passive, or peripheral support statement where real hands-on project depth is unclear (e.g., 'Tham gia hỗ trợ môi trường Linux cơ bản', 'Làm quen với quy trình CI/CD của team').
    4. Verbatim Span Preservation:
       - Return an entry in `analyses` for EVERY input span in `spans_text`, copying the `span` text verbatim without the leading '- ' bullet.
    """

    skill_id: str = dspy.InputField(
        desc="Identifier of the candidate skill(s) being evaluated (e.g., 'kubernetes', 'kafka, java')"
    )
    spans_text: str = dspy.InputField(
        desc="Bulleted list of verbatim CV evidence spans to classify"
    )
    analyses: List[SpanRichness] = dspy.OutputField(
        desc="List of SpanRichness objects for each input span with richness_label (RICH_CONTEXT, LIST_ONLY, AMBIGUOUS)"
    )
