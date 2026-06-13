"""
搜索联想/推荐模块

当用户在搜索框中输入前缀时，返回推荐查询词。
推荐来源:
  1. 历史查询日志中的高频查询
  2. 文档标题中的高频短语
  3. 热门文档标题
  4. 用户画像偏好调整
"""
import sqlite3
import os
from collections import Counter
from search_engine.inverted_index import InvertedIndex
from config.settings import DB_FILE


class SuggestEngine:
    """搜索联想引擎"""

    def __init__(self, index: InvertedIndex = None):
        self.index = index
        # 热门查询缓存
        self._popular_queries: list[str] = []
        # 标题短语缓存
        self._title_phrases: list[str] = []

    def get_suggestions(self, prefix: str, user_id: str = "default",
                        max_results: int = 10) -> list[dict]:
        """
        获取搜索建议
        返回 [{"text": "建议文本", "type": "history"/"title"/"hot", "score": float}, ...]
        """
        if not prefix:
            return self._get_hot_suggestions(max_results)

        suggestions = []

        # 1. 从历史查询日志获取
        history_suggestions = self._get_history_suggestions(prefix, max_results)
        suggestions.extend(history_suggestions)

        # 2. 从文档标题获取匹配短语
        title_suggestions = self._get_title_suggestions(prefix, max_results)
        suggestions.extend(title_suggestions)

        # 3. 从热门文档标题获取
        hot_suggestions = self._get_hot_title_suggestions(prefix, max_results)
        suggestions.extend(hot_suggestions)

        # 去重并按热度排序
        seen = set()
        unique = []
        for s in suggestions:
            if s["text"] not in seen:
                seen.add(s["text"])
                unique.append(s)
                if len(unique) >= max_results:
                    break

        # 按分数排序
        unique.sort(key=lambda x: x.get("score", 0), reverse=True)
        return unique[:max_results]

    def _get_history_suggestions(self, prefix: str, limit: int) -> list[dict]:
        """从历史查询日志获取建议"""
        if not os.path.exists(DB_FILE):
            return []

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                """SELECT query, COUNT(*) as cnt FROM search_logs
                   WHERE query LIKE ?
                   GROUP BY query
                   ORDER BY cnt DESC, MAX(search_time) DESC
                   LIMIT ?""",
                (f"{prefix}%", limit)
            )
            rows = cursor.fetchall()
            conn.close()

            max_cnt = rows[0][1] if rows else 1
            return [
                {"text": row[0], "type": "history", "score": row[1] / max_cnt}
                for row in rows
            ]
        except Exception:
            return []

    def _get_title_suggestions(self, prefix: str, limit: int) -> list[dict]:
        """从文档标题获取匹配短语作为建议"""
        if not self.index or not self.index.is_loaded:
            return []

        suggestions = []
        for doc_id, meta in self.index.doc_meta.items():
            title = meta.get("title", "")
            if prefix.lower() in title.lower():
                # 截取标题中匹配前缀的部分作为建议
                idx = title.lower().find(prefix.lower())
                # 从匹配位置开始取适当长度
                end = min(len(title), idx + 30)
                suggestion = title[idx:end].strip()
                if suggestion and suggestion not in [s["text"] for s in suggestions]:
                    suggestions.append({
                        "text": suggestion,
                        "type": "title",
                        "score": 0.5,
                    })
                if len(suggestions) >= limit:
                    break

        return suggestions

    def _get_hot_title_suggestions(self, prefix: str, limit: int) -> list[dict]:
        """从热门文档标题获取建议（使用标题词频）"""
        if not self.index or not self.index.is_loaded:
            return []

        # 收集标题中的短语（长度 2-6 个字符的片段）
        phrase_counter = Counter()
        for doc_id, meta in self.index.doc_meta.items():
            title = meta.get("title", "")
            title_len = len(title)
            for phrase_len in range(2, min(8, title_len + 1)):
                for i in range(title_len - phrase_len + 1):
                    phrase = title[i:i + phrase_len]
                    if phrase.startswith(prefix):
                        phrase_counter[phrase] += 1

        # 取最常见的前缀匹配短语
        top_phrases = phrase_counter.most_common(limit)
        if not top_phrases:
            return []

        max_cnt = top_phrases[0][1]
        return [
            {"text": phrase, "type": "hot", "score": cnt / max_cnt * 0.7}
            for phrase, cnt in top_phrases
        ]

    def _get_hot_suggestions(self, limit: int) -> list[dict]:
        """无前缀时返回热门查询"""
        if not os.path.exists(DB_FILE):
            return []

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                """SELECT query, COUNT(*) as cnt FROM search_logs
                   GROUP BY query ORDER BY cnt DESC LIMIT ?""",
                (limit,)
            )
            rows = cursor.fetchall()
            conn.close()

            max_cnt = rows[0][1] if rows else 1
            return [
                {"text": row[0], "type": "hot", "score": row[1] / max_cnt}
                for row in rows
            ]
        except Exception:
            return []
