import json

import httpx
import pytest

from tests_voice.test_voice_api import client, provider, recording  # noqa: F401
from voice.recognition import vocabulary


@pytest.mark.parametrize("phase", ["preview", "final"])
def test_one_request_even_with_legacy_verifier_configuration(client, monkeypatch, phase):
    monkeypatch.delenv("OPENROUTER_STT_MODEL")
    monkeypatch.setenv("OPENROUTER_STT_VERIFIER_MODEL", "openai/gpt-4o-transcribe")
    calls = []
    audio = recording()
    transcript = "Thì tôi sẽ nêu rõ cái vai trò của con AI và output mong muốn."
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["model"] == "openai/gpt-transcribe"
        assert body["input_audio"]["data"] == audio
        options = body["provider"]["options"]["openai"]
        assert options["languages"] == ["vi", "en"]
        assert "PostgreSQL" in options["keywords"]
        assert "language" not in body
        return httpx.Response(200, json={"text": transcript})
    provider(monkeypatch, handle)
    response = client.post("/api/v2/voice/transcribe", json={"audio": audio, "phase": phase, "terms": ["PostgreSQL"]})
    assert response.status_code == 200
    assert response.json() == {"text": transcript, "phase": phase, "review_required": False, "verification": "not_requested"}
    assert len(calls) == 1
    assert "stt_verifier_model" not in client.get("/api/v2/voice/config").json()


def test_mai_remains_an_explicit_single_model_override(client, monkeypatch):
    calls = []
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        azure = body["provider"]["options"]["azure"]
        assert body["model"] == "microsoft/mai-transcribe-2"
        assert body["response_format"] == "verbose_json"
        assert body["timestamp_granularities"] == ["word"]
        assert "language" not in body
        assert "Spring Boot" in azure["phraseList"]["phrases"]
        assert "transaction" in azure["phraseList"]["phrases"]
        assert azure["enhancedMode"]["modelOptions"]["transcribeStyle"] == "verbatim"
        return httpx.Response(200, json={"text": "Em dùng transaction trong Spring Boot."})
    provider(monkeypatch, handle)
    result = client.post("/api/v2/voice/transcribe", json={"audio": recording(),
        "terms": ["Java", "PostgreSQL"], "topic": "Xử lý transaction?"}).json()
    assert result["review_required"] is False
    assert len(calls) == 1


@pytest.mark.parametrize("failure,status", [("http", 429), ("timeout", 504), ("empty", 502), ("malformed", 502)])
def test_failure_is_retryable_and_never_calls_another_model(client, monkeypatch, failure, status):
    monkeypatch.setenv("OPENROUTER_STT_MODEL", "openai/gpt-transcribe")
    calls = []
    def handle(request):
        calls.append(json.loads(request.content)["model"])
        if failure == "http":
            return httpx.Response(429, json={"secret": "private-test-key"})
        if failure == "timeout":
            raise httpx.ReadTimeout("secret")
        return httpx.Response(200, json={"text": ""} if failure == "empty" else ["bad"])
    provider(monkeypatch, handle)
    response = client.post("/api/v2/voice/transcribe", json={"audio": recording()})
    assert response.status_code == status
    assert calls == ["openai/gpt-transcribe"]
    assert "private-test-key" not in response.text


def test_vocabulary_is_bounded_and_does_not_activate_unrelated_families():
    assert "PyTorch" not in vocabulary([], "Nói lại câu trả lời")
    assert "transaction" in vocabulary(["postgresql"], "")
    terms = vocabulary(["Java", "java", *[f"term{i}" for i in range(100)]], "")
    assert len(terms) == 80
    assert terms.count("Java") == 1
