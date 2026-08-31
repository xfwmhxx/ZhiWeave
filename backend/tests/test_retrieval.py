from uuid import uuid4

from studyrag_backend.services.retrieval import (
    _Candidate,
    _select_diverse_hits,
    expand_query_without_llm,
    tokenize_mixed_text,
)


def test_mixed_tokenizer_keeps_english_terms_and_chinese_bigrams() -> None:
    tokens = tokenize_mixed_text("MySQL 数据库检索")

    assert "mysql" in tokens
    assert "数据" in tokens
    assert "检索" in tokens


def test_non_llm_query_expansion_adds_technical_aliases() -> None:
    expanded = expand_query_without_llm("向量数据库怎么检索")

    assert "vector embedding" in expanded
    assert "database db" in expanded
    assert "retrieval search" in expanded


def test_diverse_hits_suppress_adjacent_chunks_from_the_same_document() -> None:
    document_id = uuid4()
    other_document_id = uuid4()
    first_id, adjacent_id, other_id = uuid4(), uuid4(), uuid4()
    candidates = {
        first_id: _Candidate(
            first_id, document_id, 2, "first", "Doc", None, 100, 500, 400, "WHERE"
        ),
        adjacent_id: _Candidate(
            adjacent_id, document_id, 3, "adjacent", "Doc", None, 420, 820, 400, "WHERE"
        ),
        other_id: _Candidate(
            other_id, other_document_id, 0, "other", "Other", None, 0, 300, 300, None
        ),
    }

    selected = _select_diverse_hits(
        [(first_id, 0.9), (adjacent_id, 0.89), (other_id, 0.8)], candidates, 3
    )

    assert selected == [(first_id, 0.9), (other_id, 0.8)]
