# 基于南开大学多源网站资源的校内信息检索系统

> 南开大学《信息检索系统原理》课程大作业

一个完整的 Web 信息检索系统，从南开大学36个相关网站爬取10万级网页和文档资源，构建倒排索引，提供 BM25 排序的搜索服务，支持多种查询方式和个性化推荐。

---

## 功能清单

### 核心功能
- [x] **多源网站爬取** — 支持 30+ 个南开大学网站，Round-Robin 均衡爬取（30%动态配额）
- [x] **网页解析** — HTML 标题/正文/时间提取，多种解析策略
- [x] **文档解析** — PDF (PyMuPDF)、DOCX (python-docx)、XLSX (openpyxl)，MuPDF C层 stderr 通过 os.dup2() 抑制
- [x] **中文分词** — jieba 分词 + 停用词过滤
- [x] **倒排索引** — 标题/正文双重倒排索引，支持 postings、DF
- [x] **BM25 排序** — 完整 BM25 实现，标题权重 3.0，正文权重 1.0

### 查询功能
- [x] **普通关键词查询** — jieba 分词后 OR/AND 检索
- [x] **精确查询** — 标题/URL/来源精确匹配加分
- [x] **多关键词查询** — 空格分隔，支持 AND/OR 模式切换
- [x] **通配查询** — `*` 匹配任意多个字符，`?` 匹配任意一个字符
- [x] **模糊查询** — 编辑距离 (Levenshtein Distance) ≤ 2 + 查询扩展
- [x] **文档查询** — 搜索 PDF/DOC/DOCX/XLS/XLSX/ZIP/RAR/PPT 文档
- [x] **文档下载** — 搜索结果中提供下载按钮

### 高级功能
- [x] **查询日志** — SQLite 记录所有搜索，Web 页面查看
- [x] **网页快照** — 代表性页面保存 HTML 快照
- [x] **个性化排序** — 5 种用户画像（默认/本科生/研究生/教师研究人员/行政人员）
- [x] **搜索联想推荐** — 输入前缀时弹出推荐词下拉框
- [x] **高亮摘要** — 关键词 `<mark>` 高亮，智能片段截取
- [x] **结果筛选** — 按来源/文档类型/时间范围筛选
- [x] **结果分页** — 每页 20 条，支持翻页
- [x] **断点续爬** — URL 管理器支持 checkpoint 保存与恢复
- [x] **URL 去重** — URL 级别 + 内容哈希双重去重

---

## 最终数据规模（100000 条）

| 指标 | 值 |
|------|-----|
| 总文档数 | 100000 |
| HTML 页面 | 94853 |
| 文档附件（PDF/DOC/DOCX/XLS等） | 5147 (5.1%) |
| 活跃数据源 | 36 个南开大学网站 |
| 无标题率 | 0.0% |
| 空正文率 | 0.3% |
| content_quality good | 82661 (82.7%) |
| content_quality failed | 1667 (1.7%) |
| parse_status ok | 98023 (98.0%) |
| 索引词条（标题+正文） | 32983 + 367979 |
| 短正文率（<100字） | 12.7% |
| content_quality short | 15632 (15.6%) |
| 索引构建时间 | 240.5s |
| 爬取耗时 | 约 20.4 小时 |
| 爬取速度 | 1.36 页/秒 |
| 测试通过率 | 45/45 |

> **关于"短正文率"与 "content_quality short" 的区别**：  
> "短正文（<100字）"是 `validate-data` 中按正文长度阈值统计的客观指标（12741 条，12.7%）；  
> `content_quality=short` 是内容质量分类结果（15632 条，15.6%），除长度外还结合文档类型、解析状态等因素，因此两者数值不完全相同。

### 文档附件分布

| 格式 | PDF | DOC | DOCX | XLS | XLSX | ZIP | RAR | PPT | 合计 |
|------|-----|-----|------|-----|------|-----|-----|-----|------|
| 数量 | 1449 | 1208 | 1262 | 268 | 556 | 195 | 156 | 53 | 5147 |

### 来源分布（Top 10）

| 来源 | 文档数 | 占比 |
|------|--------|------|
| 南开大学新闻网 | 41431 | 41.4% |
| 周恩来政府管理学院 | 9053 | 9.1% |
| 化学学院 | 6743 | 6.7% |
| 商学院 | 5784 | 5.8% |
| 南开大学主站 | 5165 | 5.2% |
| 人工智能学院 | 4033 | 4.0% |
| 软件学院 | 3144 | 3.1% |
| 就业指导中心 | 3133 | 3.1% |
| 经济学院 | 3128 | 3.1% |
| 医学院 | 2858 | 2.9% |
| 其他 26 个来源 | 14528 | 14.5% |

