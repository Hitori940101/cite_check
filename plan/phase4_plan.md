# Phase 4 开发计划 — Export, Polish & Testing

> **Created**: 2026-05-31 22:08 CST
> **Status**: 待执行
> **Prerequisite**: Phase 1-3 已完成 (146 tests passed)
> **Coverage Baseline**: **29%** (1426/1973 statements uncovered)

---

## 0. 开发规则（来自 CLAUDE.md）

| 规则 | 要求 |
|------|------|
| **逐功能提交** | 每完成一个功能 → 测试通过 → 立即 `git commit`，不允许攒多个功能变更 |
| **Conventional Commits** | `feat:`, `fix:`, `test:`, `docs:`, `perf:`, `refactor:` |
| **高峰期暂停** | 每日 14:00–18:00 禁止开发（3 倍计费），18:00 后恢复 |

---

## 1. 覆盖率现状分析

### 按模块覆盖率排名

#### 🟢 已达标 (≥80%)

| 模块 | Stmts | Cover | 测试文件 |
|------|-------|-------|----------|
| `s2_adapter.py` | 63 | **100%** | `test_s2_adapter.py` |
| `scorer.py` | 54 | **100%** | `test_scorer.py` |
| `models.py` | 108 | **98%** | `test_models.py` |
| `parser.py` | 125 | **90%** | `test_parser.py` |
| `engine.py` | 52 | **90%** | `test_adapters.py` |
| `key_store.py` | 65 | **88%** | `test_key_store.py` |

#### 🟡 部分覆盖 (50-79%)

| 模块 | Stmts | Cover | 未覆盖行 |
|------|-------|-------|----------|
| `base.py` | 77 | **74%** | retry 耗尽、异常分支、抽象方法 |
| `exceptions.py` | 16 | **75%** | 部分异常类未测 |
| `crossref_adapter.py` | 72 | **72%** | `query.bibliographic` 路径、错误处理 |
| `logging.py` | 17 | **41%** | 配置初始化路径 |

#### 🔴 零覆盖 (0%) — 主要缺口

| 模块 | Stmts | 优先级 | 说明 |
|------|-------|--------|------|
| `cli/main.py` | 207 | **P0** | CLI 全部命令未测 |
| `core/exporter.py` | 107 | **P0** | 导出功能虽已实现但无测试 |
| `config.py` | 38 | **P1** | 配置加载逻辑 |
| `adapters/aminer_adapter.py` | 81 | **P1** | AMiner 适配器 |
| `adapters/openalex_adapter.py` | 62 | **P1** | OpenAlex 适配器 |
| `adapters/baidu_adapter.py` | 57 | **P2** | 百度学术适配器 |
| `adapters/cnki_adapter.py` | 50 | **P2** | CNKI 适配器（Playwright） |
| GUI 全部文件 | 591 | **P2** | 11 个文件，已有 11 tests (headless skip) |

### 覆盖率缺口统计

```
已覆盖:  571 stmts (29%)
未覆盖: 1402 stmts (71%)

按优先级分解未覆盖代码:
  P0 (核心): cli 207 + exporter 107 = 314 stmts
  P1 (适配器): aminer 81 + openalex 62 + config 38 + base补齐 20 = 201 stmts
  P2 (其余): baidu 57 + cnki 50 + exceptions 4 + logging 10 + crossref补齐 20 = 141 stmts
  P3 (GUI): 591 stmts → 策略性跳过 headless 无法覆盖部分
```

---

## 2. 任务分解与执行顺序

> **原则**: 按依赖关系排序，先补核心模块测试，再做新功能，最后优化。

### Task 4.0: 覆盖率基线确认

**目标**: 确认当前覆盖率数据准确，排除配置问题

- [ ] 确认 `pyproject.toml` 中 `fail-under=80` 配置
- [ ] 确认 `.coveragerc` 或 `pyproject.toml` 的 omit 规则（排除 GUI headless 跳过部分）
- [ ] 输出当前覆盖率报告到 `plan/coverage_baseline.txt`

