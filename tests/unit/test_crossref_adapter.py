"""Unit tests for the Crossref verification adapter.

Tests cover DOI lookup, bibliographic search, author/year extraction,
and error handling — all with mocked HTTP responses.
"""

import json
from typing import Any

import httpx
import pytest

from refchecker.adapters.crossref_adapter import (
    CrossrefAdapter,
    _extract_authors,
    _extract_year,
)
from refchecker.core.models import ReferenceItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(**overrides: Any) -> ReferenceItem:
    defaults: dict[str, Any] = {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "year": 2017,
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _crossref_work(
    title: str = "Attention Is All You Need",
    authors: list[dict[str, str]] | None = None,
    year: int = 2017,
    doi: str = "10.1234/test",
    journal: str = "NeurIPS",
) -> dict:
    """Build a mock Crossref work item."""
    if authors is None:
        authors = [
            {"given": "Ashish", "family": "Vaswani"},
            {"given": "Noam", "family": "Shazeer"},
        ]
    return {
        "DOI": doi,
        "title": [title],
        "author": authors,
        "published-print": {"date-parts": [[year, 6, 12]]},
        "container-title": [journal],
    }


class MockResponse:
    """Mock httpx.Response for testing."""

    def __init__(self, data: Any, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.headers = httpx.Headers({})

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )

    @property
    def text(self) -> str:
        return json.dumps(self._data)


class MockClient:
    """Mock httpx.AsyncClient for testing."""

    def __init__(self, response: MockResponse) -> None:
        self._response = response

    async def get(self, url: str, **kwargs: Any) -> MockResponse:
        return self._response


# ---------------------------------------------------------------------------
# _extract_year / _extract_authors
# ---------------------------------------------------------------------------


class TestExtractYear:
    def test_published_print(self) -> None:
        item = {"published-print": {"date-parts": [[2023, 5, 1]]}}
        assert _extract_year(item) == 2023

    def test_published_online(self) -> None:
        item = {"published-online": {"date-parts": [[2020]]}}
        assert _extract_year(item) == 2020

    def test_created_fallback(self) -> None:
        item = {"created": {"date-parts": [[2019, 12]]}}
        assert _extract_year(item) == 2019

    def test_priority_print_over_online(self) -> None:
        item = {
            "published-print": {"date-parts": [[2022]]},
            "published-online": {"date-parts": [[2021]]},
        }
        assert _extract_year(item) == 2022

    def test_no_date_fields(self) -> None:
        assert _extract_year({}) is None

    def test_empty_date_parts(self) -> None:
        item = {"published-print": {"date-parts": [[]]}}
        assert _extract_year(item) is None


class TestExtractAuthors:
    def test_basic(self) -> None:
        item = {"author": [{"given": "Ashish", "family": "Vaswani"}]}
        assert _extract_authors(item) == ["Ashish Vaswani"]

    def test_multiple_authors(self) -> None:
        item = {
            "author": [
                {"given": "Ashish", "family": "Vaswani"},
                {"given": "Noam", "family": "Shazeer"},
            ]
        }
        assert _extract_authors(item) == ["Ashish Vaswani", "Noam Shazeer"]

    def test_family_only(self) -> None:
        item = {"author": [{"family": "Vaswani"}]}
        assert _extract_authors(item) == ["Vaswani"]

    def test_given_only(self) -> None:
        item = {"author": [{"given": "Ashish"}]}
        assert _extract_authors(item) == ["Ashish"]

    def test_empty_author_list(self) -> None:
        assert _extract_authors({}) == []
        assert _extract_authors({"author": []}) == []

    def test_empty_name_skipped(self) -> None:
        item = {"author": [{"given": "", "family": ""}]}
        assert _extract_authors(item) == []


# ---------------------------------------------------------------------------
# CrossrefAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> CrossrefAdapter:
    return CrossrefAdapter(mailto="test@example.com")


class TestCrossrefAdapterInit:
    def test_name(self) -> None:
        adapter = CrossrefAdapter()
        assert adapter.name == "crossref"

    def test_mailto(self) -> None:
        adapter = CrossrefAdapter(mailto="user@test.com")
        assert adapter.mailto == "user@test.com"

    def test_repr(self) -> None:
        adapter = CrossrefAdapter(api_key="testkey")
        assert "crossref" in repr(adapter)
        assert "key=✓" in repr(adapter)

    def test_repr_no_key(self) -> None:
        adapter = CrossrefAdapter()
        assert "key=✗" in repr(adapter)


class TestCrossrefVerifyByDoi:
    @pytest.mark.asyncio
    async def test_doi_found(self, adapter: CrossrefAdapter) -> None:
        work = _crossref_work()
        response = MockResponse({"message": work})
        client = MockClient(response)

        ref = _ref(doi="10.1234/test")
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"
        assert result.matched_doi == "10.1234/test"
        assert result.adapter_name == "crossref"

    @pytest.mark.asyncio
    async def test_doi_not_found(self, adapter: CrossrefAdapter) -> None:
        response = MockResponse({"message": "Not found"}, status_code=404)
        response.headers = httpx.Headers({})
        client = MockClient(response)

        ref = _ref(doi="10.1234/nonexistent")
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.found is False
        assert "not found" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_doi_server_error(self, adapter: CrossrefAdapter) -> None:
        response = MockResponse({}, status_code=500)
        client = MockClient(response)

        ref = _ref(doi="10.1234/test")
        with pytest.raises(httpx.HTTPStatusError):
            await adapter.verify_single(ref, client)  # type: ignore[arg-type]


class TestCrossrefVerifyBySearch:
    @pytest.mark.asyncio
    async def test_search_found(self, adapter: CrossrefAdapter) -> None:
        items = [_crossref_work()]
        response = MockResponse({"message": {"items": items}})
        client = MockClient(response)

        ref = _ref()  # No DOI → triggers search
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: CrossrefAdapter) -> None:
        response = MockResponse({"message": {"items": []}})
        client = MockClient(response)

        ref = _ref()
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_multiple_picks_best(self, adapter: CrossrefAdapter) -> None:
        items = [
            _crossref_work(title="Unrelated Paper", authors=[{"given": "X", "family": "Y"}]),
            _crossref_work(title="Attention Is All You Need"),
        ]
        response = MockResponse({"message": {"items": items}})
        client = MockClient(response)

        ref = _ref()
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_search_chinese_title(self, adapter: CrossrefAdapter) -> None:
        items = [_crossref_work(title="深度学习综述")]
        response = MockResponse({"message": {"items": items}})
        client = MockClient(response)

        ref = _ref(title="深度学习综述")
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.matched_title == "深度学习综述"


class TestCrossrefItemToMatch:
    @pytest.mark.asyncio
    async def test_scoring_with_match(self, adapter: CrossrefAdapter) -> None:
        work = _crossref_work(
            title="Attention Is All You Need",
            authors=[{"given": "Ashish", "family": "Vaswani"}],
            year=2017,
        )
        response = MockResponse({"message": work})
        client = MockClient(response)

        ref = _ref(doi="10.1234/test")
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        assert result.composite_score > 0.5
        assert result.title_score > 0
        assert result.source_url is not None
        assert "doi.org" in result.source_url

    @pytest.mark.asyncio
    async def test_no_doi_no_source_url(self, adapter: CrossrefAdapter) -> None:
        work = _crossref_work(doi="")
        response = MockResponse({"message": work})
        client = MockClient(response)

        ref = _ref(doi="10.1234/test")
        result = await adapter.verify_single(ref, client)  # type: ignore[arg-type]

        # If DOI is empty string, source_url should be None
        if not work.get("DOI"):
            assert result.source_url is None
