import asyncio
import re
import textwrap
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from bs4 import BeautifulSoup, Tag

from studyrag_backend.core.config import Settings
from studyrag_backend.services.url_safety import (
    UnsafeUrlError,
    canonicalize_url,
    validate_public_url,
)

_SPACE_LINE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_INLINE_SPACE_BEFORE = re.compile(r"\s+([,.;:!?\uff0c。\uff1b\uff1a\uff01\uff1f)\]\u3011])")
_INLINE_SPACE_AFTER = re.compile(r"([(\[【])\s+")
_SKIPPED_SUFFIXES = (
    ".7z",
    ".avi",
    ".css",
    ".doc",
    ".docx",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
)


@dataclass(frozen=True, slots=True)
class CrawledPage:
    source_url: str
    canonical_url: str
    title: str
    content: str
    language: str | None
    discovered_links: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrawlReport:
    visited_urls: int
    indexed_pages: int
    skipped_by_robots: int
    errors: tuple[dict[str, str], ...]


def normalize_content(value: str) -> str:
    lines: list[str] = []
    in_code_block = False
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            lines.append(stripped)
        elif in_code_block:
            lines.append(raw_line.rstrip())
        else:
            lines.append(_SPACE_LINE.sub(" ", raw_line).strip())
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _inline_text(node: Tag) -> str:
    value = _SPACE_LINE.sub(" ", node.get_text(" ", strip=True)).strip()
    value = _INLINE_SPACE_BEFORE.sub(r"\1", value)
    return _INLINE_SPACE_AFTER.sub(r"\1", value)


def _has_block_ancestor(node: Tag, root: Tag) -> bool:
    parent = node.parent
    while isinstance(parent, Tag) and parent is not root:
        if parent.name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table"}:
            return True
        parent = parent.parent
    return False


def _table_text(node: Tag) -> str:
    rows: list[str] = []
    for row in node.select("tr"):
        cells = [_inline_text(cell) for cell in row.select(":scope > th, :scope > td")]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _structured_text(root: Tag) -> str:
    """Serialize article blocks while keeping inline markup on the same readable line."""
    blocks: list[str] = []
    selector = "h1, h2, h3, h4, h5, h6, p, li, pre, table"
    for node in root.select(selector):
        if _has_block_ancestor(node, root):
            continue
        name = node.name.lower()
        if name.startswith("h") and len(name) == 2 and name[1].isdigit():
            value = _inline_text(node)
            block = f"{'#' * int(name[1])} {value}" if value else ""
        elif name == "pre":
            code = textwrap.dedent(node.get_text("", strip=False)).strip("\n")
            block = f"```\n{code.rstrip()}\n```" if code.strip() else ""
        elif name == "table":
            block = _table_text(node)
        elif name == "li":
            value = _inline_text(node)
            block = f"- {value}" if value else ""
        else:
            block = _inline_text(node)
        normalized = normalize_content(block)
        if normalized and (not blocks or blocks[-1] != normalized):
            blocks.append(normalized)
    return normalize_content("\n\n".join(blocks))


