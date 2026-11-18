"""Declarative DSPy signatures for CV/JD explicit skill extraction."""

import dspy

from matching_cv.dspy_modules.schemas import ExplicitSkillMentionList


class ExplicitSkillExtractionSignature(dspy.Signature):
    """Extract only explicit, job-relevant competencies from a CV or JD.

    The document may be in English or Vietnamese, and all rules apply to
    semantic meaning, not exact strings.

    What to extract:
    - Extract only named technologies, tools, programming languages, frameworks,
      standards, named techniques, named certifications, and domains explicitly
      required or demonstrated as a competency.
    - Every returned mention and source_sentence must be copied verbatim from
      document_text. Return an empty list when no qualifying competencies exist.
      Do not combine independent skills into a single mention. Preserve each
      distinct source occurrence with its own evidence sentence.

    What NEVER to extract as skills:
    - Never extract degrees or majors (e.g. "Electrical Engineering", "Điện tử viễn thông"),
      industry labels (e.g. "Telecommunications", "Viễn thông"), years of experience
      (e.g. "5 years", "2 năm kinh nghiệm"), "professional experience" /
      "kinh nghiệm làm việc", generic words ("certification" / "chứng chỉ" alone
      without a proper certification name, "production environment",
      "production services", "production issues"), people or roles
      ("project stakeholders", "executive leadership"), company or product context, or
      generic duties ("daily standup meetings", "writing technical documentation") unless the
      document names a specific technique or tool.
    - Do NOT return kind="context" (accepted in schema only for backward
      compatibility). Omit non-skill strings entirely; if such a string must be
      emitted, label it with the matching non-skill kind ("education",
      "industry", "experience_years", "job_title", or "domain").

    Positive examples:
    1. [EN] "Built real-time user interfaces with React and TypeScript, managing application state via Redux Toolkit."
       -> [{"mention": "React", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Built real-time user interfaces with React and TypeScript, managing application state via Redux Toolkit."},
           {"mention": "TypeScript", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Built real-time user interfaces with React and TypeScript, managing application state via Redux Toolkit."},
           {"mention": "Redux Toolkit", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Built real-time user interfaces with React and TypeScript, managing application state via Redux Toolkit."}]
    2. [EN] "Holds a Certified Information Systems Security Professional credential and performs automated vulnerability scanning."
       -> [{"mention": "Certified Information Systems Security Professional", "kind": "certification", "category": "Certification", "source_sentence": "Holds a Certified Information Systems Security Professional credential and performs automated vulnerability scanning."},
           {"mention": "automated vulnerability scanning", "kind": "skill", "category": "Engineering Practice", "source_sentence": "Holds a Certified Information Systems Security Professional credential and performs automated vulnerability scanning."}]
    3. [VI] "Phát triển ứng dụng di động đa nền tảng bằng Flutter và tối ưu hóa hiệu năng render UI."
       -> [{"mention": "Flutter", "kind": "skill", "category": "Technology/Tool", "source_sentence": "Phát triển ứng dụng di động đa nền tảng bằng Flutter và tối ưu hóa hiệu năng render UI."},
           {"mention": "tối ưu hóa hiệu năng render UI", "kind": "skill", "category": "Engineering Practice", "source_sentence": "Phát triển ứng dụng di động đa nền tảng bằng Flutter và tối ưu hóa hiệu năng render UI."}]

    Negative examples:
    1. [EN] "Candidate has 5 years of industry experience working alongside project stakeholders and executive leadership."
       -> [] (never extract "5 years", "industry experience", "project stakeholders", or "executive leadership"; if emitted, use non-skill kinds "experience_years" or "job_title").
    2. [EN] "Responsible for daily standup meetings, writing technical documentation, and resolving customer tickets."
       -> [] (never extract generic duties "daily standup meetings", "writing technical documentation", or "resolving customer tickets").
    3. [VI] "Ngành nghề: Viễn thông & Mạng. Yêu cầu bằng Cử nhân ngành Điện tử viễn thông, có 2 năm kinh nghiệm làm việc và có chứng chỉ chuyên môn."
       -> [] (never extract industry label "Viễn thông & Mạng" [kind="industry"], major "Điện tử viễn thông" [kind="education"], "2 năm kinh nghiệm" [kind="experience_years"], or bare "chứng chỉ chuyên môn").
    """

    document_type: str = dspy.InputField(desc="CV or JD")
    document_text: str = dspy.InputField(desc="Full extracted text of one CV or JD")
    explicit_skills: ExplicitSkillMentionList = dspy.OutputField(
        desc="Verbatim skill mentions only; omit academic qualifications and non-skill entities"
    )

