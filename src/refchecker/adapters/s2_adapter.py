"""Semantic Scholar verification adapter.

Uses the Semantic Scholar API via the semanticscholar Python SDK for:
1. Paper search by title
2. Paper lookup by DOI

Free tier: ~100 req/5min (shared, variable).
With API key: 1 RPS guaranteed.
Exponential backoff is mandatory per S2 API policy.
"""

import httpx
from semanticscholar import SemanticScholar
from semanticscholar import SemanticScholarException

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.exceptions import RateLimitError
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)


class S2Adapter(VerificationAdapter):
    """Verification adapter using the Semantic Scholar API.

    Features:
    - Title-based search for fuzzy matching
    - DOI-based lookup for exact matching
    - Optional API key for higher rate limits
    - Mandatory exponential backoff (handled by base class)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="s2", api_key=api_key, timeout=timeout)
        self._client = SemanticScholar(api_key=api_key, timeout=timeout)

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
            client: Shared async HTTP client (not used — SDK has own client).

        Returns:
            AdapterMatch with results.
        """
        try:
            if reference.has_doi:
                return await self._verify_by_doi(reference)

            return await self._verify_by_search(reference)

        except SemanticScholarException as exc:
            error_msg = str(exc)
            if "429" in error_msg or "rate" in error_msg.lower():
                raise RateLimitError(
                    f"S2 rate limit: {error_msg}",
                    adapter_name=self.name,
                ) from exc
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"S2 API error: {error_msg}",
            )

    async def _verify_by_doi(self, reference: ReferenceItem) -> AdapterMatch:
        """Look up a paper by DOI.

        Args:
            reference: Reference with a DOI.

        Returns:
            AdapterMatch.
        """
        # Run synchronous SDK call in executor to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()

        try:
            paper = await loop.run_in_executor(
                None,
                lambda: self._client.get_paper(
                    f"DOI:{reference.doi}",
                    fields=["title", "authors", "year", "venue", "externalIds"],
                ),
            )
        except SemanticScholarException as exc:
            if "404" in str(exc):
                return AdapterMatch(
                    adapter_name=self.name,
                    found=False,
                    error=f"DOI not found: {reference.doi}",
                )
            raise

        if paper is None:
            return AdapterMatch(adapter_name=self.name, found=False)

        return self._paper_to_match(paper, reference)

    async def _verify_by_search(self, reference: ReferenceItem) -> AdapterMatch:
        """Search for a paper by title.

        Args:
            reference: Reference to search for.

        Returns:
            AdapterMatch with best result.
        """
        import asyncio
        loop = asyncio.get_event_loop()

        results = await loop.run_in_executor(
            None,
            lambda: self._client.search_paper(
                reference.title,
                limit=5,
                fields=["title", "authors", "year", "venue", "externalIds"],
            ),
        )

        if not results:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for paper in results:
            match = self._paper_to_match(paper, reference)
            if match.composite_score > best_composite:
                best_composite = match.composite_score
                best_match = match

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name,
            found=False,
        )

    def _paper_to_match(
        self,
        paper: object,
        reference: ReferenceItem,
    ) -> AdapterMatch:
        """Convert a Semantic Scholar Paper object to an AdapterMatch.

        Args:
            paper: S2 Paper object.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        matched_title = getattr(paper, "title", None)
        matched_year = getattr(paper, "year", None)
        matched_venue = getattr(paper, "venue", None) or None

        authors_obj = getattr(paper, "authors", None) or []
        matched_authors = [a.name for a in authors_obj if hasattr(a, "name") and a.name]

        ext_ids = getattr(paper, "externalIds", None) or {}
        matched_doi = ext_ids.get("DOI")

        paper_id = getattr(paper, "paperId", None)
        source_url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

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
