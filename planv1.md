# Cite Check — 项目规划 v1

## 1. 项目目标

构建一个学术引文自动检测系统，支持 LaTeX（.tex/.bib）和 Word（.docx）双格式输入，对论文引文进行四层自动化审查：

| 层级 | 功能 | 说明 |
|------|------|------|
| L1 格式验证 | 引用格式合规性检查 | 检查文中引用和参考文献是否符合指定格式规范（APA / IEEE / GB/T 7714 等） |
| L2 一致性检查 | 文内-文后交叉匹配 | 正文每个 citation 在参考文献列表中有对应条目，反之亦然 |
| L3 内容准确性 | 元数据验证 | 通过 Crossref / Semantic Scholar API 验证作者、年份、标题、期刊等元数据是否正确 |
| L4 完整性检测 | 学术质量分析 | 缺失引用检测、自引比例分析、引用年份分布、引用集中度评估 |

## 2. 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | |
| 包管理 | uv | |
| 后端框架 | FastAPI | 与 paper_check 保持一致 |
| 文档解析 | python-docx（Word）+ pybtex / bibtexparser（BibTeX） | |
| API 集成 | Crossref API + Semantic Scholar API | 免费、无需 API Key 即可基础使用 |
| 配置 | Hydra + OmegaConf | 多格式规范切换 |
| 测试 | pytest + pytest-cov | 目标覆盖率 ≥ 80% |
| 版本管理 | Git + Conventional Commits | |

## 3. 核心流程

```
输入文件 (.tex/.bib 或 .docx)
  │
  ├─ 解析器选择 ──→ LaTeXParser / DocxParser
  │                   │
  │                   ├─ 提取文中引用 (in-text citations)
  │                   └─ 提取参考文献列表 (reference list)
  │
  ├─ L1 格式验证 ──→ 格式规则引擎（APA / IEEE / GB-T-7714）
  │
  ├─ L2 一致性检查 → citation ↔ reference 双向匹配
  │
  ├─ L3 内容准确性 → API 查询 + 元数据比对
  │
  ├─ L4 完整性检测 → 统计分析 + 学术质量指标
  │
  └─ 生成报告 ──→ JSON / HTML 报告
```

## 4. 项目结构（规划）

```
cite_check/
├── src/
│   └── cite_check/
│       ├── __init__.py
│       ├── main.py                 # CLI / API 入口
│       ├── parsers/                # 文档解析层
│       │   ├── __init__.py         # Parser 工厂 & Registry
│       │   ├── base.py             # BaseParser 抽象类
│       │   ├── latex_parser.py     # LaTeX + BibTeX 解析
│       │   └── docx_parser.py      # Word 文档解析
│       ├── checkers/               # 四层检查引擎
│       │   ├── __init__.py         # Checker 工厂 & Registry
│       │   ├── base.py             # BaseChecker 抽象类
│       │   ├── format_checker.py   # L1: 格式验证
│       │   ├── consistency.py      # L2: 一致性检查
│       │   ├── accuracy.py         # L3: 内容准确性
│       │   └── completeness.py     # L4: 完整性检测
│       ├── schemas/                # 数据模型
│       │   ├── __init__.py
│       │   ├── citation.py         # Citation 数据类
│       │   └── report.py           # 检查报告数据类
│       ├── apis/                   # 外部 API 客户端
│       │   ├── __init__.py
│       │   ├── crossref.py         # Crossref API
│       │   └── semantic_scholar.py # Semantic Scholar API
│       ├── rules/                  # 格式规范定义
│       │   ├── __init__.py         # 规则注册
│       │   ├── apa.py
│       │   ├── ieee.py
│       │   └── gb_t_7714.py
│       └── reporters/              # 报告生成
│           ├── __init__.py
│           ├── json_reporter.py
│           └── html_reporter.py
├── tests/
│   ├── parsers/
│   ├── checkers/
│   └── conftest.py
├── conf/                           # Hydra 配置
│   └── config.yaml
├── pyproject.toml
├── CLAUDE.md
└── planv1.md
```

## 5. 开发阶段

### Phase 1: 基础骨架 + 解析层
- 项目骨架搭建（uv init, pyproject.toml, 目录结构）
- 数据模型定义（Citation, Reference, Report）
- LaTeX 解析器（.tex 中提取 citation, .bib 中提取 reference）
- Word 解析器（.docx 中提取 citation 和 reference）
- 解析器单元测试

### Phase 2: L1 格式验证
- 格式规则引擎（规则定义 + 验证逻辑）
- APA 格式规则实现
- IEEE 格式规则实现
- GB/T 7714 格式规则实现
- 格式检查器测试 + 样例文件

### Phase 3: L2 一致性检查
- citation ↔ reference 双向匹配算法
- 模糊匹配（处理拼写差异、缩写不一致等）
- 一致性检查器测试

### Phase 4: L3 内容准确性
- Crossref API 客户端（DOI 查询、元数据检索）
- Semantic Scholar API 客户端（补充查询）
- 元数据比对逻辑（作者、年份、标题、期刊名）
- API 客户端 mock 测试 + 集成测试

### Phase 5: L4 完整性检测
- 缺失引用检测启发式规则
- 自引比例分析
- 引用年份分布统计
- 引用集中度评估（过度依赖少数来源）
- 完整性检查器测试

### Phase 6: 报告 + CLI + API
- JSON / HTML 报告生成器
- CLI 入口（click / typer）
- FastAPI REST API（可选）
- 端到端测试

## 6. 约束

- 所有 API 调用必须有 rate limiting 和重试机制
- 所有 API 调用必须有离线/mock 回退，确保测试不依赖网络
- 每个功能完成后必须测试通过再 git commit
- 文件不超过 400 行，函数不超过 50 行
