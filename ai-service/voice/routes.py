"""Internal-only voice API. The authenticated Java backend owns interview state."""
import base64
import binascii
import io
import logging
import os
import re
import wave

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v2/voice", tags=["Interview voice"])
log = logging.getLogger(__name__)
OPENROUTER = "https://openrouter.ai/api/v1"
MAX_AUDIO_BYTES = 1_500_000  # 45 seconds of 16 kHz, mono, signed 16-bit WAV


class Transcription(BaseModel):
    audio: str = Field(min_length=60, max_length=2_000_000)


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=16000)


class AvatarSession(BaseModel):
    max_session_length: int = Field(ge=1, le=7200)


def settings() -> dict:
    tts_model = os.getenv("OPENROUTER_TTS_MODEL", "heygen/heygen-voice-1-turbo:free")
    heygen = tts_model.startswith("heygen/")
    return {
        "enabled": bool(os.getenv("OPENROUTER_API_KEY"))
        and os.getenv("INTERVIEW_VOICE_ENABLED", "true").lower() == "true",
        "stt_model": os.getenv("OPENROUTER_STT_MODEL", "qwen/qwen3-asr-1.7b"),
        "tts_model": tts_model,
        "voice": os.getenv("OPENROUTER_TTS_VOICE", "nadine" if heygen else "Kore"),
        "format": os.getenv("OPENROUTER_TTS_FORMAT", "pcm"),
        "sample_rate": int(os.getenv("OPENROUTER_TTS_SAMPLE_RATE", "44100" if heygen else "24000")),
        "language": "vi",
        "avatar": {"provider": "simli", "configured": bool(os.getenv("SIMLI_API_KEY", "").strip())
                   and bool(os.getenv("SIMLI_FACE_ID", "").strip()), "sample_rate": 16000},
    }


