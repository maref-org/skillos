"""Tests for kernel.web_fetch — Web Fetch Tool"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from skillos.kernel.web_fetch import WebFetcher, WebFetchResult


@pytest.fixture
def mock_client():
    with patch("skillos.kernel.web_fetch.httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value = client_instance
        yield client_instance


def _make_response(status=200, text="<html><head><title>Test</title></head><body><p>Hello</p></body></html>"):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"content-type": "text/html"}
    resp.raise_for_status = MagicMock()
    return resp


class TestWebFetchResult:
    def test_default_fields(self):
        r = WebFetchResult(url="https://example.com")
        assert r.url == "https://example.com"
        assert r.title == ""
        assert r.content == ""
        assert r.metadata == {}
        assert r.links == []
        assert r.success is True
        assert r.error == ""
        assert r.status_code == 0
        assert r.content_length == 0

    def test_custom_fields(self):
        r = WebFetchResult(url="https://example.com", title="Example", content="content", success=False, error="err")
        assert r.title == "Example"
        assert r.content == "content"
        assert r.success is False
        assert r.error == "err"


class TestWebFetcher:
    async def test_fetch_full_mode(self, mock_client):
        fetcher = WebFetcher()
        resp = _make_response()

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.success is True
        assert result.title == "Test"
        assert "Hello" in result.content
        assert result.status_code == 200

    async def test_fetch_article_mode(self, mock_client):
        fetcher = WebFetcher()
        resp = _make_response(
            text=(
                "<html><head><title>Article</title></head>"
                "<body><article><h1>Article</h1><p>Body text here</p></article></body></html>"
            )
        )

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="article")
        assert result.success is True
        assert result.title == "Article"

    async def test_fetch_links_mode(self, mock_client):
        html = """
        <html>
        <head><title>Links</title></head>
        <body>
            <a href="/page1">Page 1</a>
            <a href="https://external.com">External</a>
            <a href="#section">Anchor</a>
            <a href="javascript:void(0)">JS</a>
        </body>
        </html>"""
        fetcher = WebFetcher()
        resp = _make_response(text=html)

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="links")
        assert result.success is True
        assert "https://example.com/page1" in result.links
        assert "https://external.com" in result.links
        assert "#section" not in str(result.links)
        assert "javascript:" not in str(result.links)
        assert "Found 2 links" in result.content

    async def test_fetch_metadata_mode(self, mock_client):
        html = """
        <html>
        <head>
            <title>Meta</title>
            <meta name="description" content="Test description">
            <meta property="og:title" content="OG Title">
            <meta charset="utf-8">
        </head>
        <body></body>
        </html>"""
        fetcher = WebFetcher()
        resp = _make_response(text=html)

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="metadata")
        assert result.success is True
        assert result.metadata.get("description") == "Test description"
        assert result.metadata.get("og:title") == "OG Title"
        assert "Metadata for: Meta" in result.content

    async def test_fetch_http_error(self, mock_client):
        fetcher = WebFetcher()
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.text = ""
        resp.headers = {}
        err = httpx.HTTPStatusError("404 Client Error", request=MagicMock(), response=resp)
        get_mock = AsyncMock(side_effect=err)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.success is False
        assert result.status_code == 404

    async def test_fetch_request_error(self, mock_client):
        fetcher = WebFetcher()
        err = httpx.RequestError("Connection failed", request=MagicMock())
        get_mock = AsyncMock(side_effect=err)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.success is False
        assert "Connection failed" in result.error

    async def test_fetch_unexpected_error(self, mock_client):
        fetcher = WebFetcher()
        get_mock = AsyncMock(side_effect=ValueError("Unexpected"))
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.success is False
        assert "Unexpected" in result.error

    async def test_fetch_max_length_truncation(self, mock_client):
        long_text = "Hello World! " * 5000
        html = f"<html><head><title>Long</title></head><body><p>{long_text}</p></body></html>"
        fetcher = WebFetcher()
        resp = _make_response(text=html)

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full", max_length=100)
        assert result.success is True
        assert len(result.content) <= 100

    async def test_close_client(self, mock_client):
        fetcher = WebFetcher()
        aclose_mock = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = aclose_mock
        fetcher._client = mock_client

        await fetcher.close()
        aclose_mock.assert_awaited_once()

    async def test_close_already_closed(self, mock_client):
        fetcher = WebFetcher()
        mock_client.is_closed = True
        fetcher._client = mock_client

        await fetcher.close()

    async def test_client_lazy_initialization(self):
        fetcher = WebFetcher()
        assert fetcher._client is None
        with patch("skillos.kernel.web_fetch.httpx.AsyncClient") as httpx_mock:
            client = await fetcher._get_client()
            httpx_mock.assert_called_once()
            assert client is not None

    async def test_extract_text_removes_noise_tags(self, mock_client):
        html = """
        <html>
        <head><title>Clean</title></head>
        <body>
            <p>Visible content</p>
            <script>alert('hidden')</script>
            <style>.hidden{}</style>
            <nav>Nav links</nav>
            <footer>Footer</footer>
        </body>
        </html>"""
        fetcher = WebFetcher()
        resp = _make_response(text=html)

        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.success is True
        assert "Visible content" in result.content
        assert "alert" not in result.content
        assert "hidden" not in result.content or ".hidden" not in result.content

    async def test_extract_links_deduplicates(self):
        from bs4 import BeautifulSoup

        html = '<html><body><a href="/a">A</a><a href="/a">A dup</a></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        links = WebFetcher._extract_links(soup, "https://example.com")
        assert links == ["https://example.com/a"]

    async def test_extract_metadata_with_charset(self):
        from bs4 import BeautifulSoup

        html = '<html><head><meta charset="utf-8"><meta name="author" content="Test"></head></html>'
        soup = BeautifulSoup(html, "html.parser")
        meta = WebFetcher._extract_metadata(soup, {"content-type": "text/html"})
        assert meta.get("author") == "Test"
        assert meta.get("charset") == "utf-8"
        assert meta.get("content_type") == "text/html"
        assert "server" in meta

    async def test_no_title(self, mock_client):
        html = "<html><head></head><body><p>No title</p></body></html>"
        fetcher = WebFetcher()
        resp = _make_response(text=html)
        get_mock = AsyncMock(return_value=resp)
        mock_client.get = get_mock

        result = await fetcher.fetch("https://example.com", extract_mode="full")
        assert result.title == ""
        assert result.success is True
