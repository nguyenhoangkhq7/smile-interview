"""Conservative checks for obvious bundled requests; problem data can contain lists."""
import re
from .models import Question


VOICE_MAX_WORDS = 90


def single_question(text: str) -> bool:
    prose = re.sub(r"```[\s\S]*?```|`[^`]*`", "", text)
    prose = re.sub(r"https?://[^\s<>]+", "", prose)
    prose = re.sub(r'''(["'])[^\s"']*\1''', "", prose)
    if prose.count("?") > 1:
        return False
    if re.search(r"\b(?:hãy|bạn hãy)\b.+?[.!;]\s*(?:sau đó|tiếp theo),?\s*(?:bạn\s+)?hãy\b",
                 prose, re.IGNORECASE | re.DOTALL):
        return False
    items = re.findall(r"^\s*(?:\d+[.)]|[-*])\s+(.+)$", prose, re.MULTILINE)
    return sum(_response_request(item) for item in items) < 2


def _response_request(item: str) -> bool:
    command = r"(?:hãy|bạn|viết|giải thích|mô tả|nêu|trình bày|write|explain|describe|review)\b"
    if re.match(command, item, re.IGNORECASE):
        return True
    conditional = re.match(r"(?:sau khi|nếu|after|if)\b", item, re.IGNORECASE)
    return bool(conditional and re.search(command, item, re.IGNORECASE))


def question_errors(question: Question, context: dict[str, object]) -> list[str]:
    contract = context["required_question_contract"]
    errors = []
    if question.mode != contract["mode"]:
        errors.append("mode must equal required_question_contract.mode exactly")
    if question.depth != contract["depth"]:
        errors.append("depth must equal required_question_contract.depth exactly (L1–L4, not proficiency)")
    if not question.evidence_scope.strip():
        errors.append("evidence_scope must be a nonempty stable case identifier")
    if "evidence_scope" in contract and question.evidence_scope != contract["evidence_scope"]:
        errors.append("CLARIFY must preserve required_question_contract.evidence_scope exactly")
    if len(question.criterion_ids) != 1 or question.criterion_ids != contract["criterion_ids"]:
        errors.append("criterion_ids must equal required_question_contract.criterion_ids exactly, with ONE criterion")
    if not single_question(question.text):
        errors.append("Ask exactly ONE response task; remove independent subquestions or numbered requests")
    if re.search(r"\b(?:hãy|bạn cần)\s+(?:thử\s+)?(?:dùng|sử dụng|mở|truy cập)\s+ChatGPT\b",
                 question.text, re.IGNORECASE):
        errors.append("Provide any needed AI output in the question and ask one task answerable directly here")
    if context.get("interaction_mode") == "VOICE" and len(question.text.split()) > VOICE_MAX_WORDS:
        errors.append(
            f"VOICE question must use at most {VOICE_MAX_WORDS} whitespace-separated words including scenario; "
            "rewrite concisely with ONE focused response task, preserving essential problem data, "
            "target criterion, evidence_scope and required depth. Do not truncate the question."
        )
    return errors
