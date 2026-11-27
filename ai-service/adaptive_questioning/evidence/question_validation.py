"""Conservative checks for source framing, single-task questions and missing problem data."""
import re
from .models import Question


VOICE_MAX_WORDS = 90
_DIRECTIVE = r"(?:hãy|(?:bạn|em)\s+(?:sẽ|cần)|please)"
_TASK_VERB = (r"(?:phân tích|chẩn đoán|xác định|chỉ ra|nêu|liệt kê|xác minh|giải thích|mô tả|trình bày|đề xuất|viết|triển khai|"
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
_JD_REFERENCE = re.compile(
    r"\b(?:JD|mô\s+tả\s+công\s+việc|yêu\s+cầu\s+công\s+việc|vị\s+trí\s+(?:này|ứng\s+tuyển))\b",
    re.IGNORECASE,
)
_CV_REFERENCE = re.compile(r"\b(?:CV|hồ\s+sơ)\b", re.IGNORECASE)
_JD_ALTERNATIVE = r"\b(?:hoặc|or)\b"
_OPTION_WORDING = re.compile(r"\b(?:hoặc|or|một\s+trong|một\s+lựa\s+chọn)\b", re.IGNORECASE)
_REQUIREMENT_CLAIM = re.compile(r"\b(?:yêu\s+cầu|đòi\s+hỏi|bắt\s+buộc|cần|phải|requires?)\b", re.IGNORECASE)
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


def required_framing(context: dict[str, object]) -> tuple[str, bool]:
    """Return the verified JD excerpt and whether a CV lead-in is required for this turn."""
    verification = context.get("verification_context")
    if not isinstance(verification, dict) or context.get("history"):
        return "", False
    jd_excerpt = verification.get("jd_excerpt")
    use_cv = bool(verification.get("detail_to_verify") and context.get("cv_evidence"))
    return jd_excerpt if isinstance(jd_excerpt, str) else "", use_cv


def _grounding_errors(text: str, context: dict[str, object]) -> list[str]:
    jd_excerpt, use_cv = required_framing(context)
    if not jd_excerpt and not use_cv:
        return []
    prose = _INLINE_CODE.sub("", _CODE_FENCE.sub("", text))
    sentences = re.split(r"(?<=[.!?])\s+|\n+", prose.strip())
    framing = [sentence for sentence in sentences[:-1] if not sentence.rstrip().endswith("?")]
    errors = []
    if jd_excerpt:
        objective = context.get("objective")
        skill_id = objective.get("skill_id", "") if isinstance(objective, dict) else ""
        errors.extend(_jd_grounding_errors(jd_excerpt, framing, skill_id))
    if use_cv and not any(_CV_REFERENCE.search(sentence) for sentence in framing):
        errors.append("Briefly link the task to a relevant fact from the candidate's CV excerpt before asking.")
    return errors


def _jd_grounding_errors(jd_excerpt: str, framing: list[str], skill_id: str) -> list[str]:
    references = [(sentence, match) for sentence in framing if (match := _JD_REFERENCE.search(sentence))]
    if not references:
        return ["Add a brief link to a specific fact in the JD excerpt before the task."]
    skill = rf"(?<!\w){re.escape(skill_id)}(?!\w)"
    alternative = rf"{skill}\s+{_JD_ALTERNATIVE}|{_JD_ALTERNATIVE}\s+{skill}"
    if skill_id and re.search(alternative, jd_excerpt, re.IGNORECASE) and any(
        _REQUIREMENT_CLAIM.search(sentence[match.end():]) and not _OPTION_WORDING.search(sentence)
        for sentence, match in references
    ):
        return ["Preserve the alternatives in the JD, or introduce the selected skill as one option."]
    return []


def question_form_errors(text: str, interaction_mode: str | None) -> dict[str, str]:
    errors = {}
    if not single_question(text):
        errors["MULTIPLE_TASKS"] = "Ask exactly ONE response task; remove independent subquestions or numbered requests"
    if _missing_referenced_code(text):
        errors["MISSING_CODE"] = ("The question refers to a missing code snippet. Include the actual code inline in a Markdown "
                                  "code block for TEXT, or describe its exact behavior and inputs aloud for VOICE without "
                                  "referring to an absent snippet.")
    if re.search(r"\b(?:hãy|bạn cần)\s+(?:thử\s+)?(?:dùng|sử dụng|mở|truy cập)\s+ChatGPT\b",
                 text, re.IGNORECASE):
        errors["EXTERNAL_TOOL"] = "Provide any needed AI output in the question and ask one task answerable directly here"
    if interaction_mode == "VOICE" and len(text.split()) > VOICE_MAX_WORDS:
        errors["LONG_VOICE_QUESTION"] = (
            f"VOICE question must use at most {VOICE_MAX_WORDS} whitespace-separated words including scenario; "
            "rewrite concisely with ONE focused response task, preserving essential problem data, "
            "target criterion, evidence_scope and required depth. Do not truncate the question."
        )
    return errors


def question_errors(question: Question, context: dict[str, object]) -> list[str]:
    contract = context["required_question_contract"]
    errors = _grounding_errors(question.text, context)
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
    errors.extend(question_form_errors(question.text, context.get("interaction_mode")).values())
    return errors
