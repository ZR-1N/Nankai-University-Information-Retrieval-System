"""
测试通配符查询功能
v3.0.0：增加 wildcard 无匹配不回退全量文档的验证
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.wildcard_search import WildcardSearch
from search_engine.inverted_index import InvertedIndex


class MockIndex(InvertedIndex):
    """模拟索引用于测试"""
    def __init__(self):
        self._title_terms = {
            "南开大学": {},
            "南开大学计算机学院": {},
            "南开大学人工智能学院": {},
            "南开大学教务部": {},
            "奖学金申请": {},
            "奖学金评定": {},
            "奖助学金": {},
            "2024年": {},
            "2025年": {},
            "2026年": {},
            "温度计": {},
            "温馨提醒": {},
            "温和": {},
            "研究生招生": {},
            "本科生教学": {},
            "人工智能": {},
            "机器学习": {},
        }
        self._content_terms = {}

    def get_title_terms_set(self):
        return set(self._title_terms.keys())

    def get_content_terms_set(self):
        return set(self._content_terms.keys())

    def get_title_postings(self, term):
        return {}

    def get_content_postings(self, term):
        return {}


class TestWildcardSearch:
    """通配符查询测试"""

    def setup_method(self):
        self.index = MockIndex()
        self.ws = WildcardSearch(self.index)

    def test_star_wildcard_prefix(self):
        """测试 * 前缀匹配: 南开*"""
        terms = self.ws.match_terms("南开*")
        assert "南开大学" in terms
        assert "南开大学计算机学院" in terms
        assert "南开大学人工智能学院" in terms
        assert "南开大学教务部" in terms
        assert len(terms) >= 4

    def test_star_wildcard_suffix(self):
        """测试 * 后缀匹配"""
        terms = self.ws.match_terms("*教学")
        assert "本科生教学" in terms

    def test_star_wildcard_middle(self):
        """测试 * 中间匹配: 奖*金 (匹配以"奖"开头、以"金"结尾的词)"""
        terms = self.ws.match_terms("奖*金")
        assert "奖助学金" in terms, f"匹配词: {terms}"
        assert "奖学金申请" not in terms

    def test_question_wildcard(self):
        """测试 ? 单字符匹配: 202?年"""
        terms = self.ws.match_terms("202?年")
        assert "2024年" in terms
        assert "2025年" in terms
        assert "2026年" in terms
        assert len(terms) == 3

    def test_multiple_question_marks(self):
        """测试多个 ? : 温?? (匹配以"温"开头的3字词)"""
        terms = self.ws.match_terms("温??")
        assert "温度计" in terms, f"匹配词: {terms}"
        # "温馨提醒" 是4字词，不应该匹配 "温??" (需要正好2个?匹配2个字符)
        assert "温馨提醒" not in terms

    def test_no_match(self):
        """测试无匹配情况"""
        terms = self.ws.match_terms("xyz123*")
        assert len(terms) == 0

    def test_exact_match(self):
        """测试不含通配符的精确匹配"""
        terms = self.ws.match_terms("人工智能")
        assert "人工智能" in terms
        assert len(terms) == 1

    def test_empty_pattern(self):
        """测试空模式"""
        terms = self.ws.match_terms("")
        assert len(terms) == 0

    def test_wildcard_search_docs(self):
        """测试通配符搜索返回文档"""
        terms = self.ws.match_terms("南开*")
        assert len(terms) >= 4

    # ================================================================
    # 新增：通配查询不应返回全量文档
    # ================================================================

    def test_no_match_should_not_fallback_to_all(self):
        """
        测试通配符无匹配时，不应回退到全量返回。
        之前 bug: match_terms 返回空时，SearchEngine 会 fallback 到全量文档。
        """
        terms = self.ws.match_terms("不存在词*")
        assert len(terms) == 0, "无匹配时应返回空列表"

    def test_wildcard_with_non_existent_dates(self):
        """
        测试不存在的日期模式不应返回文档。
        如果索引中没有 "202?年" 匹配的词，应返回空。
        """
        terms = self.ws.match_terms("199?年")
        # 索引中只有 2024年/2025年/2026年，没有 199?年
        assert len(terms) == 0

    def test_wildcard_only_matches_terms_in_index(self):
        """
        通配符只能匹配索引中实际存在的词条，不能凭空创造。
        """
        # "温???" 需匹配4字词，索引中只有"温馨提醒"是4字且以"温"开头
        terms = self.ws.match_terms("温???")
        assert "温馨提醒" in terms
        assert "温和" not in terms  # 2字，不符合???
        assert "温度计" not in terms  # 3字，不符合???

    def test_star_wildcard_does_not_match_everything(self):
        """
        * 不应匹配整个索引的所有词条，只匹配符合模式的。
        """
        terms = self.ws.match_terms("奖*")
        matched = set(terms)
        # 应该匹配以"奖"开头的词
        assert "奖学金申请" in matched
        assert "奖学金评定" in matched
        assert "奖助学金" in matched
        # 不应该包含不以"奖"开头的词
        assert "2024年" not in matched
        assert "人工智能" not in matched
        assert "南开大学" not in matched


class TestSearchEngineWildcardNoFallback:
    """
    验证 SearchEngine 层面不会因通配无匹配回退到全量文档。
    """

    def test_get_candidates_empty_for_no_terms(self):
        """
        当 query_terms 和 wildcard_terms 均为空时，
        _get_candidates 应返回空集（wildcard 模式）。
        """
        from search_engine.search import SearchEngine
        engine = SearchEngine()
        # 绕过 _ensure_initialized，直接测试逻辑
        result = engine._get_candidates([], [], "or", "wildcard")
        assert result == set(), \
            "wildcard 无匹配词时应返回空集，不能返回全量文档"

    def test_get_candidates_empty_for_normal_no_terms(self):
        """
        普通查询无词时也应返回空。
        """
        from search_engine.search import SearchEngine
        engine = SearchEngine()
        result = engine._get_candidates([], [], "or", "normal")
        assert result == set(), \
            "无查询词时应返回空集"

    def test_wildcard_process_query_no_fallback(self):
        """
        通配查询 _process_query 不应将通配模式回退到分词。
        """
        from search_engine.search import SearchEngine
        engine = SearchEngine()
        query_terms, wildcard_terms, fuzzy_expansions = engine._process_query(
            "不存在词*", "wildcard"
        )
        # 通配无匹配时应返回空列表，不应回退到 jieba 分词
        assert wildcard_terms == []
        assert query_terms == [], \
            "wildcard 模式不应将无匹配的通配符 query 回退到 jieba 分词"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
