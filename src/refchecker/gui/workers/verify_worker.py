"""Background verification worker using QThread.

Runs the VerificationEngine in a background thread and emits
progress/result signals back to the GUI thread.

Emits individual VerificationResult per reference for incremental display.
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

        Runs the async engine using asyncio.run() inside the thread.
        """
        import asyncio

        try:
            results = asyncio.run(self._run_verification())
            if not self._is_cancelled:
                self.result_ready.emit(results)
        except Exception as exc:
            logger.error("verify_worker_error", error=str(exc))
            self.error.emit(str(exc))

    async def _run_verification(self) -> list[VerificationResult]:
        """Run the verification pipeline asynchronously.

        Returns:
            List of verification results.
        """
        total = len(self._references)
        completed = 0

        def on_progress(idx: int, result: VerificationResult) -> None:
            nonlocal completed
            completed += 1
            # Emit both counts and the individual result for incremental display
            self.progress.emit(completed, total, result)

            # Check for rate-limit errors and emit signal
            for match in result.matches:
                if match.error and "rate" in match.error.lower():
                    self.rate_limited.emit(match.adapter_name)

        results = await self._engine.verify_batch(
            self._references,
            progress_callback=on_progress,
        )

        return results

    def cancel(self) -> None:
        """Request cancellation of the verification."""
        self._is_cancelled = True
        logger.info("verify_worker_cancelled")
