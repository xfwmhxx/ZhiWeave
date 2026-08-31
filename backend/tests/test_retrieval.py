from studyrag_backend.services.retrieval import expand_query_without_llm, tokenize_mixed_text


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
