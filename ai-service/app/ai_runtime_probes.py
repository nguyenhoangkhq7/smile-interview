"""On-demand latency checks using fixed sample inputs and the active AI configuration."""
import asyncio
import base64
import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from pathlib import Path
from threading import Lock
from time import perf_counter

from fastapi import HTTPException

from adaptive_questioning.evidence.provider import configured_lm
from app.ai_runtime import credential
from matching_cv.app.core.config import settings as matching
from matching_cv.app.services.semantic_embedding_service import SemanticEmbeddingService
from voice.routes import AvatarSession, Speech, Transcription, avatar_session, settings, speech, transcribe

log = logging.getLogger(__name__)
PROBE_TIMEOUT_SECONDS = 12
SAMPLE_TEXT = "Xin chào."
SAMPLE_AUDIO = Path(__file__).with_name("latency_check.wav")
_batch_lock = asyncio.Lock()
_embedding_lock = Lock()


def _result(check_id: str, status: str, detail: str, latency_ms: int | None = None) -> dict:
    return {"id": check_id, "status": status, "detail": detail, "latencyMs": latency_ms}


async def _measure(check_id: str, detail: str, operation: Callable[[], Awaitable[None]]) -> dict:
    started = perf_counter()
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
            await operation()
        return _result(check_id, "UP", detail, int((perf_counter() - started) * 1000))
    except Exception as error:
        log.warning("Admin AI probe failed: service=%s error=%s", check_id, type(error).__name__)
        timed_out = isinstance(error, TimeoutError) or isinstance(error, HTTPException) and error.status_code == 504
        reason = "Quá thời gian" if timed_out else "Phép thử thất bại"
        return _result(check_id, "DOWN", f"{detail} · {reason}", int((perf_counter() - started) * 1000))


def _encode_sample() -> None:
    # Native inference or a model load can continue in the thread after the HTTP deadline.
    if not _embedding_lock.acquire(blocking=False):
        raise HTTPException(429)
    try:
        SemanticEmbeddingService().encode_batch([SAMPLE_TEXT])
    finally:
        _embedding_lock.release()


async def _embedding() -> None:
    await asyncio.to_thread(_encode_sample)


async def _dspy() -> None:
    replies = await configured_lm().acall(prompt="Reply with OK.", max_tokens=16)
    if not replies or not isinstance(replies[0], str) or not replies[0].strip():
        raise ValueError("Missing model reply")


def _sample_audio_bytes() -> bytes:
    if SAMPLE_AUDIO.is_file():
        return SAMPLE_AUDIO.read_bytes()
    import io
    import math
    import struct
    import wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        frames = bytearray()
        for i in range(8000):
            val = int(2500 * math.sin(2 * math.pi * 440 * i / 16000))
            frames.extend(struct.pack("<h", val))
        wav.writeframes(frames)
    return buffer.getvalue()


async def _stt() -> None:
    audio = base64.b64encode(_sample_audio_bytes()).decode("ascii")
    await transcribe(Transcription(audio=audio))


async def _tts() -> None:
    audio = await speech(Speech(text=SAMPLE_TEXT))
    async with aclosing(audio.body_iterator) as chunks:
        async for chunk in chunks:
            if chunk:
                return
    raise ValueError("Missing speech audio")


async def _simli() -> None:
    await avatar_session(AvatarSession(max_session_length=60))


async def _voice(config: dict) -> list[dict]:
    if not config["enabled"]:
        return [_result("voice", "DISABLED", "OpenRouter STT/TTS")]
    stt, tts = await asyncio.gather(
        _measure("stt", "Phiên âm mẫu", _stt),
        _measure("tts", "Nhận phần âm thanh đầu tiên", _tts),
    )
    passed = sum(check["status"] == "UP" for check in (stt, tts))
    status = ("DOWN", "DEGRADED", "UP")[passed]
    return [_result("voice", status, "Đo nhận diện và tổng hợp giọng nói"), stt, tts]


async def _provider(check_id: str, enabled: bool, detail: str, operation: Callable[[], Awaitable[None]]) -> dict:
    if not enabled:
        return _result(check_id, "DISABLED", detail)
    return await _measure(check_id, detail, operation)


async def measure_runtime() -> list[dict]:
    if _batch_lock.locked():
        raise HTTPException(429, "A latency check is already running.")
    async with _batch_lock:
        cfg = settings()
        openrouter = bool(credential("openRouterKey", os.getenv("OPENROUTER_API_KEY", "")).strip())
        embedding, dspy, voice, simli = await asyncio.gather(
            _measure("embedding", f"Mã hóa câu mẫu · {matching.STAGE3_MODEL_NAME}", _embedding),
            _provider("dspy", openrouter, "Sinh phản hồi mẫu", _dspy),
            _voice(cfg),
            _provider("simli", cfg["enabled"] and cfg["avatar"]["configured"] and cfg["format"] == "pcm",
                      "Cấp token phiên avatar", _simli),
        )
        return [embedding, dspy, *voice, simli]
