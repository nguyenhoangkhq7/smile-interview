"""Audio-backed recognition only: no text rewriting or answer generation."""
import logging
import re
import time

import httpx

log = logging.getLogger(__name__)

# Canonical spellings; only relevant families are sent, never expected answers.
TERM_FAMILIES = (
    ("java|spring", ["Java", "Spring Boot", "Spring Security", "dependency injection", "JPA", "Hibernate", "JVM"]),
    ("sql|database|dữ liệu|transaction|postgres|postgresql|mysql", ["SQL", "PostgreSQL", "MySQL", "transaction", "commit", "rollback", "ACID", "deadlock", "index"]),
    ("react|javascript|typescript|frontend", ["React", "Next.js", "JavaScript", "TypeScript", "useEffect", "useState"]),
    ("docker|kubernetes|devops|cloud", ["Docker", "Kubernetes", "CI/CD", "container", "deployment"]),
    ("api|backend|http|rest", ["REST API", "HTTP", "JWT", "OAuth", "middleware", "microservices"]),
    ("python|machine learning|ai", ["Python", "FastAPI", "NumPy", "PyTorch", "embedding", "overfitting"]),
    ("cache|redis|kafka|distributed|phân tán", ["Redis", "Kafka", "cache", "message queue", "eventual consistency"]),
)


def vocabulary(terms: list[str], topic: str) -> list[str]:
    context = " ".join([topic, *terms]).casefold()
    selected = [term.strip() for term in terms if term.strip()]
    for cues, family in TERM_FAMILIES:
        if re.search(r"\b(?:" + cues + r")\b", context):
            selected.extend(family)
    # Retain English identifiers mentioned in the question, not its full prose.
    selected.extend(re.findall(r"\b[A-Za-z][A-Za-z0-9.+/#-]{2,40}\b", topic))
    seen = set()
    result = []
    for term in selected:
        key = term.casefold()
        if key not in seen and len(term) <= 100:
            seen.add(key)
            result.append(term)
    return result[:80]


def request_body(model: str, audio: str, terms: list[str]) -> dict:
    body = {"model": model, "input_audio": {"data": audio, "format": "wav"}, "response_format": "json"}
    if model == "microsoft/mai-transcribe-2":
        body.update(response_format="verbose_json", timestamp_granularities=["word"])
        body["provider"] = {"options": {"azure": {
            "phraseList": {"phrases": terms},
            "enhancedMode": {"modelOptions": {"transcribeStyle": "verbatim"}},
        }}}
        # Auto language detection preserves Vietnamese/English code switching.
    elif model == "openai/gpt-transcribe":
        body["provider"] = {"options": {"openai": {
            "languages": ["vi", "en"], "keywords": terms,
            "prompt": "Phỏng vấn kỹ thuật bằng tiếng Việt xen thuật ngữ tiếng Anh. Ghi nguyên lời nói; không dịch, không bổ sung hoặc sửa kiến thức.",
        }}}
    elif model == "openai/gpt-4o-transcribe":
        body["language"] = "vi"
        body["provider"] = {"options": {"openai": {
            "prompt": "Phỏng vấn kỹ thuật bằng tiếng Việt xen thuật ngữ tiếng Anh. Từ vựng có thể xuất hiện: " + ", ".join(terms),
        }}}
    else:
        body["language"] = "vi"
    return body


async def recognize(client: httpx.AsyncClient, endpoint: str, auth: dict, model: str,
                    audio: str, terms: list[str], check_provider) -> dict:
    started = time.perf_counter()
    response = await client.post(endpoint, headers=auth, json=request_body(model, audio, terms))
    check_provider(response)
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        raise ValueError("Missing transcript")
    text = data["text"].strip()
    if not text:
        raise ValueError("Empty transcript")
    log.info("STT request: model=%s elapsed_ms=%d", model, (time.perf_counter() - started) * 1000)
    return {"text": text}


async def transcribe_audio(client, endpoint, auth, cfg, payload, check_provider):
    terms = vocabulary(payload.terms, payload.topic)
    result = await recognize(client, endpoint, auth, cfg["stt_model"], payload.audio, terms, check_provider)
    # Preserve the wire contract for existing clients; no second model, comparison,
    # rewriting or confirmation gate. Legacy verifier environment variables are ignored.
    return {**result, "phase": payload.phase, "review_required": False, "verification": "not_requested"}
