"""Lightweight internationalization (i18n) module for RefChecker GUI.

Provides a simple dictionary-based translation system for Chinese/English
switching. No Qt linguist or .ts files needed.

Usage:
    from refchecker.gui.i18n import t
    label.setText(t("app.title"))  # → "RefChecker — 引用验证" or "RefChecker — Citation Verification"
"""

from __future__ import annotations

from typing import Literal

# Supported languages
Language = Literal["zh", "en"]

# Current language (mutable module state)
_current_lang: Language = "zh"

# All UI strings keyed by message id
_TRANSLATIONS: dict[str, dict[Language, str]] = {
    # --- App ---
    "app.title": {"zh": "RefChecker — 引用验证", "en": "RefChecker — Citation Verification"},
    "app.name": {"zh": "引用验证工具", "en": "Citation Verification Tool"},

    # --- Toolbar buttons ---
    "btn.verify": {"zh": "▶ 开始验证", "en": "▶ Verify"},
    "btn.cancel": {"zh": "✕ 取消", "en": "✕ Cancel"},
    "btn.export": {"zh": "📥 导出", "en": "📥 Export"},
    "btn.settings": {"zh": "⚙ 设置", "en": "⚙ Settings"},
    "btn.lang": {"zh": "🌐 EN", "en": "🌐 中文"},

    # --- Adapter label ---
    "label.adapters": {"zh": "数据源：", "en": "Adapters:"},

    # --- Status bar messages ---
    "status.ready": {"zh": "就绪 — 拖入 .bib 或 .txt 文件开始", "en": "Ready — drop a .bib or .txt file to start"},
    "status.loaded": {"zh": "已加载 {count} 条引用（{file}）", "en": "Loaded {count} references from {file}"},
    "status.verifying": {"zh": "验证中…", "en": "Verifying…"},
    "status.cancelled": {"zh": "验证已取消", "en": "Verification cancelled"},
    "status.done": {"zh": "完成 — {verified}/{total} 条已验证", "en": "Done — {verified}/{total} verified"},
    "status.error": {"zh": "错误：{msg}", "en": "Error: {msg}"},

    # --- Table columns ---
    "col.num": {"zh": "#", "en": "#"},
    "col.status": {"zh": "状态", "en": "Status"},
    "col.score": {"zh": "分数", "en": "Score"},
    "col.title": {"zh": "标题", "en": "Title"},
    "col.authors": {"zh": "作者", "en": "Authors"},
    "col.year": {"zh": "年份", "en": "Year"},
    "col.source": {"zh": "最佳来源", "en": "Best Source"},

    # --- File drop widget ---
    "drop.icon": {"zh": "📄", "en": "📄"},
    "drop.main": {"zh": "拖入 .bib 或 .txt 文件", "en": "Drop .bib or .txt file here"},
    "drop.sub": {"zh": "或点击选择文件", "en": "or click to browse"},
    "drop.filter": {"zh": "引用文件 (*.bib *.txt);;BibTeX (*.bib);;文本 (*.txt);;所有文件 (*)",
                    "en": "Reference Files (*.bib *.txt);;BibTeX (*.bib);;Text (*.txt);;All Files (*)"},
    "drop.dialog_title": {"zh": "打开引用文件", "en": "Open Reference File"},
    "drop.paste": {"zh": "📋 从剪贴板粘贴", "en": "📋 Paste from Clipboard"},

    # --- Paste status ---
    "status.pasted": {"zh": "已粘贴 {count} 条引用（共 {total} 条）", "en": "Pasted {count} references ({total} total)"},
    "error.paste_title": {"zh": "粘贴解析错误", "en": "Paste Parse Error"},
    "error.paste_empty": {"zh": "剪贴板为空或无法识别引用格式。", "en": "Clipboard is empty or citation format not recognized."},

    # --- Error dialogs ---
    "error.parse_title": {"zh": "解析错误", "en": "Parse Error"},
    "error.parse_msg": {"zh": "文件解析失败：\n{exc}", "en": "Failed to parse file:\n{exc}"},
    "error.verify_title": {"zh": "验证错误", "en": "Verification Error"},
    "error.no_selection": {"zh": "未选择文献", "en": "No Selection"},
    "error.no_selection_msg": {"zh": "请至少勾选一条文献进行验证。", "en": "Please select at least one reference to verify."},
    "error.no_adapters": {"zh": "无数据源", "en": "No Adapters"},
    "error.no_adapters_msg": {"zh": "请至少启用一个数据源。", "en": "Please enable at least one adapter."},

    # --- Export dialog ---
    "export.no_results": {"zh": "无结果", "en": "No Results"},
    "export.no_results_msg": {"zh": "请先运行验证。", "en": "Run verification first."},

    # --- Toast ---
    "toast.rate_limit": {"zh": "⚠️ {adapter} 达到速率限制。在设置中添加 API Key 可提升限额。",
                        "en": "⚠️ {adapter} rate limit reached. Add an API key in Settings for higher limits."},
    "toast.open_settings": {"zh": "打开设置", "en": "Open Settings"},

    # --- Settings dialog ---
    "settings.title": {"zh": "设置", "en": "Settings"},
    "settings.tab.adapters": {"zh": "数据源", "en": "Adapters"},
    "settings.tab.proxy": {"zh": "代理", "en": "Proxy"},
    "settings.key_label": {"zh": "API Key：", "en": "API Key:"},
    "settings.proxy_http": {"zh": "HTTP 代理：", "en": "HTTP Proxy:"},
    "settings.proxy_https": {"zh": "HTTPS 代理：", "en": "HTTPS Proxy:"},
    "settings.lang_label": {"zh": "语言：", "en": "Language:"},
    "settings.lang_zh": {"zh": "中文", "en": "Chinese"},
    "settings.lang_en": {"zh": "English", "en": "English"},
    "settings.save": {"zh": "保存", "en": "Save"},
    "settings.cancel": {"zh": "取消", "en": "Cancel"},
    "settings.enabled": {"zh": "启用", "en": "Enabled"},
    "settings.key_placeholder": {"zh": "输入 API Key（可选）", "en": "Enter API key (optional)"},
    "settings.store_btn": {"zh": "安全存储", "en": "Store Securely"},
    "settings.key_stored": {"zh": "🔑 已存储", "en": "🔑 Stored"},
    "settings.key_none": {"zh": "— 无", "en": "— None"},
    "settings.key_no_keyring": {"zh": "⚠ 无 keyring", "en": "⚠ No keyring"},
    "settings.empty_key_title": {"zh": "Key 为空", "en": "Empty Key"},
    "settings.empty_key_msg": {"zh": "请先输入 API Key。", "en": "Please enter an API key before saving."},
    "settings.key_stored_msg": {"zh": "{adapter} 的 API Key 已安全存储。", "en": "API key for {adapter} stored securely."},
    "settings.error": {"zh": "错误", "en": "Error"},
    "settings.keyring_required": {"zh": "需要 keyring 包才能加密存储。", "en": "keyring package is required for encrypted storage."},
    "settings.store_failed": {"zh": "存储失败：{exc}", "en": "Failed to store key: {exc}"},
    "settings.save_failed": {"zh": "保存设置失败：{exc}", "en": "Failed to save settings: {exc}"},
    "settings.s2_warning": {"zh": "⚠️ Semantic Scholar：超过 60 天未使用的 Key 可能被回收。请定期使用以保持活跃。",
                           "en": "⚠️ Semantic Scholar: Keys inactive for 60+ days may be removed. Use the tool regularly to keep your key active."},
    "settings.proxy_group": {"zh": "代理设置", "en": "Proxy Settings"},
    "settings.request_group": {"zh": "请求设置", "en": "Request Settings"},
    "settings.http_proxy_ph": {"zh": "http://proxy:port（可选）", "en": "http://proxy:port (optional)"},
    "settings.https_proxy_ph": {"zh": "https://proxy:port（可选）", "en": "https://proxy:port (optional)"},
    "settings.timeout_tip": {"zh": "请求超时（秒）", "en": "Request timeout (seconds)"},
    "settings.timeout_lbl": {"zh": "超时：", "en": "Timeout:"},
    "settings.concurrent_tip": {"zh": "最大并发请求数", "en": "Max concurrent requests"},
    "settings.concurrent_lbl": {"zh": "并发数：", "en": "Concurrency:"},

    # --- Adapter descriptions (settings) ---
    "adapter.crossref.desc": {"zh": "免费 — 无需 Key。使用 mailto 进入礼貌队列。",
                              "en": "Free — no key needed. Uses mailto for polite pool."},
    "adapter.s2.desc": {"zh": "免费版：约 100 次/5 分钟。带 Key：1 次/秒。\n申请地址：https://www.semanticscholar.org/product/api",
                        "en": "Free tier: ~100 req/5min. With key: 1 RPS guaranteed.\nApply at: https://www.semanticscholar.org/product/api"},
    "adapter.openalex.desc": {"zh": "建议申请免费 Key：10 万次/天。\n申请地址：https://openalex.org/",
                              "en": "Free key recommended: 100K credits/day.\nApply at: https://openalex.org/"},
    "adapter.aminer.desc": {"zh": "有免费额度，Key 可提升限额。\n申请地址：https://open.aminer.cn/",
                            "en": "Free tier available. Key unlocks higher limits.\nApply at: https://open.aminer.cn/"},
    "adapter.baidu.desc": {"zh": "爬虫方式 — 无需 API Key。", "en": "Scraping-based — no API key."},
    "adapter.arxiv.desc": {"zh": "免费 API — 无需 Key。搜索预印本论文。", "en": "Free API — no key required. Searches preprints."},
    "adapter.scholar.desc": {"zh": "谷粉学术镜像爬虫 — 无需 API Key。适用于无 VPN 的中国用户。",
                             "en": "Scraping via gufen mirror — no API key. For users in China without VPN."},
    "adapter.cnki.desc": {"zh": "Playwright 爬虫 — 无需 API Key。", "en": "Playwright-based — no API key."},

    # --- Context menu ---
    "menu.export": {"zh": "导出结果…", "en": "Export Results..."},
    "menu.open_browser": {"zh": "在浏览器中打开（{adapter}）", "en": "Open in Browser ({adapter})"},

    # --- Progress widget ---
    "progress.ready": {"zh": "就绪", "en": "Ready"},
    "progress.verifying": {"zh": "验证中 {current}/{total}…", "en": "Verifying {current}/{total}..."},
    "progress.done": {"zh": "完成 — {total} 条引用已验证", "en": "Done — {total} references verified"},

    # --- Export dialog (additional) ---
    "export.dlg.title": {"zh": "导出结果", "en": "Export Results"},
    "export.dlg.format_label": {"zh": "格式：", "en": "Format:"},
    "export.dlg.save_to": {"zh": "保存到：", "en": "Save to:"},
    "export.dlg.browse": {"zh": "浏览…", "en": "Browse..."},
    "export.dlg.placeholder": {"zh": "选择保存位置…", "en": "Choose save location..."},
    "export.dlg.save_btn": {"zh": "导出", "en": "Export"},
    "export.dlg.cancel_btn": {"zh": "取消", "en": "Cancel"},
    "export.dlg.no_path": {"zh": "无路径", "en": "No Path"},
    "export.dlg.no_path_msg": {"zh": "请选择保存位置。", "en": "Please choose a save location."},
    "export.dlg.complete": {"zh": "导出完成", "en": "Export Complete"},
    "export.dlg.complete_msg": {"zh": "结果已导出到：\n{path}", "en": "Results exported to:\n{path}"},
    "export.dlg.error": {"zh": "错误", "en": "Error"},
    "export.dlg.error_unknown": {"zh": "未知格式：{fmt}", "en": "Unknown format: {fmt}"},
    "export.dlg.export_error": {"zh": "导出错误", "en": "Export Error"},
    "export.dlg.export_failed": {"zh": "导出失败：\n{exc}", "en": "Failed to export:\n{exc}"},
    "export.dlg.summary_total": {"zh": "总计：{total} 条引用", "en": "Total: {total} references"},
    "export.dlg.summary_verified": {"zh": "✅ 已验证：{count}", "en": "✅ Verified: {count}"},
    "export.dlg.summary_suspicious": {"zh": "⚠️ 可疑：{count}", "en": "⚠️ Suspicious: {count}"},
    "export.dlg.summary_fabricated": {"zh": "❌ 疑似伪造：{count}", "en": "❌ Fabricated: {count}"},
    "export.dlg.summary_unable": {"zh": "ℹ️ 无法验证：{count}", "en": "ℹ️ Unable: {count}"},
    "export.dlg.save_title": {"zh": "保存结果", "en": "Save Results"},
    "export.dlg.format_csv": {"zh": "CSV (.csv)", "en": "CSV (.csv)"},
    "export.dlg.format_xlsx": {"zh": "Excel (.xlsx) — 彩色", "en": "Excel (.xlsx) — color-coded"},
    "export.dlg.format_bib": {"zh": "BibTeX (.bib) — 仅已验证", "en": "BibTeX (.bib) — verified only"},
    "export.dlg.filter_csv": {"zh": "CSV 文件 (*.csv)", "en": "CSV Files (*.csv)"},
    "export.dlg.filter_xlsx": {"zh": "Excel 文件 (*.xlsx)", "en": "Excel Files (*.xlsx)"},
    "export.dlg.filter_bib": {"zh": "BibTeX 文件 (*.bib)", "en": "BibTeX Files (*.bib)"},
    "export.dlg.filter_all": {"zh": "所有文件 (*)", "en": "All Files (*)"},
}


def t(key: str, **kwargs: object) -> str:
    """Translate a message key to the current language.

    Args:
        key: Translation key (e.g. "app.title").
        **kwargs: Format arguments (e.g. count=5).

    Returns:
        Translated string. Falls back to English if key not found.
    """
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_lang) or entry.get("en") or key
    if kwargs:
        text = text.format(**kwargs)
    return text


def get_language() -> Language:
    """Get the current UI language.

    Returns:
        Current language code.
    """
    return _current_lang


def set_language(lang: Language) -> None:
    """Set the UI language.

    Args:
        lang: Language code ("zh" or "en").
    """
    global _current_lang
    _current_lang = lang


def toggle_language() -> Language:
    """Toggle between Chinese and English.

    Returns:
        The new language after toggling.
    """
    global _current_lang
    _current_lang = "en" if _current_lang == "zh" else "zh"
    return _current_lang
