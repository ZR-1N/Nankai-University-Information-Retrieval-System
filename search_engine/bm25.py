"""
BM25 排序算法实现

BM25 公式:
    score(D, Q) = Σ IDF(qi) * (tf(qi, D) * (k1 + 1)) / (tf(qi, D) + k1 * (1 - b + b * |D|/avgdl))

其中:
    IDF(qi) = ln((N - df + 0.5) / (df + 0.5) + 1)
    N: 文档总数
    df: 包含 qi 的文档数
    tf: 词频
    |D|: 文档长度
    avgdl: 平均文档长度
    k1: 词频饱和参数 (默认 1.5)
    b: 长度归一化参数 (默认 0.75)
"""
import math
from search_engine.inverted_index import InvertedIndex


class BM25Scorer:
    """BM25 评分器，支持多字段加权"""

    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75):
        self.index = index
        self.k1 = k1
        self.b = b

        # 预计算平均文档长度
        self._avg_title_len = 0.0
        self._avg_content_len = 0.0
        self._compute_avg_lengths()

    def _compute_avg_lengths(self):
        """计算平均文档长度"""
        if self.index.doc_count == 0:
            return
        total_title = 0
        total_content = 0
        for doc_id, lengths in self.index.doc_lengths.items():
            total_title += lengths.get("title_len", 0)
            total_content += lengths.get("content_len", 0)
        self._avg_title_len = total_title / self.index.doc_count
        self._avg_content_len = total_content / self.index.doc_count

    def score(self, query_terms: list[str], doc_id: str,
              title_weight: float = 3.0,
              content_weight: float = 1.0):
        """
        计算单个文档的 BM25 分数
        分别计算标题字段和正文字段的分数，然后加权求和
        """
        total_score = 0.0
        doc_lens = self.index.get_doc_length(doc_id)
        title_len = doc_lens.get("title_len", 0)
        content_len = doc_lens.get("content_len", 0)

        for term in query_terms:
            # 标题字段 IDF
            title_df = self.index.get_title_df(term)
            if title_df > 0 and title_len > 0:
                idf_t = self._idf(self.index.doc_count, title_df)
                tf_t = self.index.get_title_postings(term).get(doc_id, 0)
                if tf_t > 0:
                    title_score = idf_t * self._bm25_tf(tf_t, title_len, self._avg_title_len)
                    total_score += title_weight * title_score

            # 正文字段 IDF
            content_df = self.index.get_content_df(term)
            if content_df > 0 and content_len > 0:
                idf_c = self._idf(self.index.doc_count, content_df)
                tf_c = self.index.get_content_postings(term).get(doc_id, 0)
                if tf_c > 0:
                    content_score = idf_c * self._bm25_tf(tf_c, content_len, self._avg_content_len)
                    total_score += content_weight * content_score

        return total_score

    def _idf(self, N: int, df: int) -> float:
        """计算 IDF"""
        return math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    def _bm25_tf(self, tf: int, doc_len: float, avg_len: float) -> float:
        """计算 BM25 的 TF 组件"""
        if avg_len == 0:
            avg_len = 1.0
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_len)
        return numerator / denominator
