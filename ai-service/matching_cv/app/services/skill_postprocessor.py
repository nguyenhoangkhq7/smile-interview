"""Service responsible for post-processing and validating skill extractions."""
import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional

from matching_cv.app.schemas.skill_extraction import (
    Evidence,
    ExtractedSkill,
    ExtractionMeta,
    ExtractionResult,
    ExtractionStats,
    KindSourceType,
    KindType,
    RawExtraction,
    RawSkillMention,
    check_verbatim_mention,
)
from matching_cv.app.services.section_tagger import find_section_spans, section_at
from matching_cv.app.services.text_locator import locate_mention_in_sentence, locate_sentence



VALID_CATEGORIES = {
    "Technology/Tool",
    "Technical Concept",
    "Engineering Practice",
    "Domain Knowledge",
    "Certification",
    "Technical Standard",
}


class SkillPostprocessor:
    """Post-processor for raw LLM extraction into final ExtractionResult contract."""

    @staticmethod
    def slugify_skill(surface_form: str) -> str:
        """Compute canonical slug from surface_form with inflectional role normalization."""
        slug = re.sub(r"[^\w\-\.]+|_+", "-", unicodedata.normalize("NFKC", surface_form).lower()).strip("-.")
        # Normalize inflectional plural role suffixes (e.g. frontends -> frontend)
        slug = re.sub(r"-backends$", "-backend", slug)
        slug = re.sub(r"-frontends$", "-frontend", slug)
        slug = re.sub(r"-pipelines$", "-pipeline", slug)
        slug = re.sub(r"-systems$", "-system", slug)
        if not slug or not slug[0].isalnum():
            return f"unmapped:{slug if slug else 'unknown'}"
        return slug

    def process_extraction(
        self,
        raw_result: Any,
        text: str,
        filename: Optional[str] = None,
        document_type: Optional[Literal["CV", "JD"]] = None,
        extraction_meta: Optional[ExtractionMeta] = None,
    ) -> ExtractionResult:
        """
        Validate and post-process raw LLM extraction into final ExtractionResult contract:
        - Validates via RawExtraction schema.
        - Computes canonical skill_id (slug) for each surface_form.
        - Preserves raw category string in category_raw; sets category if in 6 known categories.
        - Locates sentence offsets (start, end) into cleaned document text.
        - If sentence is NOT found in cleaned text, sets start=None, end=None, offset_resolved=False.
        - Preserves LLM kind with kind_source='llm', or infers from category with kind_source='inferred'.
        - Verifies verbatim occurrence (surface_form in sentence, casefold, whitespace-tolerant) -> verbatim_ok.
        - Locates mention offsets (mention_start, mention_end) inside evidence span text[ev.start:ev.end].
        - Deduplicates mentions into canonical skills while preserving unique surface_forms and merging evidences.
        - Derives canonical skill kind from its first evidence.
        - Computes stats including unresolved_mentions, ambiguous_mentions, and unknown_category_mentions.
        - Enforces ExtractionResult invariants.
        """
        if extraction_meta is None and isinstance(raw_result, dict):
            meta_dict = raw_result.get("extraction_meta") or raw_result.get("_extraction_meta")
            if meta_dict and isinstance(meta_dict, dict):
                try:
                    extraction_meta = ExtractionMeta.model_validate(meta_dict)
                except Exception:
                    pass

        raw_items: List[Any] = []
        if isinstance(raw_result, dict):
            items_candidate = raw_result.get("skills") if "skills" in raw_result else raw_result.get("explicit_skills")
            if items_candidate is not None:
                raw_items = items_candidate if isinstance(items_candidate, list) else [items_candidate]
        elif isinstance(raw_result, list):
            raw_items = raw_result
        elif hasattr(raw_result, "skills"):
            raw_items = getattr(raw_result, "skills")
        elif hasattr(raw_result, "explicit_skills"):
            raw_items = getattr(raw_result, "explicit_skills")

        section_spans = find_section_spans(text, document_type or "CV") if text else []
        skills_by_id: Dict[str, ExtractedSkill] = {}
        quarantined: List[Dict[str, Any]] = []

        VALID_KINDS = {"skill", "domain", "context", "certification"}

        # Detect compact extraction schema (explicit_compact_v1)
        is_compact = False
        if extraction_meta and getattr(extraction_meta, "schema_version", None) == "explicit_compact_v1":
            is_compact = True
        elif isinstance(raw_result, dict) and raw_result.get("schema_version") == "explicit_compact_v1":
            is_compact = True
        elif raw_items and all(
            isinstance(it, dict)
            and ("mention" in it or "name" in it)
            and ("sentence" not in it and "source_sentence" not in it)
            for it in raw_items
        ):
            is_compact = True

        if is_compact:
            from matching_cv.app.services.span_first_locator import SpanFirstLocator
            locator = SpanFirstLocator(doc_type=document_type or "CV")

            for item in raw_items:
                if not isinstance(item, dict):
                    quarantined.append({
                        "raw_item": item,
                        "errors": [f"Item is not a dictionary / object (got {type(item).__name__})"],
                    })
                    continue

                name_val = item.get("name") or item.get("mention")
                mention_val = item.get("mention") or item.get("surface_form")
                if not mention_val or not str(mention_val).strip():
                    quarantined.append({
                        "raw_item": item,
                        "errors": ["Missing required field 'mention' (or 'surface_form') in compact item"],
                    })
                    continue

                mention_str = str(mention_val).strip()
                name_str = str(name_val).strip() if name_val else mention_str
                skill_id = self.slugify_skill(name_str)

                raw_category = item.get("category", "Technology/Tool")
                category: Optional[CategoryType] = (
                    raw_category if raw_category in VALID_CATEGORIES else None  # type: ignore[assignment]
                )

                grounded_mentions = locator.locate_mention(
                    document_text=text,
                    mention=mention_str,
                    section_spans=section_spans,
                    return_all_matches=True,
                )

                for gm in grounded_mentions:
                    evidence = Evidence(
                        surface_form=gm.surface_form,
                        kind="skill",
                        kind_raw="skill",
                        kind_source="inferred",
                        category=category,
                        category_raw=raw_category,
                        sentence=gm.sentence,
                        start=gm.start,
                        end=gm.end,
                        offset_resolved=gm.offset_resolved,
                        verbatim_ok=gm.verbatim_ok,
                        modifier_text=None,
                        section=gm.section,
                        mention_start=gm.mention_start,
                        mention_end=gm.mention_end,
                        mention_ambiguous=gm.is_ambiguous,
                    )

                    if skill_id in skills_by_id:
                        existing_skill = skills_by_id[skill_id]
                        existing_skill.evidences.append(evidence)
                        if gm.surface_form and gm.surface_form not in existing_skill.surface_forms:
                            existing_skill.surface_forms.append(gm.surface_form)
                        if gm.section and gm.section not in existing_skill.sections:
                            existing_skill.sections.append(gm.section)
                    else:
                        initial_sections = [gm.section] if gm.section else []
                        skills_by_id[skill_id] = ExtractedSkill(
                            skill_id=skill_id,
                            surface_forms=[gm.surface_form] if gm.surface_form else [mention_str],
                            category=category,
                            category_raw=raw_category,
                            kind="skill",
                            type="explicit",
                            confidence=None,
                            sections=initial_sections,
                            evidences=[evidence],
                        )

            # Build stats and return ExtractionResult for compact path
            skills = list(skills_by_id.values())
            total_mentions = sum(len(s.evidences) for s in skills)
            unique_skills = len(skills)
            unresolved_evidences = sum(1 for s in skills for ev in s.evidences if not ev.offset_resolved)
            non_verbatim_mentions = sum(1 for s in skills for ev in s.evidences if not ev.verbatim_ok)
            kind_conflicts = 0
            header_evidences = sum(1 for s in skills for ev in s.evidences if ev.offset_resolved and ev.section == "header")
            unresolved_mentions = sum(1 for s in skills if not any(ev.offset_resolved for ev in s.evidences))
            ambiguous_mentions = sum(1 for s in skills for ev in s.evidences if getattr(ev, "mention_ambiguous", False))
            unknown_category_mentions = sum(1 for s in skills for ev in s.evidences if ev.category is None)

            stats = ExtractionStats(
                total_mentions=total_mentions,
                unique_skills=unique_skills,
                unresolved_mentions=unresolved_mentions,
                ambiguous_mentions=ambiguous_mentions,
                unknown_category_mentions=unknown_category_mentions,
                unresolved_evidences=unresolved_evidences,
                non_verbatim_mentions=non_verbatim_mentions,
                kind_conflicts=kind_conflicts,
                header_evidences=header_evidences,
            )

            if extraction_meta is None:
                from datetime import datetime, timezone
                extraction_meta = ExtractionMeta(
                    prompt_sha256="compact_span_first_sha256",
                    prompt_variant="COMPACT",
                    model_configured="compact_extractor",
                    extracted_at=datetime.now(timezone.utc).isoformat(),
                    schema_version="explicit_compact_v1",
                )

            return ExtractionResult(
                filename=filename,
                document_type=document_type,
                skills=skills,
                stats=stats,
                quarantined=quarantined,
                extraction_meta=extraction_meta,
            )

        # Legacy Extraction Path (schema_version != explicit_compact_v1)
        for item in raw_items:
            # Check structural requirements
            if not isinstance(item, dict):
                quarantined.append({
                    "raw_item": item,
                    "errors": [f"Item is not a dictionary / object (got {type(item).__name__})"],
                })
                continue

            sf_val = item.get("surface_form") if "surface_form" in item else item.get("mention")
            sent_val = item.get("sentence") if "sentence" in item else item.get("source_sentence")

            errors: List[str] = []
            if sf_val is None:
                errors.append("Missing required field 'surface_form' (or 'mention')")
            elif not isinstance(sf_val, str):
                errors.append(f"Field 'surface_form' must be a string, got {type(sf_val).__name__}")
            elif not sf_val.strip():
                errors.append("Field 'surface_form' must not be empty or whitespace")

            if sent_val is None:
                errors.append("Missing required field 'sentence' (or 'source_sentence')")
            elif not isinstance(sent_val, str):
                errors.append(f"Field 'sentence' must be a string, got {type(sent_val).__name__}")
            elif not sent_val.strip():
                errors.append("Field 'sentence' must not be empty or whitespace")

            if errors:
                quarantined.append({
                    "raw_item": item,
                    "errors": errors,
                })
                continue

            try:
                mention_item = RawSkillMention.model_validate(item)
            except Exception as exc:
                quarantined.append({
                    "raw_item": item,
                    "errors": [f"Pydantic validation error: {str(exc)}"],
                })
                continue

            surface_form = mention_item.surface_form.strip()
            skill_id = self.slugify_skill(surface_form)

            raw_category = mention_item.category
            if raw_category in VALID_CATEGORIES:
                category: Optional[CategoryType] = raw_category  # type: ignore[assignment]
            else:
                category = None

            # Resolve kind and kind_source: explicit LLM kind wins over category inference
            raw_kind = mention_item.kind
            if raw_kind is not None:
                raw_kind_str = str(raw_kind).strip().lower()
                if raw_kind_str in VALID_KINDS:
                    kind: Optional[KindType] = raw_kind_str  # type: ignore[assignment]
                    kind_raw = str(raw_kind)
                    kind_source: KindSourceType = "llm"
                else:
                    kind = None
                    kind_raw = str(raw_kind)
                    kind_source = "invalid"
            else:
                kind_raw = None
                if category == "Domain Knowledge":
                    kind = "domain"
                    kind_source = "inferred"
                elif category == "Certification":
                    kind = "certification"
                    kind_source = "inferred"
                else:
                    kind = "skill"
                    kind_source = "inferred"

            # Compute character offsets of sentence in raw_text using whitespace-tolerant locator
            sentence = mention_item.sentence
            span = locate_sentence(text, sentence)
            if span is not None:
                start: Optional[int] = span[0]
                end: Optional[int] = span[1]
                offset_resolved = True
                sentence_span_text = text[start:end]
                rel_start, rel_end, is_ambiguous = locate_mention_in_sentence(
                    sentence_span_text, surface_form
                )
                if rel_start is not None and rel_end is not None:
                    mention_start: Optional[int] = start + rel_start
                    mention_end: Optional[int] = start + rel_end
                    mention_ambiguous = is_ambiguous
                else:
                    mention_start = None
                    mention_end = None
                    mention_ambiguous = False
            else:
                start = None
                end = None
                offset_resolved = False
                mention_start = None
                mention_end = None
                mention_ambiguous = False

            evidence_section = section_at(section_spans, start) if start is not None else None
            verbatim_ok = check_verbatim_mention(surface_form, sentence)

            evidence = Evidence(
                surface_form=surface_form,
                kind=kind,
                kind_raw=kind_raw,
                kind_source=kind_source,
                category=category,
                category_raw=raw_category,
                sentence=sentence,
                start=start,
                end=end,
                offset_resolved=offset_resolved,
                verbatim_ok=verbatim_ok,
                modifier_text=mention_item.modifier_text,
                section=evidence_section,
                mention_start=mention_start,
                mention_end=mention_end,
                mention_ambiguous=mention_ambiguous,
            )

            if skill_id in skills_by_id:
                # Merge evidence into existing canonical skill
                existing_skill = skills_by_id[skill_id]
                existing_skill.evidences.append(evidence)
                if surface_form not in existing_skill.surface_forms:
                    existing_skill.surface_forms.append(surface_form)
                if evidence_section and evidence_section not in existing_skill.sections:
                    existing_skill.sections.append(evidence_section)
            else:
                initial_sections = [evidence_section] if evidence_section else []
                skills_by_id[skill_id] = ExtractedSkill(
                    skill_id=skill_id,
                    surface_forms=[surface_form],
                    category=category,
                    category_raw=raw_category,
                    kind=kind,
                    type="explicit",
                    confidence=None,
                    sections=initial_sections,
                    evidences=[evidence],
                )

        skills = list(skills_by_id.values())
        total_mentions = sum(len(s.evidences) for s in skills)
        unique_skills = len(skills)
        unresolved_evidences = sum(
            1 for s in skills for ev in s.evidences if not ev.offset_resolved
        )
        non_verbatim_mentions = sum(
            1 for s in skills for ev in s.evidences if not ev.verbatim_ok
        )
        kind_conflicts = sum(
            1 for s in skills if len({ev.kind for ev in s.evidences if ev.kind is not None}) > 1
        )
        header_evidences = sum(
            1 for s in skills for ev in s.evidences if ev.offset_resolved and ev.section == "header"
        )
        unresolved_mentions = sum(
            1 for s in skills for ev in s.evidences if ev.mention_start is None
        )
        ambiguous_mentions = sum(
            1 for s in skills for ev in s.evidences if ev.mention_ambiguous
        )
        unknown_category_mentions = sum(
            1 for s in skills for ev in s.evidences if ev.category_raw is not None and ev.category is None
        )
        invalid_kind_mentions = sum(
            1 for s in skills for ev in s.evidences if ev.kind is None
        )
        quarantined_mentions = len(quarantined)

        stats = ExtractionStats(
            total_mentions=total_mentions,
            unique_skills=unique_skills,
            unresolved_evidences=unresolved_evidences,
            kind_conflicts=kind_conflicts,
            non_verbatim_mentions=non_verbatim_mentions,
            header_evidences=header_evidences,
            unresolved_mentions=unresolved_mentions,
            ambiguous_mentions=ambiguous_mentions,
            unknown_category_mentions=unknown_category_mentions,
            invalid_kind_mentions=invalid_kind_mentions,
            quarantined_mentions=quarantined_mentions,
        )

        text_sha256 = (
            hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None
        )

        return ExtractionResult(
            filename=filename,
            document_type=document_type,
            text_sha256=text_sha256,
            stats=stats,
            skills=skills,
            quarantined=quarantined,
            extraction_meta=extraction_meta,
        )


skill_postprocessor = SkillPostprocessor()
