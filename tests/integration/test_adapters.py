"""Integration tests for verification adapters and engine with mocked APIs."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.models import AdapterMatch, ReferenceItem, VerificationStatus
from refchecker.engine import VerificationEngine


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


# --- Base adapter backoff tests ---

class TestBackoff:
    """Tests for exponential backoff computation."""

    def test_initial_backoff(self) -> None:
        """First attempt backoff is around 1s."""
        delay = VerificationAdapter._compute_backoff(0)
        assert 0.5 <= delay <= 1.5

    def test_second_backoff(self) -> None:
        """Second attempt backoff is around 2s."""
        delay = VerificationAdapter._compute_backoff(1)
        assert 1.5 <= delay <= 2.5

    def test_max_backoff(self) -> None:
        """Backoff is capped at 60s."""
        delay = VerificationAdapter._compute_backoff(20)
        assert delay <= 61.0

    def test_retry_after_override(self) -> None:
        """Server retry-after overrides computed backoff."""
        delay = VerificationAdapter._compute_backoff(0, retry_after=10.0)
        assert 10.0 <= delay <= 10.5

    def test_parse_retry_after_int(self) -> None:
        """Parse integer retry-after header."""
        response = MagicMock()
        response.headers = {"retry-after": "30"}
        result = VerificationAdapter._parse_retry_after(response)
        assert result == 30.0

    def test_parse_retry_after_missing(self) -> None:
        """Missing retry-after returns None."""
        response = MagicMock()
        response.headers = {}
        result = VerificationAdapter._parse_retry_after(response)
        assert result is None


# --- Engine integration tests ---

class _StubAdapter(VerificationAdapter):
    """A stub adapter that returns a predefined match."""

    def __init__(self, *, name: str, match: AdapterMatch) -> None:
        super().__init__(name=name)
        self._match = match

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        return self._match


@pytest.mark.asyncio
class TestVerificationEngine:
    """Tests for the orchestration engine."""

    async def test_single_verified(self) -> None:
        """Single reference verified by all adapters."""
        ref = _make_reference()
        match = AdapterMatch(
            adapter_name="test",
            found=True,
            matched_title="Attention Is All You Need",
            composite_score=0.95,
        )
        adapter = _StubAdapter(name="test", match=match)
        engine = VerificationEngine([adapter])

        result = await engine.verify_single(ref)

        assert result.status == VerificationStatus.VERIFIED
        assert result.best_score == 0.95

    async def test_single_suspicious(self) -> None:
        """Reference with medium score is suspicious."""
        ref = _make_reference()
        match = AdapterMatch(
            adapter_name="test",
            found=True,
            composite_score=0.72,
        )
        adapter = _StubAdapter(name="test", match=match)
        engine = VerificationEngine([adapter])

        result = await engine.verify_single(ref)

        assert result.status == VerificationStatus.SUSPICIOUS

    async def test_single_fabricated(self) -> None:
        """Reference with low score is likely fabricated."""
        ref = _make_reference()
        match = AdapterMatch(
            adapter_name="test",
            found=True,
            composite_score=0.35,
        )
        adapter = _StubAdapter(name="test", match=match)
        engine = VerificationEngine([adapter])

        result = await engine.verify_single(ref)

        assert result.status == VerificationStatus.LIKELY_FABRICATED

    async def test_single_error_only(self) -> None:
        """All adapters errored → unable to verify."""
        ref = _make_reference()
        match = AdapterMatch(
            adapter_name="test",
            found=False,
            error="Network timeout",
        )
        adapter = _StubAdapter(name="test", match=match)
        engine = VerificationEngine([adapter])

        result = await engine.verify_single(ref)

        assert result.status == VerificationStatus.UNABLE_TO_VERIFY

    async def test_multiple_adapters_best_wins(self) -> None:
        """Best score across adapters is used."""
        ref = _make_reference()
        match1 = AdapterMatch(adapter_name="a1", found=True, composite_score=0.70)
        match2 = AdapterMatch(adapter_name="a2", found=True, composite_score=0.90)
        engine = VerificationEngine([
            _StubAdapter(name="a1", match=match1),
            _StubAdapter(name="a2", match=match2),
        ])

        result = await engine.verify_single(ref)

        assert result.best_score == 0.90
        assert result.status == VerificationStatus.VERIFIED
        assert len(result.matches) == 2

    async def test_batch_verification(self) -> None:
        """Batch verifies multiple references."""
        refs = [
            _make_reference(title="Paper A"),
            _make_reference(title="Paper B"),
        ]
        match = AdapterMatch(adapter_name="test", found=True, composite_score=0.90)
        engine = VerificationEngine([_StubAdapter(name="test", match=match)])

        results = await engine.verify_batch(refs)

        assert len(results) == 2
        assert all(r.status == VerificationStatus.VERIFIED for r in results)

    async def test_batch_with_progress_callback(self) -> None:
        """Progress callback is invoked during batch."""
        refs = [_make_reference(title=f"Paper {i}") for i in range(3)]
        match = AdapterMatch(adapter_name="test", found=True, composite_score=0.90)
        engine = VerificationEngine([_StubAdapter(name="test", match=match)])

        callback_indices: list[int] = []

        def on_progress(idx: int, result: object) -> None:
            callback_indices.append(idx)

        await engine.verify_batch(refs, progress_callback=on_progress)

        assert sorted(callback_indices) == [0, 1, 2]


# --- Crossref adapter mock tests ---

@pytest.mark.asyncio
class TestCrossrefAdapterMocked:
    """Tests for Crossref adapter with mocked HTTP."""

    async def test_doi_lookup_found(self) -> None:
        """DOI lookup returns match when paper exists."""
        from refchecker.adapters.crossref_adapter import CrossrefAdapter

        ref = _make_reference()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "title": ["Attention Is All You Need"],
                "author": [
                    {"given": "Ashish", "family": "Vaswani"},
                    {"given": "Noam", "family": "Shazeer"},
                ],
                "published-print": {"date-parts": [[2017]]},
                "container-title": ["Advances in Neural Information Processing Systems"],
                "DOI": "10.48550/arXiv.1706.03762",
            }
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        adapter = CrossrefAdapter()
        result = await adapter.verify_single(ref, mock_client)

        assert result.found is True
        assert result.matched_title == "Attention Is All You Need"
        assert result.matched_year == 2017
        assert result.composite_score >= 0.85

    async def test_doi_lookup_not_found(self) -> None:
        """DOI lookup returns not found for 404."""
        from refchecker.adapters.crossref_adapter import CrossrefAdapter

        ref = _make_reference()
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        adapter = CrossrefAdapter()
        result = await adapter.verify_single(ref, mock_client)

        assert result.found is False
        assert "not found" in (result.error or "").lower()


# --- Adapter match error wrapping tests ---

@pytest.mark.asyncio
class TestAdapterErrorWrapping:
    """Tests for error handling in the base adapter."""

    async def test_network_error_retried(self) -> None:
        """Network errors trigger retries."""
        ref = _make_reference()
        call_count = 0

        class FailAdapter(VerificationAdapter):
            def __init__(self) -> None:
                super().__init__(name="fail-test")

            async def verify_single(
                self,
                reference: ReferenceItem,
                client: httpx.AsyncClient,
            ) -> AdapterMatch:
                nonlocal call_count
                call_count += 1
                raise httpx.ConnectError("Connection refused")

        adapter = FailAdapter()
        # Use verify() which wraps with backoff
        # Patch sleep to avoid actual waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await adapter.verify(ref)

        assert call_count == 5  # MAX_RETRIES
        assert result.found is False
        assert "exceeded" in (result.error or "").lower()
