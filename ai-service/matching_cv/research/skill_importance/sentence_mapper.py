"""Skill Sentence Occurrence Mapper (Component C).

Maps extracted skills (explicit & implicit) to discrete textual occurrences,
validating character offsets against cleaned JD text and enriching section
classifications via JDSectionParser.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Union

from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill
from matching_cv.research.paper_aligned_gnn.unified_embedding_contract import canonical_id_to_display_name
from matching_cv.research.skill_importance.models import JDSectionSpan, SkillSentenceOccurrence
from matching_cv.research.skill_importance.section_parser import JDSectionParser

logger = logging.getLogger(__name__)


class SkillSentenceMapper:
    """Extracts and validates granular sentence occurrences for every skill in a Job Description."""

    def __init__(self, section_parser: Optional[JDSectionParser] = None) -> None:
        self.section_parser = section_parser or JDSectionParser()

    @staticmethod
    def _validate_span(text: str, start: Optional[int], end: Optional[int]) -> bool:
        """Check if start/end span indices are valid within text bounds."""
        if start is None or end is None:
            return False
        if not (0 <= start < end <= len(text)):
            return False
        return True

    def map_occurrences(
        self,
        extracted_skills: List[Union[Dict[str, Any], Any]],
        cleaned_jd_text: str,
        section_spans: Optional[List[JDSectionSpan]] = None,
    ) -> List[SkillSentenceOccurrence]:
        """
        Map all occurrences of explicit and implicit skills to SkillSentenceOccurrence objects.
        Validates offsets against cleaned_jd_text and assigns section classifications.
        """
        if not section_spans and cleaned_jd_text:
            section_spans = self.section_parser.parse_sections(cleaned_jd_text)
        section_spans = section_spans or []

        occurrences: List[SkillSentenceOccurrence] = []

        for skill in extracted_skills:
            # Handle Pydantic model or dict
            is_dict = isinstance(skill, dict)
            raw_id = (
                (skill.get("canonical_skill_id") or skill.get("skill_id") or skill.get("name") or skill.get("label"))
                if is_dict
                else getattr(skill, "canonical_skill_id", getattr(skill, "skill_id", getattr(skill, "name", "")))
            )
            raw_name = (
                (skill.get("skill_display_name") or skill.get("name") or skill.get("label"))
                if is_dict
                else getattr(skill, "skill_display_name", getattr(skill, "name", getattr(skill, "label", "")))
            )
            if not raw_name:
                raw_name = (
                    skill.get("surface_forms", [raw_id])[0]
                    if is_dict and skill.get("surface_forms")
                    else (raw_id if raw_id else "")
                )
            skill_type = (
                skill.get("type", "explicit")
                if is_dict
                else getattr(skill, "type", getattr(skill, "extraction_type", "explicit"))
            )

            # Canonical normalization
            canon_id = normalize_canonical_skill(raw_id or raw_name) or str(raw_id or raw_name).strip().lower()
            disp_name = canonical_id_to_display_name(canon_id)

            evidences = (
                skill.get("evidences", [])
                if is_dict
                else getattr(skill, "evidences", [])
            )

            # Process explicit evidences
            if skill_type == "explicit" and evidences:
                for ev in evidences:
                    ev_dict = ev if isinstance(ev, dict) else ev.model_dump()
                    sent = (ev_dict.get("sentence") or "").strip()
                    if not sent:
                        continue

                    start = ev_dict.get("start")
                    end = ev_dict.get("end")
                    mention_start = ev_dict.get("mention_start")
                    mention_end = ev_dict.get("mention_end")
                    mod_text = ev_dict.get("modifier_text")

                    # Validate offsets against cleaned text if provided
                    if cleaned_jd_text and not self._validate_span(cleaned_jd_text, start, end):
                        # Try to locate sentence dynamically in text if offset mismatch occurred
                        idx = cleaned_jd_text.find(sent)
                        if idx != -1:
                            start = idx
                            end = idx + len(sent)
                        else:
                            start = None
                            end = None

                    # Section assignment: prioritized via section_parser spans
                    assigned_sec: Optional[str] = None
                    sec_conf = 0.0
                    if start is not None and section_spans:
                        span_hit = self.section_parser.section_at_offset(section_spans, start)
                        if span_hit:
                            assigned_sec = span_hit.section_type
                            sec_conf = span_hit.confidence
                    if not assigned_sec:
                        # Fallback to evidence's existing section attribute
                        raw_sec = ev_dict.get("section")
                        if raw_sec and raw_sec not in ("header", "unknown"):
                            assigned_sec = raw_sec
                            sec_conf = 0.70
                        elif raw_sec:
                            assigned_sec = raw_sec
                            sec_conf = 0.30

                    occurrences.append(
                        SkillSentenceOccurrence(
                            canonical_skill_id=canon_id,
                            skill_display_name=disp_name,
                            skill_type="explicit",
                            source_sentence=sent,
                            source_start=start,
                            source_end=end,
                            mention_start=mention_start,
                            mention_end=mention_end,
                            section_type=assigned_sec,
                            section_confidence=sec_conf,
                            modifier_text=mod_text,
                            evidence_type="explicit_mention",
                        )
                    )

            # Process implicit evidences
            elif skill_type == "implicit" and evidences:
                for ev in evidences:
                    ev_dict = ev if isinstance(ev, dict) else ev.model_dump()
                    raw_from = (ev_dict.get("inferred_from_raw") or ev_dict.get("inferred_from") or "").strip()
                    snippets = ev_dict.get("snippets", [])

                    if snippets:
                        for sn in snippets:
                            sn_dict = sn if isinstance(sn, dict) else sn.model_dump()
                            sn_text = (sn_dict.get("text") or raw_from).strip()
                            if not sn_text:
                                continue
                            start = sn_dict.get("start")
                            end = sn_dict.get("end")

                            if cleaned_jd_text and not self._validate_span(cleaned_jd_text, start, end):
                                idx = cleaned_jd_text.find(sn_text)
                                if idx != -1:
                                    start = idx
                                    end = idx + len(sn_text)
                                else:
                                    start = None
                                    end = None

                            assigned_sec = None
                            sec_conf = 0.0
                            if start is not None and section_spans:
                                span_hit = self.section_parser.section_at_offset(section_spans, start)
                                if span_hit:
                                    assigned_sec = span_hit.section_type
                                    sec_conf = span_hit.confidence
                            if not assigned_sec:
                                raw_sec = sn_dict.get("section")
                                if raw_sec:
                                    assigned_sec = raw_sec
                                    sec_conf = 0.60

                            occurrences.append(
                                SkillSentenceOccurrence(
                                    canonical_skill_id=canon_id,
                                    skill_display_name=disp_name,
                                    skill_type="implicit",
                                    source_sentence=sn_text,
                                    source_start=start,
                                    source_end=end,
                                    section_type=assigned_sec,
                                    section_confidence=sec_conf,
                                    modifier_text=None,
                                    evidence_type="implicit_snippet",
                                )
                            )
                    elif raw_from:
                        start = None
                        end = None
                        if cleaned_jd_text:
                            idx = cleaned_jd_text.find(raw_from)
                            if idx != -1:
                                start = idx
                                end = idx + len(raw_from)

                        assigned_sec = None
                        sec_conf = 0.0
                        if start is not None and section_spans:
                            span_hit = self.section_parser.section_at_offset(section_spans, start)
                            if span_hit:
                                assigned_sec = span_hit.section_type
                                sec_conf = span_hit.confidence

                        occurrences.append(
                            SkillSentenceOccurrence(
                                canonical_skill_id=canon_id,
                                skill_display_name=disp_name,
                                skill_type="implicit",
                                source_sentence=raw_from,
                                source_start=start,
                                source_end=end,
                                section_type=assigned_sec,
                                section_confidence=sec_conf,
                                modifier_text=None,
                                evidence_type="implicit_inferred",
                            )
                        )

        return occurrences

    def map_skills_to_sentences(
        self,
        jd_text: str,
        explicit_skills: Sequence[Union[Dict[str, Any], Any]],
        implicit_skills: Sequence[Union[Dict[str, Any], Any]],
        sections: Optional[List[JDSectionSpan]] = None,
    ) -> Dict[str, List[SkillSentenceOccurrence]]:
        """
        Map explicit and implicit skills to occurrences, grouped by canonical_skill_id.
        Accepts dicts, Pydantic objects, and flat source_sentence representations.
        """
        if not sections and jd_text:
            sections = self.section_parser.parse_sections(jd_text)

        all_skills: List[Dict[str, Any]] = []

        for s in explicit_skills:
            item = dict(s) if isinstance(s, dict) else s.model_dump()
            item["type"] = "explicit"
            # Normalize evidence structure if flat
            if not item.get("evidences"):
                sent = item.get("source_sentence") or item.get("sentence")
                if sent:
                    item["evidences"] = [
                        {
                            "sentence": sent,
                            "start": item.get("source_start") or item.get("start"),
                            "end": item.get("source_end") or item.get("end"),
                            "modifier_text": item.get("modifier_text"),
                            "section": item.get("section_type") or item.get("section"),
                        }
                    ]
            all_skills.append(item)

        for s in implicit_skills:
            item = dict(s) if isinstance(s, dict) else s.model_dump()
            item["type"] = "implicit"
            if not item.get("evidences"):
                sent = item.get("source_sentence") or item.get("sentence") or item.get("inferred_from_raw")
                if sent:
                    item["evidences"] = [
                        {
                            "inferred_from_raw": sent,
                            "snippets": [{"text": sent, "start": item.get("start"), "end": item.get("end")}],
                        }
                    ]
            all_skills.append(item)

        raw_occurrences = self.map_occurrences(all_skills, jd_text, sections)

        # Group by canonical_skill_id
        grouped: Dict[str, List[SkillSentenceOccurrence]] = {}
        for occ in raw_occurrences:
            grouped.setdefault(occ.canonical_skill_id, []).append(occ)

        # For any skill that had no explicit occurrence mapped, search text or synthesize fallback
        for s in all_skills:
            cid = s.get("canonical_skill_id") or s.get("skill_id") or s.get("name")
            norm_cid = normalize_canonical_skill(cid) or str(cid).strip().lower()
            if norm_cid not in grouped:
                disp_name = canonical_id_to_display_name(norm_cid)
                matched_sent = None
                assigned_sec = None
                sec_conf = 0.0

                # Check if JD text contains a verbatim occurrence of this skill
                if jd_text:
                    for line in jd_text.splitlines():
                        cleaned_line = line.strip("-•* \t\r")
                        if len(cleaned_line) > 5:
                            pattern = r"\b" + re.escape(disp_name) + r"\b"
                            if re.search(pattern, cleaned_line, re.IGNORECASE) or re.search(r"\b" + re.escape(norm_cid) + r"\b", cleaned_line, re.IGNORECASE):
                                matched_sent = cleaned_line
                                if sections:
                                    idx = jd_text.find(cleaned_line)
                                    if idx != -1:
                                        span_hit = self.section_parser.section_at_offset(sections, idx)
                                        if span_hit:
                                            assigned_sec = span_hit.section_type
                                            sec_conf = span_hit.confidence
                                break

                sent = s.get("source_sentence") or s.get("sentence") or matched_sent or f"Experience with {disp_name}"
                ev_type = "matched_line" if matched_sent else "fallback_synthetic"

                if not assigned_sec and sections:
                    for sec in sections:
                        if sec.section_type in ("requirements", "responsibilities"):
                            assigned_sec = sec.section_type
                            sec_conf = sec.confidence
                            break

                grouped[norm_cid] = [
                    SkillSentenceOccurrence(
                        canonical_skill_id=norm_cid,
                        skill_display_name=disp_name,
                        skill_type=s.get("type", "explicit"),
                        source_sentence=sent,
                        source_start=None,
                        source_end=None,
                        section_type=assigned_sec,
                        section_confidence=sec_conf,
                        modifier_text=None,
                        evidence_type=ev_type,
                    )
                ]

        return grouped
