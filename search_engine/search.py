"""
搜索引擎核心 - 整合倒排索引、BM25、通配、模糊、个性化排序
v3.0.0：通配查询修复 + AND 模式优化 + 导航噪声降权

支持查询类型:
  - normal: 普通关键词查询 (默认 AND 如果含空格)
  - exact: 精确匹配查询
  - multi: 多关键词查询 (AND/OR)
  - wildcard: 通配符查询 (* / ?)
  - fuzzy: 模糊查询
  - doc: 文档类型查询
"""
import time
import math
from search_engine.inverted_index import InvertedIndex
from search_engine.bm25 import BM25Scorer
from search_engine.wildcard_search import WildcardSearch
from search_engine.fuzzy_search import FuzzySearch
from search_engine.personalized_rank import PersonalizedRanker
from search_engine.highlight import (
    generate_snippet, generate_title_highlight, extract_match_explanation,
)
from indexer.preprocess import get_processor


class SearchEngine:
    """搜索引擎主类"""

    def __init__(self):
        self.processor = get_processor()
        self.index = InvertedIndex()
        self.scorer = None
        self.wildcard_search = None
        self.fuzzy_search = None
        self._initialized = False

    def _ensure_initialized(self):
        """确保索引已加载"""
        if self._initialized:
            return
        if not self.index.load():
            raise RuntimeError(
                "索引未构建。请先运行: python run.py build-index"
            )
        self.scorer = BM25Scorer(self.index)
        self.wildcard_search = WildcardSearch(self.index)
        self.fuzzy_search = FuzzySearch(self.index)
        self._initialized = True

    def search(self, query: str, search_type: str = "normal",
               user_id: str = "default", page: int = 1,
               page_size: int = 20,
               filters: dict = None,
               match_mode: str = "or") -> dict:
        """
        执行搜索

        参数:
            query: 查询字符串
            search_type: 查询类型 (normal/exact/multi/wildcard/fuzzy/doc)
            user_id: 用户画像 ID
            page: 页码（从1开始）
            page_size: 每页结果数
            filters: 筛选项
            match_mode: 多关键词匹配模式 ("or" / "and")

        返回:
            {
                "query": str,
                "search_type": str,
                "user_id": str,
                "total": int,
                "page": int,
                "page_size": int,
                "total_pages": int,
                "elapsed": float,
                "results": [doc_dict, ...],
                "matched_terms": [str, ...],
                "fuzzy_expansions": [str, ...]
            }
        """
        self._ensure_initialized()
        start_time = time.time()

        # 智能 match_mode 推断：如果含空格且未显式指定 OR，默认用 AND
        if " " in query and match_mode == "or" and search_type in ("normal", "multi"):
            match_mode = "and"

        # 处理查询词
        query_terms, wildcard_terms, fuzzy_expansions = self._process_query(
            query, search_type
        )

        # 收集候选文档
        candidate_docs = self._get_candidates(
            query_terms, wildcard_terms, match_mode, search_type
        )

        # 如果没有候选文档，返回空结果
        if not candidate_docs:
            elapsed = time.time() - start_time
            return {
                "query": query,
                "search_type": search_type,
                "user_id": user_id,
                "user_profile_name": "默认用户",
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "elapsed": round(elapsed, 3),
                "results": [],
                "matched_terms": query_terms + wildcard_terms,
                "fuzzy_expansions": fuzzy_expansions,
                "match_mode": match_mode,
            }

        # BM25 评分
        scored_docs = self._score_documents(candidate_docs, query_terms, wildcard_terms)

        # 精确匹配加分
        if search_type == "exact" or search_type == "multi":
            scored_docs = self._add_exact_match_boost(scored_docs, query)

        # 应用筛选
        if filters:
            scored_docs = self._apply_filters(scored_docs, filters)

        # 个性化排序
        ranker = PersonalizedRanker(user_id)
        scored_docs = ranker.rerank(scored_docs)

        # 导航噪声降权
        scored_docs = self._nav_noise_penalty(scored_docs)

        # 分页
        total = len(scored_docs)
        total_pages = max(1, math.ceil(total / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_results = scored_docs[start_idx:end_idx]

        # 生成高亮摘要
        all_terms = query_terms + wildcard_terms + fuzzy_expansions
        enriched_results = []
        for doc in page_results:
            enriched = self._enrich_result(doc, all_terms)
            enriched_results.append(enriched)

        elapsed = time.time() - start_time

        return {
            "query": query,
            "search_type": search_type,
            "user_id": user_id,
            "user_profile_name": ranker.profile.get("name", "默认用户"),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "elapsed": round(elapsed, 3),
            "results": enriched_results,
            "matched_terms": query_terms + wildcard_terms,
            "fuzzy_expansions": fuzzy_expansions,
            "match_mode": match_mode,
        }

    def _process_query(self, query: str, search_type: str) -> tuple:
        """处理查询，返回 (query_terms, wildcard_terms, fuzzy_expansions)"""
        query_terms = []
        wildcard_terms = []
        fuzzy_expansions = []

        if search_type == "wildcard":
            # 通配查询：只在索引词条中匹配，不进行分词
            if self.wildcard_search is None:
                self.wildcard_search = WildcardSearch(self.index)
            wildcard_terms = self.wildcard_search.match_terms(query)
            # 修复：通配查询没有匹配词时，不 fallback 到分词
            # 直接返回空 wildcard_terms，后续逻辑会返回空结果
        elif search_type == "fuzzy":
            # 模糊查询
            raw_terms = self.processor.tokenize(query)
            query_terms = raw_terms
            if self.fuzzy_search is None:
                self.fuzzy_search = FuzzySearch(self.index)
            fuzzy_expansions = self.fuzzy_search.expand_query(raw_terms)
        else:
            # 普通/精确/多关键词/文档查询
            query_terms = self.processor.tokenize(query)

        return query_terms, wildcard_terms, fuzzy_expansions

    def _get_candidates(self, query_terms: list[str],
                        wildcard_terms: list[str],
                        match_mode: str,
                        search_type: str = "normal") -> set[str]:
        """
        获取候选文档集合
        修复：wildcard 模式没有匹配词时返回空集，不返回全量
        """
        all_terms = query_terms + wildcard_terms

        # 修复：无有效查询词时，如果是 wildcard 类型返回空集
        if not all_terms:
            if search_type == "wildcard":
                return set()
            # 其他类型也无词时，返回空
            return set()

        if match_mode == "and":
            # AND 模式：所有词都必须出现
            doc_sets = []
            for term in all_terms:
                docs = set()
                docs.update(self.index.get_title_postings(term).keys())
                docs.update(self.index.get_content_postings(term).keys())
                if docs:
                    doc_sets.append(docs)

            if not doc_sets:
                return set()

            candidates = doc_sets[0]
            for ds in doc_sets[1:]:
                candidates = candidates & ds
            return candidates
        else:
            # OR 模式：任一关键词出现即可
            candidates = set()
            for term in all_terms:
                candidates.update(self.index.get_title_postings(term).keys())
                candidates.update(self.index.get_content_postings(term).keys())
            return candidates

    def _score_documents(self, candidate_docs: set[str],
                         query_terms: list[str],
                         wildcard_terms: list[str]) -> list[dict]:
        """对候选文档进行 BM25 评分"""
        all_terms = query_terms + wildcard_terms
        scored = []

        for doc_id in candidate_docs:
            meta = self.index.get_doc_meta(doc_id)
            if meta is None:
                continue

            bm25_score = self.scorer.score(
                all_terms, doc_id,
                title_weight=3.0,
                content_weight=1.0,
            )

            # 只有 BM25 > 0 才加入结果（修复：过滤零分文档）
            if bm25_score <= 0 and not query_terms:
                continue

            # 时间新鲜度加成
            recency_boost = self._compute_recency_boost(meta)

            # 来源加成
            source_boost = self._compute_source_boost(meta)

            doc_copy = dict(meta)
            doc_copy["score"] = round(bm25_score + recency_boost + source_boost, 4)
            doc_copy["bm25_score"] = round(bm25_score, 4)
            doc_copy["recency_boost"] = round(recency_boost, 4)
            doc_copy["source_boost"] = round(source_boost, 4)

            scored.append(doc_copy)

        # 按分数降序
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _add_exact_match_boost(self, results: list[dict], query: str) -> list[dict]:
        """精确匹配加成"""
        query_lower = query.lower().strip()
        for doc in results:
            title = doc.get("title", "").lower()
            url = doc.get("url", "").lower()
            source = doc.get("source_site", "").lower()

            boost = 0.0
            if query_lower == title:
                boost += 5.0
            elif query_lower in title:
                boost += 2.0

            if query_lower in url:
                boost += 1.0

            if query_lower in source:
                boost += 0.5

            doc["exact_boost"] = round(boost, 4)
            doc["score"] += boost

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def _compute_recency_boost(self, doc: dict) -> float:
        """计算时间新鲜度加成"""
        publish_time = doc.get("publish_time", "")
        if not publish_time:
            return 0.0

        try:
            from datetime import datetime, timedelta
            pub_date = datetime.strptime(publish_time, "%Y-%m-%d")
            now = datetime.now()
            days_ago = (now - pub_date).days

            if days_ago <= 7:
                return 0.3
            elif days_ago <= 30:
                return 0.2
            elif days_ago <= 90:
                return 0.1
            elif days_ago <= 365:
                return 0.05
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0

    def _compute_source_boost(self, doc: dict) -> float:
        """计算来源权威度加成"""
        source = doc.get("source_site", "")
        important_sources = {
            "南开大学主站": 0.3,
            "南开大学教务部": 0.3,
            "南开大学研究生招生网": 0.3,
            "南开新闻网": 0.2,
        }
        for name, boost in important_sources.items():
            if name in source:
                return boost
        return 0.0

    def _nav_noise_penalty(self, results: list[dict]) -> list[dict]:
        """内容质量降权：nav_noise 大幅降权，failed 适度降权"""
        for doc in results:
            cq = doc.get("content_quality", "")
            if cq == "nav_noise":
                # 大幅降权
                doc["score"] = max(0, doc["score"] - 5.0)
                doc["nav_noise_penalty"] = -5.0
            elif cq == "failed":
                # 适度降权（内容解析失败但并非噪声）
                doc["score"] = max(0, doc["score"] * 0.3)
                doc["content_quality_penalty"] = "failed"
        # 重新排序（优先 good > short > failed > nav_noise 同分时）
        cq_order = {"good": 0, "short": 1, "failed": 2, "nav_noise": 3}
        results.sort(key=lambda x: (
            x.get("score", 0),
            cq_order.get(x.get("content_quality", ""), 5)
        ), reverse=True)
        return results

    def _apply_filters(self, results: list[dict], filters: dict) -> list[dict]:
        """应用筛选条件"""
        filtered = results

        source_filter = filters.get("source", "")
        if source_filter:
            filtered = [d for d in filtered
                        if source_filter in d.get("source_site", "")]

        file_type = filters.get("file_type", "")
        if file_type:
            filtered = [d for d in filtered
                        if d.get("file_type", "") == file_type]

        date_from = filters.get("date_from", "")
        date_to = filters.get("date_to", "")
        if date_from or date_to:
            filtered = [d for d in filtered
                        if self._filter_by_date(d.get("publish_time", ""),
                                                date_from, date_to)]

        return filtered

    def _filter_by_date(self, pub_date: str, date_from: str, date_to: str) -> bool:
        """按时间范围筛选"""
        if not pub_date:
            return True
        try:
            if date_from and pub_date < date_from:
                return False
            if date_to and pub_date > date_to:
                return False
            return True
        except (ValueError, TypeError):
            return True

    def _enrich_result(self, doc: dict, query_terms: list[str]) -> dict:
        """丰富搜索结果：生成高亮摘要、标题高亮、匹配解释"""
        title = doc.get("title", "")
        content = doc.get("content", "")
        summary = doc.get("summary", "")

        enriched = dict(doc)

        # 高亮标题
        enriched["title_highlight"] = generate_title_highlight(title, query_terms)

        # 生成高亮摘要（优先使用命中词附近的内容）
        snippet = generate_snippet(content or summary, query_terms)
        enriched["snippet"] = snippet

        # 匹配解释
        enriched["match_explanation"] = extract_match_explanation(doc, query_terms)

        return enriched

    def get_stats(self) -> dict:
        """获取搜索引擎统计信息"""
        self._ensure_initialized()
        return {
            "doc_count": self.index.get_total_docs(),
            "term_count": len(self.index.get_content_terms_set()),
        }

    def get_sources(self) -> list[str]:
        """获取所有来源列表"""
        self._ensure_initialized()
        sources = set()
        for meta in self.index.doc_meta.values():
            source = meta.get("source_site", "")
            if source:
                sources.add(source)
        return sorted(sources)

    def get_file_types(self) -> list[str]:
        """获取所有文件类型列表"""
        self._ensure_initialized()
        types = set()
        for meta in self.index.doc_meta.values():
            ft = meta.get("file_type", "html")
            if ft:
                types.add(ft)
        return sorted(types)
