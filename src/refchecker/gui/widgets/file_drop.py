"""Drag-and-drop file upload widget for RefChecker.

Accepts .bib and .txt files via drag-and-drop or click-to-browse.
Emits a signal with the file path when a valid file is dropped.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QVBoxLayout,
)

from refchecker.gui.i18n import t

_ACCEPTED_EXTENSIONS = {".bib", ".txt"}
_DROP_STYLE = """
    FileDropWidget {
        border: 2px dashed #aaa;
        border-radius: 8px;
        background-color: #fafafa;
        min-height: 120px;
    }
    FileDropWidget[hover=True] {
        border: 2px dashed #4a90d9;
        background-color: #e8f0fe;
    }
"""
_LABEL_STYLE = "color: #666; font-size: 14px;"
_SUB_LABEL_STYLE = "color: #999; font-size: 12px;"


class FileDropWidget(QFrame):
    """A widget that accepts file drops and click-to-browse.

    Signals:
        file_selected(Path): Emitted when a valid file is selected.
    """

    file_selected = Signal(Path)

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("hover", False)
        self.setStyleSheet(_DROP_STYLE)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        inner = QVBoxLayout()
        inner.setSpacing(4)

        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 32px; border: none;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(icon_label)

        main_label = QLabel("Drop .bib or .txt file here")
        main_label.setStyleSheet(_LABEL_STYLE)
        main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(main_label)

        sub_label = QLabel("or click to browse")
        sub_label.setStyleSheet(_SUB_LABEL_STYLE)
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(sub_label)

        layout.addLayout(inner)

    def update_language(self) -> None:
        """Update labels to current language."""
        # Update labels by finding them in the layout
        inner = self.layout().itemAt(0).layout()
        if inner and inner.count() >= 3:
            inner.itemAt(1).widget().setText(t("drop.main"))
            inner.itemAt(2).widget().setText(t("drop.sub"))

    # --- Drag-and-drop ---

    def dragEnterEvent(self, event: object) -> None:  # type: ignore[override]
        """Accept drag events with valid file extensions."""
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDragEnterEvent

        ev = event
        if not isinstance(ev, QDragEnterEvent):
            return

        mime: QMimeData = ev.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if path.suffix.lower() in _ACCEPTED_EXTENSIONS:
                    ev.acceptProposedAction()
                    self.setProperty("hover", True)
                    self.setStyleSheet(_DROP_STYLE)

    def dragLeaveEvent(self, event: object) -> None:  # type: ignore[override]
        """Reset hover state when drag leaves."""
        self.setProperty("hover", False)
        self.setStyleSheet(_DROP_STYLE)

    def dropEvent(self, event: object) -> None:  # type: ignore[override]
        """Handle file drop."""
        from PySide6.QtCore import QMimeData
        from PySide6.QtGui import QDropEvent

        ev = event
        if not isinstance(ev, QDropEvent):
            return

        self.setProperty("hover", False)
        self.setStyleSheet(_DROP_STYLE)

        mime: QMimeData = ev.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if path.suffix.lower() in _ACCEPTED_EXTENSIONS:
                    self.file_selected.emit(path)

        ev.acceptProposedAction()

    def mousePressEvent(self, event: object) -> None:  # type: ignore[override]
        """Open file dialog on click."""
        from PySide6.QtGui import QMouseEvent

        if not isinstance(event, QMouseEvent):
            return

        file_filter = t("drop.filter")
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("drop.dialog_title"),
            "",
            file_filter,
        )
        if path:
            self.file_selected.emit(Path(path))