> **关于最大来源占比**：30000 条阶段最大来源占比为 6.1%，说明多源均衡策略在中等规模下效果良好；继续扩展到 100000 条后，部分学院网站队列逐渐耗尽，南开新闻网作为内容量最大的公共新闻源占比提升至 41.4%。系统仍保留 36 个南开相关来源，并达到 100000 条有效资源规模。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| Web 框架 | Flask + Jinja2 |
| 前端 | Bootstrap 5 + 原生 JS |
| 中文分词 | jieba |
| HTTP 请求 | requests |
| HTML 解析 | BeautifulSoup4 + lxml |
| PDF 解析 | PyMuPDF / pdfplumber |
| DOCX 解析 | python-docx |
| XLSX 解析 | openpyxl |
| 数据库 | SQLite3 |
| 排序算法 | BM25 (自实现) |
| 索引结构 | 倒排索引 (自实现) |

**无外部服务依赖** — 不需要 Elasticsearch、Docker、Redis。

---

## 目录结构

```
├── config/                     # 配置文件
│   ├── seed_urls.json          # 种子 URL 和网站配置（30个来源）
│   ├── settings.py             # 全局设置
│   └── stopwords.txt           # 中文停用词表
├── crawler/                    # 爬虫模块
│   ├── crawler.py              # 主爬虫 (BFS + 多源均衡)
│   ├── parser.py               # HTML 解析器
│   ├── downloader.py           # HTTP 下载器
│   ├── url_manager.py          # URL 管理器（Round-Robin + 动态配额）
│   ├── snapshot.py             # 网页快照管理
│   └── utils.py                # 工具函数 + 数据质量验证
├── data/                       # 数据目录
│   ├── raw_html/               # 原始 HTML 文件
│   ├── documents/              # 下载的文档文件
│   ├── snapshots/              # 网页快照
│   ├── index/                  # 索引文件（100000 条）
│   ├── metadata.jsonl          # 文档元数据（最终入库统计权威来源）
│   └── crawl_stats.json        # 爬取统计（含过程统计）
├── indexer/                    # 索引构建模块
│   ├── preprocess.py           # 文本预处理（分词）
│   └── build_index.py          # 构建倒排索引
├── search_engine/              # 搜索引擎核心
│   ├── inverted_index.py       # 倒排索引查询
│   ├── bm25.py                 # BM25 排序算法
│   ├── search.py               # 搜索引擎入口
│   ├── wildcard_search.py      # 通配符查询
│   ├── fuzzy_search.py         # 模糊查询
│   ├── personalized_rank.py    # 个性化排序
│   ├── suggest.py              # 搜索联想推荐
│   └── highlight.py            # 关键词高亮
├── database/                   # 数据库模块
│   ├── init_db.py              # 数据库初始化
│   └── db.py                   # 数据库操作
├── web/                        # Web 前端
│   ├── app.py                  # Flask 应用
│   ├── templates/              # Jinja2 模板
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── results.html
│   │   └── logs.html
│   └── static/
│       ├── css/style.css
│       └── js/suggest.js
├── tests/                      # 测试文件
├── scripts/                    # 辅助脚本
├── report_materials/           # 报告材料
├── logs/                       # 日志文件
├── run.py                      # 统一命令行入口
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

> ⚠️ 说明：由于完整 100000 条爬取数据、网页快照、文档附件和索引文件体积较大（~350MB），仓库默认不上传完整运行数据。  
> 本项目已在本地完成 100000 条真实南开资源的爬取、索引和验证；老师或助教 clone 仓库后，可按以下命令进行小规模复现，也可使用 `--resume` / `--limit` 逐步扩展到更大规模。

## 快速开始

### 1. 环境安装

```bash
pip install -r requirements.txt
```

### 2. 小规模爬取

```bash
# 爬取 100 个页面（约 2-3 分钟）
python run.py crawl --limit 100

# 查看统计
python run.py stats
```

### 3. 构建索引

```bash
python run.py build-index
```

### 4. 启动 Web 服务

```bash
python run.py web
```

浏览器打开 http://127.0.0.1:5000

### 5. 命令行搜索

```bash
# 普通查询
python run.py search "人工智能"

# 通配查询
python run.py search "奖学*" --type wildcard

# 模糊查询
python run.py search "奖学今" --type fuzzy

# AND 多关键词
python run.py search "研究生 复试" --match-mode and

