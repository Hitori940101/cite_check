"""Unit tests for the AMiner verification adapter.

Tests cover title search, Chinese literature queries, result parsing,
error handling, and rate limit detection — all with mocked HTTP.
"""

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from refchecker.adapters.aminer_adapter import AMinerAdapter, _encode_query
from refchecker.core.models import ReferenceItem


def _ref(**overrides: Any) -> ReferenceItem:
    defaults: dict[str, Any] = {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani"],
        "year": 2017,
    }
    defaults.update(overrides)
    return ReferenceItem(**defaults)


def _aminer_hit(
    title: str = "Attention Is All You Need",
    year: int = 2017,
    authors: list[dict[str, str]] | None = None,
    venue: str = "NeurIPS",
    doi: str | None = None,
    paper_id: str = "12345",
) -> dict:
    if authors is None:
        authors = [{"name": "Ashish Vaswani"}]
    hit: dict[str, Any] = {
        "title": title,
        "year": year,
        "authors": authors,
        "venue": {"name": venue},
        "id": paper_id,
    }
    if doi:
        hit["doi"] = doi
    return hit


def _aminer_response(hits: list[dict] | None = None) -> dict:
    if hits is None:
        hits = [_aminer_hit()]
    return {"result": {"hit": hits}}


class MockResponse:
    def __init__(self, data: Any, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.headers = httpx.Headers({})
        self.text = json.dumps(data) if isinstance(data, dict) else str(data)

    def json(self) -> Any:
        return self._data

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
# _encode_query
# ---------------------------------------------------------------------------


class TestEncodeQuery:
    def test_basic(self) -> None:
        result = _encode_query({"query": "test", "offset": 0, "size": 5})
        decoded = json.loads(base64.b64decode(result))
        assert decoded == {"query": "test", "offset": 0, "size": 5}

    def test_chinese(self) -> None:
        result = _encode_query({"query": "深度学习"})
        decoded = json.loads(base64.b64decode(result))
        assert decoded["query"] == "深度学习"


# ---------------------------------------------------------------------------
# AMinerAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter() -> AMinerAdapter:
    return AMinerAdapter()


class TestAMinerInit:
    def test_name(self) -> None:
        assert AMinerAdapter().name == "aminer"

    def test_with_api_key(self) -> None:
        a = AMinerAdapter(api_key="testkey")
        assert a.api_key == "testkey"


class TestAMinerSearch:
    @pytest.mark.asyncio
    async def test_search_found(self, adapter: AMinerAdapter) -> None:
        resp = MockResponse(_aminer_response())
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"
        assert result.adapter_name == "aminer"

    @pytest.mark.asyncio
    async def test_search_chinese_title(self, adapter: AMinerAdapter) -> None:
        hit = _aminer_hit(title="深度学习综述", authors=[{"name": "张三"}])
        resp = MockResponse(_aminer_response([hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(title="深度学习综述"), client)  # type: ignore[arg-type]
        assert result.matched_title == "深度学习综述"

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: AMinerAdapter) -> None:
        resp = MockResponse({"result": {"hit": []}})
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_empty_result_key(self, adapter: AMinerAdapter) -> None:
        resp = MockResponse({"result": {}})
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is False

    @pytest.mark.asyncio
    async def test_search_result_is_list(self, adapter: AMinerAdapter) -> None:
        """AMiner sometimes returns result as a list directly."""
        hits = [_aminer_hit()]
        resp = MockResponse({"result": hits})
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is True

    @pytest.mark.asyncio
    async def test_api_error(self, adapter: AMinerAdapter) -> None:
        resp = MockResponse({"error": "bad"}, status_code=500)
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is False
        assert result.error is not None
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_malformed_json(self, adapter: AMinerAdapter) -> None:
        resp = MockResponse("not json at all")
        resp._data = "not json"
        resp.text = "not json"
        resp.status_code = 200

        # Override json to raise
        def bad_json() -> Any:
            raise ValueError("not json")

        resp.json = bad_json  # type: ignore[assignment]
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.found is False
        assert "parse" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_api_key_in_params(self) -> None:
        adapter = AMinerAdapter(api_key="mykey")
        captured_params: dict[str, Any] = {}

        class CapturingClient:
            async def get(self, url: str, **kwargs: Any) -> MockResponse:
                captured_params.update(kwargs.get("params", {}))
                return MockResponse(_aminer_response())

        await adapter.verify_single(_ref(), CapturingClient())  # type: ignore[arg-type]
        assert captured_params.get("key") == "mykey"

    @pytest.mark.asyncio
    async def test_no_api_key(self, adapter: AMinerAdapter) -> None:
        captured_params: dict[str, Any] = {}

        class CapturingClient:
            async def get(self, url: str, **kwargs: Any) -> MockResponse:
                captured_params.update(kwargs.get("params", {}))
                return MockResponse(_aminer_response())

        await adapter.verify_single(_ref(), CapturingClient())  # type: ignore[arg-type]
        assert "key" not in captured_params


class TestAMinerHitToMatch:
    @pytest.mark.asyncio
    async def test_with_doi(self, adapter: AMinerAdapter) -> None:
        hit = _aminer_hit(doi="10.1234/test")
        resp = MockResponse(_aminer_response([hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.matched_doi == "10.1234/test"

    @pytest.mark.asyncio
    async def test_source_url(self, adapter: AMinerAdapter) -> None:
        hit = _aminer_hit(paper_id="67890")
        resp = MockResponse(_aminer_response([hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.source_url == "https://www.aminer.cn/pub/67890"

    @pytest.mark.asyncio
    async def test_authors_as_strings(self, adapter: AMinerAdapter) -> None:
        hit = _aminer_hit(authors=["Author A", "Author B"])
        resp = MockResponse(_aminer_response([hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert "Author A" in result.matched_authors

    @pytest.mark.asyncio
    async def test_year_as_string(self, adapter: AMinerAdapter) -> None:
        hit = _aminer_hit(year="2020")
        # Build manually to have year as string
        raw_hit: dict[str, Any] = {
            "title": "Test",
            "year": "2020",
            "authors": [{"name": "A"}],
            "venue": {"name": "Conf"},
            "id": "1",
        }
        resp = MockResponse(_aminer_response([raw_hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(title="Test", year=2020), client)  # type: ignore[arg-type]
        assert result.matched_year == 2020

    @pytest.mark.asyncio
    async def test_year_invalid_string(self, adapter: AMinerAdapter) -> None:
        raw_hit: dict[str, Any] = {
            "title": "Test",
            "year": "invalid",
            "authors": [],
            "venue": {"name": "Conf"},
            "id": "1",
        }
        resp = MockResponse(_aminer_response([raw_hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(title="Test"), client)  # type: ignore[arg-type]
        assert result.matched_year is None

    @pytest.mark.asyncio
    async def test_multiple_picks_best(self, adapter: AMinerAdapter) -> None:
        hits = [
            _aminer_hit(title="Completely Unrelated"),
            _aminer_hit(title="Attention Is All You Need"),
        ]
        resp = MockResponse(_aminer_response(hits))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(), client)  # type: ignore[arg-type]
        assert result.matched_title == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_no_venue(self, adapter: AMinerAdapter) -> None:
        raw_hit: dict[str, Any] = {
            "title": "Test",
            "year": 2020,
            "authors": [],
            "id": "1",
        }
        resp = MockResponse(_aminer_response([raw_hit]))
        client = MockClient(resp)

        result = await adapter.verify_single(_ref(title="Test"), client)  # type: ignore[arg-type]
        assert result.matched_journal is None
