"""Post-processor for implicit skill extraction: validates raw LLM output
and builds ImplicitExtractionResult with deduplication, fragment snippets,
and invariant-safe stats.
"""
import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from matching_cv.app.schemas.implicit_skill_extraction import (
    BasisType,
    CandidateVerification,
    CategoryType,
    ExtractionMeta,
    ImplicitEvidence,
    ImplicitEvidenceSnippet,
    ImplicitExtractedSkill,
    ImplicitExtractionResult,
    ImplicitExtractionStats,
    VerdictType,
)
from matching_cv.app.services.section_tagger import find_section_spans, section_at
from matching_cv.app.services.text_locator import locate_sentence

VALID_CATEGORIES: set[str] = {
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Soft Skill",
    "Certification",
}

VALID_BASES: set[str] = {
    "activity",
    "role",
    "jd_role_context",
}

VALID_VERDICTS: set[str] = {
    "entailed",
    "plausible",
    "unsupported",
    "normal_for_role",
    "possible",
    "invalid_for_basis",
}


class ImplicitSkillPostprocessor:
    """Post-processor for raw LLM implicit extraction into ImplicitExtractionResult."""

    @staticmethod
    def slugify_skill(label: str) -> str:
        """Compute deterministic slug from skill_label."""
        slug = re.sub(r"[^a-z0-9\-\.]+", "-", label.lower()).strip("-.")
        if not slug or not re.match(r"^[a-z0-9]", slug):
            return f"unmapped:{slug if slug else 'unknown'}"
        return slug

    def process_extraction(
        self,
        raw_result: Any,
        text: str,
        filename: Optional[str] = None,
        document_type: Optional[Literal["CV", "JD"]] = None,
        extraction_meta: Optional[Any] = None,
    ) -> ImplicitExtractionResult:
        """
        Validate and post-process raw LLM implicit extraction:
        - Validates each item individually; quarantines structural failures.
        - Normalizes skill_label and computes skill_id slug.
        - Deduplicates by skill_id, merging evidences across duplicate inferences.
        - Splits inferred_from into fragments on '...' and '…', resolves each via locator,
          tags section with section_tagger, and stores structured snippets.
        - Validates category against 6 known values.
        - Computes stats with invariant-safe counts.
        """
        # Precompute section spans on document text
        section_spans = (
            find_section_spans(text, document_type=document_type or "CV") if text else []
        )

        # Resolve extraction_meta if available
        if extraction_meta is None:
            if isinstance(raw_result, dict):
                meta_dict = raw_result.get("extraction_meta") or raw_result.get("_extraction_meta")
                if meta_dict and isinstance(meta_dict, dict):
                    try:
                        extraction_meta = ExtractionMeta.model_validate(meta_dict)
                    except Exception:
                        pass
            elif hasattr(raw_result, "extraction_meta") and getattr(raw_result, "extraction_meta") is not None:
                candidate = getattr(raw_result, "extraction_meta")
                if isinstance(candidate, ExtractionMeta):
                    extraction_meta = candidate
                elif isinstance(candidate, dict):
                    try:
                        extraction_meta = ExtractionMeta.model_validate(candidate)
                    except Exception:
                        pass
        elif isinstance(extraction_meta, dict):
            try:
                extraction_meta = ExtractionMeta.model_validate(extraction_meta)
            except Exception:
                pass

        # Normalize raw_items list
        raw_items: List[Any] = []
        if isinstance(raw_result, dict):
            candidate = raw_result.get("implicit_skills") or raw_result.get("skills")
            if candidate is not None:
                raw_items = candidate if isinstance(candidate, list) else [candidate]
        elif isinstance(raw_result, list):
            raw_items = raw_result
        elif hasattr(raw_result, "implicit_skills"):
            raw_items = getattr(raw_result, "implicit_skills")

        skills_by_id: Dict[str, ImplicitExtractedSkill] = {}
        quarantined: List[Dict[str, Any]] = []

        flattened_items: List[Any] = []
        for raw_it in raw_items:
            if hasattr(raw_it, "model_dump"):
                raw_it = raw_it.model_dump()
            elif hasattr(raw_it, "dict"):
                raw_it = raw_it.dict()

            if isinstance(raw_it, dict) and "evidences" in raw_it and isinstance(raw_it["evidences"], list):
                lbl = raw_it.get("skill_label") or raw_it.get("label") or raw_it.get("skill")
                cat = raw_it.get("category") or raw_it.get("category_raw")
                for ev in raw_it["evidences"]:
                    if hasattr(ev, "model_dump"):
                        ev = ev.model_dump()
                    elif hasattr(ev, "dict"):
                        ev = ev.dict()
                    if isinstance(ev, dict):
                        flattened_items.append({
                            "skill_label": lbl,
                            "category": cat,
                            "inferred_from": (
                                ev.get("inferred_from_raw")
                                or ev.get("inferred_from")
                                or ev.get("source_sentence")
                            ),
                            "reasoning": ev.get("reasoning"),
                            "confidence": (
                                ev.get("llm_confidence_raw")
                                if "llm_confidence_raw" in ev
                                else ev.get("confidence")
                            ),
                        })
                    else:
                        flattened_items.append(ev)
            else:
                flattened_items.append(raw_it)

        for item in flattened_items:
            # Handle Pydantic models
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            elif hasattr(item, "dict"):
                item = item.dict()

            if not isinstance(item, dict):
                quarantined.append({
                    "raw_item": item,
                    "errors": [f"Item is not a dict (got {type(item).__name__})"],
                })
                continue

            # Determine if this item is V2 format
            is_v2 = (
                "basis" in item
                or ("evidence" in item and isinstance(item.get("evidence"), list))
                or (
                    extraction_meta is not None
                    and getattr(extraction_meta, "prompt_variant", None) in ("v2", "implicit_v2")
                )
            )

            if is_v2:
                # --- V2 Processing Path ---
                label_val = (
                    item.get("label")
                    or item.get("skill_label")
                    or item.get("skill")
                )
                evidence_val = item.get("evidence")
                if evidence_val is None:
                    evidence_val = item.get("snippets")

                errors: List[str] = []
                if label_val is None:
                    errors.append("Missing required field 'label'")
                elif not isinstance(label_val, str):
                    errors.append(f"'label' must be a string, got {type(label_val).__name__}")
                elif not label_val.strip():
                    errors.append("'label' must not be empty")

                if evidence_val is None:
                    errors.append("Missing required field 'evidence'")
                elif not isinstance(evidence_val, list):
                    errors.append(f"'evidence' must be a list, got {type(evidence_val).__name__}")
                elif len(evidence_val) == 0:
                    errors.append("'evidence' list must not be empty")
                elif not all(isinstance(x, str) and x.strip() for x in evidence_val):
                    errors.append("'evidence' list elements must be non-empty strings")

                if errors:
                    quarantined.append({"raw_item": item, "errors": errors})
                    continue

                label = str(label_val).strip()

                # Per-item basis tolerance: unknown basis -> basis None + basis_raw
                raw_basis = item.get("basis")
                if raw_basis in VALID_BASES:
                    basis: Optional[BasisType] = raw_basis  # type: ignore[assignment]
                    basis_raw: Optional[str] = raw_basis
                else:
                    basis = None
                    basis_raw = str(raw_basis) if raw_basis is not None else "unknown"

                is_cv = (document_type or "").upper() == "CV"
                item_basis_invalid_for_cv = False
                if is_cv and (raw_basis == "jd_role_context" or basis == "jd_role_context"):
                    item_basis_invalid_for_cv = True

                # Snippet resolution: resolve directly with locator, NO splitting.
                # Snippet containing '...' or '…' is KEPT, flagged ellipsis_in_snippet=True.
                snippets: List[ImplicitEvidenceSnippet] = []
                for snip_text in evidence_val:
                    snip_str = str(snip_text).strip()
                    has_ellipsis = bool(re.search(r"\.{3,}|…", snip_str))
                    span = locate_sentence(text, snip_str) if text else None
                    if span is not None:
                        start = span[0]
                        end = span[1]
                        sec = section_at(section_spans, start) if section_spans and start is not None else None
                        v_ok = True
                    else:
                        start = None
                        end = None
                        sec = None
                        v_ok = False

                    snippets.append(
                        ImplicitEvidenceSnippet(
                            text=snip_str,
                            start=start,
                            end=end,
                            section=sec,
                            verbatim_ok=v_ok,
                            ellipsis_in_snippet=has_ellipsis,
                        )
                    )

                skill_id = self.slugify_skill(label)
                evidence = ImplicitEvidence(
                    inferred_from_raw=" ".join(evidence_val),
                    snippets=snippets,
                    reasoning=None,
                    basis=basis,
                    basis_raw=basis_raw,
                    basis_invalid_for_cv=item_basis_invalid_for_cv,
                    llm_confidence_raw=None,
                )

                if skill_id in skills_by_id:
                    skills_by_id[skill_id].evidences.append(evidence)
                    if item_basis_invalid_for_cv:
                        skills_by_id[skill_id].basis_invalid_for_cv = True
                else:
                    skills_by_id[skill_id] = ImplicitExtractedSkill(
                        skill_id=skill_id,
                        label=label,
                        category=None,
                        category_raw=None,
                        basis=basis,
                        basis_raw=basis_raw,
                        basis_invalid_for_cv=item_basis_invalid_for_cv,
                        type="implicit",
                        confidence=None,
                        evidences=[evidence],
                    )

            else:
                # --- V1 Processing Path (unchanged) ---
                label_val = (
                    item.get("skill_label")
                    or item.get("label")
                    or item.get("skill")
                )
                inferred_from_val = (
                    item.get("inferred_from")
                    or item.get("source_sentence")
                    or item.get("source")
                    or item.get("inferred_from_raw")
                )

                errors = []
                if label_val is None:
                    errors.append("Missing required field 'skill_label' (or 'label'/'skill')")
                elif not isinstance(label_val, str):
                    errors.append(f"'skill_label' must be a string, got {type(label_val).__name__}")
                elif not label_val.strip():
                    errors.append("'skill_label' must not be empty")

                if inferred_from_val is None:
                    errors.append("Missing required field 'inferred_from' (or 'source_sentence')")
                elif not isinstance(inferred_from_val, str):
                    errors.append(f"'inferred_from' must be a string, got {type(inferred_from_val).__name__}")
                elif not inferred_from_val.strip():
                    errors.append("'inferred_from' must not be empty")

                if errors:
                    quarantined.append({"raw_item": item, "errors": errors})
                    continue

                label = label_val.strip()
                raw_inf = inferred_from_val.strip()
                reasoning = item.get("reasoning")
                if reasoning is not None:
                    reasoning = str(reasoning).strip() or None

                # Resolve confidence: keep LLM raw value, never use for stats
                raw_conf = (
                    item.get("llm_confidence_raw")
                    if "llm_confidence_raw" in item
                    else item.get("confidence")
                )
                confidence = None
                if raw_conf is not None:
                    try:
                        conf_float = float(raw_conf)
                        confidence = max(0.0, min(1.0, conf_float))
                    except (TypeError, ValueError):
                        confidence = None

                # Split inferred_from into fragments on "..." and "…"
                raw_fragments = [f.strip() for f in re.split(r"\.{3,}|…", raw_inf) if f.strip()]
                if not raw_fragments:
                    raw_fragments = [raw_inf]

                snippets = []
                for frag in raw_fragments:
                    span = locate_sentence(text, frag) if text else None
                    if span is not None:
                        start = span[0]
                        end = span[1]
                        sec = section_at(section_spans, start) if section_spans else None
                        v_ok = True
                    else:
                        start = None
                        end = None
                        sec = None
                        v_ok = False

                    snippets.append(
                        ImplicitEvidenceSnippet(
                            text=frag,
                            start=start,
                            end=end,
                            section=sec,
                            verbatim_ok=v_ok,
                            ellipsis_in_snippet=False,
                        )
                    )

                # Resolve category
                raw_category = item.get("category")
                if raw_category in VALID_CATEGORIES:
                    category: Optional[CategoryType] = raw_category  # type: ignore[assignment]
                else:
                    category = None

                skill_id = self.slugify_skill(label)

                evidence = ImplicitEvidence(
                    inferred_from_raw=raw_inf,
                    snippets=snippets,
                    reasoning=reasoning,
                    llm_confidence_raw=confidence,
                )

                if skill_id in skills_by_id:
                    skills_by_id[skill_id].evidences.append(evidence)
                else:
                    skills_by_id[skill_id] = ImplicitExtractedSkill(
                        skill_id=skill_id,
                        label=label,
                        category=category,
                        category_raw=raw_category,
                        type="implicit",
                        confidence=None,
                        evidences=[evidence],
                    )

        skills = list(skills_by_id.values())
        total_inferences = sum(len(s.evidences) for s in skills)
        unique_skills = len(skills)
        unknown_category_count = sum(1 for s in skills if s.category is None)
        invalid_basis_count = sum(
            1 for s in skills for ev in s.evidences if ev.basis is None and ev.basis_raw is not None
        )
        ellipsis_snippets_count = sum(
            1 for s in skills for ev in s.evidences for snip in ev.snippets if snip.ellipsis_in_snippet
        )
        quarantined_mentions = len(quarantined)

        # Invariant-tracked metrics:
        non_verbatim_evidences = sum(
            1 for s in skills for ev in s.evidences if any(not snip.verbatim_ok for snip in ev.snippets)
        )
        multi_fragment_evidences = sum(
            1 for s in skills for ev in s.evidences if len(ev.snippets) > 1
        )
        multi_section_evidences = sum(
            1
            for s in skills
            for ev in s.evidences
            if len({snip.section for snip in ev.snippets if snip.section is not None}) > 1
        )

        basis_invalid_for_cv_count = sum(
            1 for s in skills for ev in s.evidences if ev.basis_invalid_for_cv
        )

        stats = ImplicitExtractionStats(
            total_inferences=total_inferences,
            unique_skills=unique_skills,
            unknown_category_count=unknown_category_count,
            invalid_basis=invalid_basis_count,
            ellipsis_snippets=ellipsis_snippets_count,
            quarantined_mentions=quarantined_mentions,
            non_verbatim_evidences=non_verbatim_evidences,
            multi_fragment_evidences=multi_fragment_evidences,
            multi_section_evidences=multi_section_evidences,
            basis_invalid_for_cv=basis_invalid_for_cv_count,
        )

        text_sha256 = (
            hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
        )

        return ImplicitExtractionResult(
            filename=filename,
            document_type=document_type,
            text_sha256=text_sha256,
            stats=stats,
            skills=skills,
            quarantined=quarantined,
            extraction_meta=extraction_meta,
        )


