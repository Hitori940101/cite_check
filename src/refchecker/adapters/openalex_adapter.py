"""OpenAlex verification adapter.

Uses the OpenAlex API via pyalex for broad academic paper search.
Covers 450M+ works including some Chinese journals.

Free tier: 100 credits/day (testing only).
With API key: 100,000 credits/day (strongly recommended).
"""

import httpx
import pyalex
from pyalex import Works

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.exceptions import RateLimitError
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)


class OpenAlexAdapter(VerificationAdapter):
    """Verification adapter using the OpenAlex API.

    Features:
    - Title/author/DOI search
    - Broadest academic coverage
    - Optional API key for 100K credits/day
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        mailto: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="openalex", api_key=api_key, timeout=timeout)
        self.mailto = mailto
        if api_key:
            pyalex.config.api_key = api_key
        if mailto:
            pyalex.config.email = mailto

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference against OpenAlex.

        Strategy:
        1. If DOI present → filter by DOI
        2. Otherwise → search by title

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client (not used — pyalex has own).

        Returns:
            AdapterMatch with results.
        """
        try:
            if reference.has_doi:
                return await self._verify_by_doi(reference)
            return await self._verify_by_search(reference)

        except Exception as exc:
            error_msg = str(exc)
            if "429" in error_msg or "rate" in error_msg.lower():
                raise RateLimitError(
                    f"OpenAlex rate limit: {error_msg}",
                    adapter_name=self.name,
                ) from exc
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"OpenAlex error: {error_msg}",
            )

    async def _verify_by_doi(self, reference: ReferenceItem) -> AdapterMatch:
        """Look up a work by DOI.

        Args:
            reference: Reference with a DOI.

        Returns:
            AdapterMatch.
        """
        import asyncio
        loop = asyncio.get_event_loop()

        doi_url = f"https://doi.org/{reference.doi}"
        results = await loop.run_in_executor(
            None,
            lambda: Works().filter(doi=doi_url).get(per_page=1),
        )

        if not results:
            return AdapterMatch(adapter_name=self.name, found=False)

        return self._item_to_match(results[0], reference)

    async def _verify_by_search(self, reference: ReferenceItem) -> AdapterMatch:
        """Search for a work by title.

        Args:
            reference: Reference to search for.

        Returns:
            AdapterMatch with best result.
        """
        import asyncio
        loop = asyncio.get_event_loop()

        results = await loop.run_in_executor(
            None,
            lambda: Works().search(reference.title).get(per_page=5),
        )

        if not results:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for item in results:
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
        """Convert an OpenAlex work item to an AdapterMatch.

        Args:
            item: OpenAlex work JSON dict.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        matched_title = item.get("title")
        matched_year = item.get("publication_year")

        # Extract author names
        authorships = item.get("authorships") or []
        matched_authors = [
            a.get("author", {}).get("display_name", "")
            for a in authorships
            if a.get("author", {}).get("display_name")
        ]

        # Extract venue
        source = item.get("primary_location", {}) or {}
        source_obj = source.get("source") or {}
        matched_journal = source_obj.get("display_name")

        # Extract DOI
        doi_str = item.get("doi") or ""
        matched_doi = doi_str.replace("https://doi.org/", "") if doi_str else None

        # Source URL
        paper_id = item.get("id")

        t, a, y, v, composite = score_match(
            reference,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_journal=matched_journal,
        )

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
            source_url=paper_id,
        )
