# RefChecker — Development Status

> **Last Updated**: 2026-05-31
> **Current Phase**: Phase 3 ✅ Complete → Phase 4 next
> **Test Suite**: 146 passed, 11 skipped (GUI headless), 0 failed

---

## Phase Progress Overview

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Core Data Models & Parser | ✅ Done | 100% |
| Phase 2: Verification Engine & API Adapters | ✅ Done | 100% |
| Phase 3: Desktop GUI | ✅ Done | 100% |
| Phase 4: Export, Polish & Testing | 🔲 Not started | 0% |
| Phase 5: Packaging & Distribution | 🔲 Not started | 0% |
| Phase 6: Advanced Features | 🔲 Future | 0% |

---

## Phase 1: Core Data Models & Parser ✅

| Task | Status | Implementation |
|------|--------|----------------|
| 1.1 Project skeleton | ✅ | `pyproject.toml`, conda env, project structure |
| 1.2 ReferenceItem model | ✅ | `core/models.py` — Pydantic v2, `frozen=True`, DOI normalization |
| 1.3 BibTeX parser | ✅ | `core/parser.py` — `bibtexparser` v2 integration |
| 1.4 GBT 7714 parser | ✅ | `core/parser.py` — regex-based Chinese reference format |
| 1.5 Logging module | ✅ | `core/logging.py` — structlog with JSON output |
| 1.6 Parser tests | ✅ | `tests/unit/test_parser.py` — 28 tests |
| 1.7 CLI parse command | ✅ | `cli/main.py` — `refchecker parse <file>` |

**Deliverable**: `refchecker parse paper.bib` → structured JSON ✅

---

## Phase 2: Verification Engine & API Adapters ✅

| Task | Status | Implementation |
|------|--------|----------------|
| 2.1 Abstract adapter interface | ✅ | `adapters/base.py` — `VerificationAdapter` ABC with backoff |
| 2.2 Exponential backoff | ✅ | `base.py` — 1s initial, 60s max, factor 2, jitter ±0.5s, Retry-After |
| 2.3 Crossref adapter | ✅ | `adapters/crossref_adapter.py` — DOI lookup + bibliographic search |
| 2.4 Semantic Scholar adapter | ✅ | `adapters/s2_adapter.py` — **direct REST API** (no SDK), `x-api-key` header |
| 2.5 OpenAlex adapter | ✅ | `adapters/openalex_adapter.py` — pyalex integration |
| 2.6 AMiner adapter | ✅ | `adapters/aminer_adapter.py` — Chinese literature, REST API |
| 2.7 Baidu Academic adapter | ✅ | `adapters/baidu_adapter.py` — requests-based scraping |
| 2.8 CNKI adapter | ✅ | `adapters/cnki_adapter.py` — Playwright headless |
| 2.9 Fuzzy matching scorer | ✅ | `core/scorer.py` — RapidFuzz, weighted composite (T:0.5, A:0.3, Y:0.1, V:0.1) |
| 2.10 Orchestration engine | ✅ | `engine.py` — parallel adapter queries, result aggregation |
| 2.11 API key management | ✅ | `core/key_store.py` — **encrypted storage via keyring** (OS-native) |
| 2.12 Proxy configuration | ✅ | `config.py` — HTTP/HTTPS proxy fields |
| 2.13 Integration tests | ✅ | `tests/integration/test_adapters.py` — 16 tests |
| 2.14 CLI verify command | ✅ | `cli/main.py` — `refchecker verify <file>` |

### Key Architectural Decisions (deviations from plan)

| Change | Reason |
|--------|--------|
| S2 adapter: direct REST API instead of `semanticscholar` SDK | User requirement; reduces dependency footprint |
| Added `core/key_store.py` with `keyring` encrypted storage | User requirement; API keys stored in OS keychain |
| Added CLI key management: `set-key`, `get-key`, `delete-key`, `list-keys` | Supports encrypted key store workflow |
| Config resolves keys: env var → encrypted store → None | CI/CD compatibility + interactive convenience |

### Adapter Coverage Summary

| Adapter | Method | API Key | File |
|---------|--------|---------|------|
| Crossref | REST API (httpx) | Not needed (mailto) | `crossref_adapter.py` |
| Semantic Scholar | Direct REST API (httpx) | Optional (x-api-key) | `s2_adapter.py` |
| OpenAlex | pyalex SDK | Optional | `openalex_adapter.py` |
| AMiner | REST API (httpx) | Optional | `aminer_adapter.py` |
| Baidu Academic | Scraping (httpx) | N/A | `baidu_adapter.py` |
| CNKI | Playwright | N/A | `cnki_adapter.py` |