implicit_skill_postprocessor = ImplicitSkillPostprocessor()


# -----------------------------------------------------------------------------
# Standard Porter Stemmer (Pure Python, Self-Contained)
# -----------------------------------------------------------------------------

class PorterStemmer:
    """Standard Porter Stemmer algorithm (1980) implemented in pure Python."""

    @staticmethod
    def _is_consonant(word: str, i: int) -> bool:
        if word[i] in "aeiou":
            return False
        if word[i] == "y":
            if i == 0:
                return True
            return not PorterStemmer._is_consonant(word, i - 1)
        return True

    @staticmethod
    def _measure(word: str) -> int:
        m = 0
        i = 0
        n = len(word)
        while i < n and not PorterStemmer._is_consonant(word, i):
            i += 1
        while i < n:
            while i < n and PorterStemmer._is_consonant(word, i):
                i += 1
            if i < n:
                m += 1
            while i < n and not PorterStemmer._is_consonant(word, i):
                i += 1
        return m

    @staticmethod
    def _contains_vowel(word: str) -> bool:
        return any(not PorterStemmer._is_consonant(word, i) for i in range(len(word)))

    @staticmethod
    def _ends_double_consonant(word: str) -> bool:
        return (
            len(word) >= 2
            and word[-1] == word[-2]
            and PorterStemmer._is_consonant(word, len(word) - 1)
        )

    @staticmethod
    def _cvc(word: str) -> bool:
        if (
            len(word) >= 3
            and PorterStemmer._is_consonant(word, -1)
            and not PorterStemmer._is_consonant(word, -2)
            and PorterStemmer._is_consonant(word, -3)
        ):
            return word[-1] not in "wxy"
        return False

    def stem(self, word: str) -> str:
        """Apply Porter stemming rules to lowercased word."""
        word = word.lower()
        if len(word) <= 2:
            return word

        # Step 1a
        if word.endswith("sses"):
            word = word[:-2]
        elif word.endswith("ies"):
            word = word[:-2]
        elif not word.endswith("ss") and word.endswith("s"):
            word = word[:-1]

        # Step 1b
        extra = False
        if word.endswith("eed"):
            if self._measure(word[:-3]) > 0:
                word = word[:-1]
        elif word.endswith("ed"):
            stem = word[:-2]
            if self._contains_vowel(stem):
                word = stem
                extra = True
        elif word.endswith("ing"):
            stem = word[:-3]
            if self._contains_vowel(stem):
                word = stem
                extra = True

        if extra:
            if word.endswith("at") or word.endswith("bl") or word.endswith("iz"):
                word = word + "e"
            elif (
                self._ends_double_consonant(word)
                and not word.endswith("l")
                and not word.endswith("s")
                and not word.endswith("z")
            ):
                word = word[:-1]
            elif self._measure(word) == 1 and self._cvc(word):
                word = word + "e"

        # Step 1c
        if word.endswith("y") and self._contains_vowel(word[:-1]):
            word = word[:-1] + "i"

        # Step 2
        step2_pairs = [
            ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"),
            ("izer", "ize"), ("abli", "able"), ("alli", "al"), ("entli", "ent"),
            ("eli", "e"), ("ousli", "ous"), ("ization", "ize"), ("ation", "ate"),
            ("ator", "ate"), ("alism", "al"), ("iveness", "ive"), ("fulness", "ful"),
            ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble")
        ]
        for suffix, repl in step2_pairs:
            if word.endswith(suffix):
                stem = word[:-len(suffix)]
                if self._measure(stem) > 0:
                    word = stem + repl
                break

        # Step 3
        step3_pairs = [
            ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"),
            ("ical", "ic"), ("ful", ""), ("ness", "")
        ]
        for suffix, repl in step3_pairs:
            if word.endswith(suffix):
                stem = word[:-len(suffix)]
                if self._measure(stem) > 0:
                    word = stem + repl
                break

        # Step 4
        step4_suffixes = [
            "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement",
            "ment", "ent", "ou", "ism", "ate", "iti", "ous", "ive", "ize"
        ]
        for suffix in step4_suffixes:
            if word.endswith(suffix):
                stem = word[:-len(suffix)]
                if self._measure(stem) > 1:
                    word = stem
                break
        else:
            if word.endswith("ion"):
                stem = word[:-3]
                if self._measure(stem) > 1 and len(stem) > 0 and stem[-1] in "st":
                    word = stem

        # Step 5a
        if word.endswith("e"):
            stem = word[:-1]
            m = self._measure(stem)
            if m > 1 or (m == 1 and not self._cvc(stem)):
                word = stem

        # Step 5b
        if self._measure(word) > 1 and self._ends_double_consonant(word) and word.endswith("l"):
            word = word[:-1]

        return word