**Commit**: `chore: document coverage baseline for Phase 4`

---

### Task 4.1: Exporter 单元测试 (P0)

**目标**: `core/exporter.py` 107 stmts → ≥85%

**新增测试文件**: `tests/unit/test_exporter.py`

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_export_csv_basic` | CSV 基础导出，验证列头和行数据 |
| `test_export_csv_empty` | 空结果集处理 |
| `test_export_csv_chinese` | 中文字符编码 |
| `test_export_excel_basic` | Excel 基础导出，验证 sheet 结构 |
| `test_export_excel_color_coded` | 颜色编码（绿/黄/红/灰）映射 |
| `test_export_excel_summary_sheet` | 汇总统计 sheet |
| `test_export_bibtex_basic` | BibTeX 导出，验证条目格式 |
| `test_export_bibtex_filter_fabricated` | 过滤 Likely Fabricated 条目 |
| `test_export_bibtex_filter_suspicious` | 过滤 Suspicious 条目 |
| `test_export_unsupported_format` | 不支持的格式报错 |
| `test_export_file_write_error` | 文件写入失败处理 |
| `test_round_trip_bib` | 解析 → 验证 → 导出 BibTeX 往返 |

**预估测试数**: ~15 个
**Commit**: `test: add exporter unit tests (15 tests, ~90% coverage)`

---

### Task 4.2: Adapter 单元测试补齐 (P1)

**目标**: 补齐 aminer / openalex / baidu / cnki / crossref 适配器测试

#### 4.2.1 Crossref 适配器补齐

**文件**: `tests/unit/test_crossref_adapter.py` (新建)

| 测试用例 | 覆盖行 |
|----------|--------|
| `test_bibliographic_search` | `query.bibliographic` 路径 (L149-179) |
| `test_doi_lookup_not_found` | DOI 未找到的空结果处理 |
| `test_malformed_response` | 异常响应体处理 |
| `test_rate_limit_retry` | 429 状态码重试 |
| `test_multiple_results_scoring` | 多结果匹配取最高分 |

**预估**: ~8 个测试

#### 4.2.2 AMiner 适配器

**文件**: `tests/unit/test_aminer_adapter.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_search_by_title` | 标题搜索 |
| `test_search_by_title_and_author` | 标题+作者搜索 |
| `test_chinese_title_search` | 中文标题搜索 |
| `test_empty_results` | 空结果处理 |
| `test_api_error_handling` | API 错误处理 |
| `test_rate_limit_backoff` | 速率限制退避 |
| `test_result_parsing` | 结果解析和评分 |

**预估**: ~10 个测试

#### 4.2.3 OpenAlex 适配器

**文件**: `tests/unit/test_openalex_adapter.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_search_by_title` | 标题搜索 |
| `test_search_by_doi` | DOI 精确查询 |
| `test_filter_by_year` | 年份过滤 |
| `test_empty_results` | 空结果 |
| `test_api_error` | 错误处理 |
| `test_result_to_adapter_match` | 结果转换为 AdapterMatch |

**预估**: ~8 个测试

#### 4.2.4 Baidu Academic 适配器

**文件**: `tests/unit/test_baidu_adapter.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_search_basic` | 基础搜索 |
| `test_parse_search_results` | 搜索结果解析 |
| `test_chinese_results` | 中文结果解析 |
| `test_no_results` | 无结果 |
| `test_connection_error` | 连接错误 |
| `test_html_parsing_error` | HTML 解析异常 |

**预估**: ~8 个测试

#### 4.2.5 CNKI 适配器

**文件**: `tests/unit/test_cnki_adapter.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_search_basic` | Playwright 搜索 |
| `test_extract_results` | 结果提取 |
| `test_chinese_paper` | 中文论文 |
| `test_browser_launch_failure` | 浏览器启动失败 |
| `test_page_timeout` | 页面超时 |
| `test_cleanup_browser` | 资源清理 |

**预估**: ~6 个测试

**Commit (per adapter)**:
- `test: add Crossref adapter unit tests (8 tests)`
- `test: add AMiner adapter unit tests (10 tests)`
- `test: add OpenAlex adapter unit tests (8 tests)`
- `test: add Baidu Academic adapter unit tests (8 tests)`
- `test: add CNKI adapter unit tests (6 tests)`

---

### Task 4.3: Config + Logging + Exceptions 补齐 (P1)

**目标**: `config.py` (38 stmts) + `logging.py` (17 stmts) + `exceptions.py` 补齐

#### 4.3.1 Config 测试

**文件**: `tests/unit/test_config.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_default_config` | 默认配置值 |
| `test_env_override` | 环境变量覆盖 |
| `test_proxy_config` | 代理配置 |
| `test_adapter_toggles` | 适配器开关 |
| `test_api_key_resolution` | API Key 解析链 (env → store → None) |

**预估**: ~6 个测试

#### 4.3.2 Logging 测试

**文件**: 补充到 `tests/unit/test_logging.py` (新建)

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_setup_logging` | 日志初始化 |
| `test_json_output` | JSON 格式输出 |
| `test_log_levels` | 日志级别过滤 |

