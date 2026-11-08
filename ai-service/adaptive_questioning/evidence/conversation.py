"""Brief candidate-facing acknowledgment and a bridge to the selected next task."""
from .models import Action, Snapshot, Turn

MAX_FEEDBACK_LENGTH = 300
ACKNOWLEDGMENT = "Cảm ơn bạn, mình đã ghi nhận câu trả lời."
BRIDGES = {
    Action.CLARIFY: "Mình muốn làm rõ thêm một ý trong câu trả lời vừa rồi.",
    Action.FOLLOW_UP: "Mình hỏi thêm một tình huống để hiểu rõ cách bạn áp dụng nhé.",
    Action.EASIER: "Mình thử một tình huống đơn giản hơn để hiểu rõ cách bạn tiếp cận nhé.",
    Action.VERIFY: "Mình muốn làm rõ điểm khác nhau giữa hai cách bạn vừa giải thích.",
    Action.DEEPER: "Mình thử mở rộng tình huống thêm một chút nhé.",
}


def turn_introduction(snapshot: Snapshot, turn: Turn) -> str:
    if not snapshot.turns:
        return ""
    previous = snapshot.turns[-1]
    return f"{brief_feedback(previous)}\n\n{_bridge(previous, turn)}"


def brief_feedback(turn: Turn) -> str:
    judgment = turn.judgment
    if judgment is None or judgment.feedback_contains_hint:
        return ACKNOWLEDGMENT
    feedback = " ".join(judgment.feedback.split())
    return feedback if feedback and len(feedback) <= MAX_FEEDBACK_LENGTH else ACKNOWLEDGMENT


def _bridge(previous: Turn, turn: Turn) -> str:
    if previous.skill_id != turn.skill_id:
        return f"Tiếp theo, mình chuyển sang trao đổi về {turn.skill_id} nhé."
    if previous.objective_id != turn.objective_id or previous.question.criterion_ids != turn.question.criterion_ids:
        return "Tiếp theo, mình trao đổi thêm một khía cạnh khác của bài toán này."
    return BRIDGES.get(turn.action, "Mình cùng chuyển sang câu hỏi tiếp theo nhé.")
