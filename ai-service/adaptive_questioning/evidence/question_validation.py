"""Conservative checks for single-task questions and missing problem data."""
import re
from .models import Question


VOICE_MAX_WORDS = 90
_DIRECTIVE = r"(?:hãy|(?:bạn|em)\s+(?:sẽ|cần)|please)"
_TASK_VERB = (r"(?:phân tích|chẩn đoán|xác định|giải thích|mô tả|trình bày|đề xuất|viết|triển khai|"
              r"thiết kế|sửa|so sánh|kiểm thử|analy[sz]e|diagnose|identify|explain|describe|propose|"
              r"write|implement|design|fix|compare|test)")
_SECOND_WORK_PRODUCT = r"(?:đề xuất|viết|triển khai|thiết kế|sửa|so sánh|kiểm thử|propose|write|implement|design|fix|compare|test)"
_COMBINED_REQUESTS = re.compile(
    rf"\b{_DIRECTIVE}\s+{_TASK_VERB}\b[^.!?;]*?\b(?:và|rồi|sau đó|and|then)\s+"
    rf"(?:{_DIRECTIVE}\s+)?{_SECOND_WORK_PRODUCT}\b", re.IGNORECASE,
)
_CODE_REFERENCE = re.compile(
    r"\b(?:(?:đoạn\s+)?(?:mã(?:\s+nguồn)?|code)|đoạn\s+sql)\s+"
    r"(?:[a-z][a-z0-9+#.-]*\s+)?"
    r"(?:sau\b(?!\s+(?:khi|đó|mỗi)\b)|dưới\s+đây\b|(?:(?:ở|bên)\s+)?trên\b|(?:ở|bên)\s+dưới\b)"
    r"|\b(?:the\s+following\s+(?:code|snippet)|(?:code|snippet)\s+(?:below|above))\b",
    re.IGNORECASE,
)
_CODE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n(.*?)^ {0,3}\1[ \t]*\r?$", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"(?<!`)(`+)([^`\n]+)\1(?!`)")
_CODE_LINE = re.compile(
    r"^[ \t]*(?:(?:async[ \t]+)?(?:def|function)[ \t]+\w+[ \t]*\("
    r"|(?:return|raise|select|update|insert into|delete from)[ \t]+\S"
    r"|(?:(?:const|let|var)[ \t]+)?[\w.]+(?:\[[^\]\n]+\])?[ \t]*=(?!=)[ \t]*\S"
    r"|(?:if|for|while)[ \t]+(?:\(|[^\n]+:[ \t]*$))", re.IGNORECASE | re.MULTILINE,
)
_EMPTY_CODE_LINE = re.compile(r"\s*(?:\.{3}|…|(?:#|//|--).*|\[?(?:todo|code here|đoạn mã)\]?)?\s*", re.IGNORECASE)


def _missing_referenced_code(text: str) -> bool:
    prose = _CODE_FENCE.sub("", text)
    plain_text = _INLINE_CODE.sub("", prose)
    if not _CODE_REFERENCE.search(plain_text):
        return False
    if any(
        not _EMPTY_CODE_LINE.fullmatch(line)
        for _, block in _CODE_FENCE.findall(text)
        for line in block.splitlines()
    ):
        return False
    return not (
        _CODE_LINE.search(plain_text) or any(_CODE_LINE.search(code) for _, code in _INLINE_CODE.findall(prose))
    )


def single_question(text: str) -> bool:
    prose = _INLINE_CODE.sub("", _CODE_FENCE.sub("", text))
    prose = re.sub(r"https?://[^\s<>]+", "", prose)
    prose = re.sub(r'''(["'])[^\s"']*\1''', "", prose)
    if prose.count("?") > 1:
        return False
    if _COMBINED_REQUESTS.search(prose):
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
    if _missing_referenced_code(question.text):
        errors.append("The question refers to a missing code snippet. Include the actual code inline in a Markdown "
                      "code block for TEXT, or describe its exact behavior and inputs aloud for VOICE without "
                      "referring to an absent snippet.")
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
