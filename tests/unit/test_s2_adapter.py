"""Unit tests for the Semantic Scholar REST adapter (s2_adapter.py).

Uses mocked HTTP responses to test DOI lookup, title search, and
error handling without hitting the real API.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from refchecker.adapters.s2_adapter import S2Adapter
from refchecker.core.models import AdapterMatch, ReferenceItem


# --- Test fixtures ---


def _make_reference(**overrides) -> ReferenceItem:
    """Create a test reference with sensible defaults."""
    defaults = {
        "title": "Attention Is All You Need",
        "authors": ["Vaswani, Ashish", "Shazeer, Noam"],
        "year": 2017,
        "journal": "Advances in Neural Information Processing Systems",
        "doi": "10.48550/arXiv.1706.03762",
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    raise_on_status: bool = False,
) -> MagicMock:
    """Create a mock HTTP response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json_data.get("error", "") if json_data else ""
    resp.headers = {}

    if raise_on_status and status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status = MagicMock()

    return resp


# --- S2 Adapter Tests ---


class TestS2AdapterInit:
    """Tests for S2Adapter initialization."""

    def test_init_without_key(self) -> None:
        """Adapter initializes without API key."""
        adapter = S2Adapter()
        assert adapter.name == "s2"
        assert adapter.api_key is None

    def test_init_with_key(self) -> None:
        """Adapter initializes with API key."""
        adapter = S2Adapter(api_key="test-key-123")
        assert adapter.api_key == "test-key-123"

    def test_headers_without_key(self) -> None:
        """Headers omit x-api-key when no key is set."""
        adapter = S2Adapter()
        headers = adapter._build_headers()
        assert "x-api-key" not in headers
        assert headers["Accept"] == "application/json"

    def test_headers_with_key(self) -> None:
        """Headers include x-api-key when key is set."""
        adapter = S2Adapter(api_key="test-key-123")
        headers = adapter._build_headers()
        assert headers["x-api-key"] == "test-key-123"


@pytest.mark.asyncio
class TestS2DOIQuery:
    """Tests for S2 DOI-based lookup."""

    async def test_doi_lookup_found(self) -> None:
        """DOI lookup returns match when paper exists."""
        adapter = S2Adapter()
        ref = _make_reference()

        json_data = {
            "paperId": "abc123",
            "title": "Attention Is All You Need",
            "authors": [
                {"name": "Ashish Vaswani"},
                {"name": "Noam Shazeer"},
            ],
            "year": 2017,
            "venue": "Advances in Neural Information Processing Systems",
            "externalIds": {"DOI": "10.48550/arXiv.1706.03762"},
        }
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"
        assert result.matched_year == 2017
        assert result.composite_score >= 0.6
        assert "semanticscholar.org" in (result.source_url or "")

    async def test_doi_lookup_not_found(self) -> None:
        """DOI lookup returns not found for 404."""
        adapter = S2Adapter()
        ref = _make_reference()

        resp = _mock_response(status_code=404)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.found is False
        assert "not found" in (result.error or "").lower()

    async def test_doi_lookup_sends_api_key(self) -> None:
        """DOI lookup includes x-api-key header when key is set."""
        adapter = S2Adapter(api_key="my-secret-key")
        ref = _make_reference()

        json_data = {
            "paperId": "abc123",
            "title": "Attention Is All You Need",
            "authors": [],
            "year": 2017,
            "venue": "",
            "externalIds": {"DOI": "10.48550/arXiv.1706.03762"},
        }
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        await adapter.verify_single(ref, client)

        # Verify x-api-key was in the headers
        call_args = client.get.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("x-api-key") == "my-secret-key"


@pytest.mark.asyncio
class TestS2TitleSearch:
    """Tests for S2 title-based search."""

    async def test_title_search_found(self) -> None:
        """Title search returns best match from results."""
        adapter = S2Adapter()
        ref = _make_reference(doi=None)

        json_data = {
            "total": 2,
            "data": [
                {
                    "paperId": "best123",
                    "title": "Attention Is All You Need",
                    "authors": [{"name": "Ashish Vaswani"}],
                    "year": 2017,
                    "venue": "NeurIPS",
                    "externalIds": {"DOI": "10.48550/arXiv.1706.03762"},
                },
                {
                    "paperId": "worst456",
                    "title": "Some Unrelated Paper",
                    "authors": [],
                    "year": 2020,
                    "venue": "",
                    "externalIds": {},
                },
            ],
        }
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"

    async def test_title_search_empty_results(self) -> None:
        """Title search returns not found when no results."""
        adapter = S2Adapter()
        ref = _make_reference(doi=None)

        json_data = {"total": 0, "data": []}
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.found is False

    async def test_title_search_no_data_key(self) -> None:
        """Title search handles missing 'data' key gracefully."""
        adapter = S2Adapter()
        ref = _make_reference(doi=None)

        resp = _mock_response(json_data={})

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.found is False


@pytest.mark.asyncio
class TestS2ErrorHandling:
    """Tests for S2 adapter error handling."""

    async def test_http_500_error(self) -> None:
        """HTTP 500 returns error match (not retried by base)."""
        adapter = S2Adapter()
        ref = _make_reference()

        resp = _mock_response(status_code=500)
        resp.text = "Internal Server Error"

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=resp,
            )
        )

        result = await adapter.verify_single(ref, client)

        assert result.found is False
        assert "500" in (result.error or "")

    async def test_429_raises_for_base_class(self) -> None:
        """HTTP 429 is raised for base class backoff handling."""
        adapter = S2Adapter()
        ref = _make_reference()

        resp = _mock_response(status_code=429)
        resp.text = "Rate limited"

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Too Many Requests",
                request=MagicMock(),
                response=resp,
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.verify_single(ref, client)


@pytest.mark.asyncio
class TestS2ItemConversion:
    """Tests for S2 API response item → AdapterMatch conversion."""

    async def test_missing_fields_handled(self) -> None:
        """Items with missing/null fields are handled gracefully."""
        adapter = S2Adapter()
        ref = _make_reference()

        json_data = {
            "paperId": "abc123",
            "title": None,
            "authors": None,
            "year": None,
            "venue": None,
            "externalIds": None,
        }
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        # Should still produce a result (found=False due to low score)
        assert isinstance(result, AdapterMatch)

    async def test_empty_venue_normalized(self) -> None:
        """Empty string venue is normalized to None."""
        adapter = S2Adapter()
        ref = _make_reference()

        json_data = {
            "paperId": "abc123",
            "title": "Test Paper",
            "authors": [],
            "year": 2023,
            "venue": "",
            "externalIds": {},
        }
        resp = _mock_response(json_data=json_data)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=resp)

        result = await adapter.verify_single(ref, client)

        assert result.matched_journal is None
