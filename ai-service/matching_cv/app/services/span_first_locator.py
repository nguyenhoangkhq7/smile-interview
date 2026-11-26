"""
Stage 6C.3B.7: Span-First Mention Locator and Deterministic Evidence Grounding Service.

Decouples semantic skill discovery from text localization:
1. Locates extracted skill mentions directly against document text using controlled deterministic fallbacks.
2. Slices exact sentence boundaries and assigns structural section tags offline.
3. Preserves character-level provenance and verbatim substring invariants without LLM hallucination.
"""

from dataclasses import dataclass
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from matching_cv.app.services.section_tagger import find_section_spans, SectionSpan

logger = logging.getLogger(__name__)


@dataclass
class GroundedMention:
    """Represents a deterministically grounded mention span in text."""
    surface_form: str
    sentence: str
    start: Optional[int]                 # sentence start offset
    end: Optional[int]                   # sentence end offset
    mention_start: Optional[int]         # mention start offset
    mention_end: Optional[int]           # mention end offset
    section: Optional[str]
    offset_resolved: bool
    verbatim_ok: bool
    match_strategy: str                  # exact_word, exact_sub, casefold_word, whitespace_norm, ungrounded
    is_ambiguous: bool = False
    ambiguous_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "surface_form": self.surface_form,
            "sentence": self.sentence,
            "start": self.start,
            "end": self.end,
            "mention_start": self.mention_start,
            "mention_end": self.mention_end,
            "section": self.section,
            "offset_resolved": self.offset_resolved,
            "verbatim_ok": self.verbatim_ok,
            "match_strategy": self.match_strategy,
            "is_ambiguous": self.is_ambiguous,
            "ambiguous_count": self.ambiguous_count,
        }


def _build_word_boundary_pattern(mention: str, case_sensitive: bool = True) -> Optional[re.Pattern]:
    """
    Constructs regex pattern matching mention with boundary lookarounds.
    Handles trailing/leading symbols (e.g., 'C++', 'C#', '.NET') where \\b fails.
    """
    clean = mention.strip()
    if not clean:
        return None

    escaped = re.escape(clean)

    # Left boundary
    left_boundary = r"(?<![A-Za-z0-9_])" if re.match(r"^\w", clean) else r"(?<!\S)"
    # Right boundary - avoid matching 'C' inside 'C++' or 'C#'
    if clean.upper() == "C":
        right_boundary = r"(?![A-Za-z0-9_+#])"
    else:
        right_boundary = r"(?!\w)" if re.search(r"\w$", clean) else r"(?!\S)"

    pattern_str = f"{left_boundary}{escaped}{right_boundary}"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern_str, flags)
    except re.error:
        return None


def _build_whitespace_pattern(mention: str, case_sensitive: bool = True) -> Optional[re.Pattern]:
    """Builds regex pattern matching tokens separated by flexible whitespace / punctuation."""
    tokens = [t.strip() for t in re.split(r"\s+", mention.strip()) if t.strip()]
    if not tokens:
        return None

    escaped_tokens = [re.escape(t) for t in tokens]
    # Allow whitespace and optional hyphens/slashes between tokens
    sep = r"[\s\-_/]+"
    inner = sep.join(escaped_tokens)

    left = r"(?<!\w)" if re.match(r"^\w", tokens[0]) else r"(?<!\S)"
    right = r"(?!\w)" if re.search(r"\w$", tokens[-1]) else r"(?!\S)"

    pattern_str = f"{left}{inner}{right}"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern_str, flags)
    except re.error:
        return None


def _derive_sentence_bounds(text: str, m_start: int, m_end: int, max_window: int = 300) -> Tuple[int, int]:
    """
    Derives sentence boundary offsets [start, end] around a mention span.
    Uses punctuation, newline boundaries, or list delimiters.
    """
    doc_len = len(text)

    # 1. Look back for sentence start
    back_limit = max(0, m_start - max_window)
    pre_window = text[back_limit:m_start]

    # Look for paragraph break, bullet point, or sentence terminators (.!?)
    sent_start = back_limit
    # Check for paragraph break \n\n or newline before list items
    last_pbreak = pre_window.rfind("\n\n")
    if last_pbreak != -1:
        sent_start = back_limit + last_pbreak + 2
    else:
        # Check for sentence terminal followed by whitespace: [.!?]\s+
        term_matches = list(re.finditer(r"[.!?]\s+|\n", pre_window))
        if term_matches:
            last_term = term_matches[-1]
            sent_start = back_limit + last_term.end()

    # 2. Look forward for sentence end
    fwd_limit = min(doc_len, m_end + max_window)
    post_window = text[m_end:fwd_limit]

    sent_end = fwd_limit
    first_pbreak = post_window.find("\n\n")
    if first_pbreak != -1:
        sent_end = m_end + first_pbreak
    else:
        term_match = re.search(r"[.!?](?:\s|\Z)|\n", post_window)
        if term_match:
            sent_end = m_end + term_match.end()

    # Expand slightly if boundary cuts inside whitespace
    while sent_start < m_start and text[sent_start].isspace():
        sent_start += 1
    while sent_end > m_end and text[sent_end - 1].isspace():
        sent_end -= 1

    # Guarantee validity
    sent_start = max(0, min(sent_start, m_start))
    sent_end = min(doc_len, max(sent_end, m_end))

    return sent_start, sent_end