**Deliverable**: `refchecker verify paper.bib --adapters crossref,s2,openalex` ✅

---

## Phase 3: Desktop GUI ✅

| Task | Status | Implementation |
|------|--------|----------------|
| 3.1 Main window layout | ✅ | `gui/main_window.py` — toolbar, adapter selector, results |
| 3.2 Drag-and-drop file upload | ✅ | `gui/widgets/file_drop.py` — accepts .bib/.txt |
| 3.3 Color-coded result table | ✅ | `gui/widgets/result_table.py` — green/yellow/red/blue |
| 3.4 Background verification worker | ✅ | `gui/workers/verify_worker.py` — QThread + Signal/Slot |
| 3.5 Settings dialog | ✅ | `gui/dialogs/settings.py` — encrypted API key, proxy, adapter toggle |
| 3.6 Rate-limit toast notification | ✅ | `gui/dialogs/toast.py` — auto-dismiss, action button |
| 3.7 Export dialog | ✅ | `gui/dialogs/export.py` — CSV, Excel (color-coded), BibTeX |
| 3.8 GUI tests | ✅ | `tests/unit/test_gui.py` — 11 tests (skip in headless CI) |

### Bonus: Exporter Module (Phase 4 early delivery)

| Feature | Status | File |
|---------|--------|------|
| CSV export | ✅ | `core/exporter.py` |
| Excel export (color-coded) | ✅ | `core/exporter.py` |
| BibTeX export (filtered) | ✅ | `core/exporter.py` |

**Deliverable**: `python -m refchecker.gui` launches desktop app ✅

---

## Phase 4: Export, Polish & Testing 🔲

| Task | Status | Notes |
|------|--------|-------|
| 4.1 Excel export (color-coded, summary) | ✅ Already done | `core/exporter.py` |
| 4.2 Clean .bib export (filter fabricated) | ✅ Already done | `core/exporter.py` |
| 4.3 Markdown verification report | 🔲 Todo | |
| 4.4 Test coverage ≥80% | 🔲 Todo | Current coverage needs assessment |
| 4.5 Performance (caching, batch optimization) | 🔲 Todo | |
| 4.6 Documentation & README | 🔲 Todo | |

---

## Test Coverage Summary

| Test File | Tests | Category |
|-----------|-------|----------|
| `tests/unit/test_parser.py` | 28 | Parser (BibTeX + GBT 7714) |
| `tests/unit/test_models.py` | 27 | Pydantic models |
| `tests/unit/test_scorer.py` | 27 | RapidFuzz scoring |
| `tests/unit/test_s2_adapter.py` | 14 | S2 REST adapter (mocked HTTP) |
| `tests/unit/test_key_store.py` | 22 | Encrypted key storage |
| `tests/unit/test_gui.py` | 11 | GUI widgets (skip if headless) |
| `tests/integration/test_adapters.py` | 16 | Engine + adapter integration |
| **Total** | **146 passed, 11 skipped** | |

---

## Git History (Phase 2-3)

```
3485f43 feat: implement Phase 3 — PySide6 desktop GUI
8566e3a feat: refactor S2 adapter to direct REST API, add encrypted key storage
2d72a9b feat: wire CLI verify command to orchestration engine with all adapters
c2eb276 feat: add Baidu Academic, CNKI adapters and config/API key management
442d404 test: add scorer unit tests (27) and adapter/engine integration tests (16)
6292203 feat: implement verification orchestration engine
10b91d3 feat: implement Crossref, Semantic Scholar, OpenAlex, and AMiner adapters
```

---

## Remaining Work (Phase 4-5)

### Phase 4 Priority Tasks
1. **Markdown report generation** — verification summary with statistics
2. **Test coverage audit** — run `pytest --cov` and fill gaps to ≥80%
3. **Performance optimization** — result caching, batch optimization
4. **README and documentation** — usage guide, screenshots, API docs

### Phase 5 Tasks
1. PyInstaller config for Linux build
2. GitHub Actions CI/CD (Linux, Windows, macOS)
3. Application icon and metadata
4. Smoke tests on packaged binaries

### Known Gaps
- Google Scholar adapter (`scholar_adapter.py`) — listed in plan but deferred (depends on `scholarly` lib, scraping-only)
- Proxy per-adapter override — currently global only
- GUI: no cancel-in-progress support for mid-batch cancellation
- No result caching between sessions
