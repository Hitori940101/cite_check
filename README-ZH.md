# RefChecker

> 学术引用验证工具 — 支持中英文文献。

RefChecker 通过查询 Crossref、Semantic Scholar、OpenAlex、AMiner 等学术数据库，验证 `.bib` 文件或纯文本中的引用是否真实存在。使用模糊匹配对每条引用的匹配程度进行评分。

**核心优势**：通过 AMiner API（3 亿+ 论文）和百度学术提供强大的中文文献支持 — 这是其他开源工具所不具备的。

[**English Documentation**](./README.md)

## 功能特性

- **双界面**：桌面 GUI（PySide6）+ 命令行（CLI）
- **多格式解析**：BibTeX（`.bib`）和 GBT 7714-2015 纯文本
- **8 个验证数据源**：Crossref、Semantic Scholar、OpenAlex、AMiner、百度学术、CNKI、arXiv、Google Scholar
- **中文文献支持**：AMiner（主要）、百度学术（备用）、CNKI（Playwright）
- **模糊匹配**：基于 RapidFuzz 的综合评分（标题、作者、年份、期刊）
- **开箱即用**：免费 API 无需密钥；可选密钥解锁更高限额
- **导出格式**：CSV、彩色 Excel（`.xlsx`）、筛选后的 BibTeX、Markdown 报告
- **双语界面**：中文/英文运行时切换
- **增量显示**：结果逐条实时显示
- **后台验证**：QThread 工作线程，不阻塞界面

## 验证状态

| 状态 | 符号 | 含义 |
|------|------|------|
| 已验证 | ✅ | 在 ≥1 个来源中找到，综合评分 ≥ 0.85 |
| 可疑 | ⚠️ | 部分匹配，评分 0.60–0.84 |
| 疑似伪造 | ❌ | 未找到，评分 < 0.60 |
| 无法验证 | ℹ️ | 网络错误或来源不可用 |
| 待验证 | 🔄 | 尚未检查 |

## 安装

### 前置条件

安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda。

### macOS

```bash
# 1. 克隆仓库
git clone https://github.com/Hitori940101/cite_check.git
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
- 若遇到"无法打开，因为无法验证开发者"提示，前往 **系统设置 → 隐私与安全性**，点击"仍要打开"
- 确保 conda 环境中安装了 PySide6：`pip install PySide6`

**构建 macOS .app（可选）**：

```bash
pip install pyinstaller
pyinstaller refchecker.spec
# 产物在 dist/RefChecker.app
```

### Windows

```powershell
# 1. 克隆仓库
git clone https://github.com/Hitori940101/cite_check.git
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
# 产物在 dist\RefChecker.exe — 双击即可运行，无需 Python 环境
```

> **提示**：编译后的 `.exe` 可直接分发给没有 Python 环境的 Windows 用户。

### Linux

```bash
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui
```

### 可选：爬虫适配器

CNKI 支持需要无头浏览器：

```bash
pip install -e ".[scraping]"
playwright install chromium
```

## 快速开始

### 命令行

```bash
# 解析 BibTeX 文件
refchecker parse paper.bib

# 以 JSON 格式输出
refchecker parse paper.bib --format json

# 验证引用
refchecker verify paper.bib

# 指定数据源验证
refchecker verify paper.bib --adapters crossref,s2,aminer

# 导出结果到文件
refchecker verify paper.bib --format csv --output results.csv
```

### 图形界面

```bash
# 启动桌面应用
refchecker-gui

# 或直接运行
python -m refchecker.gui
```

1. 将 `.bib` 或 `.txt` 文件拖入窗口
2. 勾选/取消要验证的引用
3. 点击 **▶ 开始验证**
4. 在彩色表格中查看结果
5. 点击 **📥 导出** 保存为 CSV、Excel 或 BibTeX

### API 密钥管理

```bash
# 存储 API Key（通过系统密钥链加密）
refchecker set-key s2 your-api-key-here

