"""Operational interview logs without document, prompt or answer contents."""
from contextvars import ContextVar
import logging


session_id = ContextVar("interview_session_id", default="-")
logger = logging.getLogger("uvicorn.error")


def event(name: str, **fields: object) -> None:
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.info("interview.%s session_id=%s %s", name, session_id.get(), details)
