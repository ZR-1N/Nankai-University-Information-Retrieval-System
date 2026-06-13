"""
索引构建模块 - 建立倒排索引并持久化
"""
import json
import os
import pickle
import time
from collections import defaultdict
from tqdm import tqdm

from config.settings import METADATA_FILE, INDEX_DIR
from indexer.preprocess import get_processor


class IndexBuilder:
    """
    索引构建器
    - 读取 metadata.jsonl
    - 对标题和正文进行分词
    - 构建倒排索引
    - 持久化到 data/index/
    """

    def __init__(self):
        self.processor = get_processor()
        self.metadata = []
        # 倒排索引: term -> {doc_id: term_freq}
        self.title_index: dict[str, dict[str, int]] = defaultdict(dict)
        self.content_index: dict[str, dict[str, int]] = defaultdict(dict)
        # 文档长度 (用于 BM25)
        self.doc_lengths: dict[str, dict] = {}  # doc_id -> {"title_len": int, "content_len": int}
        self.doc_count = 0
        # 文档元数据缓存
        self.doc_meta: dict[str, dict] = {}  # doc_id -> metadata
        # 词条的文档频率
        self.title_df: dict[str, int] = defaultdict(int)
        self.content_df: dict[str, int] = defaultdict(int)

    def run(self):
        """执行索引构建"""
        print("加载元数据...")
        self._load_metadata()

        if not self.metadata:
            print("错误: 没有元数据。请先运行爬虫: python run.py crawl --limit 100")
            return

        self.doc_count = len(self.metadata)
        print(f"共 {self.doc_count} 条文档，开始构建索引...")

        start_time = time.time()

        # 对每个文档进行分词和索引
        for doc in tqdm(self.metadata, desc="构建索引"):
            self._index_document(doc)

        # 保存索引
        print("保存索引文件...")
        self._save_index()

        elapsed = time.time() - start_time
        print(f"索引构建完成！耗时 {elapsed:.1f}s")
        print(f"  文档数: {self.doc_count}")
        print(f"  标题倒排词条数: {len(self.title_index)}")
        print(f"  正文倒排词条数: {len(self.content_index)}")

    def _load_metadata(self):
        """加载元数据"""
        if not os.path.exists(METADATA_FILE):
            return
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self.metadata.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    def _index_document(self, doc: dict):
        """为单个文档建立索引"""
        doc_id = doc["doc_id"]
        title = doc.get("title", "")
        content = doc.get("content", "")
        source_site = doc.get("source_site", "")

        # 分词
        title_terms = self.processor.tokenize_title(title)
        content_terms = self.processor.tokenize_content(content)
        source_terms = self.processor.tokenize(source_site)  # 来源也加入索引

        # 标题倒排索引
        for term in title_terms:
            self.title_index[term][doc_id] = self.title_index[term].get(doc_id, 0) + 1
            self.title_df[term] = len(self.title_index[term])

        # 把来源词也加入标题索引（用于来源检索）
        for term in source_terms:
            self.title_index[term][doc_id] = self.title_index[term].get(doc_id, 0) + 1
            self.title_df[term] = len(self.title_index[term])

        # 正文倒排索引
        for term in content_terms:
            self.content_index[term][doc_id] = self.content_index[term].get(doc_id, 0) + 1
            self.content_df[term] = len(self.content_index[term])

        # 记录文档长度
        self.doc_lengths[doc_id] = {
            "title_len": len(title_terms),
            "content_len": len(content_terms),
        }

        # 缓存元数据
        self.doc_meta[doc_id] = doc

    def _save_index(self):
        """持久化索引到磁盘"""
        os.makedirs(INDEX_DIR, exist_ok=True)

        # 使用 pickle 保存（快速序列化）
        index_data = {
            "title_index": dict(self.title_index),
            "content_index": dict(self.content_index),
            "title_df": dict(self.title_df),
            "content_df": dict(self.content_df),
            "doc_lengths": self.doc_lengths,
            "doc_count": self.doc_count,
            "doc_meta": self.doc_meta,
        }

        # 分文件保存（大索引可能需要拆分）
        with open(os.path.join(INDEX_DIR, "index.pkl"), "wb") as f:
            pickle.dump(index_data, f, protocol=pickle.HIGHEST_PROTOCOL)

        # 同时保存 JSON 格式的统计信息
        stats = {
            "doc_count": self.doc_count,
            "term_count": len(self.content_index),
            "title_term_count": len(self.title_index),
        }
        with open(os.path.join(INDEX_DIR, "index_stats.json"), "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_index(cls) -> dict | None:
        """加载已构建的索引"""
        index_path = os.path.join(INDEX_DIR, "index.pkl")
        if not os.path.exists(index_path):
            return None
        with open(index_path, "rb") as f:
            return pickle.load(f)
