"""Runtime adapter for the compiled DSPy explicit skill extraction module."""

import asyncio
import hashlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import dspy
from pydantic import ValidationError

from app.ai_runtime import active
from matching_cv.app.core.config import settings
from matching_cv.app.schemas.skill_extraction import check_verbatim_mention
from matching_cv.dspy_modules.modules import DSPyExplicitSkillExtractorModule
from matching_cv.dspy_modules.schemas import ExplicitSkillMention
from matching_cv.dspy_modules.signatures import ExplicitSkillExtractionSignature
from matching_cv.app.services.skill_postprocessor import skill_postprocessor
from matching_cv.app.services.text_locator import locate_sentence
from matching_cv.dspy_modules.dataset import get_train_val_split

COORDINATE_TEST_PHRASE_RE = re.compile(
    r"\b(unit)\s+(?:and|or|&)\s+(?:end-to-end|e2e|integration|functional|regression)\s+(tests?|testing)\b",
    re.IGNORECASE,
)
STANDALONE_ACRONYM_BEFORE_PARENS_RE = re.compile(r"\b(PWA)\s*\(")

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
        self._lm_revision: Optional[int] = None
        self._lock = threading.Lock()
        self._prompt_sha256: Optional[str] = None

    async def extract(self, text: str, document_type: str) -> Dict[str, Any]:
        """Run DSPy away from the event loop and return only grounded skill mentions."""
        return await asyncio.to_thread(self._extract_sync, text, document_type)

    def _extract_sync(self, text: str, document_type: str) -> Dict[str, Any]:
        self._ensure_initialized()
        lm = self._active_lm()
        assert self._module is not None
        with dspy.context(lm=lm):
            prediction = self._module(document_type=document_type, document_text=text)
        candidates = getattr(prediction, "explicit_skills", None)
        if candidates is None:
            raise ValueError("DSPy output is missing explicit_skills.")

        skills = [
            item
            for raw_item in candidates
            if (item := self._validated_candidate(raw_item, text)) is not None
        ]
        skills = skill_postprocessor._expand_slash_compound_raw_items(skills)
        skills = self._backfill_missing_line_occurrences(skills, text)
        return {"explicit_skills": skills}

    @staticmethod
    def _is_coordinate_ellipsis_mention(mention: str, sentence: str) -> bool:
        """
        Return True when mention is a 2-token coordinate ellipsis phrase whose head noun is
        shared across 'and'/'or' in sentence (e.g. 'unit tests' in 'Write unit and end-to-end tests').
        """
        tokens = mention.strip().split()
        if len(tokens) != 2:
            return False
        mod_tok, head_tok = re.escape(tokens[0]), re.escape(tokens[1])
        pat = re.compile(
            rf"\b{mod_tok}\s+(?:and|or|&|/|,)\s+(?:[\w\-]+\s+){{1,2}}{head_tok}\b",
            re.IGNORECASE,
        )
        return bool(pat.search(sentence))

    @staticmethod
    def _backfill_missing_line_occurrences(
        skills: List[Dict[str, Any]], text: str
    ) -> List[Dict[str, Any]]:
        """
        Deterministically backfill verbatim occurrences of already-extracted skills
        in other lines/sections of the document that the LLM omitted, plus coordinate
        test phrases ('unit and end-to-end tests') and standalone 'PWA (' acronyms.
        Uses longest-match-first per line to prevent shorter names (e.g. 'Java', 'React', 'Docker')
        from matching inside longer names ('Java 21', 'React Hook Form', 'Docker Compose').
        """
        if not skills or not text:
            return skills

        # Map lowercase mention -> (canonical_mention, kind, category)
        unique_mentions: Dict[str, Tuple[str, str, Optional[str]]] = {}
        covered_spans_by_mention: Dict[str, List[Tuple[int, int]]] = {}
        existing_mention_keys: Set[str] = set()

        for item in skills:
            m_str = str(item.get("mention", "")).strip()
            k_str = str(item.get("kind", "skill"))
            c_str = item.get("category")
            sent_str = str(item.get("source_sentence", ""))
            if len(m_str) < 2 or k_str not in ("skill", "domain", "certification"):
                continue
            m_key = m_str.casefold()
            existing_mention_keys.add(m_key)
            if m_key not in unique_mentions:
                unique_mentions[m_key] = (m_str, k_str, c_str)
            span = locate_sentence(text, sent_str)
            if span is not None:
                covered_spans_by_mention.setdefault(m_key, []).append(span)

        if not unique_mentions:
            return skills

        # Sort unique mentions by length descending so longer compound tools claim spans first
        sorted_mentions = sorted(
            unique_mentions.items(), key=lambda kv: len(kv[1][0]), reverse=True
        )
        compiled_patterns = [
            (
                m_key,
                m_str,
                k_str,
                c_str,
                re.compile(rf"(?<![\w\.\-]){re.escape(m_str)}(?![\w\.\-])", re.IGNORECASE),
            )
            for m_key, (m_str, k_str, c_str) in sorted_mentions
        ]

        backfilled = list(skills)
        offset = 0
        for raw_line in text.splitlines(keepends=True):
            line_start = offset
            offset += len(raw_line)
            line_end = offset
            line_stripped = raw_line.strip()
            if len(line_stripped) < 4:
                continue

            claimed_line_spans: List[Tuple[int, int]] = []
            for m_key, m_str, k_str, c_str, pat in compiled_patterns:
                for match in pat.finditer(line_stripped):
                    ms, me = match.start(), match.end()
                    if any(not (me <= cs or ms >= ce) for cs, ce in claimed_line_spans):
                        continue
                    claimed_line_spans.append((ms, me))

                    # Check if this line is already covered by an existing evidence sentence for m_key
                    existing_spans = covered_spans_by_mention.get(m_key, [])
                    if any(not (line_end <= es or line_start >= ee) for es, ee in existing_spans):
                        continue

                    actual_sf = line_stripped[ms:me]
                    backfilled.append(
                        {
                            "mention": actual_sf,
                            "kind": k_str,
                            "category": c_str,
                            "source_sentence": line_stripped,
                        }
                    )
                    covered_spans_by_mention.setdefault(m_key, []).append((line_start, line_end))
                    break

            # Recover first conjunct in coordinate test phrases (e.g. 'Write unit and end-to-end tests')
            m_coord = COORDINATE_TEST_PHRASE_RE.search(line_stripped)
            if m_coord:
                coord_mention = f"{m_coord.group(1)} {m_coord.group(2)}"
                coord_key = coord_mention.casefold()
                existing_spans = covered_spans_by_mention.get(coord_key, [])
                if not any(not (line_end <= es or line_start >= ee) for es, ee in existing_spans):
                    backfilled.append(
                        {
                            "mention": coord_mention,
                            "kind": "skill",
                            "category": "Engineering Practice",
                            "source_sentence": line_stripped,
                        }
                    )
                    covered_spans_by_mention.setdefault(coord_key, []).append((line_start, line_end))

            # Recover standalone 'PWA (' acronym when omitted before a parenthetical tech stack
            m_acr = STANDALONE_ACRONYM_BEFORE_PARENS_RE.search(line_stripped)
            if m_acr:
                acr_str = m_acr.group(1)
                acr_key = acr_str.casefold()
                existing_spans = covered_spans_by_mention.get(acr_key, [])
                if not any(not (line_end <= es or line_start >= ee) for es, ee in existing_spans):
                    backfilled.append(
                        {
                            "mention": acr_str,
                            "kind": "skill",
                            "category": "Technical Concept",
                            "source_sentence": line_stripped,
                        }
                    )
                    covered_spans_by_mention.setdefault(acr_key, []).append((line_start, line_end))

        return backfilled

    def _validated_candidate(self, raw_item: Any, text: str) -> Optional[Dict[str, str]]:
        """Reject malformed or ungrounded predictions before legacy post-processing."""
        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump()
        try:
            candidate = ExplicitSkillMention.model_validate(raw_item)
        except ValidationError as exc:
            logger.warning("DSPy returned an invalid explicit skill candidate; dropping it: %s", exc)
            return None
        if not candidate.mention.strip() or (
            not check_verbatim_mention(candidate.mention, candidate.source_sentence)
            and not self._is_coordinate_ellipsis_mention(candidate.mention, candidate.source_sentence)
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
        self._prompt_sha256 = self._hash_module(module)
        self._module = module

    def _active_lm(self) -> dspy.LM:
        revision = active.get().revision
        with self._lock:
            if self._lm is None or self._lm_revision != revision:
                self._lm = self._create_lm()
                self._lm_revision = revision
            return self._lm

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
