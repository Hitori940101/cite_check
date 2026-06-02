# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for RefChecker desktop application."""

import sys
from pathlib import Path

block_cipher = None

# Collect all refchecker subpackages
hidden_imports = [
    "refchecker",
    "refchecker.core",
    "refchecker.core.models",
    "refchecker.core.parser",
    "refchecker.core.scorer",
    "refchecker.core.exporter",
    "refchecker.core.reporter",
    "refchecker.core.cache",
    "refchecker.core.key_store",
    "refchecker.core.logging",
    "refchecker.core.exceptions",
    "refchecker.config",
    "refchecker.engine",
    "refchecker.adapters",
    "refchecker.adapters.base",
    "refchecker.adapters.crossref_adapter",
    "refchecker.adapters.s2_adapter",
    "refchecker.adapters.openalex_adapter",
    "refchecker.adapters.aminer_adapter",
    "refchecker.adapters.baidu_adapter",
    "refchecker.adapters.cnki_adapter",
    "refchecker.adapters.arxiv_adapter",
    "refchecker.adapters.scholar_adapter",
    "refchecker.gui",
    "refchecker.gui.app",
    "refchecker.gui.main_window",
    "refchecker.gui.i18n",
    "refchecker.gui.widgets",
    "refchecker.gui.widgets.result_table",
    "refchecker.gui.widgets.file_drop",
    "refchecker.gui.widgets.progress",
    "refchecker.gui.workers",
    "refchecker.gui.workers.verify_worker",
    "refchecker.gui.dialogs",
    "refchecker.gui.dialogs.settings",
    "refchecker.gui.dialogs.export",
    "refchecker.gui.dialogs.toast",
    "refchecker.cli",
    "refchecker.cli.main",
    # Third-party hidden imports
    "pydantic",
    "pydantic_settings",
    "bibtexparser",
    "rapidfuzz",
    "httpx",
    "structlog",
    "keyring",
    "click",
    "openpyxl",
    "PySide6",
    "PySide6.QtWidgets",
    "PySide6.QtCore",
    "PySide6.QtGui",
]

a = Analysis(
    ["src/refchecker/gui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas"],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RefChecker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI mode — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path here when available
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="RefChecker.app",
        icon=None,
        bundle_identifier="com.refchecker.app",
        version="0.1.0",
    )