**预估**: ~4 个测试

#### 4.3.3 Exceptions 补齐

**文件**: 补充到 `tests/unit/test_models.py` 或新建 `test_exceptions.py`

| 测试用例 | 覆盖行 |
|----------|--------|
| `test_verification_error_str` | L36-37 |
| `test_adapter_timeout_str` | L54-55 |

**预估**: ~3 个测试

**Commits**:
- `test: add config unit tests (6 tests)`
- `test: add logging and exception unit tests (7 tests)`

---

### Task 4.4: CLI 单元测试 (P0)

**目标**: `cli/main.py` 207 stmts → ≥80%

**文件**: `tests/unit/test_cli.py` (新建)

使用 `click.testing.CliRunner` 进行 CLI 测试：

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_parse_bib_file` | `refchecker parse paper.bib` |
| `test_parse_txt_file` | GBT 7714 文本解析 |
| `test_parse_file_not_found` | 文件不存在报错 |
| `test_parse_unsupported_format` | 不支持的格式 |
| `test_verify_basic` | `refchecker verify paper.bib` |
| `test_verify_with_adapters` | `--adapters` 参数过滤 |
| `test_verify_output_json` | `--output json` 格式 |
| `test_set_key` | `refchecker set-key` |
| `test_get_key` | `refchecker get-key` |
| `test_delete_key` | `refchecker delete-key` |
| `test_list_keys` | `refchecker list-keys` |
| `test_key_not_found` | key 不存在的友好提示 |
| `test_help_output` | `--help` 输出 |
| `test_version_output` | `--version` 输出 |

**预估**: ~15 个测试

**Commit**: `test: add CLI unit tests (15 tests, ~85% coverage)`

---

### Task 4.5: Markdown 验证报告生成 (P0 新功能)

**目标**: 新增 `core/reporter.py`，生成结构化 Markdown 报告

**报告结构设计**:

```markdown
# 引用验证报告

> 生成时间: 2026-05-31 22:30 CST
> 来源文件: paper.bib
> 验证适配器: Crossref, Semantic Scholar, OpenAlex

## 摘要统计

| 状态 | 数量 | 占比 |
|------|------|------|
| ✅ 已验证 | 12 | 60% |
| ⚠️ 可疑 | 5 | 25% |
| ❌ 疑似虚构 | 2 | 10% |
| ℹ️ 无法验证 | 1 | 5% |

## 详细结果

### ✅ 已验证 (12)

| # | 标题 | 作者 | 年份 | 最高分数 | 验证来源 |
|---|------|------|------|----------|----------|
| 1 | Attention Is All You Need | Vaswani et al. | 2017 | 0.97 | Crossref, S2 |

### ❌ 疑似虚构 (2)

