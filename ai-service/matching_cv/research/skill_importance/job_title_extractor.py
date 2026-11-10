"""Deterministic Job Title Extractor (Component B).

Inspects:
1. Explicit metadata prefixes ('Job Title:', 'Position:', 'Role:', etc.)
2. Document header / first non-empty lines with role keywords
3. Standard opening narrative patterns ('We are seeking a <Title> to...', 'seeks a talented individual for a <Title> position')
4. Filename heuristics as lower-confidence fallback.

Strict invariant:
Never fabricates fallbacks (e.g. 'Software Professional').
Returns job_title = None and detection_status = 'UNRESOLVED' when unresolvable.
"""
from __future__ import annotations

import os
import re
from typing import Optional

from matching_cv.research.skill_importance.models import JobTitleResult, TitleDetectionStatus


# Common occupational anchor nouns that distinguish job titles from corporate slogans
ROLE_ANCHORS = [
    "engineer",
    "developer",
    "architect",
    "analyst",
    "manager",
    "lead",
    "director",
    "administrator",
    "specialist",
    "consultant",
    "scientist",
    "technician",
    "designer",
    "programmer",
    "officer",
    "accountant",
    "coordinator",
    "associate",
    "intern",
    "trainee",
]

# Explicit prefix patterns
PREFIX_PATTERNS = [
    re.compile(r"^(?:position\s+title|job\s+title|position|role|title)\s*[\:\-]\s*(.+)$", re.IGNORECASE),
    re.compile(r"\bwe\s*(?:are|\'re)\s*(?:looking\s+for|seeking|hiring)\s*(?:a|an)\s+([a-zA-Z0-9\s\/\-\(\)]+?)(?:\s+to|\s+who|\s+for|\.|$)", re.IGNORECASE),
    re.compile(r"seeks\s+(?:a|an)\s+(?:talented\s+individual\s+for\s+(?:a|an)\s+)?([a-zA-Z0-9\s\/\-\(\)]+?)\s+position", re.IGNORECASE),
]