_default_stemmer = PorterStemmer()


def tokenize_and_stem(text: str) -> Set[str]:
    """Extract alphanumeric tokens, lowercase, and stem with Porter Stemmer.

    NO hand-made stoplist is applied: every token participates.
    """
    raw_tokens = re.findall(r"[a-z0-9]+", text.casefold())
    return {_default_stemmer.stem(t) for t in raw_tokens if t}


def token_jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return inter / union if union > 0 else 0.0


def build_explicit_list(
    explicit_result: Any,
    kinds: Tuple[str, ...] = ("skill", "domain", "certification"),
) -> List[str]:
    """Pure function returning distinct surface forms of mentions whose Evidence.kind is in `kinds`.

    Rules:
    - Case-insensitive de-duplication with stable order of first occurrence.
    - No sorting is applied.
    - Mentions with Evidence.kind not in `kinds` (e.g. 'context' or invalid/None) are excluded.
    """
    allowed_kinds = set(kinds)
    seen: Set[str] = set()
    result: List[str] = []

    def _consider(sf: Optional[str], k: Optional[str]) -> None:
        if not sf or k not in allowed_kinds:
            return
        sf_clean = sf.strip()
        if not sf_clean:
            return
        key = sf_clean.casefold()
        if key not in seen:
            seen.add(key)
            result.append(sf_clean)

    if explicit_result is None:
        return []

    # If it's a dict wrapper
    if isinstance(explicit_result, dict):
        if "processed_result" in explicit_result and isinstance(explicit_result["processed_result"], dict):
            return build_explicit_list(explicit_result["processed_result"], kinds=kinds)
        if "postprocessed" in explicit_result and isinstance(explicit_result["postprocessed"], dict):
            return build_explicit_list(explicit_result["postprocessed"], kinds=kinds)

        # Check skills in dict
        if "skills" in explicit_result and isinstance(explicit_result["skills"], list):
            for s in explicit_result["skills"]:
                if isinstance(s, dict):
                    evs = s.get("evidences", [])
                    if isinstance(evs, list) and evs:
                        for ev in evs:
                            if isinstance(ev, dict):
                                _consider(ev.get("surface_form"), ev.get("kind"))
                            else:
                                _consider(getattr(ev, "surface_form", None), getattr(ev, "kind", None))
                    else:
                        s_kind = s.get("kind")
                        for sf in s.get("surface_forms", []):
                            _consider(sf, s_kind)
                else:
                    evs = getattr(s, "evidences", [])
                    for ev in evs:
                        _consider(getattr(ev, "surface_form", None), getattr(ev, "kind", None))
            return result

        # Fallback for raw_llm
        if "raw_llm" in explicit_result and isinstance(explicit_result["raw_llm"], dict):
            for m in explicit_result["raw_llm"].get("explicit_skills", []):
                if isinstance(m, dict):
                    sf = m.get("mention") or m.get("surface_form")
                    _consider(sf, m.get("kind"))
            return result

        if "explicit_skills" in explicit_result and isinstance(explicit_result["explicit_skills"], list):
            for m in explicit_result["explicit_skills"]:
                if isinstance(m, dict):
                    sf = m.get("mention") or m.get("surface_form")
                    _consider(sf, m.get("kind"))
            return result

    # Object with .skills (ExtractionResult or similar)
    if hasattr(explicit_result, "skills"):
        for s in explicit_result.skills:
            evs = getattr(s, "evidences", [])
            for ev in evs:
                _consider(getattr(ev, "surface_form", None), getattr(ev, "kind", None))
        return result

    # List of skills or evidences
    if isinstance(explicit_result, (list, tuple)):
        for item in explicit_result:
            if hasattr(item, "evidences"):
                for ev in getattr(item, "evidences", []):
                    _consider(getattr(ev, "surface_form", None), getattr(ev, "kind", None))
            elif hasattr(item, "surface_form"):
                _consider(getattr(item, "surface_form", None), getattr(item, "kind", None))
            elif isinstance(item, dict):
                if "evidences" in item:
                    for ev in item.get("evidences", []):
                        if isinstance(ev, dict):
                            _consider(ev.get("surface_form"), ev.get("kind"))
                        else:
                            _consider(getattr(ev, "surface_form", None), getattr(ev, "kind", None))
                else:
                    _consider(item.get("surface_form") or item.get("mention"), item.get("kind"))
        return result

    return result