| # | 标题 | 作者 | 年份 | 最高分数 | 说明 |
|---|------|------|------|----------|------|
| 1 | ... | ... | ... | 0.23 | 所有适配器均未找到 |

## 建议操作

1. 重点关注 2 条疑似虚构引用，建议人工核查
2. 5 条可疑引用存在部分匹配，请确认作者/年份是否正确
```

**实现文件**: `src/refchecker/core/reporter.py`

**依赖**: `models.py` (VerificationResult), `engine.py`

**测试文件**: `tests/unit/test_reporter.py`

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_generate_basic_report` | 基础报告生成 |
| `test_empty_results` | 空结果报告 |
| `test_all_verified` | 全部验证通过 |
| `test_all_fabricated` | 全部疑似虚构 |
| `test_mixed_statuses` | 混合状态 |
| `test_chinese_characters` | 中文标题渲染 |
| `test_summary_statistics` | 统计数据准确性 |
| `test_markdown_formatting` | Markdown 格式合规性 |
| `test_file_output` | 文件写入 |

**预估**: ~10 个测试

**Commits**:
- `feat: add Markdown verification report generator`
- `test: add reporter unit tests (10 tests)`

---

### Task 4.6: 结果缓存层 (P1 性能优化)

**目标**: 新增 `core/cache.py`，避免重复验证相同引用

**设计**:

```
缓存策略:
- 内存缓存 (dict) — 进程内复用
- 文件缓存 (SQLite / JSON) — 跨会话复用（Phase 6 扩展点）
- 缓存 Key: (title_normalized, authors_normalized, year)
- TTL: 可配置，默认 7 天
- 缓存失效: --no-cache CLI 参数强制刷新
```

**实现文件**: `src/refchecker/core/cache.py`

**集成点**: `engine.py` — verify 前先查缓存

**测试文件**: `tests/unit/test_cache.py`

| 测试用例 | 覆盖功能 |
|----------|----------|
| `test_cache_hit` | 缓存命中 |
| `test_cache_miss` | 缓存未命中 |
| `test_cache_key_generation` | 缓存键生成（规范化） |
| `test_cache_ttl_expiry` | TTL 过期 |
| `test_cache_invalidation` | 缓存失效 |
| `test_cache_persist_and_load` | 持久化与加载 |
| `test_cache_chinese_title` | 中文标题缓存键 |

**预估**: ~8 个测试

**Commits**:
- `feat: add result caching layer with TTL support`
- `test: add cache unit tests (8 tests)`

---

### Task 4.7: GUI 测试补齐 (P2)

**目标**: GUI 模块覆盖率从 ~0% 提升到可接受水平

**策略**: 使用 `pytest-qt` + `QT_QPA_PLATFORM=offscreen` 在无头环境运行

**文件**: 补充 `tests/unit/test_gui.py`

| 测试用例 | 覆盖模块 |
|----------|----------|
| `test_main_window_creation` | `main_window.py` |
| `test_file_drop_accept_bib` | `file_drop.py` |
| `test_file_drop_reject_non_bib` | `file_drop.py` |
| `test_result_table_population` | `result_table.py` |
| `test_result_table_color_coding` | `result_table.py` |
| `test_progress_widget` | `progress.py` |
| `test_settings_dialog_open` | `settings.py` |
| `test_export_dialog_options` | `export.py` |
| `test_toast_notification` | `toast.py` |
| `test_verify_worker_signals` | `verify_worker.py` |
| `test_app_launch` | `app.py` |

**预估**: ~15 个测试（部分需 offscreen 模式）

**Commit**: `test: expand GUI tests with offscreen mode (15 tests)`

---

### Task 4.8: README 与文档 (P1)

**目标**: 完善项目文档

**文件清单**:

| 文件 | 内容 |
|------|------|
| `README.md` | 项目介绍、截图、安装、使用、贡献指南 |
| `docs/CLI.md` 或 README 内嵌 | CLI 命令详解 |
| `docs/GUI.md` 或 README 内嵌 | GUI 使用说明 |

