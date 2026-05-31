"""Verification orchestration engine.

Coordinates parallel adapter queries, aggregates results, and determines
final verification status for each reference.
"""

import asyncio
from typing import Sequence

import httpx

from refchecker.adapters.base import VerificationAdapter
from refchecker.core.logging import get_logger
from refchecker.core.models import (
    AdapterMatch,
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)

logger = get_logger(__name__)


class VerificationEngine:
    """Orchestrates the verification pipeline.

    Manages a collection of adapters, runs them in parallel per reference,
    and aggregates their results into a final VerificationResult.

    Attributes:
        adapters: List of verification adapters to query.
        timeout: HTTP client timeout in seconds.
    """

    def __init__(
        self,
        adapters: Sequence[VerificationAdapter],
        *,
        timeout: float = 30.0,
        max_concurrent: int = 3,
    ) -> None:
        self.adapters = list(adapters)
        self.timeout = timeout
        self.max_concurrent = max_concurrent

    async def verify_single(
        self,
        reference: ReferenceItem,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> VerificationResult:
        """Verify a single reference against all adapters.

        Queries all adapters in parallel and aggregates results.

        Args:
            reference: The citation reference to verify.
            client: Optional shared HTTP client.

        Returns:
            VerificationResult with aggregated matches and final status.
        """
        if client is not None:
            return await self._run_adapters(reference, client)

        async with httpx.AsyncClient(timeout=self.timeout) as inner_client:
            return await self._run_adapters(reference, inner_client)

    async def verify_batch(
        self,
        references: Sequence[ReferenceItem],
        *,
        progress_callback: object = None,
    ) -> list[VerificationResult]:
        """Verify a batch of references.

        Processes references with bounded concurrency to avoid
        overwhelming APIs.

        Args:
            references: List of references to verify.
            progress_callback: Optional callback invoked after each reference.

        Returns:
            List of VerificationResult, one per reference.
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results: list[VerificationResult | None] = [None] * len(references)

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            async def _verify_with_semaphore(
                idx: int,
                ref: ReferenceItem,
            ) -> None:
                async with semaphore:
                    result = await self.verify_single(ref, client=client)
                    results[idx] = result
                    if progress_callback and callable(progress_callback):
                        progress_callback(idx, result)

            tasks = [
                _verify_with_semaphore(i, ref)
                for i, ref in enumerate(references)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Fill any None slots with error results
        final: list[VerificationResult] = []
        for i, r in enumerate(results):
            if r is not None:
                final.append(r)
            else:
                final.append(
                    VerificationResult(
                        reference=references[i],
                        status=VerificationStatus.UNABLE_TO_VERIFY,
                    )
                )

        logger.info(
            "batch_complete",
            total=len(references),
            verified=sum(1 for r in final if r.status == VerificationStatus.VERIFIED),
            suspicious=sum(1 for r in final if r.status == VerificationStatus.SUSPICIOUS),
            fabricated=sum(1 for r in final if r.status == VerificationStatus.LIKELY_FABRICATED),
            unable=sum(1 for r in final if r.status == VerificationStatus.UNABLE_TO_VERIFY),
        )
        return final

    async def _run_adapters(
        self,
        reference: ReferenceItem,
        client: httpx.AsyncClient,
    ) -> VerificationResult:
        """Run all adapters for a single reference.

        Args:
            reference: The reference to verify.
            client: HTTP client to share.

        Returns:
            VerificationResult with aggregated matches.
        """
        result = VerificationResult(reference=reference)

        adapter_names = [a.name for a in self.adapters]
        logger.debug(
            "verify_start",
            title=reference.title[:60],
            adapters=adapter_names,
        )

        # Run adapters concurrently
        tasks = [
            adapter.verify(reference, client=client)
            for adapter in self.adapters
        ]
        matches = await asyncio.gather(*tasks, return_exceptions=True)

        for match_or_exc in matches:
            if isinstance(match_or_exc, AdapterMatch):
                result = result.with_match(match_or_exc)
            elif isinstance(match_or_exc, Exception):
                logger.warning(
                    "adapter_exception",
                    error=str(match_or_exc),
                    title=reference.title[:60],
                )
                error_match = AdapterMatch(
                    adapter_name="unknown",
                    found=False,
                    error=f"Adapter exception: {match_or_exc}",
                )
                result = result.with_match(error_match)

        # Determine final status
        result = result.determine_status()

        logger.info(
            "verify_done",
            title=reference.title[:60],
            status=result.status.value,
            best_score=round(result.best_score, 3),
        )

        return result
