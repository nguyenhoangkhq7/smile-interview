"""Two-stage extraction with validation before rule evaluation."""
import json
import logging

from .models import ConditionResult, EligibilityReport, Observations, Requirements
from .prompts import CV_PROMPT, JD_PROMPT
from .rules import evaluate, unknown

logger = logging.getLogger(__name__)


def grounded(quote: str, source: str) -> bool:
    return " ".join(quote.split()) in " ".join(source.split())


async def extract_json(prompt, payload, schema):
    from openai import AsyncOpenAI
    from matching_cv.app.core.config import settings

    key = settings.OPENROUTER_API_KEY
    if not key or key in ("not_configured", "your_openrouter_api_key_here"):
        raise ValueError("Missing matching model credentials")
    async with AsyncOpenAI(api_key=key, base_url=settings.OPENROUTER_BASE_URL,
                           timeout=settings.PIPELINE_LLM_TIMEOUT_SECONDS, max_retries=0) as client:
        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": prompt + "\nJSON schema:\n" + json.dumps(schema.model_json_schema())},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0, response_format={"type": "json_object"},
        )
    return schema.model_validate_json(response.choices[0].message.content or "")


def group_evidence(observations, conditions, cv_text):
    records = {key: [] for key in conditions}
    invalid = set()
    for item in observations.records:
        key = item.condition_id
        if key not in conditions or item.type != conditions[key].type or not grounded(item.quote, cv_text):
            invalid.add(key)
        else:
            records[key].append(item)
    return records, invalid


async def collect_evidence(conditions, cv_text, extract):
    requested = {key: c.model_dump() for key, c in conditions.items() if c.type != "manual"}
    if requested:
        try:
            data = await extract(CV_PROMPT, {"conditions": requested, "cv": cv_text}, Observations)
            return group_evidence(data, conditions, cv_text)
        except Exception as error:
            logger.warning("Eligibility CV extraction unavailable (%s)", type(error).__name__)
            return {key: [] for key in conditions}, set(requested)
    return {key: [] for key in conditions}, set()


async def check_eligibility(cv_text: str, jd_text: str, extract=extract_json) -> EligibilityReport:
    try:
        parsed = await extract(JD_PROMPT, {"jd": jd_text}, Requirements)
    except Exception as error:
        logger.warning("Eligibility JD extraction unavailable (%s)", type(error).__name__)
        return EligibilityReport(state="unavailable")

    conditions = {f"C{i}": c for i, c in enumerate(parsed.conditions, 1) if grounded(c.quote, jd_text)}
    partial = len(conditions) != len(parsed.conditions)
    records, invalid = await collect_evidence(conditions, cv_text, extract)
    results = []
    source = " ".join(cv_text.split())
    for key, condition in conditions.items():
        evidence = sorted(records[key], key=lambda r: source.index(" ".join(r.quote.split())))
        status, reason = (unknown("Chưa xác minh được dữ liệu trích xuất từ CV.") if key in invalid
                          else evaluate(condition, evidence))
        results.append(ConditionResult(
            condition_id=key, type=condition.type, priority=condition.priority, jd_quote=condition.quote,
            cv_quotes=list(dict.fromkeys(r.quote for r in evidence)), status=status, reason=reason,
        ))
    return EligibilityReport(state="partial" if partial or invalid else "complete", results=results)
