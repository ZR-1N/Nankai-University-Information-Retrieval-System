"""
测试搜索引擎集成功能
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.personalized_rank import PersonalizedRanker, USER_PROFILES
from search_engine.highlight import highlight_keywords, generate_snippet, generate_title_highlight
from search_engine.fuzzy_search import FuzzySearch


class TestPersonalizedRank:
    """个性化排序测试"""

    def test_profile_boost_study_user(self):
        """测试学习型用户画像偏向教务内容"""
        ranker = PersonalizedRanker("study_user")
        # 教务相关文档
        doc_jw = {"title": "教务部关于期末考试安排的通知", "content": "考试 教务 课程", "source_site": "南开大学教务部", "score": 5.0}
        # 无关文档
        doc_news = {"title": "校园活动新闻", "content": "活动 新闻", "source_site": "南开新闻网", "score": 5.0}

        boost_jw = ranker.compute_boost(doc_jw)
        boost_news = ranker.compute_boost(doc_news)

        assert boost_jw > boost_news, \
            f"教务文档 boost({boost_jw}) 应高于新闻文档 boost({boost_news})"

    def test_profile_boost_research_user(self):
        """测试科研型用户画像偏向科研内容"""
        ranker = PersonalizedRanker("research_user")
        doc_research = {"title": "关于申报2024年国家自然科学基金项目的通知", "content": "科研 项目 基金 申报", "source_site": "计算机学院", "score": 5.0}
        doc_other = {"title": "学生活动通知", "content": "活动 文艺", "source_site": "学生工作", "score": 5.0}

        boost_r = ranker.compute_boost(doc_research)
        boost_o = ranker.compute_boost(doc_other)

        assert boost_r > boost_o, \
            f"科研文档 boost({boost_r}) 应高于无关文档 boost({boost_o})"

    def test_rerank_changes_order(self):
        """测试个性化重排会改变排序"""
        ranker = PersonalizedRanker("admission_user")
        docs = [
            {"title": "学术论文发表通知", "content": "论文 学术", "source_site": "计算机学院", "score": 5.0},
            {"title": "2025年硕士研究生招生简章", "content": "招生 研究生 硕士", "source_site": "南开大学研究生招生网", "score": 4.5},
            {"title": "校园活动通知", "content": "活动", "source_site": "南开新闻网", "score": 4.0},
        ]

        reranked = ranker.rerank(docs)
        # 招生文档应该排在前面
        assert "招生" in reranked[0]["title"], \
            f"admission_user 应将招生文档排在最前，实际: {reranked[0]['title']}"

    def test_all_profiles_exist(self):
        """测试所有用户画像都定义了"""
        required_profiles = ["default", "study_user", "research_user", "admission_user", "news_user"]
        for profile_id in required_profiles:
            assert profile_id in USER_PROFILES, f"缺少用户画像: {profile_id}"
            assert "name" in USER_PROFILES[profile_id]
            assert "weights" in USER_PROFILES[profile_id]


class TestHighlight:
    """高亮与摘要测试"""

    def test_highlight_keywords_basic(self):
        """测试基本高亮"""
        result = highlight_keywords("南开大学计算机学院", ["南开大学"])
        assert "<mark>" in result
        assert "南开大学" in result

    def test_highlight_keywords_multiple(self):
        """测试多关键词高亮"""
        result = highlight_keywords("南开大学计算机学院通知", ["南开大学", "通知"])
        assert result.count("<mark>") >= 2

    def test_generate_snippet_finds_keyword(self):
        """测试摘要包含关键词"""
        content = "这是一段很长的文本。" * 10 + "南开大学计算机学院发布通知。" + "更多内容。" * 10
        snippet = generate_snippet(content, ["南开大学"], max_len=100)
        assert "南开大学" in snippet

    def test_generate_snippet_no_keyword(self):
        """测试无关键词时返回开头"""
        content = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
        snippet = generate_snippet(content, ["不存在"])
        assert len(snippet) > 0

    def test_title_highlight(self):
        """测试标题高亮"""
        result = generate_title_highlight("南开大学奖学金申请通知", ["奖学金"])
        assert "<mark>奖学金</mark>" in result


class TestDocTypeFilter:
    """文档类型筛选测试（单元）"""

    def test_classify_pdf(self):
        from crawler.url_manager import classify_url
        assert classify_url("https://example.com/doc.pdf") == "pdf"
        assert classify_url("https://example.com/doc.PDF?download=1") == "pdf"

    def test_classify_docx(self):
        from crawler.url_manager import classify_url
        assert classify_url("https://example.com/doc.docx") == "docx"

    def test_classify_html(self):
        from crawler.url_manager import classify_url
        assert classify_url("https://example.com/page.html") == "html"
        assert classify_url("https://example.com/page") == "html"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