def headers() -> dict[str, str]:
    if not settings()["enabled"]:
        raise HTTPException(503, "Giọng nói chưa được cấu hình trên máy chủ.")
    return {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json", "X-Title": "Smile Interview"}


def check_provider(response: httpx.Response) -> None:
    if response.is_success:
        return
    # Never return upstream bodies: they may contain the input audio or credentials.
    log.warning("OpenRouter voice request failed: status=%s", response.status_code)
    if response.status_code == 429:
        raise HTTPException(429, "Dịch vụ giọng nói đang quá tải. Hãy thử lại sau.")
    if response.status_code == 402:
        raise HTTPException(503, "Tài khoản OpenRouter không đủ số dư cho giọng nói.")
    if response.status_code in (401, 403):
        raise HTTPException(503, "Máy chủ chưa có quyền gọi model giọng nói OpenRouter.")
    raise HTTPException(502, "Model giọng nói không xử lý được yêu cầu. Hãy kiểm tra cấu hình model và giọng đọc.")


@router.get("/config")
async def config():
    return settings()


@router.post("/avatar-session")
async def avatar_session(payload: AvatarSession):
    cfg = settings()
    if not cfg["enabled"]:
        raise HTTPException(503, "Giọng nói chưa được cấu hình trên máy chủ.")
    if not cfg["avatar"]["configured"]:
        raise HTTPException(503, "Dịch vụ avatar Simli chưa được cấu hình trên máy chủ.")
    if cfg["format"] != "pcm":
        raise HTTPException(503, "Simli cần giọng đọc định dạng PCM trên máy chủ.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10)) as client:
            response = await client.post("https://api.simli.ai/compose/token",
                headers={"x-simli-api-key": os.environ["SIMLI_API_KEY"].strip(), "Content-Type": "application/json"},
                json={"faceId": os.environ["SIMLI_FACE_ID"].strip(), "handleSilence": True,
                      "maxSessionLength": payload.max_session_length,
                      "maxIdleTime": min(300, payload.max_session_length), "audioInputFormat": "pcm16"})
        if not response.is_success:
            log.warning("Simli session token failed: status=%s", response.status_code)
            if response.status_code == 429:
                raise HTTPException(429, "Simli đang giới hạn số phiên. Hãy thử lại sau.")
            raise HTTPException(503, "Không tạo được phiên Simli. Hãy kiểm tra API key, Face ID và hạn mức trên máy chủ.")
        token = response.json().get("session_token")
        if not isinstance(token, str) or not token.strip() or token == "FAIL TOKEN":
            raise ValueError("Invalid token")
        return {"session_token": token}
    except httpx.TimeoutException:
        raise HTTPException(504, "Kết nối Simli quá thời gian. Hãy thử lại.") from None
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise HTTPException(502, "Không kết nối được dịch vụ avatar Simli.") from None


@router.post("/transcribe")
async def transcribe(payload: Transcription):
    auth = headers()
    try:
        audio = base64.b64decode(payload.audio, validate=True)
        if len(audio) > MAX_AUDIO_BYTES:
            raise ValueError()
        with wave.open(io.BytesIO(audio)) as wav:
            duration = wav.getnframes() / wav.getframerate()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2
                    or wav.getframerate() != 16000 or not 0.15 <= duration <= 45):
                raise ValueError()
    except (binascii.Error, ValueError, wave.Error, EOFError, ZeroDivisionError):
        raise HTTPException(422, "Âm thanh phải là WAV mono 16 kHz, 16 bit, tối đa 45 giây.") from None
    cfg = settings()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
            response = await client.post(f"{OPENROUTER}/audio/transcriptions", headers=auth,
                json={"model": cfg["stt_model"], "input_audio": {"data": payload.audio, "format": "wav"},
                      "language": "vi", "response_format": "json"})
        check_provider(response)
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("Missing transcript")
        log.info("Voice transcription: model=%s audio_seconds=%.2f", cfg["stt_model"], duration)
        return {"text": result["text"].strip()}
    except httpx.TimeoutException:
        raise HTTPException(504, "Nhận diện giọng nói quá thời gian. Bản ghi vẫn được giữ để thử lại.") from None
    except httpx.HTTPError:
        raise HTTPException(502, "Không kết nối được OpenRouter. Hãy thử lại bản ghi.") from None
    except (ValueError, TypeError):
        raise HTTPException(502, "OpenRouter trả về bản nhận diện không hợp lệ.") from None


def spoken_text(text: str) -> str:
    # Preserve the original question in V2; speech is only a presentation of it.
    text = re.sub(r"```[\s\S]*?```", " Bạn có thể giải thích cách xử lý bằng lời, không cần viết code. ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"[`*_]", "", text)
    return text.strip()


@router.post("/speech")
async def speech(payload: Speech):
    cfg = settings()
    auth = headers()
    if cfg["format"] not in ("pcm", "mp3") or cfg["sample_rate"] not in (16000, 22050, 24000, 44100, 48000):
        raise HTTPException(503, "Cấu hình định dạng âm thanh trên máy chủ không hợp lệ.")
    if cfg["tts_model"].startswith("heygen/") and (cfg["format"] != "pcm" or cfg["sample_rate"] != 44100):
        raise HTTPException(503, "HeyGen yêu cầu OPENROUTER_TTS_FORMAT=pcm và OPENROUTER_TTS_SAMPLE_RATE=44100.")
    text = spoken_text(payload.text)
    if not text:
        raise HTTPException(422, "Câu hỏi không có nội dung để đọc.")
    if cfg["tts_model"].startswith("heygen/") and len(text) > 5000:
        raise HTTPException(422, "HeyGen chỉ hỗ trợ tối đa 5.000 ký tự đọc mỗi lần. Hãy rút gọn câu hỏi hoặc đổi model TTS.")
    body = {"model": cfg["tts_model"], "voice": cfg["voice"], "input": text,
            "response_format": cfg["format"]}
    if cfg["tts_model"].startswith("google/"):
        body["instructions"] = "Đọc bằng tiếng Việt tự nhiên, rõ ràng, như người phỏng vấn; giữ cách phát âm tiếng Anh của thuật ngữ kỹ thuật."
    client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10))
    try:
        response = await client.send(client.build_request("POST", f"{OPENROUTER}/audio/speech",
                                                        headers=auth, json=body), stream=True)
        if not response.is_success:
            await response.aread()
            check_provider(response)
        content_type = response.headers.get("content-type", "").split(";")[0]
        if content_type not in ("audio/pcm", "audio/mpeg", "application/octet-stream"):
            raise HTTPException(502, "OpenRouter không trả về âm thanh đúng định dạng.")
    except BaseException as exc:
        await client.aclose()
        if isinstance(exc, httpx.HTTPError):
            raise HTTPException(502, "Không kết nối được dịch vụ đọc giọng nói OpenRouter.") from None
        raise

    async def chunks():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    log.info("Voice synthesis: model=%s characters=%d", cfg["tts_model"], len(text))
    return StreamingResponse(chunks(), media_type="audio/pcm" if cfg["format"] == "pcm" else "audio/mpeg",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                 "X-Audio-Sample-Rate": str(cfg["sample_rate"]), "X-Audio-Format": cfg["format"]})
