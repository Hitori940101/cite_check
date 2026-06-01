"""Result table widget for RefChecker.

Displays verification results in a color-coded QTableWidget:
- Green: Verified (score >= 0.85)
- Yellow: Suspicious (score 0.60–0.84)
- Red: Likely Fabricated (score < 0.60)
- Blue: Unable to Verify
- Gray: Pending (not yet verified)

Supports:
- Checkbox column for selecting which references to verify
- Pre-verification display (PENDING status) immediately after file import
- Incremental row updates as individual verifications complete
- Right-click context menu for copy, open URL, and export.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from refchecker.core.models import (
    ReferenceItem,
    VerificationResult,
    VerificationStatus,
)
from refchecker.gui.i18n import t

# Column definitions (checkbox col 0 + original 7 columns)
_COLUMNS = ["", "#", "Status", "Score", "Title", "Authors", "Year", "Best Source"]

# i18n keys for column headers
_COL_I18N_KEYS = ["", "col.num", "col.status", "col.score", "col.title", "col.authors", "col.year", "col.source"]

# Column index constants for clarity
COL_CHECK = 0
COL_NUM = 1
COL_STATUS = 2
COL_SCORE = 3
COL_TITLE = 4
COL_AUTHORS = 5
COL_YEAR = 6
COL_SOURCE = 7

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

    Supports three states:
    1. Empty — no data loaded
    2. Pre-verification — references shown with PENDING status and checkboxes
    3. Verified — rows updated incrementally with verification results

    Signals:
        export_requested: Emitted when user requests export from context menu.
    """

    export_requested = Signal()

    def __init__(self, parent: object = None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self._references: list[ReferenceItem] = []
        self._results: list[VerificationResult] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configure table appearance."""
        self._update_header_labels()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        header = self.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_CHECK, 30)
        header.setSectionResizeMode(COL_NUM, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_NUM, 40)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_STATUS, 60)
        header.setSectionResizeMode(COL_SCORE, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_SCORE, 60)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_AUTHORS, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_YEAR, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_YEAR, 50)
        header.setSectionResizeMode(COL_SOURCE, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_SOURCE, 100)

    def _update_header_labels(self) -> None:
        """Update column headers to current language."""
        labels = [t(k) if k else "" for k in _COL_I18N_KEYS]
        self.setHorizontalHeaderLabels(labels)

    def update_language(self) -> None:
        """Refresh all UI text for the current language."""
        self._update_header_labels()
        # Re-populate all rows to refresh status symbols and score formatting
        for row, result in enumerate(self._results):
            self._populate_row(row, result)

    # ------------------------------------------------------------------
    # Pre-verification display
    # ------------------------------------------------------------------

    def set_references(self, references: list[ReferenceItem]) -> None:
        """Populate table with unverified references (PENDING status).

        Called immediately after file parsing, before verification starts.
        All checkboxes are checked by default.

        Args:
            references: List of parsed reference items.
        """
        self._references = list(references)
        self._results = []
        self.setRowCount(len(references))

        for row, ref in enumerate(references):
            pending = VerificationResult(reference=ref)
            self._results.append(pending)
            self._populate_row(row, pending)

    def get_references(self) -> list[ReferenceItem]:
        """Get the current reference items.

        Returns:
            List of ReferenceItem.
        """
        return self._references

    # ------------------------------------------------------------------
    # Full results (backward compatible)
    # ------------------------------------------------------------------

    def set_results(self, results: list[VerificationResult]) -> None:
        """Populate the table with verification results.

        Args:
            results: List of verification results to display.
        """
        self._results = list(results)
        self._references = [r.reference for r in results]
        self.setRowCount(len(results))

        for row, result in enumerate(results):
            self._populate_row(row, result)

    def get_results(self) -> list[VerificationResult]:
        """Get the current verification results.

        Returns:
            List of verification results.
        """
        return self._results

    # ------------------------------------------------------------------
    # Incremental row update
    # ------------------------------------------------------------------

    def update_row(self, row: int, result: VerificationResult) -> None:
        """Update a single row with verification result.

        Called incrementally as each reference finishes verification.
        Preserves the checkbox state from the existing row.

        Args:
            row: Table row index (0-based).
            result: Verification result for this row.
        """
        if row < 0 or row >= self.rowCount():
            return

        # Preserve checkbox state
        check_item = self.item(row, COL_CHECK)
        check_state = check_item.checkState() if check_item else Qt.CheckState.Checked

        # Update data
        if row < len(self._results):
            self._results[row] = result
        self._populate_row(row, result)

        # Restore checkbox state
        new_check = self.item(row, COL_CHECK)
        if new_check:
            new_check.setCheckState(check_state)

    # ------------------------------------------------------------------
    # Checkbox selection
    # ------------------------------------------------------------------

    def get_selected_indices(self) -> list[int]:
        """Return indices of rows whose checkboxes are checked.

        Returns:
            List of row indices (0-based) selected for verification.
        """
        selected: list[int] = []
        for row in range(self.rowCount()):
            item = self.item(row, COL_CHECK)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(row)
        return selected

    def select_all(self) -> None:
        """Check all row checkboxes."""
        for row in range(self.rowCount()):
            item = self.item(row, COL_CHECK)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def deselect_all(self) -> None:
        """Uncheck all row checkboxes."""
        for row in range(self.rowCount()):
            item = self.item(row, COL_CHECK)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_row(self, row: int, result: VerificationResult) -> None:
        """Fill a single table row with result data.

        Args:
            row: Row index.
            result: Verification result for this row.
        """
        ref = result.reference
        bg = _STATUS_BG.get(result.status, _STATUS_BG[VerificationStatus.PENDING])
        fg = _STATUS_FG.get(result.status, _STATUS_FG[VerificationStatus.PENDING])

        # Col 0: Checkbox
        check_item = QTableWidgetItem()
        check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        check_item.setCheckState(Qt.CheckState.Checked)
        check_item.setBackground(bg)
        self.setItem(row, COL_CHECK, check_item)

        # Col 1-7: Data columns
        data_items = [
            self._make_item(str(row + 1), bg, fg),                          # #
            self._make_item(result.status.symbol, bg, fg),                   # Status
            self._make_item(self._format_score(result), bg, fg),             # Score
            self._make_item(ref.title, bg, fg),                              # Title
            self._make_item(ref.display_authors, bg, fg),                    # Authors
            self._make_item(str(ref.year or ""), bg, fg),                    # Year
            self._make_item(self._find_best_source(result), bg, fg),         # Best Source
        ]

        for col_offset, item in enumerate(data_items):
            self.setItem(row, COL_NUM + col_offset, item)

    @staticmethod
    def _format_score(result: VerificationResult) -> str:
        """Format the score for display.

        Args:
            result: Verification result.

        Returns:
            Formatted score string.
        """
        if result.status == VerificationStatus.PENDING:
            return "--"
        return f"{result.best_score:.2f}"

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

        export_action = QAction(t("menu.export"), self)
        export_action.triggered.connect(self.export_requested.emit)
        menu.addAction(export_action)

        # Open URL for selected row
        row = self.currentRow()
        if 0 <= row < len(self._results):
            result = self._results[row]
            for match in result.matches:
                if match.source_url:
                    open_action = QAction(t("menu.open_browser", adapter=match.adapter_name), self)
                    url = match.source_url

                    def _open_url(u: str = url) -> None:
                        from PySide6.QtGui import QDesktopServices
                        from PySide6.QtCore import QUrl
                        QDesktopServices.openUrl(QUrl(u))

                    open_action.triggered.connect(_open_url)
                    menu.addAction(open_action)
                    break

        menu.exec(self.viewport().mapToGlobal(pos))  # type: ignore[arg-type]
