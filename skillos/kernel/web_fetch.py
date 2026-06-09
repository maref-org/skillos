#!/usr/bin/env python3
"""Web Fetch Tool — 网页抓取与内容提取

职责:
  - 使用 httpx 异步获取网页内容
  - 使用 BeautifulSoup4 解析 HTML 结构
  - 使用 readability-lxml 提取文章主体内容
  - 支持多种提取模式: full, article, links, metadata
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup
from readability import Document

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_LENGTH = 50000
_USER_AGENT = "Mozilla/5.0 (compatible; SkillOS-WebFetch/1.0)"


@dataclass
class WebFetchResult:
    url: str
    title: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    success: bool = True
    error: str = ""
    status_code: int = 0
    content_length: int = 0


class WebFetcher:
    """网页抓取器 — 支持多种提取模式"""

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch(
        self,
        url: str,
        extract_mode: str = "full",
        max_length: int = _DEFAULT_MAX_LENGTH,
    ) -> WebFetchResult:
        """抓取网页并提取内容

        Args:
            url: 目标 URL
            extract_mode: 提取模式 (full|article|links|metadata)
            max_length: 最大返回内容长度

        Returns:
            WebFetchResult 包含提取结果
        """
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            result = WebFetchResult(
                url=url,
                status_code=response.status_code,
                content_length=len(html),
            )

            result.title = soup.title.string.strip() if soup.title else ""
            result.metadata = self._extract_metadata(soup, response.headers)

            if extract_mode == "article":
                result.content = self._extract_article(html)[:max_length]
            elif extract_mode == "links":
                result.links = self._extract_links(soup, url)
                result.content = f"Found {len(result.links)} links"
            elif extract_mode == "metadata":
                result.content = f"Metadata for: {result.title}"
            else:
                result.content = self._extract_text(soup)[:max_length]

            logger.info("WebFetch OK: %s mode=%s len=%d", url, extract_mode, len(result.content))
            return result

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error fetching %s: %s", url, e)
            return WebFetchResult(url=url, success=False, error=str(e), status_code=e.response.status_code)
        except httpx.RequestError as e:
            logger.error("Request error fetching %s: %s", url, e)
            return WebFetchResult(url=url, success=False, error=str(e))
        except Exception as e:
            logger.error("Unexpected error fetching %s: %s", url, e)
            return WebFetchResult(url=url, success=False, error=str(e))

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _extract_article(html: str) -> str:
        doc = Document(html)
        return doc.summary()

    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
        from urllib.parse import urljoin

        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href and not href.startswith("#") and not href.startswith("javascript:"):
                full_url = urljoin(base_url, href)
                links.append(full_url)
        return list(dict.fromkeys(links))

    @staticmethod
    def _extract_metadata(soup: BeautifulSoup, headers: dict) -> dict[str, Any]:
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name") or tag.get("property") or tag.get("itemprop")
            content = tag.get("content")
            if name and content:
                meta[name] = content

        meta["charset"] = soup.find("meta", attrs={"charset": True})
        meta["charset"] = meta["charset"].get("charset") if meta["charset"] else None
        meta["content_type"] = headers.get("content-type", "")
        meta["last_modified"] = headers.get("last-modified", "")
        meta["server"] = headers.get("server", "")

        return {k: v for k, v in meta.items() if v is not None}
