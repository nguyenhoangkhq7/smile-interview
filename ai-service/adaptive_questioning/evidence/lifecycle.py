"""Unscored interview greetings and introduction, separate from technical turns."""
from datetime import datetime, timedelta
import re
from uuid import uuid4

from .models import (
    ConversationMessage, ConversationOpening, ConversationState, InterviewOpening,
    MAX_DIALOGUE_TEXT_LENGTH, Snapshot, StartRequest,
)

INTRODUCTION_SECONDS = 120
OPENING_SECONDS = 180
CLOSING_SECONDS = 120
MIN_DIALOGUE_CHARS = 15
MAX_SKILLS_IN_GREETING = 8
MAX_TASKS_PER_SKILL = 2
MAX_CV_EVIDENCE_ITEMS = 8
MAX_INTRO_FOR_CLOSING = 800
INTRODUCTION_BRIDGE = "Cảm ơn bạn đã chia sẻ. Bây giờ mình bắt đầu phần trao đổi chuyên môn nhé."
SKIP_BRIDGE = "Mình bắt đầu phần trao đổi chuyên môn nhé."


def message(text: str) -> ConversationMessage:
    return ConversationMessage(message_id=str(uuid4()), text=text)


def fallback_opening_text(opening: InterviewOpening) -> str:
    company = f" tại {opening.company.strip()}" if opening.company.strip() else ""
    greeting = f"Chào {opening.candidate_name.strip()}" if opening.candidate_name.strip() else "Chào bạn"
    parts = [
        f"{greeting}, mình là {opening.interviewer_name.strip() or 'Minh'}, "
        f"người phỏng vấn AI mô phỏng buổi phỏng vấn{company}.",
        f"Hôm nay chúng ta sẽ trao đổi về {opening.role_title.strip() or 'vị trí ứng tuyển'}.",
        "Trước tiên, bạn có thể giới thiệu ngắn về bản thân và kinh nghiệm liên quan được không?",
    ]
    return " ".join(parts)


def fallback_closing_text(reason: str, turns_answered: int = 0) -> str:
    if reason == "USER_STOP" and turns_answered == 0:
        return (
            "Mình đã ghi nhận yêu cầu dừng buổi phỏng vấn sớm. "
            "Cảm ơn bạn đã ghé qua và hẹn gặp lại bạn trong lượt luyện tập tiếp theo, chào bạn!"
        )
    prefix = {
        "TIME_BUDGET": "Thời gian trao đổi chuyên môn đã hết.",
        "USER_STOP": "Mình đã ghi nhận yêu cầu kết thúc buổi phỏng vấn của bạn.",
    }.get(reason, "Chúng ta đã hoàn tất phần trao đổi hôm nay.")
    return (
        f"{prefix} Cảm ơn bạn đã dành thời gian tham gia. "
        "Buổi phỏng vấn đến đây là kết thúc. Chúc bạn một ngày tốt lành, chào bạn!"
    )


def clean_dialogue_text(text: str, interaction_mode: str = "TEXT") -> str:
    """Normalize LLM dialogue and reject empty or overlong outputs."""
    cleaned = " ".join(text.split()) if interaction_mode == "VOICE" else re.sub(r"\n{3,}", "\n\n", text.strip())
    if interaction_mode == "VOICE":
        cleaned = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|[-*])\s+", "", cleaned)
        cleaned = re.sub(r"[`*_]", "", cleaned).strip()
    if len(cleaned) < MIN_DIALOGUE_CHARS or len(cleaned) > MAX_DIALOGUE_TEXT_LENGTH:
        raise ValueError("Dialogue text is out of allowed length bounds")
    return cleaned


def opening_context(request: StartRequest) -> dict[str, object]:
    """Assemble safe JD and user context for opening greeting generation."""
    opening = request.opening or InterviewOpening()
    jd_skills = [
        {"skill": skill.jd_skill_id, "tasks": [task.description for task in skill.job_tasks[:MAX_TASKS_PER_SKILL]]}
        for skill in request.skills[:MAX_SKILLS_IN_GREETING]
    ]
    cv_evidence = [span for skill in request.skills for span in skill.cv_evidence_spans if span.strip()][
        :MAX_CV_EVIDENCE_ITEMS
    ]
    return {
        "interviewer_name": opening.interviewer_name.strip() or "Minh",
        "candidate_name": opening.candidate_name.strip(),
        "company": opening.company.strip(),
        "role_title": opening.role_title.strip() or "vị trí ứng tuyển",
        "attempt_number": opening.attempt_number,
        "jd_summary": opening.jd_summary.strip(),
        "cv_summary": opening.cv_summary.strip(),
        "jd_skills": jd_skills,
        "cv_evidence": cv_evidence,
        "interaction_mode": request.config.interaction_mode,
        "focused_question_mode": request.config.focused_question_mode.value if request.config.focused_question_mode else None,
        "duration_minutes": round(request.config.duration_seconds / 60),
        "max_questions": request.config.max_questions,
    }


def closing_context(snapshot: Snapshot, reason: str, had_pending: bool = False) -> dict[str, object]:
    """Assemble safe session and JD context for farewell generation without exposing scores."""
    opening = snapshot.opening_context
    conversation = snapshot.conversation
    company = opening.company.strip() if opening else (conversation.opening.company.strip() if conversation else "")
    interviewer = (
        opening.interviewer_name.strip() if opening
        else (conversation.opening.interviewer_name.strip() if conversation else "")
    ) or "Minh"
    intro = (conversation.introduction.strip() if conversation else "")[:MAX_INTRO_FOR_CLOSING]
    return {
        "interviewer_name": interviewer,
        "candidate_name": opening.candidate_name.strip() if opening else "",
        "company": company,
        "role_title": (opening.role_title.strip() if opening else "") or "vị trí ứng tuyển",
        "jd_summary": opening.jd_summary.strip() if opening else "",
        "cv_summary": opening.cv_summary.strip() if opening else "",
        "candidate_introduction": intro,
        "termination_reason": reason,
        "turns_answered": len(snapshot.turns),
        "topics_discussed": list(dict.fromkeys(turn.skill_id for turn in snapshot.turns)),
        "had_pending_question": had_pending,
        "interaction_mode": snapshot.config.interaction_mode,
    }


def begin(opening: InterviewOpening, now: datetime, text: str | None = None) -> ConversationState:
    resolved = text.strip() if text and text.strip() else fallback_opening_text(opening)
    return ConversationState(
        phase="OPENING", message=message(resolved),
        opening=ConversationOpening(interviewer_name=opening.interviewer_name, company=opening.company),
        opening_text=resolved, expires_at=now + timedelta(seconds=OPENING_SECONDS),
    )


def close(snapshot: Snapshot, reason: str, now: datetime, text: str | None = None) -> None:
    if snapshot.conversation is None:
        return
    resolved = text.strip() if text and text.strip() else fallback_closing_text(reason, len(snapshot.turns))
    snapshot.conversation.phase = "CLOSING"
    snapshot.conversation.expires_at = now + timedelta(seconds=CLOSING_SECONDS)
    snapshot.conversation.message = message(resolved)
