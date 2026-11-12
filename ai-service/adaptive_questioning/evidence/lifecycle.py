"""Unscored interview greetings and introduction, separate from technical turns."""
from datetime import datetime, timedelta
from uuid import uuid4

from .models import ConversationMessage, ConversationState, InterviewOpening, Snapshot

INTRODUCTION_SECONDS = 120
OPENING_SECONDS = 180
CLOSING_SECONDS = 120
INTRODUCTION_BRIDGE = "Cảm ơn bạn đã chia sẻ. Bây giờ mình bắt đầu phần trao đổi chuyên môn nhé."
SKIP_BRIDGE = "Mình bắt đầu phần trao đổi chuyên môn nhé."


def message(text: str) -> ConversationMessage:
    return ConversationMessage(message_id=str(uuid4()), text=text)


def begin(opening: InterviewOpening, now: datetime) -> ConversationState:
    company = f" tại {opening.company.strip()}" if opening.company.strip() else ""
    parts = [f"Chào bạn, mình là {opening.interviewer_name.strip() or 'Minh'}, "
             f"người phỏng vấn AI mô phỏng buổi phỏng vấn{company}."]
    if opening.company_description.strip():
        parts.append(opening.company_description.strip())
    parts.extend([f"Hôm nay chúng ta sẽ trao đổi về {opening.role_title.strip() or 'vị trí ứng tuyển'}.",
                  "Trước tiên, bạn có thể giới thiệu ngắn về bản thân và kinh nghiệm liên quan được không?"])
    text = " ".join(parts)
    return ConversationState(phase="OPENING", message=message(text), opening=opening,
                             opening_text=text, expires_at=now + timedelta(seconds=OPENING_SECONDS))


def close(snapshot: Snapshot, reason: str, now: datetime) -> None:
    if snapshot.conversation is None:
        return
    prefix = {"TIME_BUDGET": "Thời gian trao đổi chuyên môn đã hết.",
              "USER_STOP": "Mình đã ghi nhận yêu cầu kết thúc buổi phỏng vấn của bạn."}.get(
                  reason, "Chúng ta đã hoàn tất phần trao đổi hôm nay.")
    snapshot.conversation.phase = "CLOSING"
    snapshot.conversation.expires_at = now + timedelta(seconds=CLOSING_SECONDS)
    snapshot.conversation.message = message(
        f"{prefix} Cảm ơn bạn đã dành thời gian tham gia. "
        "Buổi phỏng vấn đến đây là kết thúc. Chúc bạn một ngày tốt lành, chào bạn!")
