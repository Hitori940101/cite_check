# RefChecker

> Academic citation verification tool — supports Chinese and English literature.

RefChecker validates whether references in `.bib` files or plain text are real by querying Crossref, Semantic Scholar, OpenAlex, AMiner, and other academic databases. It uses fuzzy matching to score how closely each citation matches known papers.

**Key differentiator**: Strong Chinese literature support via AMiner API (300M+ papers) and Baidu Academic — a gap no other open-source tool addresses.

[**中文文档**](./README-ZH.md)

## Features

- **Dual interface**: Desktop GUI (PySide6) and CLI
- **Multi-format parsing**: BibTeX (`.bib`) and GBT 7714-2015 plain text
- **8 verification adapters**: Crossref, Semantic Scholar, OpenAlex, AMiner, Baidu Academic, CNKI, arXiv, Google Scholar
- **Chinese literature focus**: AMiner (primary), Baidu Academic (fallback), CNKI (Playwright)
- **Fuzzy matching**: RapidFuzz-powered composite scoring (title, author, year, venue)
- **Works out-of-box**: Free API tiers require no keys; optional keys unlock higher rate limits
- **Export**: CSV, color-coded Excel (`.xlsx`), filtered BibTeX, Markdown reports
- **Bilingual UI**: Chinese/English with runtime toggle
- **Incremental display**: Results appear one-by-one as each reference is verified
- **Background verification**: Non-blocking GUI with QThread workers

## Verification Status

| Status | Symbol | Meaning |
|--------|--------|---------|
| Verified | ✅ | Found in ≥1 source, composite score ≥ 0.85 |
| Suspicious | ⚠️ | Partial match, score 0.60–0.84 |
| Likely Fabricated | ❌ | Not found, score < 0.60 |
| Unable to Verify | ℹ️ | Network error or source unavailable |
| Pending | 🔄 | Not yet checked |

## Installation

### Prerequisites

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda.

### macOS

```bash
git clone https://github.com/Hitori940101/cite_check.git
cd cite_check
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui
```

**macOS first-launch note**: If you see "cannot be opened because it cannot be verified", go to **System Settings → Privacy & Security** → click "Open Anyway".

### Windows

```powershell
git clone https://github.com/Hitori940101/cite_check.git
cd cite_check
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui.exe
```

### Linux

```bash
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui
```

### Optional: Scraping Adapters (CNKI)

```bash
pip install -e ".[scraping]"
playwright install chromium
```

## Quick Start

### CLI

```bash
refchecker parse paper.bib                    # Parse a BibTeX file
refchecker parse paper.bib --format json      # JSON output
refchecker verify paper.bib                   # Verify citations
refchecker verify paper.bib --adapters crossref,s2,aminer  # Specific adapters
refchecker verify paper.bib --format csv --output results.csv  # Export to file
```

### GUI

```bash
refchecker-gui    # Launch the desktop application
```

1. Drag a `.bib` or `.txt` file into the window
2. Check/uncheck individual references to verify
3. Click **▶ Verify**
4. View results in the color-coded table
5. Click **📥 Export** to save as CSV, Excel, or BibTeX

### API Key Management

```bash
refchecker set-key s2 your-api-key    # Store a key (encrypted via OS keyring)
refchecker get-key s2                  # Check key status
refchecker delete-key s2               # Delete a key
refchecker list-keys                   # List all key statuses
```

## Configuration

### API Keys (Optional)

RefChecker works without any API keys. Adding keys unlocks higher rate limits:

| Adapter | Free Tier | With Key |
|---------|-----------|----------|
| Crossref | Polite pool (mailto) | — |
| Semantic Scholar | ~100 req/5min | 1 RPS guaranteed |
| OpenAlex | 10K/day | 100K/day |
| AMiner | Free tier | Higher limits |
| arXiv | Free, no key | — |
| Baidu Academic | Scraping, no key | — |
| CNKI | Scraping, no key | — |
| Scholar | Scraping, no key | — |

Keys can also be set in the GUI via **⚙ Settings → Adapters** tab.

### Environment Variables

```bash
export REFCHECKER_S2_API_KEY=your-key
export REFCHECKER_HTTP_PROXY=http://proxy:8080
export REFCHECKER_HTTPS_PROXY=https://proxy:443
```

## Building Standalone Executables

```bash
pip install pyinstaller
pyinstaller refchecker.spec
```

| Platform | Output | Notes |
|----------|--------|-------|
| macOS | `dist/RefChecker.app` | Double-click to open |
| Windows | `dist/RefChecker.exe` | Single-file, no Python needed |
| Linux | `dist/RefChecker` | Single binary |

## License

MIT
