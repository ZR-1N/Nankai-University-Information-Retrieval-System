"""
通配符查询模块

支持:
  * : 匹配任意多个字符
  ? : 匹配任意一个字符

示例:
  "南开*"  -> 匹配 "南开大学", "南开大学计算机学院", 等
  "202?年" -> 匹配 "2024年", "2025年", 等
  "温??"   -> 匹配 "温家宝", "温度计", 等

实现方式: 将通配符表达式转换为正则表达式，在词典（索引词条）中匹配
"""
import re
from search_engine.inverted_index import InvertedIndex


class WildcardSearch:
    """通配符搜索"""

    def __init__(self, index: InvertedIndex):
        self.index = index

    def match_terms(self, pattern: str) -> list[str]:
        """
        在索引词条中查找匹配通配符模式的词
        返回匹配的词条列表
        """
        if not pattern:
            return []

        # 将通配符转换为正则表达式
        # * -> .*
        # ? -> .
        regex_parts = []
        for char in pattern:
            if char == '*':
                regex_parts.append('.*')
            elif char == '?':
                regex_parts.append('.')
            else:
                # 转义正则特殊字符
                regex_parts.append(re.escape(char))

        regex_str = '^' + ''.join(regex_parts) + '$'

        try:
            compiled = re.compile(regex_str)
        except re.error:
            return []

        # 在标题和正文索引词条中匹配
        all_terms = self.index.get_title_terms_set() | self.index.get_content_terms_set()
        matched = [term for term in all_terms if compiled.match(term)]

        return matched

    def search_docs(self, pattern: str) -> set[str]:
        """
        查找匹配通配符的所有文档
        返回文档 ID 集合
        """
        matched_terms = self.match_terms(pattern)
        doc_ids = set()

        for term in matched_terms:
            # 查找标题和正文中包含该词条的文档
            title_docs = self.index.get_title_postings(term)
            content_docs = self.index.get_content_postings(term)
            doc_ids.update(title_docs.keys())
            doc_ids.update(content_docs.keys())

        return doc_ids
