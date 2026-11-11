"""Helper functions and fixtures for tests."""
from datetime import datetime, timezone
import hashlib
import json
import os
import time
from typing import Any, Callable, Dict, Optional

from matching_cv.app.core.config import settings
from matching_cv.app.services.llm_service import llm_service
from matching_cv.app.services.prompt_templates import IMPLICIT_SKILL_SYSTEM_PROMPT
from matching_cv.app.services.implicit_skill_postprocessor import implicit_skill_postprocessor
from matching_cv.app.schemas.implicit_skill_extraction import ExtractionMeta, RawImplicitExtraction


async def run_single_implicit_extraction(
    cleaned_text: str,
    doc_id: str,
    doc_type: str,
    run_idx: int,
    out_dir: str = "tests/fixtures/runs_implicit",
    system_prompt: str = IMPLICIT_SKILL_SYSTEM_PROMPT,
    extract_fn: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Execute a single implicit extraction, persisting raw API output before validation."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{doc_id}_run{run_idx}.json")

    prompt_sha256 = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    text_sha256 = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest() if cleaned_text else ""

    t0 = time.perf_counter()
    raw_dict = None
    api_error_str = None

    try:
        if extract_fn is not None:
            raw_dict = await extract_fn(cleaned_text, doc_type, system_prompt=system_prompt)
        else:
            raw_dict = await llm_service.extract_implicit_skills(
                cleaned_text,
                doc_type,
                system_prompt=system_prompt,
            )
    except Exception as exc:
        api_error_str = f"{type(exc).__name__}: {str(exc)}"

    latency = time.perf_counter() - t0

    metadata: Dict[str, Any] = {
        "provider": "OpenRouter",
        "model_configured": settings.OPENROUTER_MODEL,
        "model_returned": "not returned",
        "model": settings.OPENROUTER_MODEL,
        "temperature": 0.0,
        "max_tokens_setting": "not set (provider default)",
        "response_format": {"type": "json_object"},
        "finish_reason": "stop",
        "token_usage": "not returned",
        "latency_seconds": round(latency, 3),
        "variant": "default",
        "prompt_template_sha256": prompt_sha256,
        "text_sha256": text_sha256,
        "run_index": run_idx,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_validation_error": None,
    }

    if api_error_str is not None:
        metadata["raw_validation_error"] = api_error_str
        run_data = {
            "metadata": metadata,
            "raw_llm": None,
            "processed_result": None,
            "outcome": "api_error",
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2, ensure_ascii=False)
        return run_data

    # Persist raw API response before any validation
    run_data = {
        "metadata": metadata,
        "raw_llm": raw_dict,
        "processed_result": None,
        "outcome": "pending_validation",
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(run_data, f, indent=2, ensure_ascii=False)

    # Validate mention by mention via postprocessor
    validation_error = None
    processed = None
    try:
        RawImplicitExtraction.model_validate(raw_dict)

        meta_obj = ExtractionMeta(
            prompt_sha256=prompt_sha256,
            prompt_variant="default",
            model_configured=settings.OPENROUTER_MODEL,
            temperature=0.0,
            schema_version="1.0.0",
            extracted_at=metadata["timestamp"],
            confidence_calibrated=False,
        )
        processed = implicit_skill_postprocessor.process_extraction(
            raw_result=raw_dict,
            text=cleaned_text,
            filename=f"{doc_id}.pdf",
            document_type=doc_type,
            extraction_meta=meta_obj,
        )
        if processed.quarantined:
            raise ValueError(f"Schema invalid: {len(processed.quarantined)} items quarantined")
        outcome = "ok"
    except Exception as exc:
        validation_error = f"{type(exc).__name__}: {str(exc)}"
        outcome = "schema_invalid"

    metadata["raw_validation_error"] = validation_error
    run_data["outcome"] = outcome
    if processed is not None:
        run_data["processed_result"] = processed.model_dump()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(run_data, f, indent=2, ensure_ascii=False)

    return run_data
