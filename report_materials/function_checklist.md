# 功能验证清单 (Function Checklist)

> 30000 条文档规模验证，所有功能均已在 CLI 和 Web 两端验证通过。

| # | 作业要求 | 实现模块 | 验证命令 | Web 展示位置 | 视频展示方式 |
|---|---------|---------|---------|------------|------------|
| 1 | 网页抓取 | `crawler/crawler.py`, `crawler/downloader.py` | `python run.py crawl --limit 30000 --fresh` | `/crawl-status` | 展示爬取状态页和数据统计 |
| 2 | 10万规模支持 | `crawler/crawler.py` (可配置limit参数) | `python run.py crawl --limit 100000 --resume` | `/crawl-status` | 展示limit配置和10万分阶段规划 |
| 3 | 多源校内网站 | `crawler/url_manager.py` (Round-Robin多源均衡, 30%配额), `config/seed_urls.json` (30个来源) | `python run.py stats` | `/stats` (来源分布表) | 展示36个来源，最大占比6.1%（远低于30%配额） |
| 4 | 倒排索引 | `indexer/build_index.py`, `search_engine/inverted_index.py` | `python run.py build-index` | `/stats` (词条数) | 展示30000条文档→19059标题词+245302正文词 |
| 5 | BM25排序 | `search_engine/bm25.py` (k1=1.5, b=0.75) | `pytest tests/test_bm25.py -v` | 搜索结果页（相关性分数） | 展示相同词在标题vs内容中的分数差异 |
| 6 | 普通查询 | `search_engine/search.py` → `search()` | `python run.py search "人工智能"` | 首页→搜索结果 | 展示搜索"人工智能"返回2940条结果 |
| 7 | 精确查询 | `search_engine/search.py` (exact match boost) | `python run.py search "南开大学" --type exact` | 搜索类型下拉→精确查询 | 展示标题精确匹配有额外加分 |
| 8 | 多关键词查询 | `search_engine/search.py` (multi type) | `python run.py search "研究生 复试" --type multi` | 搜索类型下拉→多关键词查询 | 展示含空格query自动切换multi类型 |
| 9 | AND/OR匹配 | `search_engine/search.py` (_get_candidates集合并/交) | `python run.py search "研究生 复试" --match-mode and` | 匹配模式下拉→AND/OR | 展示OR vs AND结果数量对比 |
| 10 | 通配符* | `search_engine/wildcard_search.py` (regex替换) | `python run.py search "奖学*" --type wildcard` | 搜索类型→通配查询 | 展示1184条结果，演示前缀通配功能 |
| 11 | 通配符? | `search_engine/wildcard_search.py` (单字符regex) | `python run.py search "研究??" --type wildcard` | 搜索类型→通配查询 | 展示2790条结果，演示?匹配单个字符 |
| 12 | 模糊查询 | `search_engine/fuzzy_search.py` (Levenshtein距离≤2) | `python run.py search "研宄生" --type fuzzy` | 搜索类型→模糊查询 | 展示1013条结果，演示"宄"→"究"形近字容错 |
| 13 | 文档查询 | `search_engine/search.py` → filters(file_type), `crawler/parser.py` → extract_attachment_links() | `python run.py search "申请表" --type doc` | 筛选→文档类型 | 展示939条结果中doc/docx/xlsx/PDF文档 |
| 14 | 文档下载 | `web/app.py` → /download/<doc_id>, `crawler/downloader.py` | 点击Web下载按钮 | 结果页→下载按钮 | 展示3365个文档附件的下载按钮并实际下载 |
| 15 | 查询日志 | `database/db.py` (SQLite), `web/app.py` → /logs | `python run.py web` → /logs | `/logs` | 展示查询日志表、热门查询排行 |
| 16 | 网页快照 | `crawler/snapshot.py`, `web/app.py` → /snapshot/<doc_id> | 点击Web快照按钮 | 结果页→查看快照按钮 | 展示快照页面，关键词高亮 |
| 17 | 个性化排序 | `search_engine/personalized_rank.py` (5个用户画像) | Web端切换用户画像 | 首页/结果页→用户画像下拉 | 对比默认用户 vs 研究人员 排序差异 |
| 18 | 搜索联想推荐 | `search_engine/suggest.py`, `web/static/js/suggest.js` | 在搜索框输入字符 | 首页/结果页→搜索框下拉 | 展示输入"南开"时的联想建议 |
| 19 | Web前端 | `web/app.py` (Flask), `web/templates/*.html` (Jinja2+Bootstrap5) | `python run.py web` | 全站 | 展示首页、搜索、结果、日志、统计、爬取状态页面 |
| 20 | 数据质量报告 | `crawler/utils.py` (run_data_validation, save_validation_report) | `python run.py validate-data` | `/stats` (数据质量报告区块) | 展示无标题0.0%/空正文0.7%/failed 4.1%等核心指标 |
| 21 | 爬取状态可视化 | `web/app.py` → /crawl-status, /api/crawl-status | `python run.py web` → /crawl-status | `/crawl-status` | 展示文档数、来源分布、parse_status分布、配额信息 |
| 22 | 来源/类型/时间筛选 | `web/templates/results.html` (左侧筛选栏), `search_engine/search.py` → _apply_filters() | 在结果页使用筛选 | 搜索结果页左侧筛选栏 | 展示来源下拉、文件类型下拉、日期选择 |

