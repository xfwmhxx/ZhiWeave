from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    sequence_index: int
    content: str
    content_hash: str
    character_count: int
    start_offset: int
    end_offset: int
    token_count: int | None = None


def _preferred_end(text: str, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return len(text)
    minimum = start + max(1, int((hard_end - start) * 0.6))
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
                )
            )
        if end >= len(text):
            break
        next_start = max(end - chunk_overlap, start + 1)
        start = next_start
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
                )
            )
        if token_end >= len(token_offsets):
            break
        token_start = max(token_end - chunk_overlap, token_start + 1)
    return chunks