def _extract_explicit_mentions(explicit_result: Any) -> List[str]:
    """Helper to extract unique explicit mention surface forms from various representations."""
    mentions: Set[str] = set()

    # Pydantic ExtractionResult or similar object
    if hasattr(explicit_result, "skills"):
        for s in explicit_result.skills:
            if hasattr(s, "surface_forms") and s.surface_forms:
                for sf in s.surface_forms:
                    mentions.add(sf)
            if hasattr(s, "evidences") and s.evidences:
                for ev in s.evidences:
                    sf = getattr(ev, "surface_form", None)
                    if sf:
                        mentions.add(sf)
    elif isinstance(explicit_result, dict):
        if "processed_result" in explicit_result and isinstance(explicit_result["processed_result"], dict):
            return _extract_explicit_mentions(explicit_result["processed_result"])
        if "skills" in explicit_result:
            for s in explicit_result["skills"]:
                if isinstance(s, dict):
                    for sf in s.get("surface_forms", []):
                        if sf:
                            mentions.add(sf)
                    for ev in s.get("evidences", []):
                        if isinstance(ev, dict) and ev.get("surface_form"):
                            mentions.add(ev["surface_form"])
        if "raw_llm" in explicit_result and isinstance(explicit_result["raw_llm"], dict):
            for m in explicit_result["raw_llm"].get("explicit_skills", []):
                if isinstance(m, dict):
                    val = m.get("mention") or m.get("surface_form")
                    if val:
                        mentions.add(val)
        if "explicit_skills" in explicit_result:
            for m in explicit_result["explicit_skills"]:
                if isinstance(m, dict):
                    val = m.get("mention") or m.get("surface_form")
                    if val:
                        mentions.add(val)
    elif isinstance(explicit_result, list):
        for item in explicit_result:
            if isinstance(item, str):
                mentions.add(item)
            elif isinstance(item, dict):
                val = item.get("surface_form") or item.get("mention") or item.get("label")
                if val:
                    mentions.add(val)
                for sf in item.get("surface_forms", []):
                    if sf:
                        mentions.add(sf)
            elif hasattr(item, "surface_forms"):
                for sf in getattr(item, "surface_forms", []):
                    if sf:
                        mentions.add(sf)

    return sorted(m.strip() for m in mentions if m and m.strip())


