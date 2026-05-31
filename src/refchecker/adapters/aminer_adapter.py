"""AMiner verification adapter.

Uses the AMiner API for academic paper search, with strong coverage
of Chinese academic literature — our key differentiator.

AMiner has 300M+ papers with strong Chinese journal/conference coverage.
The API supports both English and Chinese title queries.

Free tier available. API key optional for higher limits.
"""

import asyncio
import base64
import json

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.exceptions import RateLimitError
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)

_AMINER_API_BASE = "https://apiv2.aminer.cn"


def _encode_query(params: dict) -> str:
    """Encode query parameters for AMiner v2 API (base64 JSON).

    Args:
        params: Query parameters dict.

    Returns:
        Base64-encoded JSON string.
    """
    payload = json.dumps(params, ensure_ascii=False)
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


class AMinerAdapter(VerificationAdapter):
    """Verification adapter using the AMiner API.

    Key differentiator: strong coverage of Chinese academic literature.
    Supports both Chinese and English title queries.

    Features:
    - Publication search by title
    - DOI-based lookup via title search
    - Chinese journal/conference coverage
    - Optional API key for higher limits
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="aminer", api_key=api_key, timeout=timeout)

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference against AMiner.

        Strategy: Search by title (handles both English and Chinese).

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        return await self._verify_by_search(reference, client)

    async def _verify_by_search(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Search for a publication by title.

        Args:
            reference: Reference to search for.
            client: Async HTTP client.

        Returns:
            AdapterMatch with best result.
        """
        query_params = {
            "query": reference.title,
            "offset": 0,
            "size": 5,
        }
        encoded = _encode_query(query_params)

        url = f"{_AMINER_API_BASE}/magic"
        params = {
            "service": "search.publication.n",
            "q": encoded,
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            response = await client.get(url, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitError(
                    "AMiner rate limit",
                    adapter_name=self.name,
                    retry_after=self._parse_retry_after(exc.response),
                ) from exc
            raise

        if response.status_code != 200:
            logger.warning(
                "aminer_api_error",
                status=response.status_code,
                body=response.text[:200],
            )
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"AMiner API returned {response.status_code}",
            )

        try:
            data = response.json()
        except Exception:
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error="Failed to parse AMiner response",
            )

        # Extract results from AMiner response
        hits = []
        result = data.get("result", {})
        if isinstance(result, dict):
            hits = result.get("hit", [])
        elif isinstance(result, list):
            hits = result

        if not hits:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for hit in hits:
            match = self._hit_to_match(hit, reference)
            if match.composite_score > best_composite:
                best_composite = match.composite_score
                best_match = match

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name,
            found=False,
        )

    def _hit_to_match(
        self,
        hit: dict,
        reference: ReferenceItem,
    ) -> AdapterMatch:
        """Convert an AMiner hit to an AdapterMatch.

        Args:
            hit: AMiner publication JSON dict.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        matched_title = hit.get("title")
        matched_year = hit.get("year")
        if isinstance(matched_year, str):
            try:
                matched_year = int(matched_year)
            except ValueError:
                matched_year = None

        # Extract authors
        authors_data = hit.get("authors", [])
        if isinstance(authors_data, list):
            matched_authors = []
            for a in authors_data:
                if isinstance(a, dict):
                    name = a.get("name", "")
                elif isinstance(a, str):
                    name = a
                else:
                    name = ""
                if name:
                    matched_authors.append(name)
        else:
            matched_authors = []

        matched_journal = hit.get("venue", {}).get("name") if isinstance(hit.get("venue"), dict) else None
        matched_doi = hit.get("doi")
        paper_id = hit.get("id")
        source_url = f"https://www.aminer.cn/pub/{paper_id}" if paper_id else None

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
            source_url=source_url,
        )