## 验证统计

| 类别 | 测试数 | 通过 | 备注 |
|------|--------|------|------|
| 单元测试 (pytest) | 45 | 45 ✅ | tests/test_*.py |
| CLI搜索验证 | 12 | 12 ✅ | 含AND/wildcard/fuzzy/doc |
| Web功能验证 | 11 | 11 ✅ | 首页/搜索/筛选/下载/快照/日志/统计/状态 |
| 数据质量指标 | 7 | 7 ✅ | content_quality failed 4.1% |
| **总计** | **75** | **75** | |

## 30000条数据质量指标

| 指标 | 值 | 目标 | 状态 |
|------|-----|------|------|
| 总文档数 | 30000 | — | ✅ |
| 无标题率 | 0.0% | <5% | ✅ |
| 空正文率 | 0.7% | <10% | ✅ |
| 最大source占比 | 6.1% | <30% | ✅ 远低于30%配额上限 |
| Document数量 | 3365 (11.2%) | >3000 | ✅ |
| content_quality good | 24597 (82.0%) | — | ✅ |
| content_quality failed | 1231 (4.1%) | <10% | ✅ |
| parse_status ok | 28771 (95.9%) | — | ✅ |
| 索引构建时间 | 82.6s | — | ✅ |
| 标题倒排词条数 | 19059 | — | ✅ |
| 正文倒排词条数 | 245302 | — | ✅ |
| 活跃来源数 | 36 | — | ✅ |
| pytest通过率 | 45/45 | 100% | ✅ |

## 10000→30000 关键改进

| 改进项 | 10000条 | 30000条 |
|--------|--------|---------|
| 总文档数 | 10000 | 30000 |
| 最大 source_site 占比 | 41.2%（主站） | 6.1%（均衡分布） |
| 活跃来源数 | 8 | 36 |
| 文档附件数 | 1564 (15.6%) | 3365 (11.2%) |
| content_quality failed | 523 (5.2%) | 1231 (4.1%) |
| parse_status ok | 9481 (94.8%) | 28771 (95.9%) |
| 索引构建时间 | 46.7s | 82.6s |
| 标题词条数 | 8595 | 19059 |
| 正文词条数 | 146963 | 245302 |
| MuPDF stderr | Python层抑制 | fd=2 os.dup2()彻底抑制 |
| 数据源均衡 | 8源（配额35%→30%） | 30种子URL→36活跃源（30%动态配额） |

## 30000条前优化（本次完成）

| 优化项 | 说明 | 状态 |
|--------|------|------|
| MuPDF C层stderr抑制 | os.dup2() fd=2重定向到日志文件 | ✅ |
| 多源扩充 | 从8个→30个来源（新增22个学院/部门子站） | ✅ |
| 均衡配额优化 | 默认30%配额，动态重分配，耗尽追踪 | ✅ |
| WordPress URL适配 | 校史网?p=NNNN模式识别 | ✅ |
| page_role误判修正 | 栏目名标题自动识别为list页 | ✅ |
| stats统计口径修正 | 区分最终入库统计/爬取过程统计 | ✅ |
| 演示查询优化 | 全部更新为30000条真实数据，模糊查询新增"研宄生"形近字演示 | ✅ |
| 低产出源处理 | 校史网/导师网标记optional，导师网自动适配 | ✅ |
