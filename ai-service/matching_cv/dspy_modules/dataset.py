"""Gold examples for precision-focused explicit skill extraction."""

from typing import List, Tuple

import dspy

from matching_cv.dspy_modules.schemas import ExplicitSkillMention


def _example(
    document_type: str,
    document_text: str,
    explicit_skills: List[ExplicitSkillMention],
) -> dspy.Example:
    return dspy.Example(
        document_type=document_type,
        document_text=document_text,
        explicit_skills=explicit_skills,
    ).with_inputs("document_type", "document_text")


def get_gold_examples() -> List[dspy.Example]:
    """Return bilingual positive and negative boundary examples."""
    return [
        _example(
            "JD",
            "Yêu cầu tốt nghiệp chuyên ngành Khoa học máy tính. Ứng viên cần thành thạo Python và xây dựng REST API.",
            [
                ExplicitSkillMention(mention="Python", kind="skill", category="Technology/Tool", source_sentence="Ứng viên cần thành thạo Python và xây dựng REST API."),
                ExplicitSkillMention(mention="REST API", kind="skill", category="Technical Concept", source_sentence="Ứng viên cần thành thạo Python và xây dựng REST API."),
            ],
        ),
        _example(
            "JD",
            "Tốt nghiệp ngành IT - Phần mềm. Ưu tiên ứng viên có kinh nghiệm với Docker và PostgreSQL.",
            [
                ExplicitSkillMention(mention="Docker", kind="skill", category="Technology/Tool", source_sentence="Ưu tiên ứng viên có kinh nghiệm với Docker và PostgreSQL."),
                ExplicitSkillMention(mention="PostgreSQL", kind="skill", category="Technology/Tool", source_sentence="Ưu tiên ứng viên có kinh nghiệm với Docker và PostgreSQL."),
            ],
        ),
        _example(
            "JD",
            "Bachelor's degree in Computer Science or Software Engineering required. Experience with Java and Spring Boot preferred.",
            [
                ExplicitSkillMention(mention="Java", kind="skill", category="Technology/Tool", source_sentence="Experience with Java and Spring Boot preferred."),
                ExplicitSkillMention(mention="Spring Boot", kind="skill", category="Technology/Tool", source_sentence="Experience with Java and Spring Boot preferred."),
            ],
        ),
        _example(
            "CV",
            "EDUCATION\nB.S. in Computer Science, State University.\nEXPERIENCE\nBuilt data pipelines with Python and Airflow.",
            [
                ExplicitSkillMention(mention="Python", kind="skill", category="Technology/Tool", source_sentence="Built data pipelines with Python and Airflow."),
                ExplicitSkillMention(mention="Airflow", kind="skill", category="Technology/Tool", source_sentence="Built data pipelines with Python and Airflow."),
            ],
        ),
        _example(
            "JD",
            "We are a video streaming company with millions of users. The role requires JavaScript and React experience.",
            [
                ExplicitSkillMention(mention="JavaScript", kind="skill", category="Technology/Tool", source_sentence="The role requires JavaScript and React experience."),
                ExplicitSkillMention(mention="React", kind="skill", category="Technology/Tool", source_sentence="The role requires JavaScript and React experience."),
            ],
        ),
        _example(
            "JD",
            "The employer operates an e-commerce platform. Build payment APIs using Go and Kafka.",
            [
                ExplicitSkillMention(mention="Go", kind="skill", category="Technology/Tool", source_sentence="Build payment APIs using Go and Kafka."),
                ExplicitSkillMention(mention="Kafka", kind="skill", category="Technology/Tool", source_sentence="Build payment APIs using Go and Kafka."),
            ],
        ),
        _example(
            "JD",
            "Applicants need a PMP certification. Experience writing automated tests with Playwright is required.",
            [
                ExplicitSkillMention(mention="PMP certification", kind="certification", category="Certification", source_sentence="Applicants need a PMP certification."),
                ExplicitSkillMention(mention="Playwright", kind="skill", category="Technology/Tool", source_sentence="Experience writing automated tests with Playwright is required."),
            ],
        ),
        _example(
            "JD",
            "Must have a degree in information technology. The position title is Senior Software Engineer.",
            [],
        ),
        _example(
            "CV",
            "Nguyễn An, Backend Developer. Graduated in Software Engineering from ABC University in 2022.",
            [],
        ),
        _example(
            "JD",
            "Our company provides banking software to retail clients. Candidates must know SQL and database indexing.",
            [
                ExplicitSkillMention(mention="SQL", kind="skill", category="Technology/Tool", source_sentence="Candidates must know SQL and database indexing."),
                ExplicitSkillMention(mention="database indexing", kind="skill", category="Technical Concept", source_sentence="Candidates must know SQL and database indexing."),
            ],
        ),
        _example(
            "JD",
            "Applicants should have a bachelor's degree in Information Systems. No technical skills are specified.",
            [],
        ),
        _example(
            "CV",
            "Coursework: Algorithms, Operating Systems, and Database Systems. Capstone project used Java to build a scheduling app.",
            [
                ExplicitSkillMention(mention="Java", kind="skill", category="Technology/Tool", source_sentence="Capstone project used Java to build a scheduling app."),
            ],
        ),
        _example(
            "JD",
            "Experience with inventory forecasting is required for this supply-chain analyst role.",
            [
                ExplicitSkillMention(mention="inventory forecasting", kind="skill", category="Engineering Practice", source_sentence="Experience with inventory forecasting is required for this supply-chain analyst role."),
            ],
        ),
        _example(
            "CV",
            "Led a team of three engineers, reviewed pull requests, and deployed services using Kubernetes.",
            [
                ExplicitSkillMention(mention="Kubernetes", kind="skill", category="Technology/Tool", source_sentence="Led a team of three engineers, reviewed pull requests, and deployed services using Kubernetes."),
            ],
        ),
        _example(
            "JD",
            "Bachelor's degree in computer science required. Familiarity with computer science concepts is a plus.",
            [
                ExplicitSkillMention(mention="computer science concepts", kind="domain", category="Domain Knowledge", source_sentence="Familiarity with computer science concepts is a plus."),
            ],
        ),
        _example(
            "JD",
            "We develop software for healthcare providers. Experience with HL7 and FHIR standards is required.",
            [
                ExplicitSkillMention(mention="HL7", kind="skill", category="Technical Standard", source_sentence="Experience with HL7 and FHIR standards is required."),
                ExplicitSkillMention(mention="FHIR", kind="skill", category="Technical Standard", source_sentence="Experience with HL7 and FHIR standards is required."),
            ],
        ),
    ]


def get_train_val_split() -> Tuple[List[dspy.Example], List[dspy.Example]]:
    """Use a stable document-level holdout for optimizer and local evaluation."""
    examples = get_gold_examples()
    return examples[:-4], examples[-4:]
