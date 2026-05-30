# RefChecker — Citation Verification System Development Plan

> **Version**: 2.1 (optimized with research — includes existing tool analysis)
> **Updated**: 2026-05-30
> **Status**: Pre-development

---

## 0. Existing Tool Landscape (Critical Context)

Before building from scratch, we must consider existing open-source citation verification tools:

### Existing Tool A: RefChecker (by Mark Russinovich / Microsoft)
- **GitHub**: https://github.com/markrussinovich/refchecker
- **PyPI**: `academic-refchecker[llm,webui]`
- **License**: MIT
- **Language**: Python 3.11+
- **Architecture**: Multi-stage pipeline — GROBID/LLM extraction → CrossRef/S2/OpenAlex/DBLP/ACL verification → LLM deep web search
- **Features**: Docker deployment, Web UI, bulk checking, OpenReview scanning, SQLite caching, retraction detection
- **Gap**: **No Chinese literature support** (no CNKI, Baidu Scholar, AMiner, Wanfang adapters)
- **Assessment**: Architecture is excellent reference; our project adds unique Chinese literature coverage

### Existing Tool B: Hallucinator (by Gianluca Stringhini)
- **GitHub**: https://github.com/gianlucasb/hallucinator
- **License**: AGPL-3.0
- **Language**: Rust core + Python bindings
- **Features**: TUI, CLI, offline databases (DBLP/ACL/arXiv/OpenAlex), retraction detection
- **Gap**: No Chinese literature, AGPL license limits commercial use
- **Assessment**: Performance architecture worth studying; not suitable for forking (AGPL + Rust)

### Strategic Decision

> **We will NOT fork an existing tool.** Our project's primary differentiator is **Chinese academic literature verification** — a gap no existing open-source tool addresses. We will study their adapter patterns, scoring algorithms, and pipeline designs, but build our own system focused on:
> 1. Chinese literature databases (AMiner, Baidu Scholar, CNKI)
> 2. Desktop-first UX (PySide6) for non-technical users
> 3. Bilingual (Chinese/English) reference parsing

---

## 1. Architecture Decision Records (ADRs)

### ADR-1: Application Form Factor — Desktop App (PySide6) + CLI

**Decision**: Build as a **PySide6 desktop application** with a companion **CLI interface**.

**Context**: The original plan considered two options (PySide6 vs Tauri+React). After analysis:

- The target user base (researchers, students, librarians) needs a **simple install-and-run** experience.
- PySide6 provides native desktop UX, file drag-and-drop, system tray integration, and offline capability.
- A CLI interface enables batch processing, CI/CD integration, and headless server use.
- The Tauri approach adds complexity (multi-language, sidecar process management) without proportional benefit for this use case.

**Consequences**:
- Single-language codebase (Python).
- Larger binary size (~60-100MB due to Qt), acceptable for desktop distribution.
- CLI layer can be built on top of the same core engine.

### ADR-2: Verification Strategy — API-First with Fallback Scraping

**Decision**: Prioritize **free open APIs** (Crossref → Semantic Scholar → OpenAlex) before any web scraping.

**Context**: The original plan listed scraping as a core component. Research reveals three powerful free APIs that cover the vast majority of verification needs:

| API | Coverage | Rate Limit | Python SDK | Key Feature |
|-----|----------|------------|------------|-------------|
| **Crossref** | 150M+ DOIs | Polite pool (with mailto) | `habanero` (preferred) or `crossrefapi` | `query.bibliographic` param for fuzzy lookup; includes Retraction Watch |
| **Semantic Scholar** | 200M+ papers | Free tier (1 RPS with key) | `semanticscholar` | Title/DOI search, citation graphs |
| **OpenAlex** | 450M+ works | Free key: 100K credits/day | `pyalex` | Broadest coverage, some Chinese journals |
| **AMiner** | 300M+ papers (strong Chinese) | Free tier | REST API (`requests`) | **Best free source for Chinese literature** |

