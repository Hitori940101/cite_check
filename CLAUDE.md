# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**RefChecker (Cite Check)** — a citation verification system for academic papers. Validates whether references in `.bib` files or text are real by querying Crossref, Semantic Scholar, OpenAlex, and other academic databases.

Part of the DeepScientist paper-tooling ecosystem alongside `paper_check` (format checking) and `paper_form_check` (AI-powered review).

## Current Status

This project is in the **pre-development / planning** phase. See `planv1.md` for the full development plan.

## Architecture

```
src/refchecker/
├── cli/          # CLI interface (Click/Typer)
├── gui/          # PySide6 desktop GUI
│   ├── widgets/  # Custom Qt widgets
│   ├── workers/  # QThread background workers
│   └── dialogs/  # Settings, about dialogs
├── core/         # Core verification engine
│   ├── models.py # Pydantic data models (ReferenceItem)
│   ├── parser.py # BibTeX / GBT 7714 text parser
│   ├── scorer.py # RapidFuzz fuzzy matching & scoring
│   ├── engine.py # Orchestration engine
│   └── exporter.py # CSV/Excel/bib export
├── adapters/     # API and web verification adapters
│   ├── base.py   # Abstract adapter interface
│   ├── crossref_adapter.py
│   ├── s2_adapter.py
│   ├── openalex_adapter.py
│   ├── aminer_adapter.py   # Chinese literature (key differentiator)
│   ├── baidu_adapter.py
│   ├── cnki_adapter.py
│   └── scholar_adapter.py
└── config.py     # Pydantic Settings configuration
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Environment | **conda** (`environment.yml`) |
| GUI | PySide6 (Qt for Python) |
| CLI | Click or Typer |
| Data models | Pydantic v2 |
| BibTeX parsing | bibtexparser v2 |
| Fuzzy matching | RapidFuzz |
| HTTP client | httpx (async) |
| Chinese literature | AMiner API (primary), Baidu Academic (fallback) |
| Scraping (fallback) | Playwright (CNKI only) |
| Logging | structlog |
| Export | openpyxl, csv |
| Testing | pytest, pytest-qt, pytest-asyncio |
| Linting | ruff |
| Type checking | mypy |
| Packaging | PyInstaller + GitHub Actions |

## Verification Strategy

API-first with fallback scraping:
1. **DOI lookup** → Crossref API (instant)
2. **Title + author** → Semantic Scholar → OpenAlex → AMiner
3. **Chinese lit fallback** → AMiner (API) → Baidu Academic → CNKI (Playwright, search results only)
4. **Last resort** → Google Scholar (`scholarly` lib)

## Verification Status Taxonomy

| Status | Meaning |
|--------|---------|
| Verified (✅) | Found in ≥1 source, composite score ≥0.85 |
| Suspicious (⚠️) | Partial match, score 0.60-0.84 |
| Likely Fabricated (❌) | Not found, score <0.60 |
| Unable to Verify (ℹ️) | Network error or source unavailable |
| Pending (🔄) | Not yet checked |

## Project Rules

- **每次功能改动测试合格后必须 git commit**：实现一个功能 → 运行测试通过 → 立即提交版本。不允许积累多个未提交的功能变更。提交信息遵循 Conventional Commits（`feat:`, `fix:`, `docs:` 等）。

## Conventions

- **Environment management**: conda (`environment.yml` + `conda activate refchecker`)
- **Python**: 3.11+
- **Configuration**: Pydantic Settings (not Hydra — this is a desktop app, not an ML training pipeline)
- **Working directories**: `/plan` for planning docs, `/temp` for scratch files (create as needed)

## Sibling Projects

- `../paper_check/` — Web-based academic paper format detection (FastAPI + Vue 3, Python 3.11+, SQLite). Handles `.docx`/`.doc` upload, template-based format validation, and auto-correction.
- `../paper_form_check/` — AI-powered paper content and format checking (Docker-based, FastAPI backend).

When designing this project's architecture, refer to sibling projects for established patterns (project structure, API conventions, document parsing approaches).

## Development Setup

```bash
# Create conda environment
conda env create -f environment.yml
conda activate refchecker

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run CLI
refchecker parse paper.bib
refchecker verify paper.bib

# Run GUI
python -m refchecker.gui
```

## Key Design Decisions

- **Immutability**: Use Pydantic `frozen=True` models for configuration and data items
- **Adapter pattern**: Each verification source is a pluggable adapter behind a common interface
- **QThread for GUI**: All network I/O runs in background threads, never blocking the UI
- **API-first**: Free APIs (Crossref, Semantic Scholar, OpenAlex, AMiner) cover 80%+ of citations without scraping
- **Graceful degradation**: If one adapter fails, continue with others; surface partial results
- **Chinese literature focus**: AMiner API (300M+ papers, strong Chinese coverage) is our key differentiator over existing tools
- **Optional API keys (ADR-6)**: Tool works out-of-box with free/no-key tiers; API key fields in Settings are optional upgrades; show inline "How to apply" guides only for sources that have no free tier; toast notifications guide users to Settings when rate-limited
- **Exponential backoff (mandatory)**: All adapters implement exponential backoff with jitter (initial 1s, max 60s, factor 2). This is a Semantic Scholar API policy requirement, not just best practice. Respects `Retry-After` headers.
- **Key lifecycle awareness**: Surface warnings for keys with expiration policies (e.g., S2 keys removed after 60 days inactivity). Show "last used" hints in Settings.

## Existing Tools (Reference Only)

- [RefChecker (Microsoft)](https://github.com/markrussinovich/refchecker) — MIT, Python, no Chinese lit support
- [Hallucinator](https://github.com/gianlucasb/hallucinator) — AGPL-3.0, Rust, no Chinese lit support

Our project fills the Chinese literature gap that existing tools do not address.
