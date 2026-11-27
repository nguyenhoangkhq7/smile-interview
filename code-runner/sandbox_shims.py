"""In-memory service shims and multi-argument invocation helpers for the isolated code-runner."""
from __future__ import annotations

import inspect
import json
from typing import Any
from urllib.parse import urlparse


def _parse_redis_db(url: str, default_db: int = 0) -> int:
    try:
        path = (urlparse(url).path or "").strip("/")
        return int(path) if path.isdigit() else default_db
    except ValueError:
        return default_db


def _install_redis_shim() -> bool:
    try:
        import fakeredis
        import redis
        import redis.client
    except ImportError:
        return False

    server = fakeredis.FakeServer()

    def _safe_db(raw: Any) -> int:
        try:
            return int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            return 0

    def _make_sync(*_args: Any, **kwargs: Any):
        return fakeredis.FakeRedis(
            server=server,
            db=_safe_db(kwargs.get("db", 0)),
            decode_responses=bool(kwargs.get("decode_responses", False)),
        )

    def _sync_from_url(url: str, **kwargs: Any):
        db = _safe_db(kwargs.get("db", _parse_redis_db(url)))
        return fakeredis.FakeRedis(
            server=server,
            db=db,
            decode_responses=bool(kwargs.get("decode_responses", False)),
        )

    _orig_sync_init = redis.Redis.__init__

    class _ShimmedRedis:
        # Preserve original signature so fakeredis's inspect.signature(redis.Redis.__init__)
        # retains parameters like db and decode_responses.
        __init__ = _orig_sync_init

        def __new__(cls, *args: Any, **kwargs: Any):
            return _make_sync(*args, **kwargs)

        @classmethod
        def from_url(cls, url: str, **kwargs: Any):
            return _sync_from_url(url, **kwargs)

    redis.Redis = _ShimmedRedis  # type: ignore[misc,assignment]
    redis.StrictRedis = _ShimmedRedis  # type: ignore[misc,assignment]
    redis.client.Redis = _ShimmedRedis  # type: ignore[misc,assignment]
    redis.client.StrictRedis = _ShimmedRedis  # type: ignore[misc,assignment]
    redis.from_url = _sync_from_url  # type: ignore[attr-defined]

    try:
        import fakeredis.aioredis
        import redis.asyncio as redis_async

        def _make_async(*_args: Any, **kwargs: Any):
            return fakeredis.aioredis.FakeRedis(
                server=server,
                db=_safe_db(kwargs.get("db", 0)),
                decode_responses=bool(kwargs.get("decode_responses", False)),
            )

        def _async_from_url(url: str, **kwargs: Any):
            db = _safe_db(kwargs.get("db", _parse_redis_db(url)))
            return fakeredis.aioredis.FakeRedis(
                server=server,
                db=db,
                decode_responses=bool(kwargs.get("decode_responses", False)),
            )

        _orig_async_init = redis_async.Redis.__init__

        class _ShimmedAsyncRedis:
            __init__ = _orig_async_init

            def __new__(cls, *args: Any, **kwargs: Any):
                return _make_async(*args, **kwargs)

            @classmethod
            def from_url(cls, url: str, **kwargs: Any):
                return _async_from_url(url, **kwargs)

        redis_async.Redis = _ShimmedAsyncRedis  # type: ignore[misc,assignment]
        redis_async.StrictRedis = _ShimmedAsyncRedis  # type: ignore[misc,assignment]
        redis_async.from_url = _async_from_url  # type: ignore[attr-defined]
    except ImportError:
        pass
    return True


def _install_mongo_shim() -> bool:
    try:
        import mongomock
        import pymongo
    except ImportError:
        return False

    shared_client = mongomock.MongoClient()

    class _ShimmedMongoClient:
        def __new__(cls, *_args: Any, **_kwargs: Any):
            return shared_client

    pymongo.MongoClient = _ShimmedMongoClient  # type: ignore[misc,assignment]
    if hasattr(pymongo, "mongo_client"):
        pymongo.mongo_client.MongoClient = _ShimmedMongoClient  # type: ignore[misc,assignment]
    return True


def active_shims() -> list[str]:
    names: list[str] = []
    try:
        import fakeredis  # noqa: F401
        import redis  # noqa: F401

        names.append("redis->fakeredis")
    except ImportError:
        pass
    try:
        import mongomock  # noqa: F401
        import pymongo  # noqa: F401

        names.append("pymongo->mongomock")
    except ImportError:
        pass
    return names


def install_shims() -> list[str]:
    """Patch supported client SDKs to per-process in-memory emulators."""
    installed: list[str] = []
    if _install_redis_shim():
        installed.append("redis->fakeredis")
    if _install_mongo_shim():
        installed.append("pymongo->mongomock")
    return installed


def _normalize_output(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (tuple, set)):
        return [_normalize_output(item) for item in value]
    if isinstance(value, list):
        return [_normalize_output(item) for item in value]
    if isinstance(value, dict):
        return {
            (k.decode("utf-8", errors="replace") if isinstance(k, bytes) else k): _normalize_output(v)
            for k, v in value.items()
        }
    return value


def resolve_entry_point(module: Any, entry_point: str) -> tuple[Any | None, str]:
    """Resolve the requested entry point, falling back cleanly when strictly one top-level function exists."""
    exact = getattr(module, entry_point, None)
    if callable(exact):
        return exact, ""
    candidates = [
        fn for name, fn in inspect.getmembers(module, inspect.isfunction)
        if getattr(fn, "__module__", None) == getattr(module, "__name__", None) and not name.startswith("_")
    ]
    if len(candidates) == 1:
        return candidates[0], ""
    if len(candidates) > 1:
        names = ", ".join(fn.__name__ for fn in candidates[:5])
        return None, f"Không tìm thấy hàm '{entry_point}' (đang có các hàm: {names})."
    return None, f"Không tìm thấy hàm '{entry_point}'."


def invoke_entry_point(fn: Any, raw_stdin: str) -> str:
    """Invoke a candidate function with JSON positional args, dict kwargs, or plain string fallback."""
    stripped = raw_stdin.strip()
    if stripped:
        try:
            arg: Any = json.loads(stripped)
        except ValueError:
            arg = stripped
    else:
        arg = None

    sig = inspect.signature(fn)
    positional = [
        p for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    kw_names = {
        p.name for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    has_var_kw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
    required_positional = [p for p in positional if p.default is inspect.Parameter.empty]
    required_kw = {
        p.name for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.default is inspect.Parameter.empty
    }

    has_kwonly = any(p.kind == p.KEYWORD_ONLY for p in sig.parameters.values())
    if len(positional) == 0 and not kw_names and not has_var_kw:
        out = fn()
    elif (
        isinstance(arg, dict)
        and (len(positional) > 1 or has_kwonly or (len(positional) == 0 and has_var_kw))
        and (has_var_kw or set(arg.keys()).issubset(kw_names))
        and required_kw.issubset(arg.keys())
    ):
        out = fn(**arg)
    elif len(positional) == 1:
        out = fn(arg)
    elif isinstance(arg, list) and len(required_positional) <= len(arg) <= len(positional):
        out = fn(*arg)
    else:
        out = fn(arg)

    return json.dumps(_normalize_output(out), ensure_ascii=False, default=str)
