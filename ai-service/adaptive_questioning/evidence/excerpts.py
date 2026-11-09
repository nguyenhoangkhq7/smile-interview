"""Resolve formatting-only quote differences back to the original answer text."""
import re
import unicodedata


def source_lines(line_range: tuple[int, int], answer: str) -> str | None:
    """Resolve explicit line references without reconstructing or rewriting code."""
    lines = answer.splitlines(keepends=True)
    start, end = line_range
    if not 1 <= start <= end <= len(lines):
        return None
    excerpt = "".join(lines[start - 1:end])
    return excerpt if excerpt.strip() else None


def source_excerpt(excerpt: str, answer: str) -> str | None:
    """Never paraphrase, ignore case/accents, or join noncontiguous evidence."""
    if not excerpt.strip():
        return None
    if excerpt in answer:
        return excerpt
    # Map character-cluster boundaries too: quotes may end before punctuation.
    parts = []
    starts, ends = {}, {}
    position = 0
    for match in re.finditer(r"\S+", answer):
        token = match.group()
        clusters = []
        index = 0
        while index < len(token):
            end = index + 1
            while end < len(token) and unicodedata.combining(token[end]):
                end += 1
            cluster = unicodedata.normalize("NFC", token[index:end])
            starts[position] = match.start() + index
            clusters.append(cluster)
            position += len(cluster)
            ends[position] = match.start() + end
            index = end
        parts.append("".join(clusters))
        position += 1  # single separator in the normalized text
    normalized = " ".join(parts)
    needle = " ".join(unicodedata.normalize("NFC", excerpt).split())
    offset = normalized.find(needle)
    while offset >= 0:
        end = offset + len(needle)
        if offset in starts and end in ends:
            return answer[starts[offset]:ends[end]]
        offset = normalized.find(needle, offset + 1)
    return None
