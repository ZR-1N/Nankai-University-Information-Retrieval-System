"""
全局配置文件
"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_HTML_DIR = os.path.join(DATA_DIR, "raw_html")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
INDEX_DIR = os.path.join(DATA_DIR, "index")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.jsonl")
CRAWL_STATS_FILE = os.path.join(DATA_DIR, "crawl_stats.json")

# 配置目录
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SEED_URLS_FILE = os.path.join(CONFIG_DIR, "seed_urls.json")
STOPWORDS_FILE = os.path.join(CONFIG_DIR, "stopwords.txt")

# 数据库
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DB_FILE = os.path.join(DATABASE_DIR, "search_log.db")

# 爬虫设置
CRAWL_DELAY = 1.0  # 请求间隔（秒）
CRAWL_TIMEOUT = 15  # 请求超时（秒）
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "NankaiIR-Crawler/1.0 (Educational Project; contact: student@nankai.edu.cn)"
)
MAX_RETRIES = 3

# 索引设置
BM25_K1 = 1.5
BM25_B = 0.75
TITLE_WEIGHT = 3.0
CONTENT_WEIGHT = 1.0
SOURCE_WEIGHT = 1.2

# 搜索设置
DEFAULT_PAGE_SIZE = 20
MAX_SUGGEST_RESULTS = 10

# 确保目录存在
for d in [RAW_HTML_DIR, DOCUMENTS_DIR, SNAPSHOTS_DIR, INDEX_DIR]:
    os.makedirs(d, exist_ok=True)
