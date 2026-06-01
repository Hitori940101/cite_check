"""Baidu Academic verification adapter.

Uses Baidu Academic (xueshu.baidu.com) for Chinese literature verification.
Scrapes search results via httpx — no API key, no Playwright needed.

Fallback source for Chinese academic papers not found in AMiner.
Moderate anti-crawl: use reasonable delays and headers.
"""

import re

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)

_BAIDU_SEARCH_URL = "https://xueshu.baidu.com/s"

# Regex patterns for parsing Baidu Academic HTML results
_TITLE_PATTERN = re.compile(
    r'class="t"[^>]*>\s*<a[^>]*>(.*?)</a>',
    re.DOTALL,
)
_AUTHOR_PATTERN = re.compile(
    r'class="author_text"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_YEAR_VENUE_PATTERN = re.compile(
    r'class="sc_info"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities.

    Args:
        text: HTML fragment.

    Returns:
        Cleaned plain text.
    """
    text = _HTML_TAG.sub("", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    return text.strip()


def _parse_year_from_info(info_text: str) -> int | None:
    """Extract publication year from Baidu's info line.

    Args:
        info_text: The sc_info text like "Journal Name, 2023, 10(2): 100-110"

    Returns:
        Year as int or None.
    """
    match = re.search(r"\b(19|20)\d{2}\b", info_text)
    if match:
        return int(match.group())
    return None


class BaiduAdapter(VerificationAdapter):
    """Verification adapter using Baidu Academic search.

    Fallback source for Chinese academic papers.
    No API key required. Uses requests-based HTML scraping.
    Moderate anti-crawl — respectful request frequency.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(name="baidu", api_key=None, timeout=timeout)
        self._min_request_interval = 3.0

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference via Baidu Academic search.

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        await self.throttle()

        params = {
            "wd": reference.title,
            "rsv_bp": "0",
            "tn": "SE_baiduxueshu_c1gjeupa",
            "ie": "utf-8",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        response = await client.get(
            _BAIDU_SEARCH_URL,
            params=params,
            headers=headers,
        )
        response.raise_for_status()

        html = response.text
        return self._parse_results(html, reference)

    def _parse_results(
        self,
        html: str,
        reference: ReferenceItem,
    ) -> AdapterMatch:
        """Parse Baidu Academic search results HTML.

        Args:
            html: Search results page HTML.
            reference: Original reference for scoring.

        Returns:
            AdapterMatch with best result.
        """
        titles = _TITLE_PATTERN.findall(html)
        if not titles:
            return AdapterMatch(adapter_name=self.name, found=False)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for i, title_html in enumerate(titles[:5]):
            matched_title = _strip_html(title_html)

            # Try to extract authors and year from corresponding result block
            authors = self._extract_authors(html, i)
            year = self._extract_year(html, i)

            t, a, y, v, composite = score_match(
                reference,
                matched_title=matched_title,
                matched_authors=authors,
                matched_year=year,
            )

            if composite > best_composite:
                best_composite = composite
                best_match = AdapterMatch(
                    adapter_name=self.name,
                    found=composite >= 0.6,
                    matched_title=matched_title,
                    matched_authors=authors,
                    matched_year=year,
                    title_score=t,
                    author_score=a,
                    year_score=y,
                    venue_score=v,
                    composite_score=composite,
                )

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name,
            found=False,
        )

    def _extract_authors(self, html: str, result_index: int) -> list[str]:
        """Extract authors from the n-th search result.

        Args:
            html: Full page HTML.
            result_index: Zero-indexed result position.

        Returns:
            List of author name strings.
        """
        authors = _AUTHOR_PATTERN.findall(html)
        # Each result may have multiple author links — approximate mapping
        if result_index < len(authors):
            return [_strip_html(authors[result_index])]
        return []

    def _extract_year(self, html: str, result_index: int) -> int | None:
        """Extract publication year from the n-th search result.

        Args:
            html: Full page HTML.
            result_index: Zero-indexed result position.

        Returns:
            Year as int or None.
        """
        infos = _YEAR_VENUE_PATTERN.findall(html)
        if result_index < len(infos):
            return _parse_year_from_info(_strip_html(infos[result_index]))
        return None
