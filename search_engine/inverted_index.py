"""
倒排索引查询模块 - 加载索引并提供查询接口
"""
from indexer.build_index import IndexBuilder
from indexer.preprocess import get_processor


class InvertedIndex:
    """
    倒排索引查询接口
    从持久化的索引文件中加载，提供 term 查询
    """

    def __init__(self):
        self.processor = get_processor()
        self.title_index: dict = {}
        self.content_index: dict = {}
        self.title_df: dict = {}
        self.content_df: dict = {}
        self.doc_lengths: dict = {}
        self.doc_count: int = 0
        self.doc_meta: dict = {}
        self._loaded = False

    def load(self) -> bool:
        """加载索引，返回是否成功"""
        index_data = IndexBuilder.load_index()
        if index_data is None:
            return False

        self.title_index = index_data.get("title_index", {})
        self.content_index = index_data.get("content_index", {})
        self.title_df = index_data.get("title_df", {})
        self.content_df = index_data.get("content_df", {})
        self.doc_lengths = index_data.get("doc_lengths", {})
        self.doc_count = index_data.get("doc_count", 0)
        self.doc_meta = index_data.get("doc_meta", {})
        self._loaded = True
        return True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get_title_postings(self, term: str) -> dict[str, int]:
        """获取标题倒排列表"""
        return self.title_index.get(term, {})

    def get_content_postings(self, term: str) -> dict[str, int]:
        """获取正文倒排列表"""
        return self.content_index.get(term, {})

    def get_title_df(self, term: str) -> int:
        """获取标题中的文档频率"""
        return self.title_df.get(term, 0)

    def get_content_df(self, term: str) -> int:
        """获取正文中的文档频率"""
        return self.content_df.get(term, 0)

    def get_doc_length(self, doc_id: str) -> dict:
        """获取文档长度"""
        return self.doc_lengths.get(doc_id, {"title_len": 0, "content_len": 0})

    def get_doc_meta(self, doc_id: str) -> dict | None:
        """获取文档元数据"""
        return self.doc_meta.get(doc_id)

    def get_total_docs(self) -> int:
        """获取文档总数"""
        return self.doc_count

    def get_all_terms(self) -> list[str]:
        """获取索引中所有词条"""
        all_terms = set(self.title_index.keys()) | set(self.content_index.keys())
        return list(all_terms)

    def get_all_doc_ids(self) -> list[str]:
        """获取所有文档 ID"""
        return list(self.doc_meta.keys())

    def get_title_terms_set(self) -> set:
        """获取标题索引中的词条集合（用于通配匹配）"""
        return set(self.title_index.keys())

    def get_content_terms_set(self) -> set:
        """获取正文索引中的词条集合"""
        return set(self.content_index.keys())
