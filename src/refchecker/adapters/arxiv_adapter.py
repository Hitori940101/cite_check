"""arXiv verification adapter.

Uses the free arXiv API for preprint verification.
Returns Atom XML — no API key required.
Rate limit: polite usage, ~1 request per 3 seconds.
"""

import xml.etree.ElementTree as ET

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)

_ARXIV_API_URL = "http://export.arxiv.org/api/query"
_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivAdapter(VerificationAdapter):
    """Verification adapter using the arXiv API.

    Features:
    - Free, no API key
    - Title-based search
    - Parses Atom XML responses
    - Rate-limited to 3+ seconds between requests
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        super().__init__(name="arxiv", api_key=None, timeout=timeout)
        self._min_request_interval = 3.0

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference against arXiv.

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        await self.throttle()

        params = {
            "search_query": f'ti:"{reference.title}"',
            "max_results": 5,
            "sortBy": "relevance",
        }
        headers = {"Accept": "application/atom+xml"}

        response = await client.get(_ARXIV_API_URL, params=params, headers=headers)
        response.raise_for_status()

        return self._parse_xml(response.text, reference)

    def _parse_xml(self, xml_text: str, reference: ReferenceItem) -> AdapterMatch:
        """Parse arXiv Atom XML response and score matches.

        Args:
            xml_text: Raw XML response from arXiv API.
            reference: Original reference for scoring.

        Returns:
            AdapterMatch with best result.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return AdapterMatch(adapter_name=self.name, found=False, error="XML parse error")

        entries = root.findall("atom:entry", _ARXIV_NS)
        if not entries:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for entry in entries:
            match = self._entry_to_match(entry, reference)
            if match.composite_score > best_composite:
                best_composite = match.composite_score
                best_match = match

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name, found=False,
        )

    def _entry_to_match(self, entry: ET.Element, reference: ReferenceItem) -> AdapterMatch:
        """Convert an arXiv entry to an AdapterMatch.

        Args:
            entry: Atom XML entry element.
            reference: Original reference for scoring.

        Returns:
            Scored AdapterMatch.
        """
        # Title
        title_el = entry.find("atom:title", _ARXIV_NS)
        matched_title = ""
        if title_el is not None and title_el.text:
            matched_title = title_el.text.strip().replace("\n", " ")

        # Authors
        author_elements = entry.findall("atom:author", _ARXIV_NS)
        matched_authors: list[str] = []
        for author_el in author_elements:
            name_el = author_el.find("atom:name", _ARXIV_NS)
            if name_el is not None and name_el.text:
                matched_authors.append(name_el.text.strip())

        # Year from published date
        matched_year: int | None = None
        published_el = entry.find("atom:published", _ARXIV_NS)
        if published_el is not None and published_el.text:
            try:
                matched_year = int(published_el.text[:4])
            except ValueError:
                pass

        # DOI
        matched_doi: str | None = None
        doi_el = entry.find("atom:doi", _ARXIV_NS)
        if doi_el is not None and doi_el.text:
            matched_doi = doi_el.text.strip()

        # Source URL
        source_url: str | None = None
        id_el = entry.find("atom:id", _ARXIV_NS)
        if id_el is not None and id_el.text:
            source_url = id_el.text.strip()

        t, a, y, v, composite = score_match(
            reference,
            matched_title=matched_title,
            matched_authors=matched_authors,
            matched_year=matched_year,
        )

        return AdapterMatch(
            adapter_name=self.name,
            found=composite >= 0.6,
            matched_title=matched_title or None,
            matched_authors=matched_authors,
            matched_year=matched_year,
            matched_doi=matched_doi,
            title_score=t,
            author_score=a,
            year_score=y,
            venue_score=v,
            composite_score=composite,
            source_url=source_url,
        )
