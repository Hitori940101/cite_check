"""Abstract verification adapter interface with built-in exponential backoff.

All verification adapters inherit from VerificationAdapter, which provides:
- A common verify() interface
- Automatic exponential backoff with jitter on retries
- Retry-After header support (mandatory for Semantic Scholar)
- Structured logging of verification attempts
"""

import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

import httpx

from refchecker.core.exceptions import RateLimitError
from refchecker.core.logging import get_logger
from refchecker.core.models import AdapterMatch, ReferenceItem

logger = get_logger(__name__)

# Backoff constants (per ADR-2 and S2 API policy)
_BACKOFF_INITIAL = 1.0  # seconds
_BACKOFF_MAX = 60.0  # seconds
_BACKOFF_FACTOR = 2.0
_BACKOFF_JITTER = 0.5  # ± seconds
_MAX_RETRIES = 5


class VerificationAdapter(ABC):
    """Abstract base class for all verification adapters.

    Subclasses must implement verify_single(), which performs a single
    verification attempt (no retries). The base class handles retry logic,
    exponential backoff, and error wrapping.

    Attributes:
        name: Unique adapter identifier (e.g. "crossref", "s2").
        api_key: Optional API key for higher rate limits.
    """

    def __init__(
        self,
        *,
        name: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    async def verify_single(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Perform a single verification attempt (no retries).

        Args:
            reference: The citation reference to verify.
            client: Shared async HTTP client for making requests.

        Returns:
            AdapterMatch with results.

        Raises:
            RateLimitError: When rate-limited by the API.
            httpx.HTTPError: On network errors.
        """
        ...

    async def verify(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient | None = None,
    ) -> AdapterMatch:
        """Verify a reference with automatic retries and exponential backoff.

        Creates a temporary httpx.AsyncClient if none is provided.

        Args:
            reference: The citation reference to verify.
            client: Optional shared async HTTP client.

        Returns:
            AdapterMatch with verification results.
        """
        if client is not None:
            return await self._verify_with_backoff(reference, client)

        async with httpx.AsyncClient(timeout=self.timeout) as inner_client:
            return await self._verify_with_backoff(reference, inner_client)

    async def _verify_with_backoff(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> AdapterMatch:
        """Execute verify_single with exponential backoff on rate-limit errors.

        Args:
            reference: The citation reference to verify.
            client: Async HTTP client.

        Returns:
            AdapterMatch (successful or error result).
        """
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                result = await self.verify_single(reference, client)
                if attempt > 0:
                    logger.info(
                        "backoff_success",
                        adapter=self.name,
                        attempt=attempt + 1,
                        title=reference.title[:60],
                    )
                return result

            except RateLimitError as exc:
                last_error = exc
                delay = self._compute_backoff(attempt, retry_after=exc.retry_after)
                logger.warning(
                    "rate_limited_retry",
                    adapter=self.name,
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    delay_s=round(delay, 2),
                    title=reference.title[:60],
                )
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    # Treat 429 as rate limit
                    retry_after = self._parse_retry_after(exc.response)
                    delay = self._compute_backoff(attempt, retry_after=retry_after)
                    logger.warning(
                        "http_429_retry",
                        adapter=self.name,
                        attempt=attempt + 1,
                        delay_s=round(delay, 2),
                        title=reference.title[:60],
                    )
                    await asyncio.sleep(delay)
                    continue
                # Non-429 HTTP errors: don't retry
                logger.error(
                    "http_error_no_retry",
                    adapter=self.name,
                    status_code=exc.response.status_code,
                    title=reference.title[:60],
                )
                return AdapterMatch(
                    adapter_name=self.name,
                    found=False,
                    error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                )

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                delay = self._compute_backoff(attempt)
                logger.warning(
                    "network_error_retry",
                    adapter=self.name,
                    attempt=attempt + 1,
                    error_type=type(exc).__name__,
                    delay_s=round(delay, 2),
                    title=reference.title[:60],
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                # Unexpected errors: don't retry, wrap in error result
                logger.error(
                    "unexpected_error",
                    adapter=self.name,
                    error=str(exc),
                    title=reference.title[:60],
                )
                return AdapterMatch(
                    adapter_name=self.name,
                    found=False,
                    error=f"Unexpected error: {exc}",
                )

        # Exhausted all retries
        logger.error(
            "backoff_exhausted",
            adapter=self.name,
            max_retries=_MAX_RETRIES,
            title=reference.title[:60],
        )
        return AdapterMatch(
            adapter_name=self.name,
            found=False,
            error=f"Max retries ({_MAX_RETRIES}) exceeded: {last_error}",
        )

    @staticmethod
    def _compute_backoff(
        attempt: int,
        retry_after: float | None = None,
    ) -> float:
        """Compute exponential backoff delay with jitter.

        Args:
            attempt: Zero-indexed attempt number.
            retry_after: Server-provided Retry-After value in seconds.

        Returns:
            Delay in seconds before the next retry.
        """
        if retry_after is not None and retry_after > 0:
            # Respect server-provided retry-after
            return retry_after + random.uniform(0, _BACKOFF_JITTER)

        delay = min(
            _BACKOFF_INITIAL * (_BACKOFF_FACTOR ** attempt),
            _BACKOFF_MAX,
        )
        jitter = random.uniform(-_BACKOFF_JITTER, _BACKOFF_JITTER)
        return max(0.1, delay + jitter)

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        """Parse Retry-After header from an HTTP response.

        Supports both integer (seconds) and HTTP-date formats.

        Args:
            response: The HTTP response to parse.

        Returns:
            Retry-after value in seconds, or None if not present.
        """
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            # Could be an HTTP date — for simplicity, default to 5s
            return 5.0

    def __repr__(self) -> str:
        has_key = "key=✓" if self.api_key else "key=✗"
        return f"<{type(self).__name__} name={self.name!r} {has_key}>"
