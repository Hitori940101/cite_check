# RefChecker

> Academic citation verification tool — supports Chinese and English literature.

RefChecker validates whether references in `.bib` files or plain text are real by querying Crossref, Semantic Scholar, OpenAlex, AMiner, and other academic databases. It uses fuzzy matching to score how closely each citation matches known papers.

**Key differentiator**: Strong Chinese literature support via AMiner API (300M+ papers) and Baidu Academic — a gap no other open-source tool addresses.

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

### macOS

**前置条件**：安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda。

```bash
# 1. 克隆仓库
git clone <repo-url>
cd cite_check

# 2. 创建 conda 环境
conda env create -f environment.yml
conda activate refchecker

# 3. 安装（含 GUI）
pip install -e ".[gui]"

# 4. 启动 GUI
refchecker-gui
# 或
python -m refchecker.gui
```

**macOS 首次启动注意事项**：
- 如果遇到 "无法打开，因为无法验证开发者" 提示，前往 **系统设置 → 隐私与安全性**，点击 "仍要打开"
- 确保 conda 环境中安装了 PySide6：`pip install PySide6`

**构建 macOS .app（可选）**：

```bash
pip install pyinstaller
pyinstaller refchecker.spec
# 产物在 dist/RefChecker.app
```

### Windows

**前置条件**：安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)。

```powershell
# 1. 克隆仓库
git clone <repo-url>
cd cite_check

# 2. 创建 conda 环境
conda env create -f environment.yml
conda activate refchecker

# 3. 安装（含 GUI）
pip install -e ".[gui]"

# 4. 启动 GUI
refchecker-gui.exe
# 或
python -m refchecker.gui
```

**构建 Windows .exe（可选）**：

```powershell
pip install pyinstaller
pyinstaller refchecker.spec
# 产物在 dist\RefChecker.exe（双击即可运行，无需 Python 环境）
```

> **提示**：编译后的 `.exe` 可分发给没有 Python 环境的 Windows 用户，直接双击运行。

### Linux

```bash
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui
```

### Optional: Scraping adapters

For CNKI support (requires headless browser):

```bash
pip install -e ".[scraping]"
playwright install chromium
```

## Quick Start

### CLI

```bash
# Parse a BibTeX file
refchecker parse paper.bib

# Parse with JSON output
refchecker parse paper.bib --format json

# Verify citations
refchecker verify paper.bib

# Verify with specific adapters
refchecker verify paper.bib --adapters crossref,s2,aminer

# Export results to file
refchecker verify paper.bib --format csv --output results.csv
```

### GUI

```bash
# Launch the desktop application
refchecker-gui

# Or run directly
python -m refchecker.gui
```

1. Drag a `.bib` or `.txt` file into the window
2. Check/uncheck individual references to verify
3. Click **▶ Verify**
4. View results in the color-coded table
5. Click **📥 Export** to save as CSV, Excel, or BibTeX

### API Key Management

```bash
# Store an API key (encrypted via OS keyring)
refchecker set-key s2 your-api-key-here

# Check key status
refchecker get-key s2

# Delete a key
refchecker delete-key s2

# List all key statuses
refchecker list-keys
```

## Configuration

### API Keys (Optional)

RefChecker works without any API keys using free tiers. Adding keys unlocks higher rate limits:

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
# Override API keys (priority: env var > keyring > none)
export REFCHECKER_S2_API_KEY=your-key
export REFCHECKER_OPENALEX_API_KEY=your-key

# Proxy settings
export REFCHECKER_HTTP_PROXY=http://proxy:8080
export REFCHECKER_HTTPS_PROXY=https://proxy:443
```

### TOML Config File

Create a `refchecker.toml`:

```toml
[refchecker]
enabled_adapters = ["crossref", "s2", "openalex", "aminer", "baidu", "arxiv", "scholar"]
default_export_format = "csv"
```

## Architecture

```
src/refchecker/
├── cli/          # Click CLI interface
├── gui/          # PySide6 desktop GUI
│   ├── widgets/  # Custom Qt widgets (table, progress, file drop)
│   ├── workers/  # QThread background workers
│   └── dialogs/  # Settings, export, toast dialogs
├── core/         # Core verification engine
│   ├── models.py # Pydantic data models (ReferenceItem, VerificationResult)
│   ├── parser.py # BibTeX / GBT 7714 parser
│   ├── scorer.py # RapidFuzz fuzzy matching & scoring
│   ├── engine.py # Orchestration engine (parallel adapter queries)
│   ├── exporter.py # CSV/Excel/BibTeX export
│   ├── reporter.py # Markdown report generation
│   ├── cache.py  # Result caching (in-memory + file)
│   └── key_store.py # Encrypted API key storage via keyring
├── adapters/     # Verification source adapters
│   ├── base.py   # Abstract adapter with exponential backoff
│   ├── crossref_adapter.py
│   ├── s2_adapter.py
│   ├── openalex_adapter.py
│   ├── aminer_adapter.py
│   ├── baidu_adapter.py
│   ├── cnki_adapter.py
│   ├── arxiv_adapter.py
│   └── scholar_adapter.py
└── config.py     # Pydantic Settings configuration
```

### Verification Flow

1. **Parse** — BibTeX or GBT 7714 text → `list[ReferenceItem]`
2. **Query** — Each reference sent to all enabled adapters in parallel
3. **Score** — RapidFuzz composite score (title=0.5, author=0.3, year=0.1, venue=0.1)
4. **Classify** — Status determined by best composite score threshold
5. **Export** — Results exported to chosen format

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov --cov-report=term-missing

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Building & Distribution

### 构建独立可执行文件

PyInstaller 可将应用打包为独立可执行文件，用户无需安装 Python 即可运行。

```bash
pip install pyinstaller
pyinstaller refchecker.spec
```

| 平台 | 产物 | 说明 |
|------|------|------|
| macOS | `dist/RefChecker.app` | 双击打开，可拖入 Applications |
| Windows | `dist/RefChecker.exe` | 单文件 .exe，双击运行 |
| Linux | `dist/RefChecker` | 单文件二进制 |

### GitHub Actions CI/CD

推送代码后自动运行：
- **测试矩阵**：Ubuntu / macOS / Windows × Python 3.11 / 3.12
- **代码检查**：ruff lint
- **覆盖率**：codecov 上报
- **构建产物**：三个平台的可执行文件作为 Artifact 下载

## License

MIT