# 个性化搜索
python run.py search "实验室" --user research_user
```

---

## 爬取规模

| 阶段 | 命令 | 页面数 | 状态 |
|------|------|---------|------|
| 小规模 | `--limit 100` | ~100 | ✅ |
| 中规模 | `--limit 1000` | ~1000 | ✅ |
| 大规模 | `--limit 10000` | ~10000 | ✅ |
| 完整验证 | `--limit 30000 --fresh` | ~30000 | ✅ |
| 最终提交 | `--limit 100000 --resume` | 100000 | ✅ 已完成 |

### 最终验证命令

```bash
python run.py validate-data
python run.py build-index
python run.py stats
pytest tests/ -v
```

### 续爬原理

- `--resume` 从 checkpoint 文件恢复 URL 队列
- `self.counter = len(existing)` — 从 metadata.jsonl 现有文档数开始计数
- `while self.counter < self.limit` — 继续爬取直到总量达标
- 每 50 个文档自动保存一次 checkpoint，支持多次中断续爬
- `--resume --limit 100000` 表示从当前已有数据继续爬取，直到总文档数达到 100000

---

## 功能演示

### 各种查询类型（100000 条索引）

| 查询词 | 类型 | 结果数 | 说明 |
|--------|------|--------|------|
| `人工智能` | normal | 7065 | 普通关键词查询 |
| `奖学金 申请` | multi (AND) | 856 | AND 精准过滤 |
| `研究生 复试` | multi (AND) | 1184 | 多关键词取交集 |
| `奖学*` | wildcard | 2744 | `*` 通配符前缀匹配 |
| `研究??` | wildcard | 6061 | `?` 单字符通配 |
| `奖学今` | fuzzy | 346 | 错字容错（"今"→"金"） |
| `奖学斤` | fuzzy | 86 | 同音字容错（"斤"→"金"） |
| `奖学今` | fuzzy | 346 | 错字容错（"今"→"金"） |
| `奖学斤` | fuzzy | 86 | 同音字容错（"斤"→"金"） |

### 用户画像

- **默认用户 (default):** 按相关性排序
- **本科生 (study_user):** 偏好教务、课程、考试、奖学金
- **研究生 (research_user):** 偏好科研、项目、实验室、论文
- **教师研究人员 (researcher_user):** 偏好科研、项目、成果、团队
- **行政人员 (admin_user):** 偏好通知、公告、人事、财务

---

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 单独运行
pytest tests/test_wildcard.py -v
pytest tests/test_fuzzy.py -v
pytest tests/test_bm25.py -v
pytest tests/test_search.py -v
```

---

## 数据源

系统覆盖南开大学以下网站（30 个 seed URL，运行时扩展至 36 个活跃源）：

**学部/学院：**
数学科学学院、物理科学学院、化学学院、生命科学学院、环境科学与工程学院、
医学院、药学院、经济学院、商学院、金融学院、软件学院、网络空间安全学院、
电子信息与光学工程学院、材料科学与工程学院、统计与数据科学学院、
文学院、历史学院、哲学院、外国语学院、法学院、周恩来政府管理学院、
旅游与服务学院、国际教育学院、汉语言文化学院

**直属/职能部门：**
南开大学主站、新闻网、计算机学院、人工智能学院、教务部、研究生招生网、
校史网、导师网、图书馆、人事处、国际合作与交流处、就业指导中心

> 可在 `config/seed_urls.json` 中添加更多数据源。

---

## 统计口径说明

| 统计类别 | 数据来源 | 内容 |
|---------|---------|------|
| 最终入库统计 | `metadata.jsonl`（实时计算） | 总文档数、文件类型分布、source分布、page_role分布、content_quality分布、parse_status分布 |
| 爬取过程统计 | `crawl_stats.json`（爬虫运行时记录，被 `compute_stats()` 保留） | 失败URL数（1708）、重复页面数（6073）、爬取耗时（20.4h）、平均速度（1.36页/秒） |
| 索引统计 | `data/index/index_stats.json` | 文档数（100000）、词条数（32983+367979）、构建时间（240.5s） |

> **注意**：爬取过程统计中的失败/重复 URL 不计入最终有效文档数。最终入库统计以 `metadata.jsonl` 为准。

---

## 演示视频建议流程

详见 [report_materials/video_script.md](report_materials/video_script.md)

1. 项目简介
2. 100000 条数据统计展示
3. 多源数据和文件类型分布展示
4. 普通查询：人工智能（7065条）
5. 多关键词 AND：研究生 复试（1184条）
6. 文档查询：申请表 / 培养方案
7. 通配符查询：奖学* / 研究??
8. 模糊查询：奖学今 / 奖学斤
9. 文档下载
10. 网页快照
11. 查询日志
12. 个性化排序
13. 搜索联想推荐
14. 数据质量报告
15. CLI 验证与测试
16. 总结

---

## 注意事项

1. **先小规模爬取** — 先用 `--limit 100` 测试，再逐步扩大
2. **控制请求频率** — 默认请求间隔 1 秒，避免对学校网站造成压力
3. **断点续爬** — 大规模爬取时使用 `--resume` 参数，支持多次中断续爬
4. **快照保存** — 仅对前 50 个代表性页面保存快照
5. **索引持久化** — 索引构建后自动持久化，重启 Web 不需要重建
6. **扩展数据源** — 可以随时在 `config/seed_urls.json` 中添加新的种子 URL

---

## 常见问题

**Q: 提示 "索引未构建"？**
```bash
python run.py build-index
```

**Q: 如何继续添加新的网站？**
编辑 `config/seed_urls.json`，在 `sources` 数组中添加新条目。

**Q: 如何从当前数据继续爬到更大规模？**
```bash
# 从当前已有数据继续爬到 100000
python run.py crawl --limit 100000 --resume 2>&1 | tee logs/crawl_100000.log
```

**Q: `--resume --limit 100000` 和 `--limit 100000 --fresh` 的区别？**
- `--resume`: 从已有 checkpoint 恢复，从当前文档数继续爬到总量 100000（补足模式）
- `--fresh`: 清除所有旧数据，从零开始爬取 100000 条

---

## License

MIT License — 仅供学习交流使用。
