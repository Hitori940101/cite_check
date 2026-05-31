"""CNKI verification adapter.

Uses Playwright for headless browser-based search on CNKI (cnki.net).
Search results page is public — no login required, no detail page access.

Last-resort fallback for Chinese academic literature not found
in AMiner or Baidu Academic.
"""

import asyncio

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem
from refchecker.core.scorer import compute_title_score, score_match

logger = get_logger(__name__)

_CNKI_SEARCH_URL = "https://kns.cnki.net/kns8s/search"


class CNKIAdapter(VerificationAdapter):
    """Verification adapter using CNKI search via Playwright.

    Last-resort fallback for Chinese academic literature.
    Uses headless browser because CNKI requires JavaScript rendering.
    Search results page only — no login, no detail page access.
    """

    def __init__(
        self,
        *,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(name="cnki", api_key=None, timeout=timeout)

    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Verify a reference via CNKI search using Playwright.

        Args:
            reference: The citation to verify.
            client: Shared async HTTP client (not used — Playwright has own).

        Returns:
            AdapterMatch with results.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error="Playwright not installed. Install with: pip install playwright && playwright install",
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(_CNKI_SEARCH_URL, wait_until="networkidle", timeout=self.timeout * 1000)

                # Fill search input and submit
                search_input = page.locator('input[name="txt_search"]')
                if await search_input.count() == 0:
                    # Fallback: try alternative selectors
                    search_input = page.locator("#txt_SearchText")

                await search_input.fill(reference.title)
                await search_input.press("Enter")

                # Wait for results
                await page.wait_for_selector(".result-table-list, .s-main", timeout=15000)

                # Extract result titles
                results = await page.evaluate("""() => {
                    const items = [];
                    const rows = document.querySelectorAll('tr[valign="middle"], .result-table-list tbody tr');
                    rows.forEach(row => {
                        const titleEl = row.querySelector('td.name a, .name a');
                        const authorEl = row.querySelector('td.author, .author');
                        const sourceEl = row.querySelector('td.source, .source');
                        const dateEl = row.querySelector('td.date, .date');
                        items.push({
                            title: titleEl ? titleEl.textContent.trim() : '',
                            authors: authorEl ? authorEl.textContent.trim() : '',
                            source: sourceEl ? sourceEl.textContent.trim() : '',
                            date: dateEl ? dateEl.textContent.trim() : '',
                        });
                    });
                    return items;
                })""")

                await browser.close()

        except Exception as exc:
            logger.warning("cnki_scrape_error", error=str(exc), title=reference.title[:60])
            return AdapterMatch(
                adapter_name=self.name,
                found=False,
                error=f"CNKI scrape error: {exc}",
            )

        if not results:
            return AdapterMatch(adapter_name=self.name, found=False)

        # Score each result
        best_match: AdapterMatch | None = None
        best_composite = 0.0

        for item in results[:5]:
            matched_title = item.get("title", "")
            if not matched_title:
                continue

            # Parse year from date string
            import re
            year_match = re.search(r"\b(19|20)\d{2}\b", item.get("date", ""))
            matched_year = int(year_match.group()) if year_match else None

            matched_authors = [
                a.strip()
                for a in (item.get("authors", "")).split(";")
                if a.strip()
            ]
            matched_journal = item.get("source", "") or None

            t, a, y, v, composite = score_match(
                reference,
                matched_title=matched_title,
                matched_authors=matched_authors,
                matched_year=matched_year,
                matched_journal=matched_journal,
            )

            if composite > best_composite:
                best_composite = composite
                best_match = AdapterMatch(
                    adapter_name=self.name,
                    found=composite >= 0.6,
                    matched_title=matched_title,
                    matched_authors=matched_authors,
                    matched_year=matched_year,
                    matched_journal=matched_journal,
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