class SpanFirstLocator:
    """
    Deterministic span-first mention locator.
    Resolves mentions directly against document text with strict precision and controlled fallbacks.
    """

    def __init__(self, doc_type: str = "CV"):
        self.doc_type = doc_type

    def locate_mention(
        self,
        document_text: str,
        mention: str,
        chunk_offset_start: int = 0,
        section_spans: Optional[List[SectionSpan]] = None,
        return_all_matches: bool = True,
    ) -> List[GroundedMention]:
        """
        Locate all valid occurrences of mention in document_text.
        If return_all_matches is True, returns an evidence instance for each occurrence.
        """
        if not document_text or not mention:
            return [
                GroundedMention(
                    surface_form=mention or "",
                    sentence="",
                    start=None,
                    end=None,
                    mention_start=None,
                    mention_end=None,
                    section=None,
                    offset_resolved=False,
                    verbatim_ok=False,
                    match_strategy="ungrounded",
                )
            ]

        if section_spans is None:
            section_spans = find_section_spans(document_text, self.doc_type)

        clean_mention = mention.strip()
        matched_spans: List[Tuple[int, int]] = []
        strategy_used = "ungrounded"

        # Strategy 1: Exact case-sensitive with word boundary
        wb_pat = _build_word_boundary_pattern(clean_mention, case_sensitive=True)
        if wb_pat:
            matched_spans = [m.span() for m in wb_pat.finditer(document_text)]
            if matched_spans:
                strategy_used = "exact_word_boundary"

        # Strategy 2: Exact case-sensitive substring (fallback if punctuation/symbol in mention)
        if not matched_spans:
            sub_idx = 0
            while True:
                found = document_text.find(clean_mention, sub_idx)
                if found == -1:
                    break
                matched_spans.append((found, found + len(clean_mention)))
                sub_idx = found + max(1, len(clean_mention))
            if matched_spans:
                strategy_used = "exact_substring"

        # Strategy 3: Case-insensitive with word boundary
        if not matched_spans:
            wb_pat_ci = _build_word_boundary_pattern(clean_mention, case_sensitive=False)
            if wb_pat_ci:
                matched_spans = [m.span() for m in wb_pat_ci.finditer(document_text)]
                if matched_spans:
                    strategy_used = "casefold_word_boundary"

        # Strategy 4: Flexible whitespace pattern
        if not matched_spans:
            ws_pat = _build_whitespace_pattern(clean_mention, case_sensitive=False)
            if ws_pat:
                matched_spans = [m.span() for m in ws_pat.finditer(document_text)]
                if matched_spans:
                    strategy_used = "whitespace_normalized"

        # Strategy 5: Unicode NFKC normalization fallback
        if not matched_spans:
            norm_doc = unicodedata.normalize("NFKC", document_text)
            norm_mention = unicodedata.normalize("NFKC", clean_mention)
            if norm_mention in norm_doc:
                pos = norm_doc.find(norm_mention)
                if pos != -1 and pos + len(norm_mention) <= len(document_text):
                    matched_spans = [(pos, pos + len(norm_mention))]
                    strategy_used = "unicode_nfkc_normalized"

        # If completely ungrounded
        if not matched_spans:
            return [
                GroundedMention(
                    surface_form=clean_mention,
                    sentence="",
                    start=None,
                    end=None,
                    mention_start=None,
                    mention_end=None,
                    section=None,
                    offset_resolved=False,
                    verbatim_ok=False,
                    match_strategy="ungrounded",
                    is_ambiguous=False,
                    ambiguous_count=0,
                )
            ]

        # Process grounded spans
        is_ambiguous = len(matched_spans) > 1
        ambiguous_count = len(matched_spans)

        grounded_results: List[GroundedMention] = []
        target_spans = matched_spans if return_all_matches else [matched_spans[0]]

        for local_m_start, local_m_end in target_spans:
            exact_surface = document_text[local_m_start:local_m_end]

            # Derive sentence window
            local_s_start, local_s_end = _derive_sentence_bounds(document_text, local_m_start, local_m_end)
            sentence_text = document_text[local_s_start:local_s_end].strip()

            # Global offsets
            global_m_start = chunk_offset_start + local_m_start
            global_m_end = chunk_offset_start + local_m_end
            global_s_start = chunk_offset_start + local_s_start
            global_s_end = chunk_offset_start + local_s_end

            # Section lookup
            matched_section = "header"
            for span in section_spans:
                if span.start <= local_m_start < span.end:
                    matched_section = span.name
                    break

            # Verbatim check: exact match against original document
            verbatim_ok = (exact_surface.strip().lower() == clean_mention.lower()) or (
                unicodedata.normalize("NFKC", exact_surface).strip().lower()
                == unicodedata.normalize("NFKC", clean_mention).strip().lower()
            )

            grounded_results.append(
                GroundedMention(
                    surface_form=exact_surface,
                    sentence=sentence_text,
                    start=global_s_start,
                    end=global_s_end,
                    mention_start=global_m_start,
                    mention_end=global_m_end,
                    section=matched_section,
                    offset_resolved=True,
                    verbatim_ok=verbatim_ok,
                    match_strategy=strategy_used,
                    is_ambiguous=is_ambiguous,
                    ambiguous_count=ambiguous_count,
                )
            )

        return grounded_results
