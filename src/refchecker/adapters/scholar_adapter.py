"""Google Scholar verification adapter via gufen academic mirror.

Uses 谷粉学术 (gufen scholar mirror) for users in China without VPN.
Three-layer fallback:
1. Gufen mirror (cached domain → dynamic search discovery)
2. scholarly library + proxy (requires proxy configuration)
3. Returns unable_to_verify

Rate-limited: random 3-8 second delay between requests.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from pathlib import Path
from typing import Any

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import score_match

logger = get_logger(__name__)

# Known gufen mirror patterns for discovery
_SEED_MIRRORS = [
    "https://gfsoso.vygc.top",
    "https://scholar.gufen.xyz",
    "https://scholar.gugesearch.com",
    "https://ac.scmor.com",
]

_MIRROR_CACHE_DIR = Path.home() / ".refchecker"
_MIRROR_CACHE_FILE = _MIRROR_CACHE_DIR / "gufen_mirror.json"
_MIRROR_CACHE_TTL = 86400  # 24 hours

_THROTTLE_MIN = 3.0
_THROTTLE_MAX = 8.0

# Regex patterns for parsing Scholar HTML
_TITLE_PATTERN = re.compile(
    r'class="gs_rt"[^>]*>.*?<a[^>]*href="[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TITLE_PATTERN_ALT = re.compile(
    r'class="gs_rt"[^>]*>(.*?)</h3>',
    re.DOTALL,
)
_AUTHOR_PATTERN = re.compile(
    r'class="gs_a"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_HTML_TAG = re.compile(r"<[^>]+>")

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ScholarAdapter(VerificationAdapter):
    """Verification adapter using Google Scholar via gufen mirror.

    For users in China without VPN access to Google Scholar directly.
    Three-layer fallback: gufen mirror → scholarly lib → graceful failure.
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        super().__init__(name="scholar", api_key=None, timeout=timeout)
        self._min_request_interval = 5.0
        self._last_request_time: float = 0.0
        self._working_mirror: str | None = None

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference via Google Scholar.

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client.

        Returns:
            AdapterMatch with results.
        """
        await self.throttle()

        # Layer 1: Gufen mirror
        html = await self._search_mirror(reference.title, client)
        if html is not None:
            result = self._parse_results(html, reference)
            if result.found:
                return result

        # Layer 2: scholarly library (if available and proxy configured)
        result = await self._try_scholarly(reference, client)
        if result is not None:
            return result

        # Layer 3: Graceful failure
        return AdapterMatch(
            adapter_name=self.name,
            found=False,
            error="All Scholar sources unavailable",
        )

    # ------------------------------------------------------------------
    # Layer 1: Gufen mirror with dynamic discovery
    # ------------------------------------------------------------------

    async def _search_mirror(
        self, query: str, client: httpx.AsyncClient,
    ) -> str | None:
        """Search via gufen mirror with fallback.

        Args:
            query: Search query (paper title).
            client: HTTP client.

        Returns:
            HTML response text or None.
        """
        mirrors = await self._get_mirrors(client)

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }

        for mirror in mirrors:
            try:
                url = f"{mirror}/scholar"
                params = {"q": query, "hl": "en"}
                response = await client.get(
                    url, params=params, headers=headers, timeout=15.0,
                )
                response.raise_for_status()
                self._working_mirror = mirror
                self._save_cached_mirror(mirror)
                return response.text
            except Exception as exc:
                logger.warning("scholar_mirror_error", mirror=mirror, error=str(exc))
                continue

        return None

    async def _get_mirrors(self, client: httpx.AsyncClient) -> list[str]:
        """Get ordered list of mirror URLs to try.

        Priority: working mirror → cached mirror → seed mirrors → discovered mirrors.

        Args:
            client: HTTP client for discovery.

        Returns:
            Ordered list of mirror URLs.
        """
        mirrors: list[str] = []

        # 1. Last known working mirror
        if self._working_mirror:
            mirrors.append(self._working_mirror)

        # 2. Cached mirror
        cached = self._load_cached_mirror()
        if cached and cached not in mirrors:
            mirrors.append(cached)

        # 3. Seed mirrors
        for m in _SEED_MIRRORS:
            if m not in mirrors:
                mirrors.append(m)

        # 4. Dynamic discovery (if cache is stale)
        if not cached or self._is_cache_stale():
            discovered = await self._discover_mirrors(client)
            for m in discovered:
                if m not in mirrors:
                    mirrors.append(m)

        return mirrors

    async def _discover_mirrors(self, client: httpx.AsyncClient) -> list[str]:
        """Search for gufen mirrors via Bing.

        Args:
            client: HTTP client.

        Returns:
            List of discovered mirror URLs.
        """
        discovered: list[str] = []
        try:
            search_url = "https://www.bing.com/search"
            params = {"q": "谷粉学术 Google Scholar 镜像"}
            headers = {"User-Agent": _USER_AGENT}
            response = await client.get(
                search_url, params=params, headers=headers, timeout=10.0,
            )
            text = response.text
            # Extract URLs from search results
            url_pattern = re.compile(r'https?://[^\s"<>]+?(?:gufen|gfsoso|scholar|scmor)[^\s"<>]*')
            discovered = list(set(url_pattern.findall(text)))
            # Clean URLs (remove trailing punctuation)
            discovered = [u.rstrip(".,;:)") for u in discovered]
        except Exception as exc:
            logger.warning("scholar_discovery_error", error=str(exc))
        return discovered

    # ------------------------------------------------------------------
    # Mirror cache
    # ------------------------------------------------------------------

    def _load_cached_mirror(self) -> str | None:
        """Load cached mirror URL from disk."""
        try:
            if _MIRROR_CACHE_FILE.exists():
                data = json.loads(_MIRROR_CACHE_FILE.read_text())
                return data.get("url")
        except Exception:
            pass
        return None

    def _save_cached_mirror(self, url: str) -> None:
        """Save working mirror URL to disk cache."""
        try:
            _MIRROR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {"url": url, "timestamp": time.time()}
            _MIRROR_CACHE_FILE.write_text(json.dumps(data))
        except Exception:
            pass

    def _is_cache_stale(self) -> bool:
        """Check if the cached mirror is older than TTL."""
        try:
            if _MIRROR_CACHE_FILE.exists():
                data = json.loads(_MIRROR_CACHE_FILE.read_text())
                ts = data.get("timestamp", 0)
                return (time.time() - ts) > _MIRROR_CACHE_TTL
        except Exception:
            pass
        return True

    # ------------------------------------------------------------------
    # Layer 2: scholarly library fallback
    # ------------------------------------------------------------------

    async def _try_scholarly(
        self, reference: ReferenceItem, client: httpx.AsyncClient,
    ) -> AdapterMatch | None:
        """Try using scholarly library as fallback.

        Args:
            reference: Reference to verify.
            client: HTTP client (for proxy info).

        Returns:
            AdapterMatch or None if scholarly unavailable.
        """
        try:
            from scholarly import scholarly
        except ImportError:
            return None

        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(scholarly.search_pubs(reference.title))[:5],
            )

            best_match: AdapterMatch | None = None
            best_composite = 0.0

            for pub in results:
                bib = pub.get("bib", {})
                matched_title = bib.get("title", "")
                matched_authors = bib.get("author", "").split(" and ") if bib.get("author") else []
                matched_year = bib.get("pub_year")
                if matched_year:
                    try:
                        matched_year = int(matched_year)
                    except ValueError:
                        matched_year = None

                matched_journal = bib.get("venue") or bib.get("journal")
                source_url = pub.get("pub_url")

                t, a, y, v, composite = score_match(
                    reference,
                    matched_title=matched_title or None,
                    matched_authors=matched_authors,
                    matched_year=matched_year,
                    matched_journal=matched_journal,
                )

                if composite > best_composite:
                    best_composite = composite
                    best_match = AdapterMatch(
                        adapter_name=self.name,
                        found=composite >= 0.6,
                        matched_title=matched_title or None,
                        matched_authors=matched_authors,
                        matched_year=matched_year,
                        matched_journal=matched_journal,
                        title_score=t,
                        author_score=a,
                        year_score=y,
                        venue_score=v,
                        composite_score=composite,
                        source_url=source_url,
                    )

            return best_match
        except Exception as exc:
            logger.warning("scholarly_error", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_results(self, html: str, reference: ReferenceItem) -> AdapterMatch:
        """Parse Scholar search results HTML.

        Args:
            html: Search results page HTML.
            reference: Original reference for scoring.

        Returns:
            AdapterMatch with best result.
        """
        # Try to extract titles
        titles = _TITLE_PATTERN.findall(html)
        if not titles:
            titles = _TITLE_PATTERN_ALT.findall(html)
            # Extract just the link text from alt pattern
            titles = [_HTML_TAG.sub("", self._extract_link_text(t)) for t in titles]

        if not titles:
            return AdapterMatch(adapter_name=self.name, found=False)

        author_blocks = _AUTHOR_PATTERN.findall(html)

        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for i, title_html in enumerate(titles[:5]):
            matched_title = _HTML_TAG.sub("", title_html).strip()

            # Parse authors and year from author block
            matched_authors: list[str] = []
            matched_year: int | None = None

            if i < len(author_blocks):
                info = _HTML_TAG.sub("", author_blocks[i])
                # Extract year
                year_match = re.search(r"\b(19|20)\d{2}\b", info)
                if year_match:
                    matched_year = int(year_match.group())
                # Extract authors (before the first " - ")
                author_part = info.split(" - ")[0] if " - " in info else info
                matched_authors = [a.strip() for a in author_part.split(",") if a.strip()]

            t, a, y, v, composite = score_match(
                reference,
                matched_title=matched_title or None,
                matched_authors=matched_authors,
                matched_year=matched_year,
            )

            if composite > best_composite:
                best_composite = composite
                best_match = AdapterMatch(
                    adapter_name=self.name,
                    found=composite >= 0.6,
                    matched_title=matched_title or None,
                    matched_authors=matched_authors,
                    matched_year=matched_year,
                    title_score=t,
                    author_score=a,
                    year_score=y,
                    venue_score=v,
                    composite_score=composite,
                )

        return best_match if best_match is not None else AdapterMatch(
            adapter_name=self.name, found=False,
        )

    @staticmethod
    def _extract_link_text(html: str) -> str:
        """Extract text content from the first <a> tag in HTML.

        Args:
            html: HTML fragment.

        Returns:
            Extracted text.
        """
        link_match = re.search(r'<a[^>]*>(.*?)</a>', html, re.DOTALL)
        return link_match.group(1) if link_match else html
