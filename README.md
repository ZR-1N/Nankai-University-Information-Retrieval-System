# 基于南开大学多源网站资源的校内信息检索系统

> 南开大学《信息检索系统原理》课程大作业

一个完整的 Web 信息检索系统，从南开大学相关网站爬取网页和文档资源，构建倒排索引，提供 BM25 排序的搜索服务，支持多种查询方式和个性化推荐。

---

## 功能清单

### 核心功能
- [x] **多源网站爬取** — 支持 8+ 个南开大学网站，可扩展
- [x] **网页解析** — HTML 标题/正文/时间提取，多种解析策略
- [x] **文档解析** — PDF (PyMuPDF)、DOCX (python-docx)、XLSX (openpyxl)
- [x] **中文分词** — jieba 分词 + 停用词过滤
- [x] **倒排索引** — 标题/正文双重倒排索引，支持 postings、DF
- [x] **BM25 排序** — 完整 BM25 实现，标题权重 3.0，正文权重 1.0

### 查询功能
- [x] **普通关键词查询** — jieba 分词后 OR/AND 检索
- [x] **精确查询** — 标题/URL/来源精确匹配加分
- [x] **多关键词查询** — 空格分隔，支持 AND/OR 模式切换
- [x] **通配查询** — `*` 匹配任意多个字符，`?` 匹配任意一个字符
- [x] **模糊查询** — 编辑距离 (Levenshtein Distance) + 查询扩展
- [x] **文档查询** — 搜索 PDF/DOC/DOCX/XLS/XLSX 等文档
- [x] **文档下载** — 搜索结果中提供下载按钮

### 高级功能
- [x] **查询日志** — SQLite 记录所有搜索，Web 页面查看
- [x] **网页快照** — 代表性页面保存 HTML 快照
- [x] **个性化排序** — 5 种用户画像（default/study/research/admission/news）
- [x] **搜索联想推荐** — 输入前缀时弹出推荐词下拉框
- [x] **高亮摘要** — 关键词 `<mark>` 高亮，智能片段截取
- [x] **结果筛选** — 按来源/文档类型/时间范围筛选
- [x] **结果分页** — 每页 20 条，支持翻页
- [x] **断点续爬** — URL 管理器支持 checkpoint 保存与恢复
- [x] **URL 去重** — URL 级别 + 内容哈希双重去重

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
│   ├── seed_urls.json          # 种子 URL 和网站配置
│   ├── settings.py             # 全局设置
│   └── stopwords.txt           # 中文停用词表
├── crawler/                    # 爬虫模块
│   ├── crawler.py              # 主爬虫 (BFS)
│   ├── parser.py               # HTML 解析器
│   ├── downloader.py           # HTTP 下载器
│   ├── url_manager.py          # URL 管理器
│   ├── snapshot.py             # 网页快照管理
│   └── utils.py                # 工具函数
├── data/                       # 数据目录
│   ├── raw_html/               # 原始 HTML 文件
│   ├── documents/              # 下载的文档文件
│   ├── snapshots/              # 网页快照
│   ├── index/                  # 索引文件
│   ├── metadata.jsonl          # 文档元数据
│   └── crawl_stats.json        # 爬取统计
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
├── run.py                      # 统一命令行入口
├── requirements.txt            # Python 依赖
└── README.md                   # 本文件
```

---

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
python run.py search "南开大学"

# 通配查询
python run.py search "南开*" --type wildcard

# 模糊查询
python run.py search "奖学今" --type fuzzy

# 个性化搜索
python run.py search "人工智能" --user research_user
```

---

## 爬取规模

| 阶段 | 命令 | 预计页面 | 用途 |
|------|------|---------|------|
| 小规模 | `--limit 100` | ~100 | 开发调试 |
| 中规模 | `--limit 1000` | ~1000 | 功能验证 |
| 大规模 | `--limit 10000` | ~10000 | 演示展示 |
| 完整 | `--limit 100000` | ~100000 | 最终提交 |

> 请先从 `--limit 100` 开始，确认系统正常运行后再扩大规模。

---

## 功能演示

### 各种查询类型

| 查询词 | 类型 | 说明 |
|--------|------|------|
| `南开大学` | normal | 普通关键词查询 |
| `奖学金 申请` | multi | 多关键词查询 |
| `南开大学计算机学院` | exact | 精确查询 |
| `南开*` | wildcard | `*` 通配符 |
| `202?年` | wildcard | `?` 通配符 |
| `奖学今` | fuzzy | 模糊查询（错别字） |

### 用户画像

- **默认用户 (default):** 按相关性排序
- **学习型用户 (study_user):** 偏好教务、课程、考试、奖学金
- **科研型用户 (research_user):** 偏好科研、项目、实验室、论文
- **招生型用户 (admission_user):** 偏好招生、推免、复试、调剂
- **新闻型用户 (news_user):** 偏好新闻、活动、学校动态

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

1. **南开大学主站** (www.nankai.edu.cn) — 新闻、院系、教学、科研
2. **计算机学院** (cc.nankai.edu.cn) — 通知、公告、招生、教学
3. **人工智能学院** (ai.nankai.edu.cn) — 动态、科研、招生
4. **教务部** (jwc.nankai.edu.cn) — 教务通知、附件
5. **研究生招生网** (yzb.nankai.edu.cn) — 硕博招生、推免
6. **新闻网** (news.nankai.edu.cn) — 南开要闻、媒体南开
7. **校史网** (xs.nankai.edu.cn) — 南开校史
8. **导师网** (nankai.teacher.360eol.com) — 扩展数据源

> 可在 `config/seed_urls.json` 中添加更多数据源。

---

## 演示视频建议流程

详见 [report_materials/video_script.md](report_materials/video_script.md)

1. 项目启动和首页展示
2. 爬取数据展示
3. 普通关键词查询
4. 多关键词查询
5. 精确查询
6. 文档查询与下载
7. 通配符 `*` 查询
8. 通配符 `?` 查询
9. 模糊查询
10. 网页快照
11. 查询日志
12. 个性化排序
13. 搜索联想推荐
14. 总结

---

## 注意事项

1. **先小规模爬取** — 先用 `--limit 100` 测试，再逐步扩大
2. **控制请求频率** — 默认请求间隔 1 秒，避免对学校网站造成压力
3. **断点续爬** — 大规模爬取时使用 `--resume` 参数
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

**Q: 如何增量爬取？**
```bash
python run.py crawl --limit 500 --resume
```

---

## License

MIT License — 仅供学习交流使用。
