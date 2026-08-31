import re
from dataclasses import dataclass
from hashlib import sha256

_HEADING_LINE = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
_ASCII_WORD = re.compile(r"[A-Za-z0-9_+#.-]")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    sequence_index: int
    content: str
    content_hash: str
    character_count: int
    start_offset: int
    end_offset: int
    token_count: int | None = None
    section_heading: str | None = None


def _section_heading_at(text: str, offset: int) -> str | None:
    heading: str | None = None
    for match in _HEADING_LINE.finditer(text):
        if match.start() > offset:
            break
        heading = match.group(1).strip()
    return heading


def _preferred_end(text: str, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return len(text)
    minimum = start + max(1, int((hard_end - start) * 0.6))
    if text.count("```", start, hard_end) % 2 == 1:
        opening_fence = text.rfind("```", start, hard_end)
        if opening_fence >= minimum:
            return opening_fence
    for marker in (
        "\n\n",
        "\n",
        "。",
        "\uff01",
        "\uff1f",
        ". ",
        "! ",
        "? ",
        "\uff1b",
        "; ",
        "\uff0c",
        ", ",
    ):
        index = text.rfind(marker, minimum, hard_end)
        if index != -1:
            return index + len(marker)
    return hard_end


def _preferred_overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    """Move the next start to a readable boundary instead of cutting through a word."""
    target = max(start + 1, end - overlap)
    if overlap == 0 or target >= end:
        return end

    # Prefer the first complete paragraph/sentence inside the requested overlap window.
    markers = (
        "\n\n",
        "\n",
        "。",
        "\uff01",
        "\uff1f",
        ". ",
        "! ",
        "? ",
        "\uff1b",
        "; ",
    )
    forward = [
        index + len(marker) for marker in markers if (index := text.find(marker, target, end)) != -1
    ]
    if forward:
        candidate = min(forward)
        while candidate < end and text[candidate].isspace():
            candidate += 1
        if candidate < end:
            return _align_code_fence_start(text, start, end, candidate)

    backward = [
        index + len(marker)
        for marker in markers
        if (index := text.rfind(marker, start + 1, target)) != -1
    ]
    if backward:
        candidate = max(backward)
        while candidate < end and text[candidate].isspace():
            candidate += 1
        if candidate < end:
            return _align_code_fence_start(text, start, end, candidate)

    # A long code/English line may have no sentence marker. At minimum, never restart
    # from the middle of an ASCII identifier such as "localhost" or "execute".
    candidate = target
    if (
        candidate > 0
        and candidate < end
        and _ASCII_WORD.fullmatch(text[candidate - 1])
        and _ASCII_WORD.fullmatch(text[candidate])
    ):
        while candidate < end and _ASCII_WORD.fullmatch(text[candidate]):
            candidate += 1
    while candidate < end and text[candidate].isspace():
        candidate += 1
    return _align_code_fence_start(text, start, end, candidate)


def _align_code_fence_start(text: str, start: int, end: int, candidate: int) -> int:
    if text.count("```", 0, candidate) % 2 == 0:
        return candidate
    opening_fence = text.rfind("```", start + 1, candidate + 1)
    if opening_fence != -1:
        return opening_fence
    closing_fence = text.find("```", candidate, end)
    if closing_fence == -1:
        return candidate
    after_fence = closing_fence + 3
    while after_fence < end and text[after_fence].isspace():
        after_fence += 1
    return after_fence if after_fence < end else end


def split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[ChunkDraft]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    chunks: list[ChunkDraft] = []
    start = 0
    while start < len(text):
        hard_end = min(len(text), start + chunk_size)
        end = _preferred_end(text, start, hard_end)

        left_trimmed = text[start:end].lstrip()
        actual_start = end - len(left_trimmed)
        content = left_trimmed.rstrip()
        actual_end = actual_start + len(content)
        if content:
            chunks.append(
                ChunkDraft(
                    sequence_index=len(chunks),
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    character_count=len(content),
                    start_offset=actual_start,
                    end_offset=actual_end,
                    token_count=None,
                    section_heading=_section_heading_at(text, actual_start),
                )
            )
        if end >= len(text):
            break
        start = _preferred_overlap_start(text, start, end, chunk_overlap)
    return chunks


def split_text_by_tokens(
    text: str,
    *,
    token_offsets: list[tuple[int, int]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkDraft]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")
    if not token_offsets:
        return []
    chunks: list[ChunkDraft] = []
    token_start = 0
    while token_start < len(token_offsets):
        token_end = min(len(token_offsets), token_start + chunk_size)
        start_offset = token_offsets[token_start][0]
        end_offset = token_offsets[token_end - 1][1]
        raw = text[start_offset:end_offset]
        left_trimmed = raw.lstrip()
        actual_start = end_offset - len(raw) + (len(raw) - len(left_trimmed))
        content = left_trimmed.rstrip()
        actual_end = actual_start + len(content)
        if content:
            chunks.append(
                ChunkDraft(
                    sequence_index=len(chunks),
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    character_count=len(content),
                    start_offset=actual_start,
                    end_offset=actual_end,
                    token_count=token_end - token_start,
                    section_heading=_section_heading_at(text, actual_start),
                )
            )
        if token_end >= len(token_offsets):
            break
        token_start = max(token_end - chunk_overlap, token_start + 1)
    return chunks
