from hashlib import sha256

import pytest

from studyrag_backend.services.chunking import split_text, split_text_by_tokens


def test_chunking_preserves_offsets_overlap_and_hashes() -> None:
    text = "第一段介绍 MySQL 的基本概念。\n\n" + "查询语句 SELECT 可以读取数据。" * 12
    chunks = split_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(chunk.character_count <= 100 for chunk in chunks)
    assert all(text[chunk.start_offset : chunk.end_offset] == chunk.content for chunk in chunks)
    assert chunks[1].start_offset < chunks[0].end_offset
    assert all(
        chunk.content_hash == sha256(chunk.content.encode("utf-8")).hexdigest() for chunk in chunks
    )


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(0, 0), (100, -1), (100, 100)],
)
def test_chunking_rejects_invalid_parameters(chunk_size: int, chunk_overlap: int) -> None:
    with pytest.raises(ValueError):
        split_text("content", chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def test_token_chunking_uses_token_offsets_and_overlap() -> None:
    text = "one two three four"
    offsets = [(0, 3), (4, 7), (8, 13), (14, 18)]

    chunks = split_text_by_tokens(text, token_offsets=offsets, chunk_size=3, chunk_overlap=1)

    assert [chunk.content for chunk in chunks] == ["one two three", "three four"]
    assert [chunk.token_count for chunk in chunks] == [3, 2]
    assert chunks[1].start_offset == 8
