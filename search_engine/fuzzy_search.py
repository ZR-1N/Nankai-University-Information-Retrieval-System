"""
模糊查询模块

支持用户输入错别字或近似关键词时仍能返回相关结果。

实现方式:
  1. 编辑距离 (Levenshtein Distance) - 在词典中查找相似词
  2. 拼音相似度 - 可选
  3. 关键词扩展 - 用编辑距离找到的相近词扩展查询
"""
from search_engine.inverted_index import InvertedIndex


class FuzzySearch:
    """模糊搜索"""

    def __init__(self, index: InvertedIndex, max_distance: int = 2):
        self.index = index
        self.max_distance = max_distance

    def find_similar_terms(self, query_term: str, max_results: int = 10) -> list[tuple[str, int]]:
        """
        在索引词条中查找与 query_term 编辑距离相近的词
        返回 [(词条, 编辑距离), ...] 按距离排序
        """
        if not query_term:
            return []

        all_terms = self.index.get_title_terms_set() | self.index.get_content_terms_set()

        results = []
        query_len = len(query_term)

        for term in all_terms:
            term_len = len(term)
            # 长度差过大直接跳过（优化）
            if abs(term_len - query_len) > self.max_distance:
                continue

            dist = self._levenshtein_distance(query_term, term)
            if dist <= self.max_distance:
                results.append((term, dist))

        # 按编辑距离排序，距离小的优先
        results.sort(key=lambda x: (x[1], -len(x[0])))
        return results[:max_results]

    def expand_query(self, query_terms: list[str]) -> list[str]:
        """
        扩展查询词：对每个查询词查找相似词
        返回扩展后的词条列表（含原词 + 相似词）
        """
        expanded = list(query_terms)
        for term in query_terms:
            similar = self.find_similar_terms(term, max_results=5)
            for sim_term, _ in similar:
                if sim_term not in expanded:
                    expanded.append(sim_term)
        return expanded

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        计算两个字符串的编辑距离（Levenshtein Distance）
        使用动态规划 + 空间优化（O(min(m,n))）
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        # s1 是较长的字符串
        len1, len2 = len(s1), len(s2)

        # 初始化前一行
        prev_row = list(range(len2 + 1))

        for i in range(1, len1 + 1):
            curr_row = [i]
            for j in range(1, len2 + 1):
                if s1[i - 1] == s2[j - 1]:
                    cost = 0
                else:
                    cost = 1
                curr_row.append(min(
                    prev_row[j] + 1,       # 删除
                    curr_row[j - 1] + 1,   # 插入
                    prev_row[j - 1] + cost # 替换
                ))
            prev_row = curr_row

        return prev_row[-1]

    @staticmethod
    def fuzzy_match_score(query: str, target: str) -> float:
        """
        计算两个字符串的模糊匹配分数 (0.0 - 1.0)
        1.0 表示完全匹配
        """
        if not query or not target:
            return 0.0

        query = query.lower()
        target = target.lower()

        if query == target:
            return 1.0

        # 基于编辑距离的相似度
        dist = FuzzySearch._levenshtein_static(query, target)
        max_len = max(len(query), len(target))
        if max_len == 0:
            return 1.0

        return 1.0 - (dist / max_len)

    @staticmethod
    def _levenshtein_static(s1: str, s2: str) -> int:
        """静态编辑距离方法"""
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        prev_row = list(range(len(s2) + 1))
        for i in range(1, len(s1) + 1):
            curr_row = [i]
            for j in range(1, len(s2) + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                curr_row.append(min(
                    prev_row[j] + 1,
                    curr_row[j - 1] + 1,
                    prev_row[j - 1] + cost
                ))
            prev_row = curr_row
        return prev_row[-1]
