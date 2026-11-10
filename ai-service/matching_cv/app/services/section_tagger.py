"""Deterministic section tagging for CV and JD documents."""
from dataclasses import dataclass
import re
from typing import List, Optional

CV_SECTION_ALIASES = {
    # summary/profile/objective/about me -> "summary"
    "summary": "summary",
    "profile": "summary",
    "objective": "summary",
    "about me": "summary",
    # skills/technical skills/key skills -> "skills"
    "skills": "skills",
    "technical skills": "skills",
    "key skills": "skills",
    # experience/work experience/professional experience/employment history -> "experience"
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    # education -> "education"
    "education": "education",
    # certifications/certificates/licenses & certifications -> "certifications"
    "certifications": "certifications",
    "certificates": "certifications",
    "licenses & certifications": "certifications",
    # projects -> "projects"
    "projects": "projects",
}

JD_SECTION_ALIASES = {
    # about the role/about us/overview/about the company -> "about"
    "about the role": "about",
    "about us": "about",
    "overview": "about",
    "about the company": "about",
    # key responsibilities/responsibilities/what you will do -> "responsibilities"
    "key responsibilities": "responsibilities",
    "responsibilities": "responsibilities",
    "what you will do": "responsibilities",
    # requirements/qualifications/must have -> "requirements"
    "requirements": "requirements",
    "qualifications": "requirements",
    "must have": "requirements",
    # nice to have/preferred/bonus/preferred qualifications -> "nice_to_have"
    "nice to have": "nice_to_have",
    "preferred": "nice_to_have",
    "bonus": "nice_to_have",
    "preferred qualifications": "nice_to_have",
    # benefits/what we offer -> "benefits"
    "benefits": "benefits",
    "what we offer": "benefits",
}

# Matches ALL-CAPS words, spaces, &, /, - only; length 3..41; no digits or dots
UNKNOWN_HEADING_REGEX = re.compile(r"^[A-Z][A-Z &/\-]{2,40}$")


@dataclass
class SectionSpan:
    name: str
    heading_text: str
    start: int
    end: int


def normalize_line(line: str) -> str:
    """
    Normalize a line for heading lookup:
    strip, remove a trailing ':', casefold, collapse whitespace.
    """
    s = line.strip()
    if s.endswith(":"):
        s = s[:-1].strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


def find_section_spans(text: str, document_type: str = "CV") -> List[SectionSpan]:
    """
    Walk the cleaned text line by line, tracking each line's start offset.
    A line is a HEADING iff its normalized form exactly equals a key in the alias table,
    or matches UNKNOWN_HEADING_REGEX (creating an 'unknown' section span).
    Text before the first heading belongs to a 'header' span.
    Each span runs from its heading line start to the next heading line start (last span: end of text).

    Note on documents without recognized headings:
    If a document contains no recognized section headings (e.g. short unformatted text snippets),
    the entire text is assigned to a single fallback span with name="header" (start=0, end=len(text)).
    Consequently, in such documents, all resolved evidences are tagged with section="header", and
    stats.header_evidences will equal the count of all resolved evidences.
    Therefore, stats.header_evidences is primarily meaningful for documents where section headings
    were successfully identified.
    """
    if not text:
        return []

    doc_type_upper = document_type.upper() if document_type else "CV"
    aliases = JD_SECTION_ALIASES if "JD" in doc_type_upper else CV_SECTION_ALIASES

    raw_headings = []
    offset = 0

    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(raw_line)
        stripped = raw_line.rstrip("\r\n").strip()
        if not stripped:
            continue

        norm = normalize_line(stripped)
        if norm in aliases:
            raw_headings.append((line_start, aliases[norm], stripped))
        elif UNKNOWN_HEADING_REGEX.fullmatch(stripped):
            raw_headings.append((line_start, "unknown", stripped))

    spans: List[SectionSpan] = []
    if not raw_headings:
        return [SectionSpan(name="header", heading_text="", start=0, end=len(text))]

    # Text before the first heading belongs to "header"
    if raw_headings[0][0] > 0:
        spans.append(SectionSpan(name="header", heading_text="", start=0, end=raw_headings[0][0]))

    # Intermediate spans
    for i in range(len(raw_headings) - 1):
        spans.append(
            SectionSpan(
                name=raw_headings[i][1],
                heading_text=raw_headings[i][2],
                start=raw_headings[i][0],
                end=raw_headings[i + 1][0],
            )
        )

    # Last span runs to the end of text
    spans.append(
        SectionSpan(
            name=raw_headings[-1][1],
            heading_text=raw_headings[-1][2],
            start=raw_headings[-1][0],
            end=len(text),
        )
    )

    return spans


def section_at(spans: List[SectionSpan], offset: Optional[int]) -> Optional[str]:
    """
    Find the section name of the span containing offset.
    Returns None if offset is None or not found.
    """
    if offset is None:
        return None
    for span in spans:
        if span.start <= offset < span.end:
            return span.name
    # Handle offset at the exact end of text
    if spans and offset == spans[-1].end:
        return spans[-1].name
    return None
