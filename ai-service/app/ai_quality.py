"""Check persisted AI outputs against their sources without external model calls."""
import json
import re
import unicodedata
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field

from adaptive_questioning.evidence.question_validation import VOICE_MAX_WORDS, question_form_errors

Status = Literal["REVIEW", "INSUFFICIENT"]
Source = Literal["CV", "JD"]
MAX_EXCERPT_LENGTH = 360
SOURCE_QUOTES = re.compile(
    r"\b(?:trong|theo)\s+(?P<source>CV|hồ sơ|JD|mô tả công việc)"
    r"(?:\s+của\s+bạn)?\s*[:,]?\s*"
    r"(?:(?:bạn\s+)?(?:có\s+)?(?:ghi|viết|nêu|đề cập)(?:\s+rằng)?\s*[:,]?\s*)?"
    r"(?:“(?P<curly>[^”\r\n]+)”|«(?P<angle>[^»\r\n]+)»|\"(?P<plain>[^\"\r\n]+)\")",
    re.IGNORECASE,
)
QUESTION_DETAILS = {
    "MULTIPLE_TASKS": "Câu hỏi có dấu hiệu yêu cầu nhiều việc độc lập.",
    "MISSING_CODE": "Câu hỏi nhắc đến đoạn mã nhưng không cung cấp đoạn mã đó.",
    "EXTERNAL_TOOL": "Câu hỏi yêu cầu ứng viên dùng ChatGPT bên ngoài phiên.",
    "LONG_VOICE_QUESTION": f"Câu hỏi giọng nói dài hơn {VOICE_MAX_WORDS} từ.",
}


class ReviewQuestion(BaseModel):
    text: str | None = None
    skill: str | None = None


class ReviewInput(BaseModel):
    cv: str | None = None
    jd: str | None = None
    skillsJson: str | None = None
    reportJson: str | None = None
    mode: str | None = None
    questions: list[ReviewQuestion] = Field(default_factory=list)


class Finding(BaseModel):
    status: Status
    code: str
    detail: str
    skill: str | None = None
    turn: int | None = None
    excerpt: str | None = None


class Section(BaseModel):
    total: int
    findings: list[Finding]


class QualityReview(BaseModel):
    matching: Section
    questions: Section


def _normalize(text: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def _excerpt(text: str) -> str:
    return text if len(text) <= MAX_EXCERPT_LENGTH else text[:MAX_EXCERPT_LENGTH - 1] + "…"


def _parse_json(value: str | None):
    try:
        return json.loads(value) if value else None
    except (ValueError, RecursionError):
        return None


def _spans(value) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _jd_spans(entry: dict) -> list[str]:
    spans = _spans(entry.get("jd_evidence_spans"))
    tasks = entry.get("job_tasks")
    if isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict):
                spans.extend(_spans(task.get("evidence_spans")))
    return spans


def _has_quote(document: str, quote: str) -> bool:
    # A skill such as "Java" must not be verified by a substring of "JavaScript".
    start = r"(?<!\w)" if re.match(r"\w", quote[0]) else ""
    end = r"(?!\w)" if re.match(r"\w", quote[-1]) else ""
    return re.search(start + re.escape(quote) + end, document) is not None


def _quote_findings(source: Source, spans: Iterable[str], document: str) -> Iterable[Finding]:
    if not document:
        yield Finding(status="INSUFFICIENT", code="SOURCE_MISSING", detail=f"Thiếu văn bản {source} đã lưu để đối chiếu.")
        return
    quotes = dict.fromkeys(_normalize(span) for span in spans)
    if not quotes:
        yield Finding(status="INSUFFICIENT", code="QUOTE_MISSING", detail=f"Kết quả chưa có trích dẫn từ {source}.")
    for quote in quotes:
        if not _has_quote(document, quote):
            yield Finding(status="REVIEW", code="QUOTE_NOT_FOUND",
                          detail=f"Không tìm thấy trích dẫn này trong {source} đã lưu.", excerpt=_excerpt(quote))


def _matching_findings(entry, documents: dict[Source, str]) -> Iterable[Finding]:
    if not isinstance(entry, dict):
        yield Finding(status="INSUFFICIENT", code="INVALID_SKILL", detail="Một mục kỹ năng lưu sai định dạng.")
        return
    skill = next((entry[key] for key in ("jd_skill_name", "jd_skill_id")
                  if isinstance(entry.get(key), str) and entry[key].strip()), None)
    cv = _spans(entry.get("cv_evidence_spans"))
    if cv or entry.get("semantic_alignment") in ("MATCH", "PARTIAL") or entry.get("matched_cv_skill_id"):
        yield from (finding.model_copy(update={"skill": skill}) for finding in _quote_findings("CV", cv, documents["CV"]))
    jd = _quote_findings("JD", _jd_spans(entry), documents["JD"])
    yield from (finding.model_copy(update={"skill": skill}) for finding in jd)


def _matching(review: ReviewInput, documents: dict[Source, str]) -> Section:
    report = _parse_json(review.reportJson)
    skills = _parse_json(review.skillsJson)
    findings = []
    if isinstance(report, dict) and report.get("degraded") is True:
        findings.append(Finding(status="REVIEW", code="DEGRADED_MATCHING",
                                detail="Kết quả đối sánh có cờ suy giảm do pipeline ghi lại."))
    if not isinstance(skills, list):
        if review.skillsJson is not None or isinstance(report, dict):
            findings.append(Finding(status="INSUFFICIENT", code="MISSING_SKILLS",
                                    detail="Thiếu danh sách đối sánh theo kỹ năng có thể đọc được."))
        return Section(total=0, findings=findings)
    findings.extend(finding for entry in skills for finding in _matching_findings(entry, documents))
    return Section(total=len(skills), findings=findings)


def _question_findings(text: str, documents: dict[Source, str], mode: str | None) -> Iterable[Finding]:
    for code in question_form_errors(text, mode):
        yield Finding(status="REVIEW", code=code, detail=QUESTION_DETAILS[code])
    for match in SOURCE_QUOTES.finditer(text):
        source: Source = "CV" if match["source"].casefold() in ("cv", "hồ sơ") else "JD"
        quote = match["curly"] or match["angle"] or match["plain"]
        if quote.strip():
            yield from _quote_findings(source, [quote], documents[source])


def _questions(review: ReviewInput, documents: dict[Source, str]) -> Section:
    first_seen: dict[str, int] = {}
    findings = []
    total = 0
    for turn, question in enumerate(review.questions, start=1):
        text = question.text
        if not text or not text.strip():
            continue
        total += 1
        checks = list(_question_findings(text, documents, review.mode))
        initial_turn = first_seen.setdefault(_normalize(text).casefold(), turn)
        if initial_turn != turn:
            checks.append(Finding(status="REVIEW", code="REPEATED_QUESTION",
                                  detail=f"Câu hỏi trùng nội dung đã hỏi ở lượt {initial_turn}."))
        findings.extend(check.model_copy(update={
            "turn": turn, "skill": question.skill, "excerpt": check.excerpt or _excerpt(text),
        }) for check in checks)
    return Section(total=total, findings=findings)


def review_quality(review: ReviewInput) -> QualityReview:
    documents: dict[Source, str] = {"CV": _normalize(review.cv), "JD": _normalize(review.jd)}
    return QualityReview(matching=_matching(review, documents), questions=_questions(review, documents))