**Layered verification strategy**:
1. **DOI direct lookup** (if DOI present) → Crossref API (instant, deterministic)
2. **Title + author search** → Semantic Scholar API → OpenAlex API → AMiner API
3. **Chinese literature fallback** → AMiner (API) → Baidu Academic (requests-based) → CNKI search page (Playwright, search results only, no login)
4. **Last resort** → Google Scholar via `scholarly` library (with proxy support)

**Consequences**:
- 80%+ of English citations can be verified via APIs alone (no scraping, no anti-crawl issues).
- Scraping is reduced to a **fallback** for Chinese databases and edge cases.
- More reliable, faster, and respectful of source databases.

### ADR-3: Environment Management — Conda

**Decision**: Use **conda** for environment management.

**Context**: User specification. Conda provides:
- Cross-platform binary dependency management (especially useful for Qt/PySide6).
- Consistent environment across dev/machine boundaries.
- `environment.yml` for reproducible setups.

### ADR-4: Fuzzy Matching — RapidFuzz

**Decision**: Use **RapidFuzz** (not raw Levenshtein) for citation matching.

**Context**: [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) is a C++-backed fuzzy string matching library that is significantly faster than pure-Python alternatives. A [peer-reviewed comparative study](https://www.researchgate.net/publication/390846511) confirms it outperforms FuzzyWuzzy, difflib, and python-Levenshtein across multilingual datasets.

**Matching algorithm design**:
- Title similarity: `fuzz.ratio` + `fuzz.token_sort_ratio` (handles word reordering)
- Author matching: `fuzz.token_set_ratio` (handles subset/superset author lists)
- Year matching: exact match or ±1 tolerance
- Composite score: weighted combination (title: 0.5, author: 0.3, year: 0.1, venue: 0.1)
- Thresholds: ≥0.85 = **Verified**, 0.60-0.84 = **Suspicious**, <0.60 = **Likely Fabricated**

### ADR-5: BibTeX Parsing — bibtexparser v2

**Decision**: Use **bibtexparser v2** (beta, `2.0.0b9`).

**Context**: v2 is rewritten with `pyparsing` and recommended for new projects. While still in beta, it is actively maintained and more robust than v1. The bib format is well-standardized, so beta risk is minimal.

### ADR-6: API Key Strategy — Optional Keys with Graceful Tiering

**Decision**: The application works **out-of-box without any API keys**. Keys are optional upgrades that unlock higher rate limits or additional data sources.

**Context**: Requiring users to register for API keys before first use creates friction. The tool should be immediately useful with free-tier/no-key sources, with keys as an opt-in enhancement.

**API key tiers by source**:

| Adapter | No Key (Default) | With Free Key | Key Required? |
|---------|-------------------|---------------|---------------|
| **Crossref** | Polite pool (add mailto) | Same | ❌ Never |
| **Semantic Scholar** | ~100 req/5min (shared, variable) | 1 RPS guaranteed | ❌ Optional upgrade |
| **OpenAlex** | 100 credits/day (testing only) | 100,000 credits/day | ⚠️ Strongly recommended |
| **AMiner** | Free tier available | Higher limits | ❌ Optional upgrade |
| **Baidu Academic** | N/A (scraping, no key) | N/A | ❌ Never |
| **CNKI** | N/A (Playwright, no key) | N/A | ❌ Never |
| **Google Scholar** | N/A (scholarly lib) | N/A (but proxy helps) | ❌ Never |

**Semantic Scholar API key application prerequisites** (per their policy):
> Users must confirm: (1) they have already made successful unauthenticated requests, (2) they acknowledge there are only 2 rate plans, (3) they will apply exponential backoff, (4) keys inactive for 60+ days may be removed.

This means **we MUST implement exponential backoff as a hard requirement**, not just best practice — it is a condition of API access.

**Implementation rules**:
1. **Default behavior**: All adapters work with free/no-key access. On first launch, the user can verify citations immediately — no registration required.
2. **Settings dialog**: Each API-source has an optional API key field. Empty = use free tier. Each field has a subtle hint about what the key unlocks (e.g., *"Adding a key increases Semantic Scholar limits from ~100/5min to 1 RPS"*).
3. **Key status indicators**: Show ✅/⚠️/❌ next to each source in settings indicating key status and current rate limit tier.
4. **Application guides with prerequisites**: The "How to apply" link for each source shows a step-by-step guide. For Semantic Scholar specifically, remind users they must make unauthenticated requests first before applying. Include direct URL to the API registration page.
5. **Key lifecycle warning**: Display a note in Settings for sources with key expiration policies (e.g., Semantic Scholar: *"⚠️ Keys inactive for 60+ days may be removed. Use the tool regularly to keep your key active."*). Optionally show "last used" date if we track it.
6. **Exponential backoff (mandatory)**: All adapters MUST implement exponential backoff with jitter. This is not optional — it is a Semantic Scholar API requirement and best practice for all sources. Implementation: initial delay 1s, max delay 60s, factor 2, jitter ±0.5s. Respects `Retry-After` headers when present.
7. **Rate limit feedback**: When a rate limit is hit, surface a non-blocking toast notification: *"Semantic Scholar rate limit reached. Add an API key in Settings for higher limits."* with a direct link to the settings dialog.

---

## 2. Tech Stack Summary

```
┌─────────────────────────────────────────────────────┐
│                   Presentation Layer                 │
│  PySide6 (desktop GUI)  │  Click/Typer (CLI)        │
├─────────────────────────────────────────────────────┤
│                    Application Layer                  │
│  QThread workers  │  Signal/Slot  │  Progress bars   │
├─────────────────────────────────────────────────────┤
│                      Core Engine                      │
│  Parser → Verifier → Scorer → Reporter               │
│  (bibtexparser)   (API adapters)  (RapidFuzz)        │
├─────────────────────────────────────────────────────┤
│                   Infrastructure Layer                │
│  Crossref │ Semantic Scholar │ OpenAlex │ AMiner │ Baidu/CNKI │
│  (habanero) (semanticscholar) (pyalex) (requests) (playwright)│
├─────────────────────────────────────────────────────┤
│                    Cross-cutting                      │
│  Logging (structlog) │ Config (Pydantic Settings)    │
│  Error handling      │ Export (openpyxl/csv)         │
└─────────────────────────────────────────────────────┘
```

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PySide6` | ≥6.7 | Desktop GUI framework |
| `bibtexparser` | ≥2.0.0b7 | BibTeX file parsing |
| `habanero` | ≥2.3 | Crossref REST API client (preferred over crossrefapi) |
| `semanticscholar` | ≥0.8 | Semantic Scholar API client |
| `pyalex` | ≥0.14 | OpenAlex API client |
| `rapidfuzz` | ≥3.9 | Fuzzy string matching |
| `httpx` | ≥0.28 | Async HTTP client (API calls) |
| `playwright` | ≥1.40 | Headless browser (CNKI fallback) |
| `structlog` | ≥24.1 | Structured logging |
| `pydantic` | ≥2.0 | Data models and settings |
| `openpyxl` | ≥3.1 | Excel export |
| `click` or `typer` | latest | CLI interface |
| `qasync` | ≥0.27 | Qt + asyncio integration |

### Dev Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing framework |
| `pytest-qt` | Qt widget testing |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linting + formatting |
| `mypy` | Type checking |
| `pre-commit` | Git hook management |

---

## 3. Project Structure

```
cite_check/
├── CLAUDE.md
├── README.md
├── environment.yml                    # Conda environment
├── pyproject.toml                     # Project metadata & deps
├── src/
│   └── refchecker/
│       ├── __init__.py
│       ├── cli/                       # CLI interface
│       │   ├── __init__.py
│       │   └── main.py               # Click/Typer CLI entry
│       ├── gui/                       # PySide6 desktop GUI
│       │   ├── __init__.py
│       │   ├── app.py                # QApplication setup
│       │   ├── main_window.py        # Main window layout
│       │   ├── widgets/              # Custom widgets
│       │   │   ├── __init__.py
│       │   │   ├── file_drop.py      # Drag-drop file upload
│       │   │   ├── result_table.py   # Verification result grid
│       │   │   └── progress.py       # Progress bar widget
│       │   ├── workers/              # QThread workers
│       │   │   ├── __init__.py
│       │   │   └── verify_worker.py  # Background verification
│       │   └── dialogs/              # Settings, about dialogs
│       │       ├── __init__.py
│       │       └── settings.py
│       ├── core/                      # Core verification engine
│       │   ├── __init__.py
│       │   ├── models.py             # Pydantic data models
│       │   ├── parser.py             # BibTeX/text parser
│       │   ├── scorer.py             # Fuzzy matching & scoring
│       │   ├── engine.py             # Orchestration engine
│       │   └── exporter.py           # CSV/Excel/bib export
│       ├── adapters/                  # API/web adapters
│       │   ├── __init__.py
│       │   ├── base.py               # Abstract adapter interface
│       │   ├── crossref_adapter.py   # Crossref API
│       │   ├── s2_adapter.py         # Semantic Scholar API
│       │   ├── openalex_adapter.py   # OpenAlex API
│       │   ├── aminer_adapter.py     # AMiner API (Chinese literature)
│       │   ├── baidu_adapter.py      # Baidu Academic
│       │   ├── cnki_adapter.py       # CNKI (Playwright)
│       │   └── scholar_adapter.py    # Google Scholar (scholarly)
│       └── config.py                 # Settings & configuration
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_scorer.py
│   │   ├── test_models.py
│   │   └── test_exporter.py
│   ├── integration/
│   │   ├── test_crossref_adapter.py
│   │   ├── test_s2_adapter.py
│   │   ├── test_openalex_adapter.py
│   │   └── test_engine.py
│   └── e2e/
│       ├── test_cli.py
│       └── test_gui.py
├── plan/                              # Planning documents
│   └── planv1.md                      # This file
├── temp/                              # Scratch files
├── .github/
│   └── workflows/
│       └── build.yml                  # Cross-platform build CI
└── .pre-commit-config.yaml
```

---

## 4. Phased Development Plan

### Phase 1: Core Data Models & Parser (Week 1-2)

**Goal**: Parse `.bib` files into structured internal representation.

| Task | Description | Est. |
|------|-------------|------|
| 1.1 | Set up conda environment, project skeleton, `pyproject.toml` | 0.5d |
| 1.2 | Define `ReferenceItem` (Pydantic model): title, authors, year, journal/venue, DOI, volume, issue, pages, verification status | 0.5d |
| 1.3 | Implement BibTeX parser using `bibtexparser` v2 | 1d |
| 1.4 | Implement GBT 7714 text parser (regex-based) | 1d |
| 1.5 | Build logging module (`structlog`) and error hierarchy | 0.5d |
| 1.6 | Unit tests for parser (≥90% coverage) | 1d |
| 1.7 | CLI skeleton: `refchecker parse <file>` command | 0.5d |

**Deliverable**: `refchecker parse paper.bib` produces structured JSON output.

### Phase 2: Verification Engine & API Adapters (Week 3-5) ⭐ HARDEST

**Goal**: Verify citations against multiple academic databases.

| Task | Description | Est. |
|------|-------------|------|
| 2.1 | Define abstract `VerificationAdapter` interface with built-in exponential backoff | 0.5d |
| 2.2 | Implement **exponential backoff mixin** (base class): initial 1s, max 60s, factor 2, jitter ±0.5s, `Retry-After` header support — **mandatory** per S2 API policy | 0.5d |
| 2.3 | Implement **Crossref adapter** (DOI lookup + `query.bibliographic`) via `habanero` | 1.5d |
| 2.4 | Implement **Semantic Scholar adapter** (title/DOI search, backoff-aware) | 1.5d |
| 2.5 | Implement **OpenAlex adapter** (title/author/DOI search) via `pyalex` | 1d |
| 2.6 | Implement **AMiner adapter** (Chinese literature — key differentiator) | 1.5d |
| 2.7 | Implement **Baidu Academic adapter** (requests-based, moderate anti-crawl) | 1.5d |
| 2.8 | Implement **CNKI adapter** (Playwright, search results only) | 2d |
| 2.9 | Implement fuzzy matching scorer using RapidFuzz | 1d |
| 2.10 | Build orchestration engine (parallel adapter queries, result aggregation) | 1.5d |
| 2.11 | API key management module (load/save per-adapter keys, key status check, lifecycle warnings) | 0.5d |
| 2.12 | Proxy configuration module (HTTP/SOCKS5, per-adapter override) | 0.5d |
| 2.13 | Integration tests with mocked API responses | 1d |
| 2.14 | CLI: `refchecker verify <file>` command | 0.5d |

**Verification priority chain**:
```
Input → DOI present?
  ├─ Yes → Crossref DOI lookup → Found? → Score → Done
  └─ No → Title+Author search:
            ├─ Semantic Scholar → Score
            ├─ OpenAlex → Score
            ├─ AMiner → Score (best for Chinese lit)
            └─ (fallback) Baidu Academic → Score
         → Aggregate scores → Final verdict
```

**Deliverable**: `refchecker verify paper.bib --adapters crossref,s2,openalex` outputs verification results.

### Phase 3: Desktop GUI (Week 6-7)

**Goal**: Intuitive PySide6 desktop interface.

| Task | Description | Est. |
|------|-------------|------|
| 3.1 | Main window layout (file upload area, channel selector, results table) | 1d |
| 3.2 | Drag-and-drop file upload widget | 0.5d |
| 3.3 | Result table with color-coded status (green/yellow/red) | 1d |
| 3.4 | Background verification worker (QThread + Signal/Slot) | 1d |
| 3.5 | **Settings dialog**: per-adapter API key fields (optional), proxy config, adapter enable/disable; show ✅/⚠️/❌ key status indicators; inline "How to apply" links for sources requiring keys | 1d |
| 3.6 | Rate-limit toast notification system (*"Rate limit reached. Add API key in Settings."*) | 0.5d |
| 3.7 | Export dialog (CSV, Excel, clean .bib) | 0.5d |
| 3.8 | GUI tests with `pytest-qt` | 1d |

**Deliverable**: `python -m refchecker.gui` launches desktop app.

### Phase 4: Export, Polish & Testing (Week 8)

**Goal**: Production-quality export and comprehensive test coverage.

| Task | Description | Est. |
|------|-------------|------|
| 4.1 | Export to Excel (color-coded, with summary statistics) | 0.5d |
| 4.2 | Export to clean .bib (remove fabricated entries) | 0.5d |
| 4.3 | Generate verification report (Markdown) | 0.5d |
| 4.4 | Comprehensive test coverage (≥80%) | 1d |
| 4.5 | Performance optimization (batch API calls, caching) | 1d |
| 4.6 | Documentation and README | 0.5d |

**Deliverable**: Fully functional, tested application with documentation.

### Phase 5: Packaging & Distribution (Week 9)

**Goal**: Cross-platform distribution.

| Task | Description | Est. |
|------|-------------|------|
| 5.1 | PyInstaller config for Linux build | 0.5d |
| 5.2 | GitHub Actions workflow (Linux, Windows, macOS) | 1d |
| 5.3 | Application icon and metadata | 0.5d |
| 5.4 | Smoke tests on packaged binaries | 0.5d |

**Deliverable**: `.exe`, `.dmg`, and `.AppImage` downloads from GitHub Releases.

### Phase 6: Advanced Features (Future)

| Feature | Description |
|---------|-------------|
| LLM-assisted text parsing | Use lightweight LLM API (DeepSeek/Qwen) to parse non-standard citation formats |
| PDF citation extraction | Extract references directly from PDF files |
| Batch processing | Process multiple .bib files or entire directories |
| Zotero integration | Import from / export to Zotero collections |
| Citation graph visualization | Show citation relationships visually |

---

## 5. Key Risk Mitigations

### Anti-Crawl Protection

| Risk | Mitigation |
|------|------------|
| IP ban from CNKI/Google Scholar | Random 3-8s delay between requests; user-configurable proxy; limit to search results page only |
| Rate limiting from APIs | Respect `Retry-After` headers; implement exponential backoff; use polite pool with email |
| CAPTCHA blocking | Surface error to user with manual retry option; recommend proxy rotation |

### Chinese Literature Coverage

| Challenge | Approach |
|-----------|----------|
| No Chinese API in existing tools | **AMiner API** (free, 300M+ papers, strong Chinese coverage) is our key differentiator |
| CNKI requires campus IP | Search results page is public; no detail page access needed |
| Baidu Academic rate limits | Moderate request frequency; parse search results with `requests` + `BeautifulSoup4` |
| Mixed Chinese/English metadata | Unicode-aware string matching; RapidFuzz handles CJK characters |

### Desktop Application

| Challenge | Approach |
|-----------|----------|
| UI freezing during verification | QThread + Signal/Slot pattern; progress updates per-item |
| Large .bib files (1000+ entries) | Chunked processing with progress feedback; cancel support |
| Binary size (~60-100MB) | Acceptable for desktop; use UPX compression |

---

## 6. Verification Result Taxonomy

| Status | Color | Criteria |
|--------|-------|----------|
| ✅ **Verified** | Green | Found in ≥1 source with composite score ≥0.85 |
| ⚠️ **Suspicious** | Yellow | Partial match (score 0.60-0.84), or found with significant discrepancies |
| ❌ **Likely Fabricated** | Red | Not found in any source, or very low match score (<0.60) |
| ℹ️ **Unable to Verify** | Gray | Network error, rate limited, or source unavailable |
| 🔄 **Pending** | White | Not yet checked |

---

## 7. Research Sources

### Existing Citation Verification Tools
- [RefChecker (Mark Russinovich / Microsoft)](https://github.com/markrussinovich/refchecker) — MIT, Python 3.11+, most comprehensive existing tool
- [Hallucinator (Gianluca Stringhini)](https://github.com/gianlucasb/hallucinator) — AGPL-3.0, Rust core + Python bindings
- [HALLMARK Benchmark](https://github.com/rpatrik96/hallmark) — Citation hallucination detection benchmark

### APIs
- [Crossref API — Verifying References](https://community.crossref.org/t/verifying-references/15794)
- [habanero — Crossref Python client](https://github.com/sckott/habanero) (preferred over crossrefapi)
- [Semantic Scholar API Docs](https://api.semanticscholar.org/api-docs/)
- [Semantic Scholar Python SDK](https://semanticscholar.readthedocs.io/en/latest/overview.html)
- [OpenAlex API](https://developers.openalex.org/)
- [PyAlex Python library](https://github.com/J535D165/pyalex)
- [OpenAlex API Key Requirement (Feb 2025)](https://docs.ropensci.org/openalexR/)
- [AMiner Open API](https://open.aminer.cn/) — Best free API for Chinese academic literature

### Libraries
- [bibtexparser v2](https://bibtexparser.readthedocs.io/)
- [RapidFuzz — Fuzzy Matching Library](https://github.com/rapidfuzz/RapidFuzz)
- [RapidFuzz Comparative Study](https://www.researchgate.net/publication/390846511)
- [Google Scholar Scraping Alternatives](https://scrapfly.io/blog/posts/google-scholar-api-and-alternatives)

### Chinese Database Scraping
- [CNKI Scraping with Selenium (2025)](https://www.cnblogs.com/ofnoname/p/18751494)
- [CNKI-download Python tool](https://blog.csdn.net/gitblog_00449/article/details/161271275)

### Desktop App & Packaging
- [PySide6 Packaging with PyInstaller](https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/)
- [PyInstaller v6.x Changelog](https://pyinstaller.org/en/v6.16.0/CHANGES.html)
