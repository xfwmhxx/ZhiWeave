from studyrag_backend.services.web_crawler import extract_page, normalize_content


def test_extract_page_prefers_article_content_and_keeps_source_links() -> None:
    html = """
    <html lang="zh-CN">
      <head>
        <title>站点标题</title>
        <link rel="canonical" href="/mysql/mysql-select-query.html">
      </head>
      <body>
        <h1>站点公共标题</h1>
        <nav>不应该进入正文</nav>
        <div class="article-intro">
          <h1>MySQL SELECT 查询</h1>
          <p>SELECT 语句用于从表中读取数据。</p>
          <a href="/mysql/mysql-where-clause.html">下一节</a>
        </div>
        <script>window.noise = true</script>
      </body>
    </html>
    """

    page = extract_page(html, "https://www.runoob.com/mysql/mysql-select-query.html")

    assert page.title == "MySQL SELECT 查询"
    assert "SELECT 语句用于从表中读取数据" in page.content
    assert "不应该进入正文" not in page.content
    assert page.canonical_url == "https://www.runoob.com/mysql/mysql-select-query.html"
    assert page.language == "zh-CN"
    assert "https://www.runoob.com/mysql/mysql-where-clause.html" in page.discovered_links


def test_normalize_content_collapses_spacing() -> None:
    assert normalize_content("标题   \n\n\n\n  正文\t内容  ") == "标题\n\n正文 内容"


def test_extract_page_keeps_inline_code_and_code_blocks_readable() -> None:
    html = """
    <html lang="zh-CN"><body><article>
      <h1>Python 数据库操作</h1>
      <h2>执行 SQL</h2>
      <p>调用 <code>cursor.</code><code>execute</code>(<code>sql</code>,
      <code>values</code>) 执行语句。</p>
      <pre><code>cursor.execute(sql, values)\nrows = cursor.fetchall()</code></pre>
    </article></body></html>
    """

    page = extract_page(html, "https://example.com/python/database.html")

    assert "## 执行 SQL" in page.content
    assert "cursor.\nexecute" not in page.content
    assert "cursor.execute(sql, values)\nrows = cursor.fetchall()" in page.content
    assert "```" in page.content


def test_extract_page_falls_back_to_direct_text_inside_a_semantic_container() -> None:
    page = extract_page(
        "<html><body><main>没有段落标签的正文内容</main></body></html>",
        "https://example.com/plain.html",
    )

    assert page.content == "没有段落标签的正文内容"