def coverage_vs_explicit(
    implicit_result: Any,
    explicit_result: Any,
) -> List[Dict[str, Any]]:
    """Evaluate lexical coverage of inferred implicit skills against explicit skill mentions.

    Rule:
    -----
    For each implicit skill in `implicit_result`:
    1. Extract the implicit skill label (e.g. 'Event-Driven Architecture Design').
    2. Normalize and tokenize both the implicit label and all explicit mentions in `explicit_result`:
       - Lowercase, extract alphanumeric tokens (`[a-z0-9]+`), and stem using the standard
         Porter Stemmer algorithm.
       - No hand-made stoplist is applied (all stemmed tokens participate).
    3. Compute Jaccard similarity:
       Jaccard(A, B) = |A ∩ B| / |A ∪ B|
       between the set of stemmed tokens of the implicit label and each explicit mention.
    4. Rank explicit mentions descending by Jaccard score (tie-breaking alphabetically on mention text),
       and retain the top-3 explicit mentions.
    5. Flag `possibly_covered: bool = True` if the top Jaccard score >= 0.34, else `False`.

    Constraints & Limitations:
    --------------------------
    - Pure function: Never deletes, filters, or mutates any implicit or explicit item.
    - Purely lexical token overlap: Semantic synonyms without morphological stem overlap
      (e.g., 'scalability' vs 'high-throughput') will have Jaccard = 0.0 and will NOT be flagged.
    - Token length sensitivity: A single shared token in a 2-word implicit label vs a 1-word explicit
      mention yields Jaccard = 1/2 = 0.50 (>= 0.34, flagged), whereas a single shared token in two
      2-word phrases yields Jaccard = 1/3 = 0.333 (< 0.34, not flagged).
    - No stopword filtering: Common words (e.g. 'system', 'practice', 'development') are retained,
      allowing exact domain phrasing overlap to be detected without subjective manual stoplists.

    Returns:
    --------
    List[Dict[str, Any]], where each item represents an implicit skill:
    {
        "skill_id": str,
        "label": str,
        "top_matches": List[Dict[str, Any]],  # up to 3: {"mention": str, "surface_form": str, "jaccard": float}
        "possibly_covered": bool,             # True if top match Jaccard >= 0.34
    }
    """
    # Extract implicit skills
    implicit_skills: List[Any] = []
    if isinstance(implicit_result, list):
        implicit_skills = implicit_result
    elif hasattr(implicit_result, "skills"):
        implicit_skills = implicit_result.skills
    elif isinstance(implicit_result, dict):
        if "skills" in implicit_result:
            implicit_skills = implicit_result["skills"]
        elif "implicit_skills" in implicit_result:
            implicit_skills = implicit_result["implicit_skills"]
        else:
            implicit_skills = [implicit_result]

    explicit_mentions = _extract_explicit_mentions(explicit_result)
    exp_tokens_map = {m: tokenize_and_stem(m) for m in explicit_mentions}

    coverage_report: List[Dict[str, Any]] = []

    for skill in implicit_skills:
        if isinstance(skill, str):
            skill_id = ""
            label = skill
        elif isinstance(skill, dict):
            skill_id = skill.get("skill_id") or ""
            label = skill.get("label") or skill.get("skill_label") or ""
        else:
            skill_id = getattr(skill, "skill_id", "")
            label = getattr(skill, "label", "") or getattr(skill, "skill_label", "")

        label_tokens = tokenize_and_stem(label)

        scored_matches: List[Tuple[float, str]] = []
        for m, m_tokens in exp_tokens_map.items():
            sim = token_jaccard(label_tokens, m_tokens)
            scored_matches.append((sim, m))

        # Sort descending by Jaccard score, then ascending alphabetically by mention
        scored_matches.sort(key=lambda x: (-x[0], x[1]))
        top3_pairs = scored_matches[:3]

        top_matches = [
            {"mention": m, "surface_form": m, "jaccard": round(sim, 4)}
            for sim, m in top3_pairs
        ]

        top_score = top_matches[0]["jaccard"] if top_matches else 0.0
        possibly_covered = top_score >= 0.34

        coverage_report.append({
            "skill_id": skill_id,
            "label": label,
            "top_matches": top_matches,
            "possibly_covered": possibly_covered,
        })

    return coverage_report


