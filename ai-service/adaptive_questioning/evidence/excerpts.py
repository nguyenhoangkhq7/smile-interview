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


_VOICE_EDGE_PUNCT = ",.;:?!"


def _strip_voice_punct(token: str) -> str:
    return token.strip(_VOICE_EDGE_PUNCT)


def _match_voice_punctuation(excerpt: str, answer: str) -> str | None:
    """Allow light STT punctuation differences (`, . ; : ? !`) while requiring exact contiguous words/accents."""
    if "..." in excerpt or "…" in excerpt:
        return None
    needle_tokens = [
        _strip_voice_punct(unicodedata.normalize("NFC", token))
        for token in excerpt.split()
    ]
    needle_tokens = [token for token in needle_tokens if token]
    if not needle_tokens:
        return None
    answer_tokens: list[tuple[str, int, int]] = []
    for match in re.finditer(r"\S+", answer):
        cleaned = _strip_voice_punct(unicodedata.normalize("NFC", match.group()))
        if cleaned:
            answer_tokens.append((cleaned, match.start(), match.end()))
    count = len(needle_tokens)
    for index in range(len(answer_tokens) - count + 1):
        if all(answer_tokens[index + offset][0] == needle_tokens[offset] for offset in range(count)):
            return answer[answer_tokens[index][1]:answer_tokens[index + count - 1][2]]
    return None


def source_excerpt(
    excerpt: str,
    answer: str,
    *,
    allow_punctuation_tolerance: bool = False,
) -> str | None:
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
    if allow_punctuation_tolerance:
        return _match_voice_punctuation(excerpt, answer)
    return None
