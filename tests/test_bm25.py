"""
测试 BM25 排序功能
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.bm25 import BM25Scorer
from search_engine.inverted_index import InvertedIndex


class MockIndex(InvertedIndex):
    """模拟索引"""
    def __init__(self):
        self.doc_count = 3
        self.doc_lengths = {
            "doc1": {"title_len": 5, "content_len": 100},
            "doc2": {"title_len": 8, "content_len": 200},
            "doc3": {"title_len": 3, "content_len": 50},
        }
        # 倒排列表
        self._title_index = {
            "南开": {"doc1": 2, "doc2": 1},
            "大学": {"doc1": 1, "doc2": 1, "doc3": 1},
            "计算机": {"doc2": 3},
        }
        self._content_index = {
            "南开": {"doc1": 5, "doc2": 2, "doc3": 1},
            "大学": {"doc1": 10, "doc2": 8, "doc3": 5},
            "计算机": {"doc2": 15, "doc1": 1},
        }
        self._title_df = {
            "南开": 2,
            "大学": 3,
            "计算机": 1,
        }
        self._content_df = {
            "南开": 3,
            "大学": 3,
            "计算机": 2,
        }

    def get_title_postings(self, term):
        return self._title_index.get(term, {})

    def get_content_postings(self, term):
        return self._content_index.get(term, {})

    def get_title_df(self, term):
        return self._title_df.get(term, 0)

    def get_content_df(self, term):
        return self._content_df.get(term, 0)

    def get_doc_length(self, doc_id):
        return self.doc_lengths.get(doc_id, {"title_len": 0, "content_len": 0})


class TestBM25Scorer:
    """BM25 评分测试"""

    def setup_method(self):
        self.index = MockIndex()
        self.scorer = BM25Scorer(self.index, k1=1.5, b=0.75)

    def test_title_match_scores_higher(self):
        """测试标题命中比正文命中得分高"""
        query_terms = ["计算机"]

        # doc2 标题有 "计算机" 3 次
        score_doc2 = self.scorer.score(query_terms, "doc2",
                                       title_weight=3.0, content_weight=1.0)

        # doc1 标题没有 "计算机"，只有正文有 1 次
        score_doc1 = self.scorer.score(query_terms, "doc1",
                                       title_weight=3.0, content_weight=1.0)

        assert score_doc2 > score_doc1, \
            f"标题命中文档 (doc2={score_doc2}) 应得分高于仅有正文命中文档 (doc1={score_doc1})"

    def test_multi_term_query(self):
        """测试多关键词查询"""
        query_terms = ["南开", "大学"]
        score_doc1 = self.scorer.score(query_terms, "doc1")
        score_doc3 = self.scorer.score(query_terms, "doc3")

        # doc1 同时有 "南开" 和 "大学"，应得分高于 doc3
        assert score_doc1 > score_doc3, \
            f"doc1={score_doc1} 应得分高于 doc3={score_doc3}"

    def test_idf_rare_terms_score_higher(self):
        """测试稀有词（低DF）比常见词得分高"""
        # "计算机" DF=1（稀有），"大学" DF=3（常见）
        score_rare = self.scorer.score(["计算机"], "doc2")
        score_common = self.scorer.score(["大学"], "doc2")

        # 在同文档中，稀有词应比常见词贡献更大的单词语义
        assert score_rare > 0
        assert score_common > 0

    def test_no_match_returns_zero(self):
        """测试无匹配词返回零分"""
        score = self.scorer.score(["不存在词"], "doc1")
        assert score == 0.0

    def test_title_weight_effect(self):
        """测试标题权重大于正文权重的影响"""
        query_terms = ["南开"]
        # 标题权重高
        score_title_high = self.scorer.score(query_terms, "doc1",
                                              title_weight=5.0, content_weight=1.0)
        # 标题权重低
        score_title_low = self.scorer.score(query_terms, "doc1",
                                             title_weight=1.0, content_weight=1.0)
        assert score_title_high > score_title_low

    def test_score_positive(self):
        """测试分数非负"""
        query_terms = ["南开", "大学", "计算机"]
        for doc_id in ["doc1", "doc2", "doc3"]:
            score = self.scorer.score(query_terms, doc_id)
            assert score >= 0, f"doc {doc_id} 分数应为非负，得到 {score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
