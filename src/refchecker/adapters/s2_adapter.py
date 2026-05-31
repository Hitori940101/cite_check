"""Semantic Scholar verification adapter.

Uses the Semantic Scholar public REST API directly (no SDK):
1. Paper lookup by DOI: GET /graph/v1/paper/DOI:{doi}
2. Paper search by title: GET /graph/v1/paper/search?query=...

API docs: https://api.semanticscholar.org/api-docs/

Free tier: publicly accessible, rate-limited.
With API key (x-api-key header): higher rate limits.
Exponential backoff is mandatory per S2 API policy.
"""

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)

# Semantic Scholar API base URL
_S2_API_BASE = "https://api.semanticscholar.org/graph/v1"

# Fields to request from the API
_PAPER_FIELDS = "title,authors,year,venue,externalIds"


class S2Adapter(VerificationAdapter):
    """Verification adapter using the Semantic Scholar REST API.

    Uses direct HTTP calls to api.semanticscholar.org instead of
    the semanticscholar Python SDK, reducing dependency footprint.

    Features:
    - DOI-based lookup for exact matching
    - Title-based search for fuzzy matching
    - Optional API key via x-api-key header for higher rate limits
    - Mandatory exponential backoff (handled by base class)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="s2", api_key=api_key, timeout=timeout)

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including optional API key.

        Returns:
            Dict of headers for S2 API requests.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference against Semantic Scholar.

        Strategy:
        1. If DOI present → paper lookup by DOI
        2. Otherwise → search by title

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        try:
            if reference.has_doi:
                return await self._verify_by_doi(reference, client)

            return await self._verify_by_search(reference, client)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise  # Let base class handle rate limiting
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"S2 API HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )

    async def _verify_by_doi(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Look up a paper by DOI.

        Endpoint: GET /graph/v1/paper/DOI:{doi}?fields=...

        Args:
            reference: Reference with a DOI.
            client: Async HTTP client.

        Returns:
            AdapterMatch.
        """
        url = f"{_S2_API_BASE}/paper/DOI:{reference.doi}"
        params = {"fields": _PAPER_FIELDS}

        response = await client.get(
            url,
            headers=self._build_headers(),
            params=params,
        )

        if response.status_code == 404:
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"DOI not found: {reference.doi}",
            )

        response.raise_for_status()
        data = response.json()

        return self._api_item_to_match(data, reference)

    async def _verify_by_search(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Search for a paper by title.

        Endpoint: GET /graph/v1/paper/search?query=...&fields=...&limit=5

        Args:
            reference: Reference to search for.
            client: Async HTTP client.

        Returns:
            AdapterMatch with best result.
        """
        url = f"{_S2_API_BASE}/paper/search"
        params = {
            "query": reference.title,
            "fields": _PAPER_FIELDS,
            "limit": 5,
        }

        response = await client.get(
            url,
            headers=self._build_headers(),
            params=params,
        )
        response.raise_for_status()

        data = response.json()
        items = data.get("data", [])

        if not items:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for item in items:
            match = self._api_item_to_match(item, reference)
            if match.composite_score > best_composite:
                best_composite = match.composite_score
                best_match = match

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name,
            found=False,
        )

    def _api_item_to_match(
        self,
        item: dict,
        reference: ReferenceItem,
    ) -> AdapterMatch:
        """Convert a Semantic Scholar API response item to an AdapterMatch.

        Args:
            item: S2 API JSON dict for a paper.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        matched_title = item.get("title")
        matched_year = item.get("year")

        # Venue may be None or empty string
        matched_venue = item.get("venue") or None

        # Extract author names
        authors_data = item.get("authors") or []
        matched_authors = [
            a.get("name", "")
            for a in authors_data
            if a.get("name")
        ]

        # Extract DOI from externalIds
        ext_ids = item.get("externalIds") or {}
        matched_doi = ext_ids.get("DOI")

        paper_id = item.get("paperId")
        source_url = (
            f"https://www.semanticscholar.org/paper/{paper_id}"
            if paper_id
            else None
        )

        t, a, y, v, composite = score_match(
            reference,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_journal=matched_venue,
        )

        return AdapterMatch(
            adapter_name=self.name,
            found=composite >= 0.6,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_journal=matched_venue,
            matched_doi=matched_doi,
            title_score=t,
            author_score=a,
            year_score=y,
            venue_score=v,
            composite_score=composite,
            source_url=source_url,
        )
