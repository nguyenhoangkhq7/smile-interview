import base64
import io
import struct
import wave

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voice import routes


def recording():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(struct.pack("<h", 1000) * 8000)
    return base64.b64encode(out.getvalue()).decode()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    monkeypatch.setenv("INTERVIEW_VOICE_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_STT_MODEL", "microsoft/mai-transcribe-2")
    monkeypatch.setenv("OPENROUTER_TTS_MODEL", "google/gemini-3.8-flash-lite-tts")
    monkeypatch.setenv("OPENROUTER_TTS_VOICE", "Kore")
    monkeypatch.setenv("OPENROUTER_TTS_FORMAT", "pcm")
    monkeypatch.setenv("OPENROUTER_TTS_SAMPLE_RATE", "24000")
    monkeypatch.delenv("SIMLI_API_KEY", raising=False)
    monkeypatch.delenv("SIMLI_FACE_ID", raising=False)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as test:
        yield test


def provider(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr(routes.httpx, "AsyncClient", lambda **kwargs:
        factory(transport=httpx.MockTransport(handler), **kwargs))


def test_config_never_returns_credentials(client, monkeypatch):
    response = client.get("/api/v2/voice/config")
    assert response.json()["enabled"] is True
    assert "private-test-key" not in response.text
    monkeypatch.setenv("INTERVIEW_VOICE_ENABLED", "false")
    assert client.post("/api/v2/voice/transcribe", json={"audio": recording()}).status_code == 503


def test_transcription_uses_dedicated_openrouter_endpoint(client, monkeypatch):
    import json
    def handle(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer private-test-key"
        body = json.loads(request.content)
        assert body["model"] == "qwen/qwen3-asr-1.7b"
        assert body["input_audio"]["format"] == "wav"
        assert body["language"] == "vi"
        assert base64.b64decode(body["input_audio"]["data"])[:4] == b"RIFF"
        return httpx.Response(200, json={"text": " Em dùng transaction. "})
    monkeypatch.setenv("OPENROUTER_STT_MODEL", "qwen/qwen3-asr-1.7b")
    provider(monkeypatch, handle)
    response = client.post("/api/v2/voice/transcribe", json={"audio": recording(), "phase": "preview"})
    assert response.status_code == 200
    assert response.json()["text"] == "Em dùng transaction."
    assert response.json()["phase"] == "preview"


def test_rejects_invalid_audio_before_charging_provider(client, monkeypatch):
    provider(monkeypatch, lambda _: pytest.fail("Invalid recordings must not reach OpenRouter"))
    for audio in ["!" * 100, base64.b64encode(b"bad audio" * 100).decode()]:
        assert client.post("/api/v2/voice/transcribe", json={"audio": audio}).status_code == 422


@pytest.mark.parametrize("upstream,status", [(402, 503), (401, 503), (429, 429), (400, 502)])
def test_errors_are_actionable_and_do_not_leak_provider_body(client, monkeypatch, upstream, status):
    provider(monkeypatch, lambda _: httpx.Response(upstream, json={"secret": "private-test-key", "audio": recording()}))
    response = client.post("/api/v2/voice/transcribe", json={"audio": recording()})
    assert response.status_code == status
    assert "private-test-key" not in response.text


def test_streaming_audio_and_markdown_question(client, monkeypatch):
    import json
    def handle(request):
        assert request.url.path == "/api/v1/audio/speech"
        body = json.loads(request.content)
        assert body["response_format"] == "pcm"
        assert "instructions" in body
        assert "```" not in body["input"] and "SELECT" not in body["input"]
        return httpx.Response(200, headers={"Content-Type": "audio/pcm"}, content=b"\x00\x01" * 64)
    monkeypatch.setenv("OPENROUTER_TTS_MODEL", "google/gemini-3.8-flash-lite-tts")
    provider(monkeypatch, handle)
    response = client.post("/api/v2/voice/speech", json={"text": "## Câu hỏi\nĐọc code:\n```sql\nSELECT 1;\n```\nGiải thích?"})
    assert response.status_code == 200
    assert response.headers["x-audio-sample-rate"] == "24000"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == b"\x00\x01" * 64


def test_tts_failure_is_json_before_stream_starts(client, monkeypatch):
    provider(monkeypatch, lambda _: httpx.Response(402, json={"error": "private-test-key"}))
    response = client.post("/api/v2/voice/speech", json={"text": "Xin chào"})
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert "private-test-key" not in response.text


def test_wrong_provider_format_does_not_become_audio(client, monkeypatch):
    provider(monkeypatch, lambda _: httpx.Response(200, json={"error": "No audio"}))
    assert client.post("/api/v2/voice/speech", json={"text": "Xin chào"}).status_code == 502


def test_free_heygen_defaults_and_native_pcm(client, monkeypatch):
    import json
    for name in ("OPENROUTER_TTS_MODEL", "OPENROUTER_TTS_VOICE", "OPENROUTER_TTS_FORMAT",
                 "OPENROUTER_TTS_SAMPLE_RATE"):
        monkeypatch.delenv(name, raising=False)
    cfg = client.get("/api/v2/voice/config").json()
    assert (cfg["tts_model"], cfg["voice"], cfg["format"], cfg["sample_rate"]) == (
        "heygen/heygen-voice-1-turbo:free", "nadine", "pcm", 44100)

    def handle(request):
        assert json.loads(request.content) == {
            "model": "heygen/heygen-voice-1-turbo:free", "voice": "nadine",
            "input": "Xin chào", "response_format": "pcm"}
        return httpx.Response(200, headers={"Content-Type": "audio/pcm"}, content=b"\x00\x01" * 64)
    provider(monkeypatch, handle)
    response = client.post("/api/v2/voice/speech", json={"text": "Xin chào"})
    assert response.status_code == 200
    assert response.headers["x-audio-sample-rate"] == "44100"
    assert response.headers["x-audio-format"] == "pcm"
    assert response.content == b"\x00\x01" * 64


@pytest.mark.parametrize("audio_format,sample_rate", [("mp3", "44100"), ("pcm", "24000")])
def test_heygen_rejects_incompatible_audio_config(client, monkeypatch, audio_format, sample_rate):
    monkeypatch.setenv("OPENROUTER_TTS_MODEL", "heygen/heygen-voice-1-turbo:free")
    monkeypatch.setenv("OPENROUTER_TTS_FORMAT", audio_format)
    monkeypatch.setenv("OPENROUTER_TTS_SAMPLE_RATE", sample_rate)
    provider(monkeypatch, lambda _: pytest.fail("Bad server config must not reach OpenRouter"))
    response = client.post("/api/v2/voice/speech", json={"text": "Xin chào"})
    assert response.status_code == 503
    assert "44100" in response.json()["detail"]


def test_heygen_character_limit_keeps_provider_errors_actionable(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_TTS_MODEL", "heygen/heygen-voice-1-turbo:free")
    monkeypatch.setenv("OPENROUTER_TTS_SAMPLE_RATE", "44100")
    provider(monkeypatch, lambda _: pytest.fail("Oversized text must not reach OpenRouter"))
    response = client.post("/api/v2/voice/speech", json={"text": "a" * 5001})
    assert response.status_code == 422
    assert "5.000" in response.json()["detail"]


def test_simli_requires_server_configuration_before_request(client, monkeypatch):
    assert client.get('/api/v2/voice/config').json()['avatar'] == {
        'provider': 'simli', 'configured': False, 'sample_rate': 16000}
    provider(monkeypatch, lambda _: pytest.fail('Unconfigured avatar must not call Simli'))
    assert client.post('/api/v2/voice/avatar-session', json={'max_session_length': 60}).status_code == 503


def test_simli_token_uses_private_key_and_returns_only_session_token(client, monkeypatch):
    import json
    monkeypatch.setenv('SIMLI_API_KEY', 'private-simli-key')
    monkeypatch.setenv('SIMLI_FACE_ID', 'server-face')
    def handle(request):
        assert str(request.url) == 'https://api.simli.ai/compose/token'
        assert request.headers['x-simli-api-key'] == 'private-simli-key'
        assert json.loads(request.content) == {
            'faceId': 'server-face', 'handleSilence': True, 'maxSessionLength': 600,
            'maxIdleTime': 300, 'audioInputFormat': 'pcm16'}
        return httpx.Response(200, json={'session_token': 'short-lived-token', 'api_key': 'must-not-leak'})
    provider(monkeypatch, handle)
    cfg = client.get('/api/v2/voice/config')
    assert cfg.json()['avatar']['configured'] is True
    assert 'private-simli-key' not in cfg.text and 'server-face' not in cfg.text
    response = client.post('/api/v2/voice/avatar-session', json={'max_session_length': 600})
    assert response.status_code == 200
    assert response.json() == {'session_token': 'short-lived-token'}
    assert client.post('/api/v2/voice/avatar-session', json={'max_session_length': 7201}).status_code == 422


@pytest.mark.parametrize('upstream,expected', [(401, 503), (402, 503), (422, 503), (429, 429)])
def test_simli_errors_do_not_expose_provider_secrets(client, monkeypatch, upstream, expected):
    monkeypatch.setenv('SIMLI_API_KEY', 'private-simli-key')
    monkeypatch.setenv('SIMLI_FACE_ID', 'server-face')
    provider(monkeypatch, lambda _: httpx.Response(upstream, json={'detail': 'private-simli-key'}))
    response = client.post('/api/v2/voice/avatar-session', json={'max_session_length': 60})
    assert response.status_code == expected
    assert 'private-simli-key' not in response.text


def test_simli_rejects_false_tokens_and_non_pcm_config(client, monkeypatch):
    monkeypatch.setenv('SIMLI_API_KEY', 'private-simli-key')
    monkeypatch.setenv('SIMLI_FACE_ID', 'server-face')
    provider(monkeypatch, lambda _: httpx.Response(200, json={'session_token': 'FAIL TOKEN'}))
    assert client.post('/api/v2/voice/avatar-session', json={'max_session_length': 60}).status_code == 502
    monkeypatch.setenv('OPENROUTER_TTS_FORMAT', 'mp3')
    provider(monkeypatch, lambda _: pytest.fail('Invalid TTS config must not spend Simli credits'))
    assert client.post('/api/v2/voice/avatar-session', json={'max_session_length': 60}).status_code == 503
