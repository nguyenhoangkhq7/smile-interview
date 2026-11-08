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


async def main(tts_only: bool = False):
    cfg = settings()
    if cfg["format"] != "pcm":
        raise RuntimeError("The live round-trip check needs OPENROUTER_TTS_FORMAT=pcm")
    response = await speech(Speech(text="Xin chào, tôi muốn luyện phỏng vấn về cơ sở dữ liệu."))
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
    result = await transcribe(Transcription(audio=base64.b64encode(out.getvalue()).decode()))
    if not result["text"]:
        raise RuntimeError("Provider returned an empty transcript")
    print(f"PASS: OpenRouter TTS ({cfg['tts_model']}) -> WAV -> STT ({cfg['stt_model']})")
    print("Synthetic transcript:", result["text"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tts-only", action="store_true", help="Only test synthesis; do not call the paid STT model")
    args = parser.parse_args()
    try:
        asyncio.run(main(tts_only=args.tts_only))
    except HTTPException as exc:
        print(f"Voice check failed ({exc.status_code}): {exc.detail}")
        sys.exit(1)