# 查看 Key 状态
refchecker get-key s2

# 删除 Key
refchecker delete-key s2

# 列出所有 Key 状态
refchecker list-keys
```

## 配置

### API 密钥（可选）

RefChecker 无需任何 API 密钥即可使用免费版。添加密钥可解锁更高限额：

| 适配器 | 免费额度 | 带密钥 |
|--------|----------|--------|
| Crossref | 礼貌队列（mailto） | — |
| Semantic Scholar | 约 100 次/5 分钟 | 保证 1 次/秒 |
| OpenAlex | 1 万次/天 | 10 万次/天 |
| AMiner | 有免费额度 | 更高限额 |
| arXiv | 免费，无需密钥 | — |
| 百度学术 | 爬虫，无需密钥 | — |
| CNKI | 爬虫，无需密钥 | — |
| Scholar | 爬虫，无需密钥 | — |

密钥也可在 GUI 中通过 **⚙ 设置 → 数据源** 标签页设置。

### 环境变量

```bash
# 覆盖 API 密钥（优先级：环境变量 > 密钥链 > 无）
export REFCHECKER_S2_API_KEY=your-key
export REFCHECKER_OPENALEX_API_KEY=your-key

# 代理设置
export REFCHECKER_HTTP_PROXY=http://proxy:8080
export REFCHECKER_HTTPS_PROXY=https://proxy:443
```

### TOML 配置文件

创建 `refchecker.toml`：

```toml
[refchecker]
enabled_adapters = ["crossref", "s2", "openalex", "aminer", "baidu", "arxiv", "scholar"]
default_export_format = "csv"
```

## 架构

```
src/refchecker/
├── cli/          # Click 命令行界面
├── gui/          # PySide6 桌面 GUI
│   ├── widgets/  # 自定义 Qt 组件（表格、进度、文件拖放）
│   ├── workers/  # QThread 后台工作线程
│   └── dialogs/  # 设置、导出、提示对话框
├── core/         # 核心验证引擎
│   ├── models.py # Pydantic 数据模型（ReferenceItem, VerificationResult）
│   ├── parser.py # BibTeX / GBT 7714 解析器
│   ├── scorer.py # RapidFuzz 模糊匹配与评分
│   ├── engine.py # 编排引擎（并行适配器查询）
│   ├── exporter.py # CSV/Excel/BibTeX 导出
│   ├── reporter.py # Markdown 报告生成
│   ├── cache.py  # 结果缓存（内存 + 文件）
│   └── key_store.py # 加密 API 密钥存储
├── adapters/     # 验证数据源适配器
│   ├── base.py   # 抽象适配器（含指数退避）
│   ├── crossref_adapter.py
│   ├── s2_adapter.py
│   ├── openalex_adapter.py
│   ├── aminer_adapter.py
│   ├── baidu_adapter.py
│   ├── cnki_adapter.py
│   ├── arxiv_adapter.py
│   └── scholar_adapter.py
└── config.py     # Pydantic Settings 配置
```

### 验证流程

1. **解析** — BibTeX 或 GBT 7714 文本 → `list[ReferenceItem]`
2. **查询** — 每条引用并行发送到所有启用的适配器
3. **评分** — RapidFuzz 综合评分（标题=0.5，作者=0.3，年份=0.1，期刊=0.1）
4. **分类** — 根据最佳综合评分阈值确定状态
5. **导出** — 结果导出为所选格式

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行覆盖率
pytest --cov --cov-report=term-missing

# 代码检查
ruff check src/ tests/

# 类型检查
mypy src/
```

## 构建与分发

### 构建独立可执行文件

PyInstaller 将应用打包为独立可执行文件，用户无需安装 Python。

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

代码推送后自动运行：
- **测试矩阵**：Ubuntu × Python 3.11 / 3.12
- **代码检查**：ruff lint
- **覆盖率**：codecov 上报
- **构建产物**：Actions 标签页下载

## 许可证

MIT
