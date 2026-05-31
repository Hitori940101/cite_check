"""Toast notification widget for non-blocking user feedback.

Shows a temporary notification that auto-dismisses after a few seconds.
Used for rate-limit warnings and other transient messages.
"""

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

# Toast duration in milliseconds
_TOAST_DURATION_MS = 5000

# Styles by severity
_TOAST_STYLES = {
    "info": """
        ToastWidget {
            background-color: #dbeafe;
            border: 1px solid #93c5fd;
            border-radius: 6px;
            padding: 10px 16px;
        }
        QLabel { color: #1e40af; font-size: 13px; }
        QPushButton { color: #1e40af; border: none; font-size: 14px; }
        QPushButton:hover { color: #1e3a8a; }
    """,
    "warning": """
        ToastWidget {
            background-color: #fef3c7;
            border: 1px solid #fcd34d;
            border-radius: 6px;
            padding: 10px 16px;
        }
        QLabel { color: #92400e; font-size: 13px; }
        QPushButton { color: #92400e; border: none; font-size: 14px; }
        QPushButton:hover { color: #78350f; }
    """,
    "error": """
        ToastWidget {
            background-color: #fee2e2;
            border: 1px solid #fca5a5;
            border-radius: 6px;
            padding: 10px 16px;
        }
        QLabel { color: #991b1b; font-size: 13px; }
        QPushButton { color: #991b1b; border: none; font-size: 14px; }
        QPushButton:hover { color: #7f1d1d; }
    """,
}


class ToastWidget(QWidget):
    """A temporary notification toast that auto-dismisses.

    Signals:
        action_clicked: Emitted when the action button is clicked.
        dismissed: Emitted when the toast is dismissed.
    """

    action_clicked = Signal()
    dismissed = Signal()

    def __init__(
        self,
        message: str,
        *,
        severity: str = "info",
        action_text: str | None = None,
        duration_ms: int = _TOAST_DURATION_MS,
        parent: object = None,
    ) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

        self._setup_ui(message, severity, action_text)
        self._timer.start(duration_ms)

    def _setup_ui(
        self,
        message: str,
        severity: str,
        action_text: str | None,
    ) -> None:
        """Build the toast layout.

        Args:
            message: Notification text.
            severity: One of "info", "warning", "error".
            action_text: Optional action button text.
        """
        self.setObjectName("ToastWidget")
        style = _TOAST_STYLES.get(severity, _TOAST_STYLES["info"])
        self.setStyleSheet(style)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label, stretch=1)

        if action_text:
            action_btn = QPushButton(action_text)
            action_btn.setFlat(True)
            action_btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(action_btn)

        close_btn = QPushButton("✕")
        close_btn.setFlat(True)
        close_btn.setFixedWidth(24)
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn)

        # Opacity effect for fade-out
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)

    def dismiss(self) -> None:
        """Dismiss the toast and remove from parent."""
        self._timer.stop()
        self.dismissed.emit()
        self.hide()
        self.deleteLater()


class ToastManager:
    """Manages toast notifications in a parent widget.

    Stacks toasts at the bottom of the parent widget.
    """

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._active_toasts: list[ToastWidget] = []

    def show(
        self,
        message: str,
        *,
        severity: str = "info",
        action_text: str | None = None,
        on_action: object = None,
    ) -> ToastWidget:
        """Show a toast notification.

        Args:
            message: Notification text.
            severity: Severity level (info/warning/error).
            action_text: Optional action button text.
            on_action: Optional callback for action button.

        Returns:
            The created ToastWidget.
        """
        toast = ToastWidget(
            message,
            severity=severity,
            action_text=action_text,
            parent=self._parent,
        )
        toast.dismissed.connect(lambda: self._remove_toast(toast))

        if on_action and action_text:
            toast.action_clicked.connect(lambda: on_action())  # type: ignore[arg-type]

        self._active_toasts.append(toast)
        toast.show()
        self._reposition_toasts()

        return toast

    def _remove_toast(self, toast: ToastWidget) -> None:
        """Remove a dismissed toast from tracking.

        Args:
            toast: The toast to remove.
        """
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
        self._reposition_toasts()

    def _reposition_toasts(self) -> None:
        """Reposition active toasts at the bottom of the parent."""
        if not self._parent or not self._active_toasts:
            return

        parent_rect = self._parent.rect()
        y_offset = parent_rect.height() - 10

        for toast in reversed(self._active_toasts):
            height = toast.sizeHint().height()
            y_offset -= height + 4
            toast.setGeometry(
                parent_rect.x() + 20,
                parent_rect.y() + y_offset,
                parent_rect.width() - 40,
                height + 20,
            )
