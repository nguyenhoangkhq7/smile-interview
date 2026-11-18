"""Runtime adapter for the compiled DSPy explicit skill extraction module."""

import asyncio
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import dspy
from pydantic import ValidationError

from matching_cv.app.core.config import settings
from matching_cv.app.schemas.skill_extraction import check_verbatim_mention
from matching_cv.dspy_modules.modules import DSPyExplicitSkillExtractorModule
from matching_cv.dspy_modules.schemas import ExplicitSkillMention
from matching_cv.dspy_modules.signatures import ExplicitSkillExtractionSignature
from matching_cv.app.services.text_locator import locate_sentence
from matching_cv.dspy_modules.dataset import get_train_val_split

logger = logging.getLogger(__name__)
COMPILED_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "dspy_modules"
    / "compiled_modules"
    / "explicit_skill_extractor.json"
)


class DSPyExplicitSkillService:
    """Load a compiled module once and adapt its predictions to the legacy schema."""

    def __init__(self, compiled_path: Optional[Path] = None) -> None:
        self._compiled_path = compiled_path or COMPILED_MODULE_PATH
        self._module: Optional[DSPyExplicitSkillExtractorModule] = None
        self._lm: Optional[dspy.LM] = None
        self._lock = threading.Lock()
        self._prompt_sha256: Optional[str] = None

    async def extract(self, text: str, document_type: str) -> Dict[str, Any]:
        """Run DSPy away from the event loop and return only grounded skill mentions."""
        return await asyncio.to_thread(self._extract_sync, text, document_type)

    def _extract_sync(self, text: str, document_type: str) -> Dict[str, Any]:
        self._ensure_initialized()
        assert self._module is not None and self._lm is not None
        with dspy.context(lm=self._lm):
            prediction = self._module(document_type=document_type, document_text=text)
        candidates = getattr(prediction, "explicit_skills", None)
        if candidates is None:
            raise ValueError("DSPy output is missing explicit_skills.")

        skills = [
            item
            for raw_item in candidates
            if (item := self._validated_candidate(raw_item, text)) is not None
        ]
        return {"explicit_skills": skills}

    def _validated_candidate(self, raw_item: Any, text: str) -> Optional[Dict[str, str]]:
        """Reject malformed or ungrounded predictions before legacy post-processing."""
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump()
        try:
            candidate = ExplicitSkillMention.model_validate(raw_item)
        except ValidationError as exc:
            logger.warning("DSPy returned an invalid explicit skill candidate; dropping it: %s", exc)
            return None
        if not candidate.mention.strip() or not check_verbatim_mention(
            candidate.mention, candidate.source_sentence
        ):
            logger.warning("DSPy returned a mention not present in its evidence sentence; dropping it.")
            return None
        if locate_sentence(text, candidate.source_sentence) is None:
            logger.warning("DSPy returned an evidence sentence not found in the document; dropping it.")
            return None
        return candidate.model_dump()

    def _ensure_initialized(self) -> None:
        if self._module is not None:
            return
        with self._lock:
            if self._module is not None:
                return
            self._initialize()

    def _initialize(self) -> None:
        module = self._load_module()
        self._lm = self._create_lm()
        self._prompt_sha256 = self._hash_module(module)
        self._module = module

    @staticmethod
    def _create_lm() -> dspy.LM:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key or api_key.strip() in {"your_openrouter_api_key_here", "not_configured"}:
            raise ValueError("OPENROUTER_API_KEY chưa được cấu hình hợp lệ trong file .env.")
        model_name = settings.OPENROUTER_MODEL
        model = model_name if model_name.startswith("openrouter/") else f"openrouter/{model_name}"
        return dspy.LM(
            model,
            api_key=api_key,
            api_base=settings.OPENROUTER_BASE_URL,
            temperature=0.0,
            cache=False,
            timeout=60,
            num_retries=3,
            extra_body={"reasoning": {"effort": "none"}},
        )

    def _load_module(self) -> DSPyExplicitSkillExtractorModule:
        module = DSPyExplicitSkillExtractorModule()
        if self._compiled_path.is_file():
            module.load(str(self._compiled_path))
            if ExplicitSkillExtractionSignature.__doc__:
                module.extract.signature = module.extract.signature.with_instructions(
                    ExplicitSkillExtractionSignature.__doc__.strip()
                )
            logger.info("Loaded compiled explicit skill DSPy module from %s", self._compiled_path)
            return module
        trainset, _ = get_train_val_split()
        seeded = dspy.LabeledFewShot(k=min(6, len(trainset))).compile(module, trainset=trainset)
        logger.warning(
            "No compiled explicit skill module at %s; seeded DSPy with local gold examples.",
            self._compiled_path,
        )
        return seeded

    @staticmethod
    def _hash_module(module: DSPyExplicitSkillExtractorModule) -> str:
        signature_text = module.extract.signature.instructions
        state_text = json.dumps(module.dump_state(), sort_keys=True, default=str)
        payload = f"{signature_text}\n{state_text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def prompt_sha256(self) -> str:
        """Return a stable digest for the active signature and compiled demonstrations."""
        self._ensure_initialized()
        assert self._prompt_sha256 is not None
        return self._prompt_sha256


dspy_explicit_skill_service = DSPyExplicitSkillService()
