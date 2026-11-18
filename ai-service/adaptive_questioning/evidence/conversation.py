"""Optional feedback before the next question, with a cue when changing skills."""
from .models import Snapshot, Turn

MAX_FEEDBACK_LENGTH = 300
ACKNOWLEDGMENT = "Cảm ơn bạn, mình đã ghi nhận câu trả lời."
INABILITY_ACKNOWLEDGMENT = "Cảm ơn bạn đã chia sẻ."


def turn_introduction(snapshot: Snapshot, turn: Turn) -> str:
    if not snapshot.turns:
        return ""
    previous = snapshot.turns[-1]
    feedback = brief_feedback(previous)
    if previous.skill_id != turn.skill_id:
        bridge = f"Tiếp theo, mình chuyển sang trao đổi về {turn.skill_id} nhé."
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
