"""Optional feedback before the next question, with human-readable skill transitions."""
from collections.abc import Sequence
import re
from .models import InterviewSkillContext, Snapshot, Turn

MAX_FEEDBACK_LENGTH = 300
MAX_PRACTICE_FEEDBACK_LENGTH = 550
ACKNOWLEDGMENT = "Cảm ơn bạn, mình đã ghi nhận câu trả lời."
INABILITY_ACKNOWLEDGMENT = "Cảm ơn bạn đã chia sẻ."
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
_MIN_TRIMMED_FEEDBACK_CHARS = 20

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


def fit_feedback_length(
    text: str,
    *,
    max_length: int = MAX_FEEDBACK_LENGTH,
    allow_sentence_trim: bool = False,
) -> str:
    """Keep feedback within max_length; trim PRACTICE coaching at a sentence boundary instead of discarding."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    if allow_sentence_trim:
        window = cleaned[:max_length]
        last_end = -1
        for match in _SENTENCE_END.finditer(window):
            last_end = match.start() + 1
        if last_end >= _MIN_TRIMMED_FEEDBACK_CHARS:
            return window[:last_end].strip()
    return ACKNOWLEDGMENT


def turn_introduction(snapshot: Snapshot, turn: Turn) -> str:
    if not snapshot.turns:
        return ""
    previous = snapshot.turns[-1]
    is_practice = snapshot.config.session_purpose == "PRACTICE"
    max_len = MAX_PRACTICE_FEEDBACK_LENGTH if is_practice else MAX_FEEDBACK_LENGTH
    feedback = brief_feedback(previous, max_length=max_len, allow_sentence_trim=is_practice)
    if turn.practice_step:
        if turn.practice_step == "RETRY" and feedback in {"", ACKNOWLEDGMENT, INABILITY_ACKNOWLEDGMENT}:
            state = snapshot.objectives[turn.objective_id]
            criterion = next(c for c in state.objective.criteria if c.criterion_id in turn.question.criterion_ids)
            feedback = f"Ở lần thử này, hãy tập trung vào {criterion.description.rstrip('.')}."
        bridge = ("Hãy thử trả lời lại câu vừa rồi sau phần góp ý."
                  if turn.practice_step == "RETRY" else "Giờ bạn thử tự giải một tình huống mới cùng mức độ nhé.")
        return "\n\n".join(part for part in (feedback, bridge) if part)
    if previous.skill_id != turn.skill_id:
        skill_label = display_skill_name(turn.skill_id, snapshot.skills)
        bridge = f"Tiếp theo, mình chuyển sang trao đổi về {skill_label} nhé."
        return "\n\n".join(part for part in (feedback, bridge) if part)
    return feedback


def brief_feedback(
    turn: Turn,
    *,
    max_length: int = MAX_FEEDBACK_LENGTH,
    allow_sentence_trim: bool = False,
) -> str:
    judgment = turn.judgment
    if judgment and judgment.explicit_inability and all(
        item.observation == "NO_EVIDENCE" for item in judgment.observations
    ):
        return INABILITY_ACKNOWLEDGMENT
    if judgment is None or judgment.feedback_contains_hint:
        return ACKNOWLEDGMENT
    return fit_feedback_length(
        judgment.feedback,
        max_length=max_length,
        allow_sentence_trim=allow_sentence_trim,
    )
