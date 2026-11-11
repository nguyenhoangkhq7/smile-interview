"""Unit and integration tests for LLM integration endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from matching_cv.app.main import app


@pytest.fixture
def client():
    """Test client fixture bypassing heavy model loads."""
    with patch("matching_cv.app.core.model_loader.model_loader.load_model"):
        with TestClient(app) as test_client:
            yield test_client


def test_llm_test_endpoint_missing_api_key(client):
    """Test that missing or default API key returns 400 with helpful message."""
    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", ""):
        response = client.get("/api/v1/llm/test-llm")
        assert response.status_code == 400
        assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_llm_test_endpoint_success(client):
    """Test successful LLM connection ping with mocked AsyncOpenAI response."""
    mock_choice = MagicMock()
    mock_choice.message.content = "PONG"

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.model = "google/gemini-2.5-flash"

    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-or-v1-mock-test-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        response = client.get("/api/v1/llm/test-llm")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "connected"
        assert data["model_used"] == "google/gemini-2.5-flash"
        assert data["response"] == "PONG"


def test_llm_test_endpoint_upstream_error(client):
    """Test upstream failure handling when OpenRouter rejects request."""
    mock_create = AsyncMock(side_effect=Exception("Unauthorized: Invalid OpenRouter API Key"))

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-or-v1-invalid-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        response = client.get("/api/v1/llm/test-llm")
        assert response.status_code == 500
        assert "Lỗi kết nối hoặc xác thực OpenRouter LLM" in response.json()["detail"]


@pytest.mark.anyio
async def test_extract_explicit_skills_default_sends_production_prompt():
    """Verify that extract_explicit_skills called without system_prompt sends
    the byte-identical EXPLICIT_SKILL_SYSTEM_PROMPT to the client."""
    import hashlib
    import json
    from matching_cv.app.services.llm_service import LLMService
    from matching_cv.app.services.prompt_templates import EXPLICIT_SKILL_SYSTEM_PROMPT

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"explicit_skills": []})
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        service = LLMService()
        await service.extract_explicit_skills("sample text", "CV")

        assert mock_create.called
        call_kwargs = mock_create.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        sent_prompt = system_msg["content"]

        sent_sha256 = hashlib.sha256(sent_prompt.encode("utf-8")).hexdigest()
        assert sent_sha256 == "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"
        assert sent_prompt == EXPLICIT_SKILL_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_extract_explicit_skills_meta_default_and_variant():
    """Verify that extraction_meta reports the production sha256 for default runs
    and the variant's own sha256 for variant runs."""
    import hashlib
    import json
    from matching_cv.app.services.llm_service import LLMService
    from matching_cv.app.services.prompt_templates import (
        EXPLICIT_SKILL_SYSTEM_PROMPT,
        EXPLICIT_SKILL_SYSTEM_PROMPT_C1,
    )

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"explicit_skills": []})
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_create = AsyncMock(return_value=mock_completion)

    with patch("matching_cv.app.core.config.settings.OPENROUTER_API_KEY", "sk-mock-key"), \
         patch("matching_cv.app.services.llm_service.AsyncOpenAI") as mock_openai_cls:

        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_openai_cls.return_value = mock_instance

        service = LLMService()

        # 1. Default path (no prompt argument)
        res_default = await service.extract_explicit_skills("sample text", "CV")
        meta_default = res_default.get("extraction_meta")
        assert meta_default is not None
        assert meta_default["prompt_sha256"] == "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"
        assert meta_default["prompt_variant"] == "default"
        assert meta_default["temperature"] == 0.0
        assert meta_default["schema_version"] == "1.0.0"

        # 2. Variant path (C1)
        c1_sha256 = hashlib.sha256(EXPLICIT_SKILL_SYSTEM_PROMPT_C1.encode("utf-8")).hexdigest()
        res_variant = await service.extract_explicit_skills(
            "sample text",
            "CV",
            system_prompt=EXPLICIT_SKILL_SYSTEM_PROMPT_C1,
            prompt_variant="C1",
        )
        meta_variant = res_variant.get("extraction_meta")
        assert meta_variant is not None
        assert meta_variant["prompt_sha256"] == c1_sha256
        assert meta_variant["prompt_sha256"] != "0b3a3b5112b086d35b28274cb7470455e27a022d1d53ce3703ee6b7ade4e4fce"
        assert meta_variant["prompt_variant"] == "C1"
        assert meta_variant["temperature"] == 0.0
        assert meta_variant["schema_version"] == "1.0.0"
