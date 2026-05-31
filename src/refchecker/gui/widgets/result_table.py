"""Result table widget for RefChecker.

Displays verification results in a color-coded QTableWidget:
- Green: Verified (score >= 0.85)
- Yellow: Suspicious (score 0.60–0.84)
- Red: Likely Fabricated (score < 0.60)
- Blue: Unable to Verify

Provides right-click context menu for copy, open URL, and export.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from refchecker.core.models import VerificationResult, VerificationStatus

# Column definitions
_COLUMNS = ["#", "Status", "Score", "Title", "Authors", "Year", "Best Source"]

# Status colors
_STATUS_BG = {
    VerificationStatus.VERIFIED: QColor(198, 239, 206),
    VerificationStatus.SUSPICIOUS: QColor(255, 235, 156),
    VerificationStatus.LIKELY_FABRICATED: QColor(255, 199, 206),
    VerificationStatus.UNABLE_TO_VERIFY: QColor(217, 226, 243),
    VerificationStatus.PENDING: QColor(245, 245, 245),
}

_STATUS_FG = {
    VerificationStatus.VERIFIED: QColor(0, 97, 0),
    VerificationStatus.SUSPICIOUS: QColor(156, 101, 0),
    VerificationStatus.LIKELY_FABRICATED: QColor(156, 0, 6),
    VerificationStatus.UNABLE_TO_VERIFY: QColor(31, 78, 121),
    VerificationStatus.PENDING: QColor(128, 128, 128),
}


class ResultTableWidget(QTableWidget):
    """Table widget displaying verification results with color coding.

    Signals:
        export_requested: Emitted when user requests export from context menu.
    """

    export_requested = Signal()

    def __init__(self, parent: object = None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self._results: list[VerificationResult] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configure table appearance."""
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore[name-defined]
        self.customContextMenuRequested.connect(self._show_context_menu)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 60)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 60)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 50)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 100)

    def set_results(self, results: list[VerificationResult]) -> None:
        """Populate the table with verification results.

        Args:
            results: List of verification results to display.
        """
        self._results = results
        self.setRowCount(len(results))

        for row, result in enumerate(results):
            self._populate_row(row, result)

    def get_results(self) -> list[VerificationResult]:
        """Get the current verification results.

        Returns:
            List of verification results.
        """
        return self._results

    def _populate_row(self, row: int, result: VerificationResult) -> None:
        """Fill a single table row with result data.

        Args:
            row: Row index.
            result: Verification result for this row.
        """
        ref = result.reference
        bg = _STATUS_BG.get(result.status, _STATUS_BG[VerificationStatus.PENDING])
        fg = _STATUS_FG.get(result.status, _STATUS_FG[VerificationStatus.PENDING])

        items = [
            self._make_item(str(row + 1), bg, fg),
            self._make_item(result.status.symbol, bg, fg),
            self._make_item(f"{result.best_score:.2f}", bg, fg),
            self._make_item(ref.title, bg, fg),
            self._make_item(ref.display_authors, bg, fg),
            self._make_item(str(ref.year or ""), bg, fg),
            self._make_item(self._find_best_source(result), bg, fg),
        ]

        for col, item in enumerate(items):
            self.setItem(row, col, item)

    def _make_item(
        self,
        text: str,
        bg: QColor,
        fg: QColor,
    ) -> QTableWidgetItem:
        """Create a styled table item.

        Args:
            text: Cell text.
            bg: Background color.
            fg: Foreground color.

        Returns:
            Styled QTableWidgetItem.
        """
        item = QTableWidgetItem(text)
        item.setBackground(bg)
        item.setForeground(fg)
        item.setToolTip(text)
        return item

    @staticmethod
    def _find_best_source(result: VerificationResult) -> str:
        """Find the adapter name with the best score.

        Args:
            result: Verification result.

        Returns:
            Adapter name or empty string.
        """
        for match in result.matches:
            if match.found and match.composite_score == result.best_score:
                return match.adapter_name
        return ""

    def _show_context_menu(self, pos: object) -> None:
        """Show the right-click context menu.

        Args:
            pos: Click position.
        """
        menu = QMenu(self)

        export_action = QAction("Export Results...", self)
        export_action.triggered.connect(self.export_requested.emit)
        menu.addAction(export_action)

        # Open URL for selected row
        row = self.currentRow()
        if 0 <= row < len(self._results):
            result = self._results[row]
            for match in result.matches:
                if match.source_url:
                    open_action = QAction(f"Open in Browser ({match.adapter_name})", self)
                    url = match.source_url

                    def _open_url(u: str = url) -> None:
                        from PySide6.QtGui import QDesktopServices
                        from PySide6.QtCore import QUrl
                        QDesktopServices.openUrl(QUrl(u))

                    open_action.triggered.connect(_open_url)
                    menu.addAction(open_action)
                    break

        menu.exec(self.viewport().mapToGlobal(pos))  # type: ignore[arg-type]