def extract_page(html: str, source_url: str) -> CrawledPage:
    soup = BeautifulSoup(html, "lxml")
    for unwanted in soup.select("script, style, noscript, nav, footer, iframe, form"):
        unwanted.decompose()

    content_node: Tag | None = None
    for selector in (".article-intro", "article", "main", "[role='main']"):
        selected = soup.select_one(selector)
        if isinstance(selected, Tag):
            content_node = selected
            break

    article_title = content_node.select_one("h1") if content_node is not None else None
    title_node = article_title or soup.select_one("h1") or soup.select_one("title")
    title = normalize_content(title_node.get_text(" ", strip=True)) if title_node else source_url

    if content_node is not None:
        content = _structured_text(content_node) or normalize_content(
            content_node.get_text(" ", strip=True)
        )
    else:
        extracted = trafilatura.extract(
            html,
            url=source_url,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
        content = normalize_content(extracted or soup.get_text("\n", strip=True))
    if not content:
        raise ValueError("page did not contain extractable article content")

    links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if isinstance(href, str):
            try:
                links.append(canonicalize_url(urljoin(source_url, href)))
            except UnsafeUrlError:
                continue

    html_node = soup.select_one("html")
    language = html_node.get("lang") if isinstance(html_node, Tag) else None
    canonical_node = soup.select_one("link[rel='canonical'][href]")
    canonical_url = source_url
    if isinstance(canonical_node, Tag):
        canonical_href = canonical_node.get("href")
        if isinstance(canonical_href, str):
            try:
                canonical_url = canonicalize_url(urljoin(source_url, canonical_href))
            except UnsafeUrlError:
                canonical_url = source_url
    return CrawledPage(
        source_url=source_url,
        canonical_url=canonical_url,
        title=title[:500],
        content=content,
        language=str(language)[:32] if language else None,
        discovered_links=tuple(dict.fromkeys(links)),
    )


class WebCrawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.report = CrawlReport(0, 0, 0, ())

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> tuple[str, str]:
        current = url
        for redirect_count in range(self.settings.crawler_max_redirects + 1):
            current = await validate_public_url(
                current,
                trusted_proxy_cidrs=self.settings.crawler_trusted_dns_proxy_cidrs,
            )
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    if redirect_count >= self.settings.crawler_max_redirects:
                        raise RuntimeError("crawler redirect limit exceeded")
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("redirect response did not include a location")
                    current = canonicalize_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if (
                    content_length
                    and int(content_length) > self.settings.crawler_max_response_bytes
                ):
                    raise RuntimeError("crawler response exceeded the configured size limit")

                chunks: list[bytes] = []
                size = 0
                async for part in response.aiter_bytes():
                    size += len(part)
                    if size > self.settings.crawler_max_response_bytes:
                        raise RuntimeError("crawler response exceeded the configured size limit")
                    chunks.append(part)
                encoding = response.encoding or "utf-8"
                return current, b"".join(chunks).decode(encoding, errors="replace")
        raise RuntimeError("crawler redirect limit exceeded")

    async def crawl(self, seed_url: str, *, max_pages: int) -> list[CrawledPage]:
        seed = await validate_public_url(
            seed_url,
            trusted_proxy_cidrs=self.settings.crawler_trusted_dns_proxy_cidrs,
        )
        seed_parts = urlsplit(seed)
        allowed_host = seed_parts.hostname
        allowed_prefix = seed_parts.path.rsplit("/", 1)[0] + "/"
        robots_url = f"{seed_parts.scheme}://{seed_parts.netloc}/robots.txt"
        headers = {"User-Agent": self.settings.crawler_user_agent}
        timeout = httpx.Timeout(self.settings.crawler_timeout_seconds)
        pages: list[CrawledPage] = []
        pending = deque([seed])
        queued = {seed}
        visited: set[str] = set()
        skipped_by_robots = 0
        errors: list[dict[str, str]] = []

        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=False
        ) as client:
            robots = RobotFileParser()
            try:
                _, robots_body = await self._fetch(client, robots_url)
                robots.parse(robots_body.splitlines())
            except (httpx.HTTPError, RuntimeError, UnsafeUrlError, ValueError):
                robots.parse([])

            while pending and len(pages) < max_pages:
                url = pending.popleft()
                if url in visited:
                    continue
                visited.add(url)
                if not robots.can_fetch(self.settings.crawler_user_agent, url):
                    skipped_by_robots += 1
                    continue
                if pages and self.settings.crawler_delay_seconds:
                    await asyncio.sleep(self.settings.crawler_delay_seconds)

                try:
                    final_url, html = await self._fetch(client, url)
                    page = extract_page(html, final_url)
                except (httpx.HTTPError, RuntimeError, UnsafeUrlError, ValueError) as exc:
                    errors.append(
                        {"url": url, "error": type(exc).__name__, "message": str(exc)[:300]}
                    )
                    continue
                pages.append(page)
                for link in page.discovered_links:
                    parsed = urlsplit(link)
                    if (
                        parsed.hostname != allowed_host
                        or not parsed.path.startswith(allowed_prefix)
                        or parsed.path.lower().endswith(_SKIPPED_SUFFIXES)
                        or link in queued
                    ):
                        continue
                    queued.add(link)
                    pending.append(link)
        self.report = CrawlReport(
            visited_urls=len(visited),
            indexed_pages=len(pages),
            skipped_by_robots=skipped_by_robots,
            errors=tuple(errors),
        )
        return pages
