"""Settings dialog for RefChecker.

Per-adapter API key fields with:
- Optional API key input (masked password fields)
- Key status indicators (stored / not stored)
- Adapter enable/disable checkboxes
- Proxy configuration
- Inline "How to apply" hints for sources requiring keys
- Chinese/English i18n support
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from refchecker.core.logging import get_logger
from refchecker.gui.i18n import t

logger = get_logger(__name__)

# Adapter metadata: (display_name, key_name, hint_i18n_key, requires_key)
_ADAPTER_INFO = [
    ("Crossref", "crossref", "adapter.crossref.desc", False),
    ("Semantic Scholar", "s2", "adapter.s2.desc", False),
    ("OpenAlex", "openalex", "adapter.openalex.desc", True),
    ("AMiner", "aminer", "adapter.aminer.desc", False),
    ("Baidu Academic", "baidu", "adapter.baidu.desc", False),
    ("arXiv", "arxiv", "adapter.arxiv.desc", False),
    ("Scholar", "scholar", "adapter.scholar.desc", False),
    ("CNKI", "cnki", "adapter.cnki.desc", False),
]


class SettingsDialog(QDialog):
    """Application settings dialog.

    Features:
    - Tab 1: Adapter API keys and enable/disable
    - Tab 2: Proxy and network settings
    """

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._key_fields: dict[str, QLineEdit] = {}
        self._adapter_checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load_current_state()

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)

        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(520)

        self._tabs = QTabWidget()
        self._adapters_tab = self._build_adapters_tab()
        self._network_tab = self._build_network_tab()
        self._tabs.addTab(self._adapters_tab, t("settings.tab.adapters"))
        self._tabs.addTab(self._network_tab, t("settings.tab.proxy"))

        layout.addWidget(self._tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._save_btn = QPushButton(t("settings.save"))
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn = QPushButton(t("settings.cancel"))
        self._cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _build_adapters_tab(self) -> QWidget:
        """Build the adapter settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        for display_name, adapter_name, hint_key, requires_key in _ADAPTER_INFO:
            group = QGroupBox(display_name)
            group_layout = QVBoxLayout(group)

            # Enable checkbox
            check = QCheckBox(t("settings.enabled"))
            check.setChecked(True)
            self._adapter_checks[adapter_name] = check
            group_layout.addWidget(check)

            # API key field (only for adapters that support keys)
            if adapter_name in ("s2", "openalex", "aminer"):
                key_row = QHBoxLayout()
                key_label = QLabel(t("settings.key_label"))
                key_label.setMinimumWidth(60)

                key_field = QLineEdit()
                key_field.setPlaceholderText(t("settings.key_placeholder"))
                key_field.setEchoMode(QLineEdit.EchoMode.Password)
                self._key_fields[adapter_name] = key_field

                # Toggle visibility button
                toggle_btn = QPushButton("👁")
                toggle_btn.setFixedWidth(30)
                toggle_btn.setCheckable(True)
                toggle_btn.toggled.connect(
                    lambda checked, f=key_field: f.setEchoMode(
                        QLineEdit.EchoMode.Normal if checked
                        else QLineEdit.EchoMode.Password
                    )
                )

                # Store button
                store_btn = QPushButton(t("settings.store_btn"))
                store_btn.clicked.connect(
                    lambda checked, n=adapter_name, f=key_field: self._store_key(n, f)
                )

                # Status indicator
                status_label = QLabel("—")
                status_label.setObjectName(f"status_{adapter_name}")
                self._check_key_status(adapter_name, status_label)

                key_row.addWidget(key_label)
                key_row.addWidget(key_field, stretch=1)
                key_row.addWidget(toggle_btn)
                key_row.addWidget(store_btn)
                key_row.addWidget(status_label)
                group_layout.addLayout(key_row)

            # Hint label
            hint_text = t(hint_key)
            hint_label = QLabel(hint_text)
            hint_label.setStyleSheet("color: #888; font-size: 11px;")
            hint_label.setWordWrap(True)
            group_layout.addWidget(hint_label)

            layout.addWidget(group)

        # S2 lifecycle warning
        warning = QLabel(t("settings.s2_warning"))
        warning.setStyleSheet("color: #b45309; font-size: 11px; padding: 8px; background: #fef3c7; border-radius: 4px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        layout.addStretch()
        return widget

    def _build_network_tab(self) -> QWidget:
        """Build the network/proxy settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        proxy_group = QGroupBox(t("settings.proxy_group"))
        proxy_layout = QVBoxLayout(proxy_group)

        self._http_proxy = QLineEdit()
        self._http_proxy.setPlaceholderText(t("settings.http_proxy_ph"))
        proxy_layout.addWidget(QLabel(t("settings.proxy_http")))
        proxy_layout.addWidget(self._http_proxy)

        self._https_proxy = QLineEdit()
        self._https_proxy.setPlaceholderText(t("settings.https_proxy_ph"))
        proxy_layout.addWidget(QLabel(t("settings.proxy_https")))
        proxy_layout.addWidget(self._https_proxy)

        layout.addWidget(proxy_group)

        request_group = QGroupBox(t("settings.request_group"))
        request_layout = QVBoxLayout(request_group)

        self._timeout_spin = self._make_spinbox(5, 120, 30, t("settings.timeout_tip"))
        request_layout.addLayout(self._labeled_row(t("settings.timeout_lbl"), self._timeout_spin))

        self._concurrent_spin = self._make_spinbox(1, 10, 3, t("settings.concurrent_tip"))
        request_layout.addLayout(self._labeled_row(t("settings.concurrent_lbl"), self._concurrent_spin))

        layout.addWidget(request_group)
        layout.addStretch()
        return widget

    def _make_spinbox(self, min_val: int, max_val: int, default: int, tooltip: str) -> object:
        """Create a QSpinBox with common settings."""
        from PySide6.QtWidgets import QSpinBox

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setToolTip(tooltip)
        return spin

    def _labeled_row(self, text: str, widget: object) -> QHBoxLayout:
        """Create a labeled row layout."""
        row = QHBoxLayout()
        label = QLabel(text)
        label.setMinimumWidth(90)
        row.addWidget(label)
        row.addWidget(widget, stretch=1)
        return row

    def _load_current_state(self) -> None:
        """Load current configuration into the dialog fields."""
        try:
            from refchecker.config import load_config
            config = load_config()

            # Adapter enabled states
            for name, check in self._adapter_checks.items():
                check.setChecked(config.is_adapter_enabled(name))

            # Network settings
            proxy = config.get_proxy_url()
            if proxy:
                self._https_proxy.setText(proxy)
            self._timeout_spin.setValue(int(config.adapters.request_timeout))
            self._concurrent_spin.setValue(config.adapters.max_concurrent)

        except Exception as exc:
            logger.warning("settings_load_error", error=str(exc))

    def _check_key_status(self, adapter_name: str, label: QLabel) -> None:
        """Check and display whether a key is stored for an adapter."""
        try:
            from refchecker.core.key_store import load_key
            key_name = f"{adapter_name}_api_key"
            value = load_key(key_name)
            if value is not None:
                label.setText(t("settings.key_stored"))
                label.setStyleSheet("color: #16a34a; font-weight: bold;")
            else:
                label.setText(t("settings.key_none"))
                label.setStyleSheet("color: #999;")
        except ImportError:
            label.setText(t("settings.key_no_keyring"))
            label.setStyleSheet("color: #d97706;")

    def _store_key(self, adapter_name: str, field: QLineEdit) -> None:
        """Store an API key from the field into encrypted storage."""
        key_value = field.text().strip()
        if not key_value:
            QMessageBox.warning(self, t("settings.empty_key_title"), t("settings.empty_key_msg"))
            return

        try:
            from refchecker.core.key_store import store_key
            key_name = f"{adapter_name}_api_key"
            store_key(key_name, key_value)
            field.clear()

            # Update status label
            status_label = self.findChild(QLabel, f"status_{adapter_name}")
            if status_label:
                status_label.setText(t("settings.key_stored"))
                status_label.setStyleSheet("color: #16a34a; font-weight: bold;")

            QMessageBox.information(
                self, t("settings.key_stored"), t("settings.key_stored_msg", adapter=adapter_name),
            )
        except ImportError:
            QMessageBox.critical(self, t("settings.error"), t("settings.keyring_required"))
        except Exception as exc:
            QMessageBox.critical(self, t("settings.error"), t("settings.store_failed", exc=str(exc)))

    def _on_save(self) -> None:
        """Save settings and close dialog."""
        try:
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, t("settings.error"), t("settings.save_failed", exc=str(exc)))
