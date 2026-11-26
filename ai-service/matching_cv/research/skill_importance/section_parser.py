"""Deterministic and pattern-based section parser for Job Descriptions (Component A).

Overcomes the 73.3% failure rate of legacy section_tagger by supporting:
- Case-insensitive and title-case matching
- Numbered and bulleted headings (e.g. '1. Requirements:', 'Section A: Responsibilities')
- Colon-terminated and prefix-formatted headings
- Common colloquial variations ('What You'll Do', 'Nice to Have', 'Basic Qualifications')
- Controlled unknown retention without over-classifying regular prose lines as headings.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from matching_cv.research.skill_importance.models import JDSectionSpan, SectionType


# Comprehensive category alias mapping
SECTION_PATTERNS: Dict[SectionType, List[str]] = {
    "requirements": [
        "requirements",
        "key requirements",
        "minimum requirements",
        "basic requirements",
        "core requirements",
        "technical requirements",
        "qualifications",
        "basic qualifications",
        "minimum qualifications",
        "required qualifications",
        "key qualifications",
        "required skills",
        "must have",
        "must haves",
        "what you need",
        "what you'll need",
        "what you will need",
        "what we are looking for",
        "what we're looking for",
        "who you are",
        "skills and experience",
        "required experience",
        "candidate profile",
        "profile requirements",
    ],
    "responsibilities": [
        "responsibilities",
        "key responsibilities",
        "primary responsibilities",
        "core responsibilities",
        "role responsibilities",
        "position responsibilities",
        "what you'll do",
        "what you will do",
        "what you do",
        "what your day will look like",
        "a typical day might include",
        "the role",
        "your mission",
        "your impact",
        "duties",
        "key duties",
        "primary duties",
        "essential duties",
        "duties & responsibilities",
        "duties and responsibilities",
        "day to day",
    ],
    "nice_to_have": [
        "nice to have",
        "nice to haves",
        "preferred",
        "preferred qualifications",
        "preferred skills",
        "preferred experience",
        "preferred requirements",
        "desired skills",
        "desired qualifications",
        "desired experience",
        "bonus",
        "bonus points",
        "bonus skills",
        "additional qualifications",
        "additional skills",
        "plus",
        "pluses",
        "good to have",
    ],
    "about": [
        "about the role",
        "about the job",
        "about this role",
        "about this job",
        "about us",
        "about the company",
        "about our company",
        "about team",
        "about the team",
        "who we are",
        "company overview",
        "job overview",
        "role overview",
        "position overview",
        "overview",
        "job description",
        "the opportunity",
        "company description",
        "life at",
    ],
    "benefits": [
        "benefits",
        "perks",
        "perks & benefits",
        "perks and benefits",
        "what we offer",
        "what you'll get",
        "what you will get",
        "why join us",
        "compensation",
        "compensation & benefits",
        "compensation and benefits",
        "our offer",
    ],
}

# Regex to strip numbering / bullets prefix: e.g. "1.", "Section 2:", "A.", "•"
PREFIX_NUMBER_REGEX = re.compile(
    r"^(?:(?:\d+|[A-Za-z])[\.\)\:]\s*|(?:section|part)\s+\d+[\.\:\s]*|[\*\-\•\+]\s*)",
    re.IGNORECASE,
)

# Regex matching ALL-CAPS unknown headings (3..45 chars, uppercase words, spaces, &, /, -)
ALL_CAPS_UNKNOWN_REGEX = re.compile(r"^[A-Z][A-Z &/\-]{2,45}$")


class JDSectionParser:
    """Deterministic section parser for Job Descriptions with multi-format pattern matching."""

    def __init__(self, patterns: Optional[Dict[SectionType, List[str]]] = None) -> None:
        self.patterns = patterns or SECTION_PATTERNS
        # Inverted index for normalized phrase -> (section_type, exact_phrase)
        self._phrase_index: Dict[str, Tuple[SectionType, str]] = {}
        for sec_type, phrases in self.patterns.items():
            for p in phrases:
                norm_p = self.normalize_text(p)
                self._phrase_index[norm_p] = (sec_type, p)

    @staticmethod
    def normalize_text(text: str) -> str:
        """Strip punctuation, trailing colons, and collapse whitespace."""
        s = text.strip()
        if s.endswith(":"):
            s = s[:-1].strip()
        # Replace non-alphanumeric (except / and & and -) with space
        s = re.sub(r"[^\w\s\&\/\-]", " ", s)
        s = re.sub(r"\s+", " ", s).strip().casefold()
        return s

    def classify_heading_line(self, raw_line: str) -> Optional[Tuple[SectionType, float, str]]:
        """
        Evaluate if raw_line is a section heading.
        Returns (section_type, confidence, detection_method) or None.
        """
        stripped = raw_line.strip()
        if not stripped:
            return None

        # Check line length constraints: Headings are typically 1-10 words, <= 65 chars
        # Lines ending in standard sentence periods '.' are almost never headings (unless abbreviations)
        words = stripped.split()
        if len(words) > 12 or len(stripped) > 70:
            return None

        # Ignore lines ending in period if more than 3 words (likely full sentence prose)
        if stripped.endswith(".") and len(words) > 3:
            return None

        # Strip prefixes like "1. ", "Section A: ", "• "
        stripped_no_prefix = PREFIX_NUMBER_REGEX.sub("", stripped).strip()
        had_prefix = stripped_no_prefix != stripped

        norm_line = self.normalize_text(stripped_no_prefix)
        if not norm_line:
            return None

        # 1. Exact phrase lookup in alias index
        if norm_line in self._phrase_index:
            sec_type, _ = self._phrase_index[norm_line]
            method = "pattern_numbered" if had_prefix else "alias_exact"
            conf = 0.95 if had_prefix else 1.00
            return sec_type, conf, method

        # 2. Check if norm_line starts with or contains any strong key phrase
        for key_phrase, (sec_type, _) in self._phrase_index.items():
            # Only match if key_phrase is a complete token boundary inside norm_line
            pattern = r"\b" + re.escape(key_phrase) + r"\b"
            if re.search(pattern, norm_line):
                # Ensure the key phrase makes up a significant portion of the line (>50% length)
                if len(key_phrase) / max(1, len(norm_line)) >= 0.50:
                    method = "pattern_substring"
                    return sec_type, 0.85, method

        # 3. Colon-terminated lines ending in a section keyword
        if stripped.endswith(":") and len(words) <= 5:
            norm_no_colon = self.normalize_text(stripped[:-1])
            if norm_no_colon in self._phrase_index:
                sec_type, _ = self._phrase_index[norm_no_colon]
                return sec_type, 0.90, "colon_pattern"

        # 4. ALL-CAPS Unknown Heading (e.g. 'OTHER REQUIREMENTS', 'BACKGROUND CHECK')
        if ALL_CAPS_UNKNOWN_REGEX.fullmatch(stripped_no_prefix) and len(words) <= 6:
            return "unknown", 0.60, "regex_all_caps"

        return None

    def parse_sections(self, text: str) -> List[JDSectionSpan]:
        """
        Parse raw cleaned JD text into non-overlapping sequential JDSectionSpans.
        Guarantees:
        - Text before the first recognized heading belongs to 'header'
        - If no headings detected, entire text is tagged 'unknown' with low confidence
        - Offsets cover [0, len(text)] continuously.
        """
        if not text or not text.strip():
            return []

        detected_headings: List[Tuple[int, SectionType, str, float, str]] = []  # (offset, type, heading_text, conf, method)
        offset = 0

        for raw_line in text.splitlines(keepends=True):
            line_start = offset
            offset += len(raw_line)
            classification = self.classify_heading_line(raw_line)
            if classification is not None:
                sec_type, conf, method = classification
                detected_headings.append((line_start, sec_type, raw_line.strip(), conf, method))

        # Fallback if no headings detected anywhere in text
        if not detected_headings:
            return [
                JDSectionSpan(
                    section_type="unknown",
                    heading_text="",
                    start=0,
                    end=len(text),
                    confidence=0.10,
                    detection_method="fallback_unknown",
                )
            ]

        spans: List[JDSectionSpan] = []

        # 1. Header span: text before the first heading
        first_start = detected_headings[0][0]
        if first_start > 0:
            spans.append(
                JDSectionSpan(
                    section_type="header",
                    heading_text="",
                    start=0,
                    end=first_start,
                    confidence=0.80,
                    detection_method="pre_heading_header",
                )
            )

        # 2. Intermediate spans
        for i in range(len(detected_headings) - 1):
            h_start, h_type, h_text, h_conf, h_method = detected_headings[i]
            next_start = detected_headings[i + 1][0]
            spans.append(
                JDSectionSpan(
                    section_type=h_type,
                    heading_text=h_text,
                    start=h_start,
                    end=next_start,
                    confidence=h_conf,
                    detection_method=h_method,
                )
            )

        # 3. Final span running to EOF
        last_start, last_type, last_text, last_conf, last_method = detected_headings[-1]
        spans.append(
            JDSectionSpan(
                section_type=last_type,
                heading_text=last_text,
                start=last_start,
                end=len(text),
                confidence=last_conf,
                detection_method=last_method,
            )
        )

        return spans

    @staticmethod
    def section_at_offset(spans: List[JDSectionSpan], offset: Optional[int]) -> Optional[JDSectionSpan]:
        """Find the JDSectionSpan containing the given character offset."""
        if offset is None or not spans:
            return None
        for span in spans:
            if span.start <= offset < span.end:
                return span
        # If offset is at exact end of text
        if spans and offset == spans[-1].end:
            return spans[-1]
        return None
