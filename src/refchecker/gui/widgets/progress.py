"""Progress indicator widget for verification pipeline.

Shows a progress bar with status text: "Verifying 12/45 references..."
"""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QWidget,
)


class ProgressWidget(QWidget):
    """Progress indicator for the verification pipeline.

    Shows a progress bar with current/total label.
    """

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the widget layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(20)

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #666; font-size: 12px;")

        layout.addWidget(self._progress_bar, stretch=3)
        layout.addWidget(self._status_label, stretch=1)

    def set_progress(self, current: int, total: int) -> None:
        """Update progress indicator.

        Args:
            current: Number of completed verifications.
            total: Total number of references.
        """
        if total > 0:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)
            self._status_label.setText(f"Verifying {current}/{total}…")
        else:
            self._progress_bar.setValue(0)
            self._status_label.setText("Ready")

    def set_complete(self, total: int) -> None:
        """Mark verification as complete.

        Args:
            total: Total number of references processed.
        """
        self._progress_bar.setValue(100)
        self._status_label.setText(f"Done — {total} references verified")

    def reset(self) -> None:
        """Reset to initial state."""
        self._progress_bar.setValue(0)
        self._status_label.setText("Ready")