def postprocess_verification(
    raw_result: Any,
    candidates: Optional[List[Any]] = None,
    model_used: Optional[str] = None,
) -> List[CandidateVerification]:
    """Parse and validate verifier LLM output with per-item tolerance.

    Per-item tolerance:
    If a candidate has an invalid verdict (not in VALID_VERDICTS),
    the verdict becomes 'invalid', is kept and returned.
    If a verdict is incompatible with its basis, it becomes 'invalid_for_basis'.
    """
    verifications_raw: List[Any] = []
    if isinstance(raw_result, dict):
        candidate_list = (
            raw_result.get("verifications")
            or raw_result.get("candidates")
            or raw_result.get("results")
        )
        if isinstance(candidate_list, list):
            verifications_raw = candidate_list
        else:
            verifications_raw = [raw_result]
    elif isinstance(raw_result, list):
        verifications_raw = raw_result

    basis_by_label: Dict[str, Optional[str]] = {}
    if candidates:
        for c in candidates:
            lbl = ""
            b = None
            if isinstance(c, dict):
                lbl = c.get("label") or c.get("skill_label") or c.get("skill") or ""
                b = c.get("basis")
            else:
                lbl = getattr(c, "label", None) or getattr(c, "skill_label", "") or ""
                b = getattr(c, "basis", None)
            if lbl:
                basis_by_label[lbl.strip().casefold()] = str(b).strip() if b is not None else None

    results: List[CandidateVerification] = []
    for item in verifications_raw:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif hasattr(item, "dict"):
            item = item.dict()

        if not isinstance(item, dict):
            continue

        raw_label = item.get("label") or item.get("skill_label") or ""
        raw_verdict = str(item.get("verdict", "")).strip().casefold()
        verdict: VerdictType = (
            raw_verdict  # type: ignore[assignment]
            if raw_verdict in VALID_VERDICTS
            else "invalid"
        )
        covered_by = item.get("covered_by")
        if covered_by is not None:
            covered_by = str(covered_by).strip() or None
            if covered_by and covered_by.lower() in ("none", "null"):
                covered_by = None
        note = item.get("note")
        if note is not None:
            note = str(note).strip() or None

        raw_basis = item.get("basis")
        if raw_basis is not None:
            raw_basis = str(raw_basis).strip() or None
        elif candidates:
            cand_key = str(raw_label).strip().casefold()
            if cand_key in basis_by_label:
                raw_basis = basis_by_label[cand_key]

        # Validate verdict against basis
        if verdict != "invalid":
            if raw_basis in ("activity", "role"):
                if verdict not in ("entailed", "plausible", "unsupported"):
                    verdict = "invalid_for_basis"
            elif raw_basis == "jd_role_context":
                if verdict not in ("normal_for_role", "possible", "unsupported"):
                    verdict = "invalid_for_basis"
            elif raw_basis is None:
                if verdict in ("normal_for_role", "possible"):
                    verdict = "invalid_for_basis"

        model_used_clean: Optional[str] = None
        if isinstance(model_used, str) and model_used.strip():
            model_used_clean = model_used.strip()

        results.append(
            CandidateVerification(
                label=str(raw_label).strip(),
                basis=raw_basis,
                verdict=verdict,
                covered_by=covered_by,
                note=note,
                model_used=model_used_clean,
            )
        )

    return results


