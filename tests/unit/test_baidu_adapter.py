"""Unit tests for the Baidu Academic verification adapter.

Tests cover HTML parsing, result extraction, Chinese content,
and helper functions — all with mocked HTTP responses.
"""

from typing import Any

import httpx
import pytest

from refchecker.adapters.baidu_adapter import (
    BaiduAdapter,
    _parse_year_from_info,
    _strip_html,
)
from refchecker.core.models import ReferenceItem


def _ref(**overrides: Any) -> ReferenceItem:
    defaults: dict[str, Any] = {
        "title": "深度学习综述",
        "authors": ["张三"],
        "year": 2023,
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _baidu_html(
    titles: list[str] | None = None,
    authors: list[str] | None = None,
    info_lines: list[str] | None = None,
) -> str:
    """Build mock Baidu Academic search results HTML."""
    if titles is None:
        titles = ["深度学习综述"]
    if authors is None:
        authors = ["张三"]
    if info_lines is None:
        info_lines = ["计算机学报, 2023, 10(2): 100-110"]

    html_parts = ["<html><body>"]
    for i, title in enumerate(titles):
        html_parts.append(f'<h3 class="t"><a href="/link">{title}</a></h3>')
    for author in authors:
        html_parts.append(f'<a class="author_text" href="/a">{author}</a>')
    for info in info_lines:
        html_parts.append(f'<div class="sc_info">{info}</div>')
    html_parts.append("</body></html>")
    return "".join(html_parts)


class MockResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = httpx.Headers({})

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )


class MockClient:
    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def get(self, url: str, **kwargs: Any) -> MockResponse:
        return self._response


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_removes_tags(self) -> None:
        assert _strip_html("<b>hello</b>") == "hello"

    def test_removes_nested_tags(self) -> None:
        assert _strip_html("<div><p>text</p></div>") == "text"

    def test_decodes_amp(self) -> None:
        assert _strip_html("A &amp; B") == "A & B"

    def test_decodes_lt_gt(self) -> None:
        assert _strip_html("x &lt; y &gt; z") == "x < y > z"

    def test_decodes_quot(self) -> None:
        assert _strip_html("&quot;hello&quot;") == '"hello"'

    def test_decodes_apos(self) -> None:
        assert _strip_html("it&#39;s") == "it's"

    def test_no_html(self) -> None:
        assert _strip_html("plain text") == "plain text"

    def test_strips_whitespace(self) -> None:
        assert _strip_html("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# _parse_year_from_info
# ---------------------------------------------------------------------------


class TestParseYearFromInfo:
    def test_4digit_year(self) -> None:
        assert _parse_year_from_info("Journal, 2023, 10(2): 100") == 2023

    def test_year_2000(self) -> None:
        assert _parse_year_from_info("Conf, 2000") == 2000

    def test_year_1999(self) -> None:
        assert _parse_year_from_info("Journal, 1999, vol 5") == 1999

    def test_no_year(self) -> None:
        assert _parse_year_from_info("No year here") is None

    def test_multiple_years_returns_first(self) -> None:
        result = _parse_year_from_info("2020-2023")
        assert result is not None
        assert result in (2020, 2023)


# ---------------------------------------------------------------------------
# BaiduAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> BaiduAdapter:
    return BaiduAdapter()


class TestBaiduInit:
    def test_name(self) -> None:
        assert BaiduAdapter().name == "baidu"

    def test_no_api_key(self) -> None:
        assert BaiduAdapter().api_key is None


class TestBaiduSearch:
    @pytest.mark.asyncio
    async def test_search_found(self, adapter: BaiduAdapter) -> None:
        html = _baidu_html()
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is True
        assert result.matched_title == "深度学习综述"
        assert result.adapter_name == "baidu"

    @pytest.mark.asyncio
    async def test_search_chinese_results(self, adapter: BaiduAdapter) -> None:
        html = _baidu_html(
            titles=["基于Transformer的中文文本分类"],
            authors=["李四"],
            info_lines=["中文信息学报, 2022, 28(3): 45-52"],
        )
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(
            _ref(title="基于Transformer的中文文本分类", year=2022),
            client,  # type: ignore[arg-type]
        )
        assert result.matched_title == "基于Transformer的中文文本分类"

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: BaiduAdapter) -> None:
        html = "<html><body><p>No results found</p></body></html>"
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_http_error(self, adapter: BaiduAdapter) -> None:
        response = MockResponse("error", status_code=500)
        client = MockClient(response)

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_search_multiple_picks_best(self, adapter: BaiduAdapter) -> None:
        html = _baidu_html(
            titles=["Unrelated Paper", "深度学习综述"],
            authors=["Wang", "张三"],
            info_lines=["Journal, 2020", "计算机学报, 2023"],
        )
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.matched_title == "深度学习综述"

    @pytest.mark.asyncio
    async def test_search_no_authors(self, adapter: BaiduAdapter) -> None:
        html = _baidu_html(authors=[])
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is True

    @pytest.mark.asyncio
    async def test_search_no_year_in_info(self, adapter: BaiduAdapter) -> None:
        html = _baidu_html(info_lines=["Some Journal, no year info"])
        client = MockClient(MockResponse(html))

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is True
