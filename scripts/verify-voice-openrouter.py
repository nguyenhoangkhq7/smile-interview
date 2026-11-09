"""Opt-in live check: synthesizes one synthetic Vietnamese sentence and transcribes it.

Uses the existing server key; incurs a small amount of OpenRouter usage. No CV/JD data.
Run from the repository with the AI service Python environment.
"""
import asyncio
import argparse
import base64
import io
from pathlib import Path
import sys
import wave

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ai-service"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "ai-service" / ".env", override=True)
from fastapi import HTTPException
from voice.routes import Speech, Transcription, settings, speech, transcribe


async def main(tts_only: bool = False, audio_file: str | None = None, save_audio: str | None = None):
    cfg = settings()
    if cfg["format"] != "pcm":
        raise RuntimeError("The live round-trip check needs OPENROUTER_TTS_FORMAT=pcm")
    if audio_file:
        return await recognize_recording(Path(audio_file).read_bytes(), cfg)
    response = await speech(Speech(text="Trong Spring Boot, em dùng transaction với PostgreSQL. Khi có lỗi thì rollback."))
    audio = bytearray()
    async for chunk in response.body_iterator:
        audio.extend(chunk)
        if len(audio) > 4_000_000:
            raise RuntimeError("Unexpectedly large speech response")
    if len(audio) < 1000 or len(audio) % 2:
        raise RuntimeError("Invalid PCM response")
    if tts_only:
        print(f"PASS: OpenRouter TTS ({cfg['tts_model']}), voice={cfg['voice']}, "
              f"PCM {cfg['sample_rate']} Hz, bytes={len(audio)}")
        return
    # A simple average downsample is sufficient for this synthetic smoke recording.
    import numpy as np
    samples = np.frombuffer(audio, dtype="<i2").astype(np.float64)
    target = np.interp(np.arange(int(len(samples) * 16000 / cfg["sample_rate"]))
                       * cfg["sample_rate"] / 16000, np.arange(len(samples)), samples).astype("<i2")
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(target.tobytes())
    if save_audio:
        Path(save_audio).write_bytes(out.getvalue())
    await recognize_recording(out.getvalue(), cfg)


async def recognize_recording(audio: bytes, cfg: dict):
    result = await transcribe(Transcription(audio=base64.b64encode(audio).decode(),
        terms=["Spring Boot", "PostgreSQL", "transaction", "rollback"], topic="Phỏng vấn Java Backend"))
    if not result["text"]:
        raise RuntimeError("Provider returned an empty transcript")
    print(f"STT: {cfg['stt_model']}; single model, no verification call")
    print("Transcript:", result["text"])
    if result['review_required'] or 'alternative_text' in result:
        raise RuntimeError("Unexpected comparison response in single-model mode")
    print("PASS: the selected STT model accepted the audio and provider options.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tts-only", action="store_true", help="Only test synthesis; do not call the paid STT model")
    parser.add_argument("--audio-file", help="Use an existing mono 16 kHz PCM16 WAV instead of synthesis")
    parser.add_argument("--save-audio", help="Save the synthetic WAV for STT-only retries or comparisons")
    args = parser.parse_args()
    try:
        asyncio.run(main(tts_only=args.tts_only, audio_file=args.audio_file, save_audio=args.save_audio))
    except HTTPException as exc:
        print(f"Voice check failed ({exc.status_code}): {exc.detail}")
        sys.exit(1)
