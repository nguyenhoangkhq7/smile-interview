"""Read the current AI configuration from the authenticated backend for each AI request."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.responses import JSONResponse

TOKEN_HEADER = "X-Smile-Runtime-Token"
TOKEN_CONTEXT = b"smile-ai-runtime-client-v1"
PAYLOAD_CONTEXT = b"smile-ai-runtime-response-v1"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Runtime:
    revision: int = 0
    settings: dict | None = None
    credentials: dict[str, str] = field(default_factory=dict, repr=False)


active: ContextVar[Runtime] = ContextVar("smile_ai_runtime", default=Runtime())


def model_value(name: str, default):
    settings = active.get().settings
    return settings["models"].get(name, default) if settings else default


def policy_value(name: str, default):
    settings = active.get().settings
    return settings["policy"].get(name, default) if settings else default


def credential(name: str, default: str = "") -> str:
    return active.get().credentials.get(name, default)


def openrouter_id(value: str) -> str:
    return value.removeprefix("openrouter/")


def key_bytes() -> bytes:
    default = Path(__file__).resolve().parents[2] / ".runtime" / "ai-runtime.key"
    key = Path(os.getenv("AI_RUNTIME_KEY_FILE", str(default))).read_bytes()
    if len(key) != 32:
        raise ValueError("Invalid AI runtime key length")
    return key


def machine_token(key: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.digest(key, TOKEN_CONTEXT, hashlib.sha256)).decode().rstrip("=")


def decode_runtime(encoded: str, key: bytes) -> Runtime:
    message = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    value = json.loads(AESGCM(key).decrypt(message[:12], message[12:], PAYLOAD_CONTEXT))
    return Runtime(value["revision"], value["settings"], value["credentials"])


def authorized(token: str | None) -> bool:
    try:
        return bool(token and hmac.compare_digest(token.encode(), machine_token(key_bytes()).encode()))
    except (OSError, ValueError):
        return False


async def runtime_middleware(request, call_next):
    backend = os.getenv("AI_RUNTIME_BACKEND_URL", "").strip().rstrip("/")
    path = request.url.path
    runtime_paths = ("/internal/runtime/status", "/internal/runtime/probe")
    internal_path = path.rstrip("/")
    internal_runtime = internal_path in runtime_paths
    if (internal_runtime or internal_path == "/internal/runtime/quality") and not authorized(request.headers.get(TOKEN_HEADER)):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    if not backend or not (path.startswith(("/api/v1/", "/api/v2/")) or internal_runtime):
        return await call_next(request)
    try:
        key = key_bytes()
        response = await request.app.state.ai_runtime_http.get(
            backend + "/api/internal/ai-runtime", headers={TOKEN_HEADER: machine_token(key)}
        )
        response.raise_for_status()
        runtime = decode_runtime(response.json()["payload"], key)
    except (OSError, ValueError, KeyError, TypeError, InvalidTag, httpx.HTTPError) as error:
        logger.warning("AI runtime configuration unavailable (%s)", type(error).__name__)
        return JSONResponse({"detail": "AI runtime configuration is temporarily unavailable."}, status_code=503)
    token = active.set(runtime)
    try:
        return await call_next(request)
    finally:
        active.reset(token)
