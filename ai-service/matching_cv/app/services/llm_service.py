"""LLM Service utilizing AsyncOpenAI client compatible with OpenRouter API."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI

from matching_cv.app.core.config import settings

logger = logging.getLogger(__name__)


class ProvenanceMismatchError(ValueError):
    """Raised when explicit_result text_sha256 does not match document text sha256."""
    pass


def extract_stored_text_sha256(res: Any) -> Optional[str]:
    """Extract text_sha256 from an ExtractionResult or stored run dictionary."""
    if res is None:
        return None
    if isinstance(res, dict):
        return (
            res.get("text_sha256")
            or res.get("metadata", {}).get("text_sha256")
            or res.get("processed_result", {}).get("text_sha256")
        )
    val = getattr(res, "text_sha256", None)
    if val:
        return val
    meta = getattr(res, "metadata", None)
    if meta and hasattr(meta, "text_sha256"):
        return meta.text_sha256
    return None


class LLMService:
    """Service managing LLM connections and asynchronous inference via OpenRouter."""

    def __init__(self) -> None:
        self.api_key: str = settings.OPENROUTER_API_KEY
        self.base_url: str = settings.OPENROUTER_BASE_URL
        self.model: str = settings.OPENROUTER_MODEL

        # OpenRouter standard tracking headers
        self.default_headers = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Inference Service - HR System",
        }

        # Initialize AsyncOpenAI client (fallback placeholder if key not yet provided in .env)
        self.client = AsyncOpenAI(
            api_key=self.api_key or "not_configured",
            base_url=self.base_url,
            default_headers=self.default_headers,
        )

    async def test_connection(self) -> Dict[str, Any]:
        """
        Verify connection to OpenRouter API and validate LLM model inference.
        Sends a simple ping prompt with deterministic parameters (temperature=0.0).
        Safely handles reasoning models (e.g. Qwen, DeepSeek) where thinking tokens
        may precede content.
        """
        # 1. Validate API Key configuration
        current_key = settings.OPENROUTER_API_KEY
        if not current_key or current_key.strip() in [
            "",
            "your_openrouter_api_key_here",
            "not_configured",
        ]:
            raise ValueError(
                "OPENROUTER_API_KEY chưa được cấu hình hợp lệ trong file .env. "
                "Vui lòng thiết lập key từ https://openrouter.ai/keys để thực hiện kết nối."
            )

        # Refresh client credentials in case settings changed at runtime
        client = AsyncOpenAI(
            api_key=current_key,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers=self.default_headers,
        )

        model_to_use = settings.OPENROUTER_MODEL or self.model
        prompt = "Ping test! Trả về đúng 1 từ duy nhất: 'PONG'."

        logger.info(f"Testing LLM connection with OpenRouter model '{model_to_use}'...")

        try:
            # First attempt: Try disabling reasoning for fast, cheap ping test
            try:
                chat_completion = await client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=150,
                    extra_body={"reasoning": {"effort": "none"}},
                )
            except Exception:
                # Fallback: standard call if model doesn't support reasoning parameter
                chat_completion = await client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=150,
                )

            # Safely extract text (handles reasoning models where content might initially be None)
            raw_response = ""
            if chat_completion.choices and len(chat_completion.choices) > 0:
                first_choice = chat_completion.choices[0]
                msg = first_choice.message
                if getattr(msg, "content", None):
                    raw_response = str(msg.content).strip()
                elif getattr(msg, "reasoning", None):
                    raw_response = str(msg.reasoning).strip()
                elif getattr(msg, "reasoning_content", None):
                    raw_response = str(msg.reasoning_content).strip()
                elif getattr(msg, "refusal", None):
                    raw_response = f"[Refusal]: {msg.refusal}"

            model_used = chat_completion.model or model_to_use

            logger.info(
                f"LLM connection successful. Model: '{model_used}', Response: '{raw_response}'"
            )

            return {
                "status": "connected",
                "model_used": model_used,
                "response": raw_response or "PONG",
            }

        except Exception as exc:
            logger.error(f"Failed to communicate with OpenRouter LLM: {str(exc)}", exc_info=True)
            raise exc

    async def extract_explicit_skills(
        self,
        text: str,
        document_type: str,
        system_prompt: Optional[str] = None,
        prompt_variant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract explicit skills from CV or JD text using LLM with JSON structured output.
        Focuses strictly on explicit keywords physically present in the text with grounded citations.
        """
        from matching_cv.app.services.prompt_templates import (
            EXPLICIT_SKILL_SYSTEM_PROMPT,
            EXPLICIT_SKILL_SYSTEM_PROMPT_EN,
        )

        current_key = settings.OPENROUTER_API_KEY
        if not current_key or current_key.strip() in [
            "",
            "your_openrouter_api_key_here",
            "not_configured",
        ]:
            raise ValueError(
                "OPENROUTER_API_KEY chưa được cấu hình hợp lệ trong file .env."
            )

        client = AsyncOpenAI(
            api_key=current_key,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers=self.default_headers,
        )

        model_to_use = settings.OPENROUTER_MODEL or self.model
        if system_prompt is not None:
            prompt_content = system_prompt
        elif prompt_variant and prompt_variant.upper() == "EN":
            prompt_content = EXPLICIT_SKILL_SYSTEM_PROMPT_EN
        else:
            prompt_content = EXPLICIT_SKILL_SYSTEM_PROMPT
        prompt_sha256 = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()
        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": f"Document Type: {document_type}\n\nText:\n{text}"},
        ]

        from matching_cv.app.services.extraction_recovery import request_stage_context_var
        request_stage_context_var.set("explicit")

        logger.info(
            f"Extracting explicit skills for {document_type} (length={len(text)} chars) with model '{model_to_use}'..."
        )

        try:
            try:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    extra_body={"reasoning": {"effort": "none"}},
                )
            except Exception:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

            # Safely retrieve response string
            result_str = ""
            if response.choices and len(response.choices) > 0:
                first_msg = response.choices[0].message
                if getattr(first_msg, "content", None):
                    result_str = str(first_msg.content).strip()
                elif getattr(first_msg, "reasoning", None):
                    result_str = str(first_msg.reasoning).strip()
                elif getattr(first_msg, "reasoning_content", None):
                    result_str = str(first_msg.reasoning_content).strip()

            # Clean markdown code block if wrapped in ```json ... ```
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            elif result_str.startswith("```"):
                result_str = result_str[3:]

            if result_str.endswith("```"):
                result_str = result_str[:-3]

            result_str = result_str.strip()

            if not result_str:
                raise ValueError("Mô hình LLM trả về phản hồi rỗng.")

            try:
                parsed_json = json.loads(result_str)
                from matching_cv.app.services.extraction_recovery import (
                    explicit_recovery_diag_var,
                    last_recovery_diag_var,
                )
                explicit_recovery_diag_var.set(None)
                last_recovery_diag_var.set(None)
            except Exception as json_err:
                from matching_cv.app.services.extraction_recovery import (
                    attempt_json_truncation_recovery,
                    explicit_recovery_diag_var,
                    last_recovery_diag_var,
                )

                logger.warning(
                    f"Direct json.loads failed ({json_err}). Attempting multi-tier truncation recovery..."
                )
                repaired, diag = attempt_json_truncation_recovery(result_str)
                if repaired is not None and diag.get("success"):
                    parsed_json = repaired
                    parsed_json["_recovery_diagnostics"] = diag
                    explicit_recovery_diag_var.set(diag)
                    last_recovery_diag_var.set(diag)
                else:
                    raise json_err
            if isinstance(parsed_json, dict):
                variant_name = (
                    prompt_variant
                    if prompt_variant is not None
                    else ("default" if system_prompt is None else None)
                )
                parsed_json["extraction_meta"] = {
                    "prompt_sha256": prompt_sha256,
                    "prompt_variant": variant_name,
                    "model_configured": model_to_use,
                    "temperature": 0.0,
                    "schema_version": "1.0.0",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }
            return parsed_json

        except Exception as exc:
            logger.error(f"Error during explicit skill extraction: {str(exc)}", exc_info=True)
            raise exc

    async def extract_implicit_skills(
        self,
        text: str,
        document_type: str,
        explicit_mentions: Optional[List[str]] = None,
        explicit_result: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        prompt_variant: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Infer implicit skills from CV or JD text using LLM with JSON structured output.
        Implicit skills are NOT verbatim in the text; they are inferred from context,
        role descriptions, and activities.
        """
        from matching_cv.app.services.prompt_templates import (
            IMPLICIT_SKILL_SYSTEM_PROMPT,
            IMPLICIT_SKILL_SYSTEM_PROMPT_V2,
            IMPLICIT_SKILL_SYSTEM_PROMPT_EN,
        )

        doc_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        explicit_source: Optional[str] = None
        effective_explicit: Optional[List[str]] = explicit_mentions

        if explicit_result is not None:
            stored_sha = extract_stored_text_sha256(explicit_result)
            if stored_sha != doc_sha256:
                raise ProvenanceMismatchError(
                    f"Provenance mismatch: explicit_result text_sha256 ({stored_sha}) "
                    f"does not match sha256(text) ({doc_sha256})"
                )
            if effective_explicit is None:
                from matching_cv.app.services.implicit_skill_postprocessor import build_explicit_list
                effective_explicit = build_explicit_list(explicit_result)
            explicit_source = "extraction_result"
        elif explicit_mentions is not None:
            explicit_source = "caller_list"

        current_key = settings.OPENROUTER_API_KEY
        if not current_key or current_key.strip() in [
            "",
            "your_openrouter_api_key_here",
            "not_configured",
        ]:
            raise ValueError(
                "OPENROUTER_API_KEY chưa được cấu hình hợp lệ trong file .env."
            )

        client = AsyncOpenAI(
            api_key=current_key,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers=self.default_headers,
        )

        model_to_use = settings.OPENROUTER_MODEL or self.model
        if system_prompt is not None:
            prompt_content = system_prompt
        elif prompt_variant and prompt_variant.upper() in ("EN", "ENGLISH"):
            prompt_content = IMPLICIT_SKILL_SYSTEM_PROMPT_EN
        elif prompt_variant and prompt_variant.upper() == "V2":
            prompt_content = IMPLICIT_SKILL_SYSTEM_PROMPT_V2
        else:
            prompt_content = IMPLICIT_SKILL_SYSTEM_PROMPT
        prompt_sha256 = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()

        # Build user message: if effective_explicit is provided, include ALREADY EXPLICIT section
        if effective_explicit is not None:
            seen = set()
            unique_explicit = []
            for m in effective_explicit:
                if m not in seen:
                    seen.add(m)
                    unique_explicit.append(m)

            user_content = (
                f"Document Type: {document_type}\n\n"
                f"ALREADY EXPLICIT:\n{json.dumps(unique_explicit, ensure_ascii=False)}\n\n"
                f"Text:\n{text}"
            )
        else:
            user_content = f"Document Type: {document_type}\n\nText:\n{text}"

        messages = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": user_content},
        ]

        temp_to_use = 0.0 if temperature is None else float(temperature)

        from matching_cv.app.services.extraction_recovery import request_stage_context_var
        request_stage_context_var.set("implicit")

        logger.info(
            f"Inferring implicit skills for {document_type} (length={len(text)} chars) with model '{model_to_use}'..."
        )

        try:
            try:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    temperature=temp_to_use,
                    response_format={"type": "json_object"},
                    extra_body={"reasoning": {"effort": "none"}},
                )
            except Exception:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    temperature=temp_to_use,
                    response_format={"type": "json_object"},
                )

            result_str = ""
            if response.choices and len(response.choices) > 0:
                first_msg = response.choices[0].message
                if getattr(first_msg, "content", None):
                    result_str = str(first_msg.content).strip()
                elif getattr(first_msg, "reasoning", None):
                    result_str = str(first_msg.reasoning).strip()
                elif getattr(first_msg, "reasoning_content", None):
                    result_str = str(first_msg.reasoning_content).strip()

            # Strip markdown code fences if present
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            elif result_str.startswith("```"):
                result_str = result_str[3:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
            result_str = result_str.strip()

            if not result_str:
                raise ValueError("Mô hình LLM trả về phản hồi rỗng.")

            try:
                parsed_json = json.loads(result_str)
                from matching_cv.app.services.extraction_recovery import (
                    implicit_recovery_diag_var,
                    last_recovery_diag_var,
                )
                implicit_recovery_diag_var.set(None)
                # DO NOT clear explicit_recovery_diag_var!
            except Exception as json_err:
                from matching_cv.app.services.extraction_recovery import (
                    attempt_json_truncation_recovery,
                    implicit_recovery_diag_var,
                    last_recovery_diag_var,
                )

                logger.warning(
                    f"Direct json.loads failed ({json_err}). Attempting multi-tier truncation recovery..."
                )
                repaired, diag = attempt_json_truncation_recovery(result_str)
                if repaired is not None and diag.get("success"):
                    parsed_json = repaired
                    parsed_json["_recovery_diagnostics"] = diag
                    implicit_recovery_diag_var.set(diag)
                    last_recovery_diag_var.set(diag)
                else:
                    raise json_err
            if isinstance(parsed_json, dict):
                if prompt_variant is not None:
                    variant_name = prompt_variant
                elif system_prompt is None:
                    variant_name = "default"
                elif prompt_content == IMPLICIT_SKILL_SYSTEM_PROMPT_V2:
                    variant_name = "v2"
                elif prompt_content == IMPLICIT_SKILL_SYSTEM_PROMPT_EN:
                    variant_name = "EN"
                else:
                    variant_name = None

                parsed_json["extraction_meta"] = {
                    "prompt_sha256": prompt_sha256,
                    "prompt_variant": variant_name,
                    "model_configured": model_to_use,
                    "temperature": temp_to_use,
                    "schema_version": "1.0.0",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "explicit_source": explicit_source,
                }
            return parsed_json

        except Exception as exc:
            logger.error(f"Error during implicit skill inference: {str(exc)}", exc_info=True)
            raise exc

    async def verify_candidates(
        self,
        text: str,
        candidates: List[Any],
        explicit_mentions: Optional[List[str]] = None,
        explicit_result: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> List[Any]:
        """
        Verify candidate implicit skills against document text and explicit mentions.
        The verifier receives:
        - document text
        - candidate label, basis (if provided), and snippets (NOT the generator's note)
        - explicit mentions list
        """
        from matching_cv.app.services.prompt_templates import (
            VERIFIER_PROMPT_V1,
            VERIFIER_PROMPT_V2,
        )
        from matching_cv.app.services.implicit_skill_postprocessor import postprocess_verification

        if not candidates:
            return []

        doc_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if explicit_result is not None:
            stored_sha = extract_stored_text_sha256(explicit_result)
            if stored_sha != doc_sha256:
                raise ProvenanceMismatchError(
                    f"Provenance mismatch: explicit_result text_sha256 ({stored_sha}) "
                    f"does not match sha256(text) ({doc_sha256})"
                )
            if explicit_mentions is None:
                from matching_cv.app.services.implicit_skill_postprocessor import build_explicit_list
                explicit_mentions = build_explicit_list(explicit_result)

        # Prepare payload for verifier containing label, basis (if present), and snippets
        formatted_candidates = []
        for c in candidates:
            if isinstance(c, dict):
                lbl = c.get("label") or c.get("skill_label") or c.get("skill") or ""
                raw_basis = c.get("basis")
                ev = c.get("evidence") or c.get("snippets") or []
                if isinstance(ev, list):
                    snip_texts = [
                        s.get("text") if isinstance(s, dict) else str(s)
                        for s in ev
                    ]
                else:
                    snip_texts = [str(ev)]
            else:
                lbl = getattr(c, "label", None) or getattr(c, "skill_label", "") or ""
                raw_basis = getattr(c, "basis", None)
                snip_texts = []
                for ev in getattr(c, "evidences", []):
                    for snip in getattr(ev, "snippets", []):
                        snip_texts.append(snip.text)

            cand_entry: Dict[str, Any] = {"label": lbl}
            if raw_basis is not None:
                cand_entry["basis"] = str(raw_basis)
            cand_entry["snippets"] = snip_texts
            formatted_candidates.append(cand_entry)

        unique_explicit = []
        if explicit_mentions:
            seen = set()
            for m in explicit_mentions:
                if m not in seen:
                    seen.add(m)
                    unique_explicit.append(m)

        user_content = (
            f"Document Text:\n{text}\n\n"
            f"ALREADY EXPLICIT:\n{json.dumps(unique_explicit, ensure_ascii=False)}\n\n"
            f"Candidate Implicit Skills:\n{json.dumps(formatted_candidates, ensure_ascii=False)}"
        )

        prompt_to_use = system_prompt if system_prompt is not None else VERIFIER_PROMPT_V2
        messages = [
            {"role": "system", "content": prompt_to_use},
            {"role": "user", "content": user_content},
        ]

        current_key = settings.OPENROUTER_API_KEY
        if not current_key or current_key.strip() in [
            "",
            "your_openrouter_api_key_here",
            "not_configured",
        ]:
            raise ValueError(
                "OPENROUTER_API_KEY chưa được cấu hình hợp lệ trong file .env."
            )

        client = AsyncOpenAI(
            api_key=current_key,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers=self.default_headers,
        )

        verifier_env_model = (
            os.getenv("OPENROUTER_VERIFIER_MODEL")
            or getattr(settings, "OPENROUTER_VERIFIER_MODEL", "")
        ).strip()
        model_to_use = model or verifier_env_model or settings.OPENROUTER_MODEL or self.model
        temp_to_use = 0.0 if temperature is None else float(temperature)

        try:
            response = await client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=temp_to_use,
                response_format={"type": "json_object"},
            )
        except Exception:
            response = await client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=temp_to_use,
            )

        model_val = getattr(response, "model", None)
        if isinstance(model_val, str) and model_val.strip():
            model_returned = model_val.strip()
        else:
            model_returned = str(model_to_use)

        result_str = ""
        if response.choices and len(response.choices) > 0:
            first_msg = response.choices[0].message
            if getattr(first_msg, "content", None):
                result_str = str(first_msg.content).strip()
            elif getattr(first_msg, "reasoning", None):
                result_str = str(first_msg.reasoning).strip()

        if result_str.startswith("```json"):
            result_str = result_str[7:]
        elif result_str.startswith("```"):
            result_str = result_str[3:]
        if result_str.endswith("```"):
            result_str = result_str[:-3]
        result_str = result_str.strip()

        parsed = json.loads(result_str)
        return postprocess_verification(
            parsed,
            candidates=candidates,
            model_used=model_returned,
        )


# Global singleton service instance
llm_service = LLMService()


async def verify_candidates(
    text: str,
    candidates: List[Any],
    explicit_mentions: Optional[List[str]] = None,
    explicit_result: Optional[Any] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> List[Any]:
    """Module-level convenience wrapper for verify_candidates."""
    return await llm_service.verify_candidates(
        text=text,
        candidates=candidates,
        explicit_mentions=explicit_mentions,
        explicit_result=explicit_result,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
    )


