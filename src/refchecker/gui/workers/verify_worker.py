"""Background verification worker using QThread.

Runs the VerificationEngine in a background thread and emits
progress/result signals back to the GUI thread.

Emits individual VerificationResult per reference for incremental display.
Supports cooperative cancellation between reference verifications.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal

from refchecker.core.logging import get_logger
from refchecker.core.models import ReferenceItem, VerificationResult
from refchecker.engine import VerificationEngine

logger = get_logger(__name__)


class VerifyWorker(QThread):
    """Background thread for citation verification.

    Signals:
        progress(int, int, object): Emitted after each reference is verified.
            (current, total, VerificationResult) — carries the result for
            incremental row updates in the GUI.
        result_ready(list): Emitted with all VerificationResult when complete.
        error(str): Emitted if an error occurs.
        rate_limited(str): Emitted when an adapter hits a rate limit.
    """

    progress = Signal(int, int, object)  # current, total, VerificationResult
    result_ready = Signal(list)  # list[VerificationResult]
    error = Signal(str)
    rate_limited = Signal(str)  # adapter name

    def __init__(
        self,
        references: list[ReferenceItem],
        engine: VerificationEngine,
        parent: object = None,
    ) -> None:
        super().__init__(parent)
        self._references = references
        self._engine = engine
        self._is_cancelled = False

    def run(self) -> None:
        """Execute verification in background thread.

        Verifies references sequentially, checking for cancellation
        between each one. This allows the user to stop verification
        and see partial results.
        """
        import asyncio

        try:
            results = asyncio.run(self._run_verification())
            if not self._is_cancelled:
                self.result_ready.emit(results)
            else:
                # Still emit partial results on cancel
                self.result_ready.emit(results)
        except Exception as exc:
            logger.error("verify_worker_error", error=str(exc))
            self.error.emit(str(exc))

    async def _run_verification(self) -> list[VerificationResult]:
        """Run verification sequentially with cancellation checks.

        Returns:
            List of verification results (may be partial if cancelled).
        """
        import asyncio

        total = len(self._references)
        results: list[VerificationResult] = []

        for i, ref in enumerate(self._references):
            if self._is_cancelled:
                logger.info("verify_worker_cancelled", completed=i, total=total)
                break

            try:
                result = await self._engine.verify_single(ref)
                results.append(result)

                # Emit progress and check for rate limits
                self.progress.emit(i + 1, total, result)
                for match in result.matches:
                    if match.error and "rate" in match.error.lower():
                        self.rate_limited.emit(match.adapter_name)

            except Exception as exc:
                logger.warning("verify_single_error", error=str(exc))
                # Create an error result so the row still appears
                results.append(VerificationResult(
                    reference=ref,
                    status=None,  # type: ignore[arg-type]
                    matches=[],
                    best_score=0.0,
                ))

        return results

    def cancel(self) -> None:
        """Request cancellation of the verification.

        The running verification will stop after the current reference
        finishes. Partial results are still emitted via result_ready.
        """
        self._is_cancelled = True
        logger.info("verify_worker_cancel_requested")
