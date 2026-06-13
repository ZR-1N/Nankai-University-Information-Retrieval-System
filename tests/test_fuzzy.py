"""
测试模糊查询功能
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.fuzzy_search import FuzzySearch
from search_engine.inverted_index import InvertedIndex


class MockIndex(InvertedIndex):
    """模拟索引"""
    def __init__(self):
        self._title_terms = {
            "南开大学", "南开大院", "南开大穴",
            "计算机学院", "计算计学院", "计算机学",
        }
        self._content_terms = {
            "奖学金申请", "奖学金评定", "奖学今申请",
        }

    def get_title_terms_set(self):
        return self._title_terms

    def get_content_terms_set(self):
        return self._content_terms

    def get_title_postings(self, term):
        return {}

    def get_content_postings(self, term):
        return {}


class TestFuzzySearch:
    """模糊查询测试"""

    def setup_method(self):
        self.index = MockIndex()
        self.fs = FuzzySearch(self.index, max_distance=2)

    def test_levenshtein_distance_identical(self):
        """测试编辑距离：相同字符串"""
        dist = self.fs._levenshtein_distance("南开大学", "南开大学")
        assert dist == 0

    def test_levenshtein_distance_one_char(self):
        """测试编辑距离：差一个字符"""
        dist = self.fs._levenshtein_distance("南开大学", "南开大院")
        assert dist == 1

    def test_levenshtein_distance_two_chars(self):
        """测试编辑距离：差两个字符"""
        dist = self.fs._levenshtein_distance("ab", "")
        assert dist == 2

    def test_levenshtein_distance_different_length(self):
        """测试编辑距离：不同长度"""
        dist = self.fs._levenshtein_distance("计算机", "计算机学院")
        assert dist == 2  # 插入 "学院" 两个字符

    def test_find_similar_terms_correct_word(self):
        """测试查找相似词：正确拼写"""
        results = self.fs.find_similar_terms("南开大学")
        assert any(term == "南开大学" for term, _ in results)

    def test_find_similar_terms_typo(self):
        """测试查找相似词：错别字"""
        # "南开大院" 与 "南开大学" 差一个字符
        results = self.fs.find_similar_terms("南开大学")
        matched_terms = [term for term, _ in results]
        assert "南开大院" in matched_terms or "南开大穴" in matched_terms

    def test_fuzzy_match_score_perfect(self):
        """测试模糊匹配分数：完全匹配"""
        score = FuzzySearch.fuzzy_match_score("南开大学", "南开大学")
        assert score == 1.0

    def test_fuzzy_match_score_partial(self):
        """测试模糊匹配分数：部分匹配"""
        score = FuzzySearch.fuzzy_match_score("南开大学", "南开大院")
        assert 0.0 < score < 1.0

    def test_fuzzy_match_score_no_match(self):
        """测试模糊匹配分数：完全不匹配"""
        score = FuzzySearch.fuzzy_match_score("abc", "xyz")
        assert score < 0.5

    def test_expand_query(self):
        """测试查询扩展"""
        expanded = self.fs.expand_query(["南开大学"])
        assert len(expanded) >= 1
        assert "南开大学" in expanded

    def test_max_distance_limit(self):
        """测试编辑距离限制"""
        fs_strict = FuzzySearch(self.index, max_distance=0)
        results = fs_strict.find_similar_terms("南开大学")
        # 只有完全匹配
        assert len(results) == 1
        assert results[0][0] == "南开大学"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
