"""Unit tests for the CNKI verification adapter.

Tests cover Playwright-based search, result extraction, error handling,
and the import-not-installed fallback — all with mocked Playwright.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from refchecker.adapters.cnki_adapter import CNKIAdapter
from refchecker.core.models import ReferenceItem


def _ref(**overrides: Any) -> ReferenceItem:
    defaults: dict[str, Any] = {
        "title": "深度学习综述",
        "authors": ["张三"],
        "year": 2023,
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _cnki_result(
    title: str = "深度学习综述",
    authors: str = "张三; 李四",
    source: str = "计算机学报",
    date: str = "2023-05-01",
) -> dict:
    return {
        "title": title,
        "authors": authors,
        "source": source,
        "date": date,
    }


def _make_mock_page(evaluate_return: list[dict] | None = None) -> MagicMock:
    """Build a properly structured mock Playwright page.

    Playwright API:
    - page.locator(text) → sync, returns Locator
    - locator.count() → async
    - locator.fill(text) → async
    - locator.press(key) → async
    - page.goto(url) → async
    - page.wait_for_selector(sel) → async
    - page.evaluate(js) → async
    """
    page = MagicMock()  # sync methods like .locator()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=evaluate_return or [])

    # locator() returns a Locator (sync), locator.count() is async
    primary_locator = MagicMock()
    primary_locator.count = AsyncMock(return_value=1)
    primary_locator.fill = AsyncMock()
    primary_locator.press = AsyncMock()

    page.locator.return_value = primary_locator
    return page


def _make_mock_pw(page: MagicMock) -> MagicMock:
    """Build a mock async_playwright context manager."""
    browser = AsyncMock()
    browser.new_page.return_value = page
    browser.close = AsyncMock()

    pw = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    # async_playwright() returns an async context manager
    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=pw)
    async_cm.__aexit__ = AsyncMock(return_value=None)

    return async_cm


@pytest.fixture
def adapter() -> CNKIAdapter:
    return CNKIAdapter()


class TestCNKIInit:
    def test_name(self) -> None:
        assert CNKIAdapter().name == "cnki"

    def test_default_timeout(self) -> None:
        assert CNKIAdapter().timeout == 60.0


class TestCNKIPlaywrightNotInstalled:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self, adapter: CNKIAdapter) -> None:
        """When playwright is not installed, return error match gracefully."""
        import builtins
        real_import = builtins.__import__

        def selective_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "playwright.async_api":
                raise ImportError("No module named 'playwright'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=selective_import):
            result = await adapter.verify_single(
                _ref(),
                MagicMock(),  # type: ignore[arg-type]
            )
        assert result.found is False
        assert "not installed" in (result.error or "").lower()


class TestCNKISearch:
    @pytest.mark.asyncio
    async def test_search_found(self, adapter: CNKIAdapter) -> None:
        page = _make_mock_page(evaluate_return=[_cnki_result()])
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "深度学习综述"
        assert result.adapter_name == "cnki"

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: CNKIAdapter) -> None:
        page = _make_mock_page(evaluate_return=[])
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_browser_launch_failure(self, adapter: CNKIAdapter) -> None:
        pw = MagicMock()
        pw.chromium.launch = AsyncMock(side_effect=RuntimeError("Browser not found"))

        async_cm = AsyncMock()
        async_cm.__aenter__ = AsyncMock(return_value=pw)
        async_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("playwright.async_api.async_playwright", return_value=async_cm):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.found is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_search_page_timeout(self, adapter: CNKIAdapter) -> None:
        page = _make_mock_page()
        page.goto.side_effect = TimeoutError("Page load timed out")
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.found is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_search_fallback_selector(self, adapter: CNKIAdapter) -> None:
        """Test fallback to #txt_SearchText when primary selector fails."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.evaluate = AsyncMock(return_value=[_cnki_result()])

        # Primary locator: count() returns 0 (not found)
        primary = MagicMock()
        primary.count = AsyncMock(return_value=0)
        primary.fill = AsyncMock()
        primary.press = AsyncMock()

        # Fallback locator
        fallback = MagicMock()
        fallback.fill = AsyncMock()
        fallback.press = AsyncMock()

        page.locator.side_effect = [primary, fallback]
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.found is True
        assert page.locator.call_count == 2


class TestCNKIResultParsing:
    @pytest.mark.asyncio
    async def test_multiple_results_picks_best(self, adapter: CNKIAdapter) -> None:
        results = [
            _cnki_result(title="Unrelated Paper", authors="Wang", source="Conf"),
            _cnki_result(title="深度学习综述", authors="张三", source="计算机学报"),
        ]
        page = _make_mock_page(evaluate_return=results)
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.matched_title == "深度学习综述"

    @pytest.mark.asyncio
    async def test_result_with_year_extraction(self, adapter: CNKIAdapter) -> None:
        page = _make_mock_page(evaluate_return=[_cnki_result(date="2023-05-01")])
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.matched_year == 2023

    @pytest.mark.asyncio
    async def test_result_with_empty_title_skipped(self, adapter: CNKIAdapter) -> None:
        results = [
            {"title": "", "authors": "A", "source": "J", "date": "2023"},
            _cnki_result(),
        ]
        page = _make_mock_page(evaluate_return=results)
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.matched_title == "深度学习综述"

    @pytest.mark.asyncio
    async def test_authors_split_by_semicolon(self, adapter: CNKIAdapter) -> None:
        page = _make_mock_page(evaluate_return=[_cnki_result(authors="张三; 李四; 王五")])
        mock_pw = _make_mock_pw(page)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw):
            result = await adapter.verify_single(_ref(), MagicMock())  # type: ignore[arg-type]

        assert result.matched_authors == ["张三", "李四", "王五"]
