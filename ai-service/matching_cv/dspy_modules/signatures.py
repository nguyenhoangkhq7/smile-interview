"""Declarative DSPy signatures for CV/JD explicit skill extraction."""

from typing import List

import dspy

from matching_cv.dspy_modules.schemas import ExplicitSkillMention


class ExplicitSkillExtractionSignature(dspy.Signature):
    """Extract only explicit, job-relevant competencies from a CV or JD.

    Include only concrete skills, tools, techniques, standards, certifications,
    or genuinely required/used domain competencies. Do not extract education
    qualifications, degree names, majors, academic fields, coursework, job
    titles, employer industries, company/product names, generic duties, or
    performance results as skills. For example, "Computer Science" in
    "Bachelor's degree in Computer Science required" is an academic field, not
    a skill. "IT - Software" in an education/major requirement is also not a
    skill. Keep a domain only when the document explicitly requires or
    demonstrates that domain as a competency, rather than merely describing
    the employer or product context.

    Every returned mention and source_sentence must be copied verbatim from
    document_text. Return an empty list when no qualifying competencies exist.
    Do not combine independent skills into a single mention. A phrase that is
    itself one named competency may remain intact. Preserve each distinct
    source occurrence with its own evidence sentence.
    """

    document_type: str = dspy.InputField(desc="CV or JD")
    document_text: str = dspy.InputField(desc="Full extracted text of one CV or JD")
    explicit_skills: List[ExplicitSkillMention] = dspy.OutputField(
        desc="Verbatim skill mentions only; omit academic qualifications and non-skill entities"
    )
