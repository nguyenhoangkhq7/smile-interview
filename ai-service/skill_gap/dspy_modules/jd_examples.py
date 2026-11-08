"""JD demonstrations aligned with task grounding and optionality-independent depth."""
import dspy

from skill_gap.domain.models import JDRequirement, JobTask


def _requirement(skill, level, quote, description, kind="REQUIRED", basis="EXPLICIT"):
    reason = (f"Mức {level} dựa trên nhiệm vụ/độ sâu: {quote}. "
              "Optional chỉ là mức bắt buộc, không thay đổi độ sâu; thiếu nhiệm vụ thì dùng mức suy luận.")
    tasks = [JobTask(description=description, required_level=level, evidence_spans=[quote],
                     requirement_kind=kind, level_basis=basis)] if description else []
    return JDRequirement(jd_skill_id=skill, required_level=level, reasoning=reason, tasks=tasks), quote


def _example(title, entries):
    requirements = [entry[0] for entry in entries]
    quotes = [entry[1] for entry in entries]
    return dspy.Example(
        jd_text=title + "\n" + "\n".join(quotes),
        skills_context="\n\n".join(f"Skill ID: {req.jd_skill_id}\nEvidence Spans:\n  - {quote}"
                                     for req, quote in entries),
        reasoning="\n".join(req.reasoning for req in requirements),
        requirements=requirements,
    ).with_inputs("jd_text", "skills_context")


def get_gold_jd_requirement_examples() -> list[dspy.Example]:
    return [
        _example("DevOps Engineer", [
            _requirement("kubernetes", 4, "Independently diagnose production Kubernetes incidents.",
                         "Diagnose production incidents"),
            _requirement("terraform", 3.5, "Proficient in maintaining Terraform infrastructure modules.",
                         "Maintain infrastructure modules"),
            _requirement("gcp", 2, "Basic knowledge of GCP is a plus.", None, "OPTIONAL"),
        ]),
        _example("Database Engineer", [
            _requirement("postgresql", 4, "Advanced PostgreSQL query optimization at production scale is optional.",
                         "Optimize queries at production scale", "OPTIONAL"),
            _requirement("sql", 2, "Write simple SQL queries with guidance.", "Write simple queries with guidance"),
        ]),
        _example("Backend Intern", [
            _requirement("java", 2, "Implement basic Java CRUD endpoints with mentor support.",
                         "Implement basic CRUD endpoints"),
            _requirement("git", 1.5, "Understand basic Git commands.", None),
        ]),
        _example("Principal Platform Engineer", [
            _requirement("kubernetes", 5, "Lead enterprise-wide Kubernetes architecture and multi-region disaster recovery.",
                         "Design enterprise architecture and multi-region recovery"),
            _requirement("golang", 4, "Golang", None, basis="FALLBACK"),
        ]),
        _example("Backend Developer", [
            _requirement("python", 3, "At least two years of Python experience.", None, basis="INFERRED"),
            _requirement("docker", 3, "Independently package and deploy applications with Docker.",
                         "Package and deploy applications independently"),
        ]),
    ]
