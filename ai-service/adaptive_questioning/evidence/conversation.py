"""Optional feedback before the next question, with human-readable skill transitions."""
from collections.abc import Sequence
from .models import InterviewSkillContext, Snapshot, Turn

MAX_FEEDBACK_LENGTH = 300
ACKNOWLEDGMENT = "Cảm ơn bạn, mình đã ghi nhận câu trả lời."
INABILITY_ACKNOWLEDGMENT = "Cảm ơn bạn đã chia sẻ."

_KNOWN_ACRONYMS = {
    "sql": "SQL",
    "api": "API",
    "rest": "REST",
    "http": "HTTP",
    "html": "HTML",
    "css": "CSS",
    "aws": "AWS",
    "gcp": "GCP",
    "ci": "CI",
    "cd": "CD",
    "ui": "UI",
    "ux": "UX",
    "qa": "QA",
    "jvm": "JVM",
    "nosql": "NoSQL",
    "graphql": "GraphQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "nodejs": "Node.js",
    "nextjs": "Next.js",
    "fastapi": "FastAPI",
    "devops": "DevOps",
    "oop": "OOP",
    "jwt": "JWT",
    "oauth2": "OAuth2",
}


def format_skill_slug(skill_id: str) -> str:
    """Turn raw snake_case/kebab-case skill IDs into natural display names."""
    raw = (skill_id or "").strip()
    if not raw:
        return ""
    if "_" not in raw and "-" not in raw:
        mapped = _KNOWN_ACRONYMS.get(raw.casefold())
        if mapped:
            return mapped
        return raw if any(ch.isupper() for ch in raw) else raw.capitalize()
    tokens = [part for part in raw.replace("-", " ").replace("_", " ").split() if part]
    formatted = [
        _KNOWN_ACRONYMS.get(token.casefold(), token if any(ch.isupper() for ch in token) else token.capitalize())
        for token in tokens
    ]
    return " ".join(formatted)


def display_skill_name(skill_id: str, skills: Sequence[InterviewSkillContext] | None = None) -> str:
    """Prefer jd_skill_name from Module 2 when available; fall back to clean slug formatting."""
    if skills:
        for item in skills:
            if item.jd_skill_id == skill_id and item.jd_skill_name and item.jd_skill_name.strip():
                return item.jd_skill_name.strip()
    return format_skill_slug(skill_id)


def turn_introduction(snapshot: Snapshot, turn: Turn) -> str:
    if not snapshot.turns:
        return ""
    previous = snapshot.turns[-1]
    feedback = brief_feedback(previous)
    if previous.skill_id != turn.skill_id:
        skill_label = display_skill_name(turn.skill_id, snapshot.skills)
        bridge = f"Tiếp theo, mình chuyển sang trao đổi về {skill_label} nhé."
        return "\n\n".join(part for part in (feedback, bridge) if part)
    return feedback


def brief_feedback(turn: Turn) -> str:
    judgment = turn.judgment
    if judgment and judgment.explicit_inability and all(
        item.observation == "NO_EVIDENCE" for item in judgment.observations
    ):
        return INABILITY_ACKNOWLEDGMENT
    if judgment is None or judgment.feedback_contains_hint:
        return ACKNOWLEDGMENT
    feedback = " ".join(judgment.feedback.split())
    return feedback if len(feedback) <= MAX_FEEDBACK_LENGTH else ACKNOWLEDGMENT