**README 结构**:

```markdown
# RefChecker 🔍

> 学术论文引用验证工具 — 支持中英文文献

## 特性
- BibTeX / GBT 7714 解析
- 6 大数据源验证 (Crossref, S2, OpenAlex, AMiner, Baidu, CNKI)
- 模糊匹配评分 (RapidFuzz)
- 桌面 GUI + CLI 双模式
- 中文文献支持（AMiner 核心优势）
- API Key 可选，开箱即用

## 安装
## 快速开始 (CLI)
## 快速开始 (GUI)
## 验证状态说明
## 配置 (API Key)
## 导出格式
## 开发
## 致谢
## License
```

**Commit**: `docs: add README with installation and usage guide`

---

## 3. 执行时间线

```
Phase 4 预估: 5-7 个非高峰工作段（18:00-14:00 次日）

Session 1:  Task 4.0 (基线确认) + Task 4.1 (Exporter 测试)
            → 覆盖率: 29% → ~38%

Session 2:  Task 4.2.1-4.2.3 (Crossref/AMiner/OpenAlex 适配器测试)
            → 覆盖率: ~38% → ~52%

Session 3:  Task 4.2.4-4.2.5 (Baidu/CNKI 适配器测试) + Task 4.3 (Config/Logging/Exceptions)
            → 覆盖率: ~52% → ~62%

Session 4:  Task 4.4 (CLI 测试)
            → 覆盖率: ~62% → ~72%

Session 5:  Task 4.5 (Markdown 报告新功能)
            → 覆盖率: ~72% → ~75% (新增代码也需测试)

Session 6:  Task 4.6 (缓存层) + Task 4.8 (README)
            → 覆盖率: ~75% → ~80%+

Session 7:  Task 4.7 (GUI 测试补齐，如有余力)
            → 覆盖率进一步提升

每个 Session 结束条件: 所有新增测试通过 + 已 commit
```

---

## 4. 覆盖率提升预测

```
29%  ──── 基线 (Phase 3 完成时)
  │
  ├─ +Task 4.1 (Exporter)        → ~35%
  ├─ +Task 4.2 (Adapters)        → ~52%
  ├─ +Task 4.3 (Config/Log/Exc)  → ~57%
  ├─ +Task 4.4 (CLI)             → ~67%
  ├─ +Task 4.5 (Reporter)        → ~70%
  ├─ +Task 4.6 (Cache)           → ~73%
  ├─ +Task 4.7 (GUI)             → ~82%
  │
80%  ──── 目标线 ✅
  │
  └─ +Task 4.8 (文档，不计覆盖率)
```

> 注: 覆盖率百分比为估算值，实际取决于新增代码量和被测代码行数。关键策略是优先覆盖 P0 模块 (cli 207 + exporter 107 = 314 stmts)，这些贡献最大。

---

## 5. 已知风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| CNKI 适配器测试需要 Playwright | 测试环境依赖重 | Mock Playwright 对象，仅验证逻辑路径 |
| GUI 测试在 CI 无头环境不稳定 | 覆盖率波动 | `QT_QPA_PLATFORM=offscreen` + mark `@pytest.mark.gui` |
| 新增 Reporter/Cache 增加代码总量 | 分母变大可能压低覆盖率 | 新代码必须同步写测试，覆盖率要求同 ≥80% |
| 高峰期规则中断开发 | Session 可能跨天 | 每个 Task 独立 commit，中断不影响已完成工作 |

---

## 6. 完成标准

- [ ] `pytest --cov` 报告总覆盖率 ≥ 80%
- [ ] 所有 Phase 4 新功能有对应单元测试
- [ ] `refchecker report paper.bib` 生成 Markdown 报告
- [ ] 结果缓存减少重复验证开销
- [ ] README.md 完整可读
- [ ] DEV_STATUS.md 更新为 Phase 4 ✅
- [ ] 所有变更已 push 到远程仓库