def aggregate_runs(
    results: List[Any],
    use_snippet_rule: bool = True,
) -> List[Dict[str, Any]]:
    """Cluster candidates across K runs using stem-Jaccard and evidence snippet sharing.

    Clustering rules:
    - Two candidates are linked if:
      1. stem_jaccard(label_a, label_b) >= 0.5
         OR
      2. (use_snippet_rule AND candidates share an evidence snippet AND stem_jaccard(label_a, label_b) >= 0.25)
    - Clusters are connected components of linked candidates.
    - agreement = (number of distinct runs containing the cluster) / K.
    - returns agreement, member_labels, run_indices, and cluster_size for each cluster.
    """
    if not results:
        return []

    K = len(results)

    # Flatten candidates with run index
    candidates: List[Dict[str, Any]] = []
    for r_idx, run in enumerate(results):
        items = []
        if hasattr(run, "skills"):
            items = run.skills
        elif isinstance(run, dict):
            items = run.get("skills") or run.get("implicit_skills") or []
        elif isinstance(run, list):
            items = run

        for it in items:
            if isinstance(it, dict):
                lbl = it.get("label") or it.get("skill_label") or it.get("skill") or ""
                snips = set()
                raw_ev = it.get("evidence") or it.get("snippets") or it.get("evidences")
                if isinstance(raw_ev, list):
                    for e in raw_ev:
                        if isinstance(e, str):
                            snips.add(re.sub(r"\s+", " ", e).strip().casefold())
                        elif isinstance(e, dict):
                            t = e.get("text") or e.get("inferred_from") or e.get("inferred_from_raw")
                            if t:
                                snips.add(re.sub(r"\s+", " ", str(t)).strip().casefold())
                            if "snippets" in e and isinstance(e["snippets"], list):
                                for s in e["snippets"]:
                                    st = s.get("text") if isinstance(s, dict) else str(s)
                                    if st:
                                        snips.add(re.sub(r"\s+", " ", st).strip().casefold())
                elif isinstance(raw_ev, str):
                    snips.add(re.sub(r"\s+", " ", raw_ev).strip().casefold())
            else:
                lbl = getattr(it, "label", None) or getattr(it, "skill_label", "") or ""
                snips = set()
                evidences = getattr(it, "evidences", [])
                for ev in evidences:
                    raw_from = getattr(ev, "inferred_from_raw", None)
                    if raw_from:
                        snips.add(re.sub(r"\s+", " ", raw_from).strip().casefold())
                    for snip in getattr(ev, "snippets", []):
                        snip_text = getattr(snip, "text", "")
                        if snip_text:
                            snips.add(re.sub(r"\s+", " ", snip_text).strip().casefold())

            lbl_clean = lbl.strip()
            if not lbl_clean:
                continue

            candidates.append({
                "run_idx": r_idx,
                "label": lbl_clean,
                "stems": tokenize_and_stem(lbl_clean),
                "snippets": {s for s in snips if s},
            })

    if not candidates:
        return []

    # Build adjacency graph
    N = len(candidates)
    adj: List[List[int]] = [[] for _ in range(N)]

    for i in range(N):
        for j in range(i + 1, N):
            cand_i = candidates[i]
            cand_j = candidates[j]
            jaccard = token_jaccard(cand_i["stems"], cand_j["stems"])
            shared_snippet = bool(cand_i["snippets"] & cand_j["snippets"])

            if jaccard >= 0.5 or (use_snippet_rule and shared_snippet and jaccard >= 0.25):
                adj[i].append(j)
                adj[j].append(i)

    # Connected components
    visited = [False] * N
    clusters = []

    for i in range(N):
        if not visited[i]:
            component = []
            queue = [i]
            visited[i] = True
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in adj[curr]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)

            member_labels = [candidates[idx]["label"] for idx in component]
            represented_runs = sorted(list({candidates[idx]["run_idx"] for idx in component}))
            agreement = len(represented_runs) / K

            clusters.append({
                "agreement": round(agreement, 4),
                "member_labels": member_labels,
                "run_indices": represented_runs,
                "cluster_size": len(member_labels),
            })

    # Sort descending by agreement, then by cluster_size, then by first member label
    clusters.sort(key=lambda c: (-c["agreement"], -c["cluster_size"], c["member_labels"][0] if c["member_labels"] else ""))
    return clusters


