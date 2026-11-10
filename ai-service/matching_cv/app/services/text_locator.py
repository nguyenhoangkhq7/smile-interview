"""Text locator service providing whitespace-tolerant exact substring location."""
import re
from typing import Optional, Tuple


def locate_sentence(text: str, sentence: str) -> Optional[Tuple[int, int]]:
    """
    Locate the span (start, end) of a sentence within text in a whitespace-tolerant manner.

    Algorithm:
    - Splits sentence into whitespace-delimited tokens.
    - If no tokens, returns None.
    - Builds regex pattern matching tokens separated by one or more whitespace characters (\\s+).
    - Returns match.span() on the original text, or None if not found.
    - Does NOT perform fuzzy matching (no lowercasing, no punctuation stripping).
    - Offsets directly index the original text without modification.
    """
    if not text or not sentence:
        return None

    tokens = sentence.split()
    if not tokens:
        return None

    pattern = r"\s+".join(re.escape(t) for t in tokens)
    match = re.search(pattern, text)
    if match:
        return match.span()
    return None


def norm_casefold(s: str) -> str:
    """Normalize whitespace and casefold string."""
    return re.sub(r"\s+", " ", s).strip().casefold()


def locate_mention_in_sentence(
    sentence_text: str, surface_form: str
) -> Tuple[Optional[int], Optional[int], bool]:
    """
    Search surface_form (whitespace-tolerant, casefold) inside sentence_text.

    Returns:
        (rel_start, rel_end, is_ambiguous)
        - rel_start, rel_end: offsets relative to sentence_text (or None, None if not found)
        - is_ambiguous: True if surface_form occurs more than once in sentence_text
        First occurrence wins for rel_start, rel_end.
    """
    if not sentence_text or not surface_form:
        return None, None, False

    tokens = surface_form.split()
    if not tokens:
        return None, None, False

    pattern = r"\s+".join(re.escape(t) for t in tokens)
    matches = list(re.finditer(pattern, sentence_text, flags=re.IGNORECASE))
    if not matches:
        return None, None, False

    first_match = matches[0]
    is_ambiguous = len(matches) > 1
    return first_match.start(), first_match.end(), is_ambiguous

