"""Unit tests for the OpenAlex verification adapter.

Tests cover DOI lookup, title search, rate limit detection, and
result parsing — all with mocked pyalex responses.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from refchecker.adapters.openalex_adapter import OpenAlexAdapter
from refchecker.core.exceptions import RateLimitError
from refchecker.core.models import ReferenceItem


def _ref(**overrides: Any) -> ReferenceItem:
    defaults: dict[str, Any] = {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani"],
        "year": 2017,
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _openalex_work(
    title: str = "Attention Is All You Need",
    year: int = 2017,
    authors: list[dict] | None = None,
    journal: str = "NeurIPS",
    doi: str = "https://doi.org/10.1234/test",
    paper_id: str = "https://openalex.org/W12345",
) -> dict:
    if authors is None:
        authors = [
            {"author": {"display_name": "Ashish Vaswani"}},
        ]
    return {
        "title": title,
        "publication_year": year,
        "authorships": authors,
        "primary_location": {
            "source": {"display_name": journal},
        },
        "doi": doi,
        "id": paper_id,
    }


# ---------------------------------------------------------------------------
# OpenAlexAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> OpenAlexAdapter:
    return OpenAlexAdapter()


class TestOpenAlexInit:
    def test_name(self) -> None:
        assert OpenAlexAdapter().name == "openalex"

    def test_with_api_key(self) -> None:
        a = OpenAlexAdapter(api_key="testkey")
        assert a.api_key == "testkey"


class TestOpenAlexDoiLookup:
    @pytest.mark.asyncio
    async def test_doi_found(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work()
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/test")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"
        assert result.matched_doi == "10.1234/test"

    @pytest.mark.asyncio
    async def test_doi_not_found(self, adapter: OpenAlexAdapter) -> None:
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = []

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/nonexistent")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.found is False


class TestOpenAlexSearch:
    @pytest.mark.asyncio
    async def test_search_found(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work()
        mock_works = MagicMock()
        mock_works.search.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref()  # No DOI → triggers search
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: OpenAlexAdapter) -> None:
        mock_works = MagicMock()
        mock_works.search.return_value.get.return_value = []

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref()
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_multiple_picks_best(self, adapter: OpenAlexAdapter) -> None:
        works = [
            _openalex_work(title="Completely Unrelated Paper"),
            _openalex_work(title="Attention Is All You Need"),
        ]
        mock_works = MagicMock()
        mock_works.search.return_value.get.return_value = works

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref()
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.matched_title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_search_filters_by_year(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work(year=2020)
        mock_works = MagicMock()
        mock_works.search.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(year=2017)  # Year mismatch
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        # Score should be lower due to year mismatch, but still return a result
        assert result.matched_year == 2020


class TestOpenAlexRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, adapter: OpenAlexAdapter) -> None:
        mock_works = MagicMock()
        mock_works.search.return_value.get.side_effect = Exception("429 Too Many Requests")

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref()
            with pytest.raises(RateLimitError):
                await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]


class TestOpenAlexItemToMatch:
    @pytest.mark.asyncio
    async def test_author_extraction(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work(authors=[
            {"author": {"display_name": "Ashish Vaswani"}},
            {"author": {"display_name": "Noam Shazeer"}},
        ])
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/test")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert "Ashish Vaswani" in result.matched_authors
        assert "Noam Shazeer" in result.matched_authors

    @pytest.mark.asyncio
    async def test_no_doi(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work(doi="")
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/test")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.matched_doi is None

    @pytest.mark.asyncio
    async def test_no_journal(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work()
        work["primary_location"] = None
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/test")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.matched_journal is None

    @pytest.mark.asyncio
    async def test_source_url(self, adapter: OpenAlexAdapter) -> None:
        work = _openalex_work(paper_id="https://openalex.org/W99999")
        mock_works = MagicMock()
        mock_works.filter.return_value.get.return_value = [work]

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref(doi="10.1234/test")
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.source_url == "https://openalex.org/W99999"

    @pytest.mark.asyncio
    async def test_generic_error(self, adapter: OpenAlexAdapter) -> None:
        mock_works = MagicMock()
        mock_works.search.return_value.get.side_effect = Exception("Connection failed")

        with patch("refchecker.adapters.openalex_adapter.Works", return_value=mock_works):
            ref = _ref()
            result = await adapter.verify_single(ref, MagicMock())  # type: ignore[arg-type]

        assert result.found is False
        assert "error" in (result.error or "").lower()
