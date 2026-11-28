"""Deterministic comparisons over source-grounded records."""
import operator
import re

from .models import Decision, Education, Experience, GPA, Grade, Period, Study

COMPARE = {">": operator.gt, ">=": operator.ge, "=": operator.eq, "<=": operator.le, "<": operator.lt}
Outcome = tuple[Decision, str]


def unknown(reason: str) -> Outcome:
    return "insufficient_evidence", reason


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def compare(value, operation, threshold, unit: str) -> Outcome:
    status = "met" if COMPARE[operation](value, threshold) else "not_met"
    return status, f"CV ghi {value:g}{unit}. JD yêu cầu {operation} {threshold:g}{unit}."


def education(condition: Education, records: list[Study]) -> Outcome:
    fields = [key for key in ("school", "degree", "status") if getattr(condition, key)]
    if not fields:
        return unknown("JD chưa nêu rõ tiêu chí học vấn.")
    excluded = False
    for record in records:
        matches = [normalize(getattr(record, key) or "") == normalize(getattr(condition, key)) for key in fields]
        if all(matches):
            return "met", "Thông tin của cùng một chương trình học đáp ứng các yêu cầu đã nêu."
        if record.exclusive and all(getattr(record, key) for key in fields):
            excluded = True
    if excluded:
        return "not_met", "CV xác nhận thông tin học vấn loại trừ điều kiện này."
    return unknown("Chưa có đủ bằng chứng về chương trình học đáp ứng điều kiện.")


def grade_in_quote(value: float | None, quote: str) -> bool:
    numbers = re.findall(r"(?<!\d)\d+(?:[.,]\d+)?", quote)
    return value is not None and any(float(n.replace(",", ".")) == value for n in numbers)


def supported_grade(item: GPA | Grade) -> bool:
    return (item.scale is not None and item.scale > 0 and item.value is not None
            and item.value <= item.scale and grade_in_quote(item.value, item.quote)
            and grade_in_quote(item.scale, item.quote))


def grade(condition: GPA, records: list[Grade]) -> Outcome:
    if not condition.operator or not supported_grade(condition):
        return unknown("Chưa xác minh được ngưỡng hoặc thang GPA trong JD.")
    if not records or any(not supported_grade(r) or r.scale != condition.scale for r in records):
        return unknown("Cần GPA có bằng chứng trên cùng thang điểm với JD.")
    values = {r.value for r in records}
    if len(values) != 1:
        return unknown("CV có nhiều GPA khác nhau, cần xác định GPA áp dụng.")
    return compare(values.pop(), condition.operator, condition.value, f"/{condition.scale:g}")


def month_index(value: str) -> int:
    year, month = map(int, value.split("-"))
    return year * 12 + month


def sequential_months(records: list[Period]) -> int:
    # The caller orders records by their verified positions in the original CV.
    chain: dict[str, int] = {}
    for role in records:
        if role.quote in chain or (role.start and role.end):
            continue
        duration = role.months or 0
        previous = chain.get(role.after_quote or "", 0)
        chain[role.quote] = previous + duration
    return max(chain.values(), default=0)


def confirmed_months(records: list[Period]) -> int:
    # Count the union of dated intervals. Undated roles can overlap any of these.
    intervals = sorted((month_index(r.start), month_index(r.end))
                       for r in records if r.start and r.end and r.start <= r.end)
    counted, last = 0, -1
    for start, end in intervals:
        counted += max(0, end - max(last + 1, start) + 1)
        last = max(last, end)
    return max(counted, sequential_months(records))


def experience(condition: Experience, records: list[Period]) -> Outcome:
    if not condition.operator or condition.months is None or not condition.domain:
        return unknown("JD chưa đủ thông tin để so sánh thời lượng kinh nghiệm.")
    relevant = [r for r in records if r.relevance == "confirmed"]
    totals = {r.months for r in relevant if r.scope == "explicit_domain_total" and r.months is not None}
    lower = confirmed_months([r for r in relevant if r.scope == "role"])
    if totals:
        if len(totals) != 1 or min(totals) < lower:
            return unknown("Tổng kinh nghiệm trong CV chưa nhất quán với các giai đoạn làm việc.")
        return compare(totals.pop(), condition.operator, condition.months, " tháng")
    op, threshold = condition.operator, condition.months
    if relevant and op in (">", ">=") and COMPARE[op](lower, threshold):
        return "met", f"CV xác nhận ít nhất {lower} tháng kinh nghiệm phù hợp."
    if relevant and op in ("<", "<=", "=") and (lower > threshold or (op == "<" and lower == threshold)):
        return "not_met", f"Ít nhất {lower} tháng đã xác nhận, vượt giới hạn trong JD."
    uncertain = [r for r in records if r.relevance == "unknown" and r.scope == "role"]
    if len(uncertain) == 1 and uncertain[0].months:
        return unknown(f"Đã xác nhận ít nhất {lower} tháng. Có giai đoạn {uncertain[0].months} tháng chưa rõ lĩnh vực.")
    if not records:
        return unknown("Chưa tìm thấy bằng chứng về thời gian làm việc trong lĩnh vực yêu cầu.")
    return unknown(f"Đã xác nhận ít nhất {lower} tháng. CV chưa xác định đủ tổng thời gian trong lĩnh vực yêu cầu.")


def evaluate(condition, records) -> Outcome:
    if isinstance(condition, Education):
        return education(condition, records)
    if isinstance(condition, GPA):
        return grade(condition, records)
    if isinstance(condition, Experience):
        return experience(condition, records)
    return unknown("Điều kiện này cần được đối chiếu thủ công.")
