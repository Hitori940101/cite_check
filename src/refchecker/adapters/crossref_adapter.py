"""Crossref verification adapter.

Uses the Crossref API via habanero for:
1. Direct DOI lookup (instant, deterministic)
2. Bibliographic (fuzzy title) search

Free, no API key required. Polite pool with mailto header.
"""

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)


def _extract_year(item: dict) -> int | None:
    """Extract publication year from a Crossref work item.

    Tries published-print, published-online, created, in order.

    Args:
        item: Crossref work JSON dict.

    Returns:
        Year as int, or None if not found.
    """
    for field in ("published-print", "published-online", "created"):
        parts = item.get(field, {}).get("date-parts", [[]])
        if parts and parts[0]:
            return parts[0][0]
    return None


def _extract_authors(item: dict) -> list[str]:
    """Extract author names from a Crossref work item.

    Args:
        item: Crossref work JSON dict.

    Returns:
        List of "Given Family" author name strings.
    """
    authors_data = item.get("author", [])
    result: list[str] = []
    for author in authors_data:
        given = author.get("given", "")
        family = author.get("family", "")
        name = f"{given} {family}".strip()
        if name:
            result.append(name)
    return result


class CrossrefAdapter(VerificationAdapter):
    """Verification adapter using the Crossref API.

    Features:
    - Direct DOI lookup for exact matching
    - Bibliographic (fuzzy title) search for non-DOI references
    - Polite pool with configurable mailto
    - No API key required
    """

    def __init__(
        self,
        *,
        mailto: str = "refchecker@example.com",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="crossref", api_key=api_key, timeout=timeout)
        self.mailto = mailto

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference against Crossref.

        Strategy:
        1. If DOI present → direct DOI lookup
        2. Otherwise → bibliographic search by title

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        if reference.has_doi:
            return await self._verify_by_doi(reference, client)

        return await self._verify_by_search(reference, client)

    async def _verify_by_doi(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Look up a reference by DOI.

        Args:
            reference: Reference with a DOI.
            client: Async HTTP client.

        Returns:
            AdapterMatch.
        """
        url = f"https://api.crossref.org/works/{reference.doi}"
        headers = {"User-Agent": f"RefChecker/0.1 (mailto:{self.mailto})"}

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return AdapterMatch(
                    adapter_name=self.name,
                    found=False,
                    error=f"DOI not found: {reference.doi}",
                )
            raise

        data = response.json()
        item = data.get("message", {})

        return self._item_to_match(item, reference)

    async def _verify_by_search(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Search for a reference by title.

        Args:
            reference: Reference without a DOI.
            client: Async HTTP client.

        Returns:
            AdapterMatch with best result.
        """
        url = "https://api.crossref.org/works"
        headers = {"User-Agent": f"RefChecker/0.1 (mailto:{self.mailto})"}
        params = {
            "query.bibliographic": reference.title,
            "rows": 5,
            "select": "DOI,title,author,published-print,published-online,created,container-title,score",
        }

        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        items = data.get("message", {}).get("items", [])

        if not items:
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
            )

        # Score each candidate and return the best
        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for item in items:
            match = self._item_to_match(item, reference)
            if match.composite_score > best_composite:
                best_composite = match.composite_score
                best_match = match

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name,
            found=False,
        )

    def _item_to_match(
        self,
        item: dict,
        reference: ReferenceItem,
    ) -> AdapterMatch:
        """Convert a Crossref API item to an AdapterMatch with scores.

        Args:
            item: Crossref work JSON dict.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        titles = item.get("title", [])
        matched_title = titles[0] if titles else None
        matched_authors = _extract_authors(item)
        matched_year = _extract_year(item)

        containers = item.get("container-title", [])
        matched_journal = containers[0] if containers else None
        matched_doi = item.get("DOI")

        t, a, y, v, composite = score_match(
            reference,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_journal=matched_journal,
        )

        source_url = f"https://doi.org/{matched_doi}" if matched_doi else None

        return AdapterMatch(
            adapter_name=self.name,
            found=composite >= 0.6,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_journal=matched_journal,
            matched_doi=matched_doi,
            title_score=t,
            author_score=a,
            year_score=y,
            venue_score=v,
            composite_score=composite,
            source_url=source_url,
        )