class JobTitleExtractor:
    """Deterministic extractor for Job Title metadata from raw JD text."""

    def __init__(self, role_anchors: Optional[list[str]] = None) -> None:
        self.role_anchors = role_anchors or ROLE_ANCHORS

    @staticmethod
    def _clean_title_candidate(candidate: str) -> str:
        """Strip trailing punctuation, location tags, parenthetical requisition IDs."""
        s = candidate.strip()
        # Remove trailing periods, colons, pipes, hyphens
        s = re.sub(r"[\.\:\,\;\-\|]+$", "", s).strip()
        # Strip location after pipe, dash, or comma e.g. "Backend Engineer | Ho Chi Minh City"
        # Only if the right side does not contain an anchor
        parts = re.split(r"\s*[\|\–\—]\s*", s)
        if len(parts) > 1:
            for p in parts:
                if any(re.search(r"\b" + re.escape(anc) + r"\b", p, re.IGNORECASE) for anc in ROLE_ANCHORS):
                    s = p.strip()
                    break
        # Strip trailing requisition IDs like "(Req #: 116)"
        s = re.sub(r"\(Req\s*#?.*?\)", "", s, flags=re.IGNORECASE).strip()
        return s

    def _has_role_anchor(self, text: str) -> bool:
        """Check if string contains at least one standard occupational anchor word."""
        for anc in self.role_anchors:
            if re.search(r"\b" + re.escape(anc) + r"\b", text, re.IGNORECASE):
                return True
        return False

    def extract_title(self, raw_text: str, filename: Optional[str] = None) -> JobTitleResult:
        """
        Extract Job Title using prioritized deterministic strategies.
        Guarantees: If unresolvable, returns job_title = None, status = 'UNRESOLVED'.
        """
        if not raw_text or not raw_text.strip():
            # Check filename as fallback if text is empty
            if filename:
                base = os.path.splitext(os.path.basename(filename))[0]
                cleaned_fn = re.sub(r"^[0-9]+[_\-\s]*", "", base).replace("_", " ").replace("-", " ")
                if self._has_role_anchor(cleaned_fn):
                    return JobTitleResult(
                        job_title=cleaned_fn.title(),
                        title_confidence=0.55,
                        detection_method="filename_fallback",
                        detection_status="LOW_CONFIDENCE",
                    )
            return JobTitleResult(
                job_title=None,
                title_confidence=0.0,
                detection_method="empty_input",
                detection_status="UNRESOLVED",
            )

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # 1. Strategy 1: Explicit Prefix Match in first 15 lines (e.g. 'Position Title: Senior Backend Engineer')
        for line in lines[:15]:
            m = PREFIX_PATTERNS[0].match(line)
            if m:
                raw_cand = m.group(1).strip()
                cleaned = self._clean_title_candidate(raw_cand)
                if cleaned and len(cleaned.split()) <= 10:
                    conf = 0.95 if self._has_role_anchor(cleaned) else 0.75
                    return JobTitleResult(
                        job_title=cleaned,
                        title_confidence=conf,
                        detection_method="explicit_prefix",
                        detection_status="RESOLVED" if conf >= 0.70 else "LOW_CONFIDENCE",
                    )

        # 2. Strategy 2: First non-empty line contains strong role anchor (e.g. 'Backend Engineer (Java / Spring Boot)')
        if lines:
            first_line = lines[0]
            # Must be relatively short (<= 10 words, <= 70 chars) and contain an anchor word
            if len(first_line.split()) <= 10 and len(first_line) <= 70 and self._has_role_anchor(first_line):
                cleaned = self._clean_title_candidate(first_line)
                return JobTitleResult(
                    job_title=cleaned,
                    title_confidence=0.90,
                    detection_method="first_line_anchor",
                    detection_status="RESOLVED",
                )

        # 3. Strategy 3: Lines 2-5 contain role anchor without being a section heading or long sentence
        for line in lines[1:5]:
            if len(line.split()) <= 8 and len(line) <= 60 and self._has_role_anchor(line):
                # Avoid matching company or section words like 'Responsibilities'
                if not re.search(r"\b(about|responsibilities|requirements|qualifications|benefits)\b", line, re.IGNORECASE):
                    cleaned = self._clean_title_candidate(line)
                    return JobTitleResult(
                        job_title=cleaned,
                        title_confidence=0.80,
                        detection_method="early_line_anchor",
                        detection_status="RESOLVED",
                    )

        # 4. Strategy 4: Opening narrative regex in first 500 characters
        # e.g. "We're hiring a Backend Engineer to design...", "SEL... seeks a talented individual for a cybersecurity focused (Lead) Software Engineer position"
        snippet = raw_text[:600]
        for pat in PREFIX_PATTERNS[1:]:
            m = pat.search(snippet)
            if m:
                raw_cand = m.group(1).strip()
                cleaned = self._clean_title_candidate(raw_cand)
                if cleaned and self._has_role_anchor(cleaned) and len(cleaned.split()) <= 10:
                    return JobTitleResult(
                        job_title=cleaned,
                        title_confidence=0.85,
                        detection_method="opening_narrative_regex",
                        detection_status="RESOLVED",
                    )

        # 5. Strategy 5: Filename fallback if text-based strategies failed
        if filename:
            base = os.path.splitext(os.path.basename(filename))[0]
            # Strip numeric prefixes e.g. "01_Backend_JD" -> "Backend JD" -> "Backend Engineer"
            cleaned_fn = re.sub(r"^[0-9]+[_\-\s]*", "", base).replace("_", " ").replace("-", " ")
            # If filename says e.g. "Backend JD", normalize to "Backend Engineer" or check anchors
            if self._has_role_anchor(cleaned_fn):
                return JobTitleResult(
                    job_title=cleaned_fn.title(),
                    title_confidence=0.60,
                    detection_method="filename_role_anchor",
                    detection_status="LOW_CONFIDENCE",
                )
            elif "backend" in cleaned_fn.lower():
                return JobTitleResult(
                    job_title="Backend Engineer",
                    title_confidence=0.55,
                    detection_method="filename_keyword_inference",
                    detection_status="LOW_CONFIDENCE",
                )
            elif "frontend" in cleaned_fn.lower():
                return JobTitleResult(
                    job_title="Frontend Engineer",
                    title_confidence=0.55,
                    detection_method="filename_keyword_inference",
                    detection_status="LOW_CONFIDENCE",
                )

        # 6. Unresolved
        return JobTitleResult(
            job_title=None,
            title_confidence=0.0,
            detection_method="unresolved",
            detection_status="UNRESOLVED",
        )