async def verify_candidates(*args, **kwargs):
    """Module-level async wrapper for verify_candidates."""
    from matching_cv.app.services.llm_service import llm_service
    return await llm_service.verify_candidates(*args, **kwargs)


def aggregate_single_candidate_passes(
    passes: List[Any],
) -> Dict[str, Any]:
    """Aggregate 3 single-candidate verification passes per GATE I2c specification.

    Rules:
    - final_verdict = majority of 3 passes (count >= 2). If no majority, 'unstable'.
    - covered_by_final = normalized covered_by string if it appears in >= 2 of 3 passes,
      else None with covered_unstable = True (if covered_by was present in 1 pass or split).
      If all 3 passes had covered_by as None/empty, covered_unstable = False.
    - Never drops an item automatically.

    Returns:
    {
        "pass_verdicts": List[str],
        "pass_covered_by": List[Optional[str]],
        "final_verdict": str,
        "covered_by_final": Optional[str],
        "covered_unstable": bool,
    }
    """
    verdicts: List[str] = []
    covered_by_list: List[Optional[str]] = []

    for p in passes:
        verdict = "missing"
        cb: Optional[str] = None
        if isinstance(p, dict):
            vers = p.get("verifications", [])
            if vers:
                first = vers[0]
                if isinstance(first, dict):
                    verdict = first.get("verdict", "missing")
                    cb = first.get("covered_by")
                else:
                    verdict = getattr(first, "verdict", "missing")
                    cb = getattr(first, "covered_by", None)
            elif "verdict" in p:
                verdict = p["verdict"]
                cb = p.get("covered_by")
        elif hasattr(p, "verdict"):
            verdict = getattr(p, "verdict", "missing")
            cb = getattr(p, "covered_by", None)

        verdicts.append(str(verdict).strip() if verdict else "missing")
        cb_norm = str(cb).strip() if cb and str(cb).strip().lower() not in ("none", "null", "") else None
        covered_by_list.append(cb_norm)

    # Majority of 3 for verdict
    v_counts = Counter(verdicts)
    top_verdict, top_v_count = v_counts.most_common(1)[0]
    final_verdict = top_verdict if top_v_count >= 2 else "unstable"

    # Covered_by aggregation
    non_null_cbs = [cb for cb in covered_by_list if cb is not None]
    cb_counts = Counter(non_null_cbs)
    if cb_counts:
        top_cb, top_cb_count = cb_counts.most_common(1)[0]
        if top_cb_count >= 2:
            covered_by_final = top_cb
            covered_unstable = False
        else:
            covered_by_final = None
            covered_unstable = True
    else:
        covered_by_final = None
        covered_unstable = False

    return {
        "pass_verdicts": verdicts,
        "pass_covered_by": covered_by_list,
        "final_verdict": final_verdict,
        "covered_by_final": covered_by_final,
        "covered_unstable": covered_unstable,
    }


