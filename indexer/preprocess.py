"""
文本预处理模块 - 中文分词、停用词处理、文本归一化
"""
import os
import re
import jieba
from config.settings import STOPWORDS_FILE


class TextProcessor:
    """文本预处理器：分词、去停用词、归一化"""

    def __init__(self, stopwords_file: str = None):
        self.stopwords = self._load_stopwords(stopwords_file or STOPWORDS_FILE)
        # 预加载 jieba
        jieba.initialize()

    def _load_stopwords(self, filepath: str) -> set:
        """加载停用词表"""
        stopwords = set()
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        stopwords.add(word)
        return stopwords

    def tokenize(self, text: str) -> list[str]:
        """
        对文本进行分词
        返回去除停用词后的词条列表
        """
        if not text:
            return []

        # 清洗文本
        text = self._clean_text(text)

        # jieba 分词（精确模式）
        words = jieba.lcut(text)

        # 过滤
        result = []
        for word in words:
            word = word.strip().lower()
            # 跳过空词、单字符（除英文单个字母外）、纯数字、停用词
            if not word:
                continue
            if len(word) == 1 and not word.isascii():
                # 单个中文字符通常有意义，保留常见字
                if word in self.stopwords:
                    continue
            if word in self.stopwords:
                continue
            # 纯数字、纯标点
            if re.match(r'^[\d\W_]+$', word):
                continue
            result.append(word)

        return result

    def tokenize_title(self, title: str) -> list[str]:
        """对标题进行分词（可以保留更多短词）"""
        return self.tokenize(title)

    def tokenize_content(self, content: str) -> list[str]:
        """对正文进行分词"""
        return self.tokenize(content)

    def extract_keywords(self, text: str, topk: int = 10) -> list[str]:
        """提取关键词（基于 TF 粗略排序）"""
        if not text:
            return []
        words = self.tokenize(text)
        # 简单词频统计
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        # 按频率排序返回前 topk
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:topk]]

    def _clean_text(self, text: str) -> str:
        """文本清洗"""
        # 去除 HTML 标签残留
        text = re.sub(r'<[^>]+>', ' ', text)
        # 去除 URL
        text = re.sub(r'https?://\S+', ' ', text)
        # 去除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 去除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()


# 全局单例
_text_processor_instance = None


def get_processor() -> TextProcessor:
    global _text_processor_instance
    if _text_processor_instance is None:
        _text_processor_instance = TextProcessor()
    return _text_processor_instance
