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
git clone https://github.com/Hitori940101/cite_check.git
cd cite_check
conda env create -f environment.yml
conda activate refchecker
pip install -e ".[gui]"
refchecker-gui
```

**macOS 首次启动**：若遇到"无法验证开发者"提示，前往 **系统设置 → 隐私与安全性** → 点击"仍要打开"。

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

### 可选：CNKI 爬虫支持

```bash
pip install -e ".[scraping]"
playwright install chromium
```

## 快速开始

### 命令行

```bash
refchecker parse paper.bib                    # 解析 BibTeX 文件
refchecker parse paper.bib --format json      # JSON 输出
refchecker verify paper.bib                   # 验证引用
refchecker verify paper.bib --adapters crossref,s2,aminer  # 指定数据源
refchecker verify paper.bib --format csv --output results.csv  # 导出结果
```

### 图形界面

```bash
refchecker-gui    # 启动桌面应用
```

1. 将 `.bib` 或 `.txt` 文件拖入窗口
2. 勾选/取消要验证的引用
3. 点击 **▶ 开始验证**
4. 在彩色表格中查看结果
5. 点击 **📥 导出** 保存为 CSV、Excel 或 BibTeX

### API 密钥管理

```bash
refchecker set-key s2 your-api-key    # 存储密钥（系统密钥链加密）
refchecker get-key s2                 # 查看密钥状态
refchecker delete-key s2              # 删除密钥
refchecker list-keys                  # 列出所有密钥状态
```

## 配置

### API 密钥（可选）

RefChecker 无需任何密钥即可使用。添加密钥可解锁更高限额：

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
export REFCHECKER_S2_API_KEY=your-key
export REFCHECKER_HTTP_PROXY=http://proxy:8080
export REFCHECKER_HTTPS_PROXY=https://proxy:443
```

## 构建独立可执行文件

```bash
pip install pyinstaller
pyinstaller refchecker.spec
```

| 平台 | 产物 | 说明 |
|------|------|------|
| macOS | `dist/RefChecker.app` | 双击打开 |
| Windows | `dist/RefChecker.exe` | 单文件，无需 Python |
| Linux | `dist/RefChecker` | 单文件二进制 |

## 许可证

MIT
