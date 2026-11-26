"""Document Layout & Structure Remediator (JSI-4 Research Module).

Addresses upstream web scraping flattening where linebreaks and colons were stripped:
1. Strips applicant portal boilerplate instructions ('The position is described below...')
   to bring genuine job titles into the detection horizon.
2. Restores paragraph line breaks before recognized heading patterns collapsed into single text blocks.
3. Classifies structure provenance:
   - ORIGINAL (document already possessed natural linebreaks and section delimiters)
   - RECOVERED_HIGH_CONFIDENCE (standard headings cleanly segmented by boundary regex)
   - RECOVERED_UNCERTAIN (heuristic boundary recovery)
   - UNAVAILABLE (true unstructured free-text prose)
"""
from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

StructureProvenanceType = Literal[
    "ORIGINAL",
    "RECOVERED_HIGH_CONFIDENCE",
    "RECOVERED_UNCERTAIN",
    "UNAVAILABLE",
]


class RemediationResult(BaseModel):
    """Result of document layout and heading boundary remediation."""

    remediated_text: str
    provenance_status: StructureProvenanceType
    boilerplate_removed: bool
    headings_recovered: List[str]
    original_line_count: int
    remediated_line_count: int


# Applicant portal wrapper boilerplate regex
PORTAL_WRAPPER_PATTERNS = [
    re.compile(r"^The position is described below\.\s+If you want to apply,.*?(?:Please review the following job description:|\bJob Description:\b)", re.IGNORECASE | re.DOTALL),
    re.compile(r"^To apply for this position, click Apply Now.*?Need Help\?.*?(?:Please review the following job description:|\bJob Description:\b)", re.IGNORECASE | re.DOTALL),
]

# Common inline heading phrases that need preceding line breaks when collapsed into long paragraphs
INLINE_HEADING_PATTERNS = [
    (re.compile(r"(?<=[a-z0-9\.\!\?])\s+(About\s+the\s+Role|About\s+Us|Company\s+Overview)\b", re.IGNORECASE), r"\n\n\1\n"),
    (re.compile(r"(?<=[a-z0-9\.\!\?])\s+(Experiences?\s+Required\s+for\s+This\s+Role|Minimum\s+Qualifications?|Required\s+Qualifications?|Requirements?)\b", re.IGNORECASE), r"\n\n\1:\n"),
    (re.compile(r"(?<=[a-z0-9\.\!\?])\s+(Preferred\s+Qualifications?|Desired\s+Skills?|Nice\s+to\s+Have)\b", re.IGNORECASE), r"\n\n\1:\n"),
    (re.compile(r"(?<=[a-z0-9\.\!\?])\s+(Key\s+Responsibilities?|Responsibilities?\s+Include|Core\s+Duties?|What\s+You\s+Will\s+Do)\b", re.IGNORECASE), r"\n\n\1:\n"),
    (re.compile(r"(?<=[a-z0-9\.\!\?])\s+(Benefits?|What\s+We\s+Offer|Perks)\b", re.IGNORECASE), r"\n\n\1:\n"),
]


class DocumentLayoutRemediator:
    """Pre-parser layout recovery utility to restore structure lost during web scraping."""

    def remediate_layout(self, raw_text: str) -> RemediationResult:
        if not raw_text or not raw_text.strip():
            return RemediationResult(
                remediated_text="",
                provenance_status="UNAVAILABLE",
                boilerplate_removed=False,
                headings_recovered=[],
                original_line_count=0,
                remediated_line_count=0,
            )

        orig_lines = [l for l in raw_text.splitlines() if l.strip()]
        orig_count = len(orig_lines)

        text = raw_text
        bp_removed = False

        # 1. Strip applicant portal boilerplate wrapper if present at start
        for pat in PORTAL_WRAPPER_PATTERNS:
            if pat.search(text):
                text = pat.sub("", text).strip()
                bp_removed = True
                break

        # 2. Check if text is flattened (few lines relative to length)
        is_flattened = orig_count <= 4 and len(raw_text) > 400
        headings_found = []

        if is_flattened or bp_removed:
            # Insert linebreaks before collapsed headings
            for pat, repl in INLINE_HEADING_PATTERNS:
                matches = pat.findall(text)
                if matches:
                    headings_found.extend(matches)
                    text = pat.sub(repl, text)

        remediated_lines = [l for l in text.splitlines() if l.strip()]
        rem_count = len(remediated_lines)

        # Classify status
        if not is_flattened and not bp_removed:
            status: StructureProvenanceType = "ORIGINAL"
        elif headings_found:
            status = "RECOVERED_HIGH_CONFIDENCE"
        elif bp_removed:
            status = "RECOVERED_UNCERTAIN"
        else:
            status = "UNAVAILABLE"

        return RemediationResult(
            remediated_text=text,
            provenance_status=status,
            boilerplate_removed=bp_removed,
            headings_recovered=list(dict.fromkeys(headings_found)),
            original_line_count=orig_count,
            remediated_line_count=rem_count,
        )
