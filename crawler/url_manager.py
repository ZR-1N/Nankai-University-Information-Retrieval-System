"""
URL 管理器 - 管理待爬取队列、已爬取集合、去重
支持优先级队列、URL 元数据（anchor_text、source_site、category）
v3.0.0：多源均衡爬取（round-robin + 单源配额）
"""
import hashlib
import json
import os
import re
from collections import deque, defaultdict
from urllib.parse import urlparse


# 优先级映射（数值越小越优先）
PRIORITY = {
    "document": 0,
    "detail": 1,
    "list": 2,
    "portal": 3,
}


class URLEntry:
    """URL 条目，包含爬取所需的元数据"""
    __slots__ = ("url", "anchor_text", "source_site", "category",
                 "parent_url", "priority", "normalized")

    def __init__(self, url: str, anchor_text: str = "",
                 source_site: str = "", category: str = "",
                 parent_url: str = "", priority: int = 2):
        self.url = url
        self.anchor_text = anchor_text
        self.source_site = source_site
        self.category = category
        self.parent_url = parent_url
        self.priority = priority
        self.normalized = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "anchor_text": self.anchor_text,
            "source_site": self.source_site,
            "category": self.category,
            "parent_url": self.parent_url,
            "priority": self.priority,
            "normalized": self.normalized,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "URLEntry":
        entry = cls(
            url=d.get("url", ""),
            anchor_text=d.get("anchor_text", ""),
            source_site=d.get("source_site", ""),
            category=d.get("category", ""),
            parent_url=d.get("parent_url", ""),
            priority=d.get("priority", 2),
        )
        entry.normalized = d.get("normalized", "")
        return entry


class URLManager:
    """
    URL 管理器：优先级队列 + 去重 + 断点续爬
    v3.0.0：每个 source_site 独立队列，round-robin 轮询，单源配额
    """

    def __init__(self, checkpoint_path: str = "data/url_manager_checkpoint.json",
                 max_source_ratio: float = 0.30, balanced: bool = True):
        # 每个 source_site 独立 4 级优先级队列
        # source_site -> {priority: deque of URLEntry}
        self._source_queues: dict[str, dict[int, deque]] = {}
        # Round-robin 轮询顺序
        self._source_round_order: list[str] = []
        self._source_round_idx: int = 0
        # 已爬取的 URL 集合
        self._visited: set = set()
        # 内容哈希去重
        self._url_content_hash: set = set()
        # 所有队列中 URL 的快速查重
        self._url_set: set = set()
        # 断点路径
        self.checkpoint_path = checkpoint_path
        # 均衡模式
        self.balanced = balanced
        self.max_source_ratio = max_source_ratio
        # 统计：每个 source_site 已爬取成功数量
        self.source_crawled: dict[str, int] = defaultdict(int)
        # 跟踪队列耗尽状态（用于动态配额重分配）
        self._depleted_sources: set = set()

    # ============================================================
    # Seed URL 加载
    # ============================================================

    def add_seed_urls(self, sources_config: list):
        """批量添加种子 URL（从配置加载）"""
        for source in sources_config:
            source_name = source.get("name", "")
            for item in source.get("seed_urls", []):
                if isinstance(item, str):
                    url = item
                    category = ""
                    priority = PRIORITY.get("list", 2)
                else:
                    url = item.get("url", "")
                    category = item.get("category", "")
                    page_role = item.get("page_role", "list")
                    priority = PRIORITY.get(page_role, 2)

                self.add_url(url, source_site=source_name,
                            category=category, priority=priority)

    # ============================================================
    # 添加 URL
    # ============================================================

    def add_url(self, url: str, anchor_text: str = "",
                source_site: str = "", category: str = "",
                parent_url: str = "", priority: int = None,
                is_detail: bool = False) -> bool:
        """
        添加待爬取 URL
        - priority: None 时根据 is_detail 自动推断
        - is_detail: True 时优先级设为 detail(1)
        返回是否成功添加
        """
        normalized = self._normalize_url(url)
        if not normalized:
            return False
        if normalized in self._visited:
            return False
        if normalized in self._url_set:
            return False

        # 自动推断优先级
        if priority is None:
            if is_detail:
                priority = 1  # detail
            elif is_attachment_url(url):
                priority = 0  # document
            else:
                priority = 2  # list

        # 限制优先级范围
        priority = max(0, min(3, priority))

        entry = URLEntry(
            url=url,
            anchor_text=anchor_text,
            source_site=source_site,
            category=category,
            parent_url=parent_url,
            priority=priority,
        )
        entry.normalized = normalized

        # 确保 source_site 存在（未知来源用 "其他"）
        site = source_site if source_site else "其他"
        if site not in self._source_queues:
            self._source_queues[site] = {
                0: deque(),  # document
                1: deque(),  # detail
                2: deque(),  # list
                3: deque(),  # portal
            }
            self._source_round_order.append(site)

        self._source_queues[site][priority].append(entry)
        self._url_set.add(normalized)
        return True

    # ============================================================
    # 获取下一个 URL（Round-Robin 轮询）
    # ============================================================

    def get_next(self, total_target: int = None) -> URLEntry | None:
        """
        获取下一个待爬取 URL
        - balanced 模式：round-robin 轮询各 source_site
        - 单源超过 max_source_ratio 配额则跳过
        - 如果某个 source_site 队列耗尽，动态重分配配额给活跃站点
        - 活跃站点数量变化时，配额上限按比例重新计算
        返回 None 表示所有队列均已空
        """
        if not self._source_round_order:
            return None

        # 动态计算活跃 source 数量（有队列的 source）
        active_sources = [
            s for s in self._source_round_order
            if s not in self._depleted_sources and self._source_has_entries(s)
        ]
        if not active_sources:
            # 全部耗尽，尝试所有 source 兜底
            active_sources = list(self._source_round_order)

        num_active = len(active_sources)
        if num_active == 0:
            return None

        # 动态配额上限：当活跃 source 超过阈值时启用严格配额
        # 配额 = max(total * ratio, total / num_active) 保证每个 source 都有机会
        max_per_source = None
        if total_target and self.max_source_ratio > 0:
            base_quota = int(total_target * self.max_source_ratio)
            # 如果有多个活跃源，按活跃源数量动态调整
            # 保证每个源至少有 total / num_active 的配额
            fair_share = max(1, int(total_target / num_active))
            max_per_source = max(base_quota, fair_share)

        if self.balanced and len(self._source_round_order) > 1:
            # Round-robin: 尝试每个 source_site
            for _ in range(len(self._source_round_order)):
                idx = self._source_round_idx % len(self._source_round_order)
                source = self._source_round_order[idx]
                self._source_round_idx = (self._source_round_idx + 1) % len(self._source_round_order)

                # 跳过已耗尽的 source
                if source in self._depleted_sources:
                    continue

                # 配额检查：仅在活跃源较多时启用
                if max_per_source and num_active > 3:
                    if self.source_crawled.get(source, 0) >= max_per_source:
                        continue

                entry = self._pop_from_source(source)
                if entry is not None:
                    return entry

            # 当前轮次没有取到（所有有配额的 source 的当前优先级队列空）
            # 尝试跨优先级取
            for source in self._source_round_order:
                if source in self._depleted_sources:
                    continue
                entry = self._pop_from_source(source)
                if entry is not None:
                    return entry

            # 所有 source 队列都空了
            return None
        else:
            # 非均衡模式：按优先级全局取
            for priority in sorted(range(4)):
                for source in self._source_round_order:
                    queues = self._source_queues.get(source, {})
                    q = queues.get(priority, deque())
                    while q:
                        entry = q.popleft()
                        self._url_set.discard(entry.normalized)
                        if entry.normalized in self._visited:
                            continue
                        return entry

        return None

    def _pop_from_source(self, source: str) -> URLEntry | None:
        """从指定 source 的队列中按优先级取出一个 URL"""
        queues = self._source_queues.get(source, {})
        if not queues:
            return None
        for priority in sorted(queues.keys()):
            q = queues[priority]
            while q:
                entry = q.popleft()
                self._url_set.discard(entry.normalized)
                if entry.normalized in self._visited:
                    continue
                return entry
        # 该 source 所有队列都空了
        return None

    def _source_has_entries(self, source: str) -> bool:
        """检查指定 source 的队列是否还有条目"""
        queues = self._source_queues.get(source, {})
        if not queues:
            return False
        return any(len(q) > 0 for q in queues.values())

    def mark_source_depleted(self, source: str):
        """标记某个 source 队列已耗尽"""
        self._depleted_sources.add(source)

    def is_source_depleted(self, source: str) -> bool:
        """检查某个 source 是否已耗尽"""
        return source in self._depleted_sources

    def get_source_quota_info(self, total_target: int = None) -> dict:
        """返回各 source_site 的配额信息（用于 crawl_stats.json）

        返回格式:
        {
            "source_name": {
                "crawled": int,      # 已爬取数量
                "queue_size": int,   # 队列剩余URL数
                "quota_max": int,    # 配额上限
                "depleted": bool,    # 是否队列耗尽
                "pct": float,        # 当前占比
            }
        }
        """
        total_crawled = sum(self.source_crawled.values())
        num_active = sum(1 for s in self._source_round_order
                        if s not in self._depleted_sources and self._source_has_entries(s))

        max_per_source = None
        if total_target and self.max_source_ratio > 0:
            base_quota = int(total_target * self.max_source_ratio)
            fair_share = max(1, int(total_target / max(1, num_active)))
            max_per_source = max(base_quota, fair_share)

        result = {}
        for source in self._source_round_order:
            crawled = self.source_crawled.get(source, 0)
            queue_size = sum(len(q) for q in self._source_queues.get(source, {}).values())
            pct = round(crawled / max(1, total_crawled) * 100, 1) if total_crawled else 0.0
            result[source] = {
                "crawled": crawled,
                "queue_size": queue_size,
                "quota_max": max_per_source,
                "depleted": source in self._depleted_sources or (
                    queue_size == 0 and crawled > 0
                ),
                "pct": pct,
            }
        return result

    # ============================================================
    # 状态管理
    # ============================================================

    def record_crawled(self, source_site: str):
        """记录某个 source_site 爬取成功一个文档"""
        site = source_site if source_site else "其他"
        self.source_crawled[site] += 1

    def mark_visited(self, url: str):
        """标记 URL 已爬取"""
        normalized = self._normalize_url(url)
        if normalized:
            self._visited.add(normalized)

    def is_visited(self, url: str) -> bool:
        """检查 URL 是否已爬取"""
        return self._normalize_url(url) in self._visited

    def add_content_hash(self, content_hash: str) -> bool:
        """添加内容哈希，返回 False 表示重复"""
        if content_hash in self._url_content_hash:
            return False
        self._url_content_hash.add(content_hash)
        return True

    # ============================================================
    # 队列状态
    # ============================================================

    @property
    def queue_size(self) -> int:
        return sum(
            len(q) for queues in self._source_queues.values()
            for q in queues.values()
        )

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    def queue_sizes_by_priority(self) -> dict:
        """返回各优先级队列大小"""
        result = defaultdict(int)
        for queues in self._source_queues.values():
            for p, q in queues.items():
                result[p] += len(q)
        return dict(result)

    def queue_sizes_by_source(self) -> dict:
        """返回各 source_site 的队列大小"""
        return {
            site: sum(len(q) for q in queues.values())
            for site, queues in self._source_queues.items()
        }

    def source_distribution(self) -> dict:
        """返回各 source_site 的已爬取数量"""
        return dict(self.source_crawled)

    # ============================================================
    # URL 规范化
    # ============================================================

    def _normalize_url(self, url: str) -> str:
        """URL 规范化"""
        if not url:
            return ""
        # 处理相对 URL 中的 ../
        url = url.replace("/../", "/")
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if normalized.endswith("/") and len(parsed.path) > 1:
            normalized = normalized.rstrip("/")
        return normalized

    # ============================================================
    # 断点续爬
    # ============================================================

    def save_checkpoint(self):
        """保存断点"""
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        checkpoint = {
            "source_queues": {
                site: {
                    str(p): [entry.to_dict() for entry in q]
                    for p, q in queues.items()
                }
                for site, queues in self._source_queues.items()
            },
            "source_round_order": self._source_round_order,
            "source_round_idx": self._source_round_idx,
            "visited": list(self._visited),
            "content_hashes": list(self._url_content_hash),
            "source_crawled": dict(self.source_crawled),
        }
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False)

    def load_checkpoint(self) -> bool:
        """加载断点"""
        if not os.path.exists(self.checkpoint_path):
            return False
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint = json.load(f)

            self._source_queues = {}
            for site, queues_dict in checkpoint.get("source_queues", {}).items():
                if site not in self._source_queues:
                    self._source_queues[site] = {}
                for p_str, entries in queues_dict.items():
                    p = int(p_str)
                    self._source_queues[site][p] = deque(
                        URLEntry.from_dict(e) for e in entries
                    )

            self._source_round_order = checkpoint.get("source_round_order", [])
            self._source_round_idx = checkpoint.get("source_round_idx", 0)
            self._visited = set(checkpoint.get("visited", []))
            self._url_content_hash = set(checkpoint.get("content_hashes", []))
            self.source_crawled = defaultdict(
                int, checkpoint.get("source_crawled", {})
            )

            # 重建 url_set
            self._url_set = set()
            for queues in self._source_queues.values():
                for q in queues.values():
                    for entry in q:
                        self._url_set.add(entry.normalized)

            # 兼容旧 checkpoint 格式（非 source 分组）
            if not self._source_queues and "queues" in checkpoint:
                self._source_queues = {}
                legacy = checkpoint.get("queues", {})
                for p_str, entries in legacy.items():
                    p = int(p_str)
                    for e_dict in entries:
                        source = e_dict.get("source_site", "其他")
                        if source not in self._source_queues:
                            self._source_queues[source] = {
                                0: deque(), 1: deque(), 2: deque(), 3: deque()
                            }
                            self._source_round_order.append(source)
                        entry = URLEntry.from_dict(e_dict)
                        self._source_queues[source][p].append(entry)
                        self._url_set.add(entry.normalized)

            return True
        except (json.JSONDecodeError, KeyError):
            return False

    @staticmethod
    def make_content_hash(title: str, content: str) -> str:
        """基于标题和正文内容生成哈希"""
        text = (title or "") + "|" + (content or "")
        return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


# ============================================================
# URL 工具函数
# ============================================================

def is_allowed_domain(url: str, allowed_domains: list) -> bool:
    """检查 URL 是否属于允许的域名"""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        for domain in allowed_domains:
            if host == domain or host.endswith("." + domain):
                return True
        return False
    except Exception:
        return False


def is_attachment_url(url: str) -> bool:
    """判断是否为附件 URL（含 query 参数检测）"""
    url_lower = url.lower()
    # 按扩展名检测
    attachment_extensions = [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".rar", ".ppt", ".pptx",
    ]
    # 从 URL 路径中去掉 query string 检测扩展名
    path = urlparse(url).path.lower() if "://" in url else url_lower
    for ext in attachment_extensions:
        if ext in path:
            return True
    return False


def classify_url(url: str) -> str:
    """根据 URL 判断文件类型（支持 query 参数）"""
    url_lower = url.lower()
    path = urlparse(url).path.lower() if "://" in url else url_lower
    ext_map = [
        (".pdf", "pdf"), (".docx", "docx"), (".doc", "doc"),
        (".xlsx", "xlsx"), (".xls", "xls"), (".zip", "zip"),
        (".rar", "rar"), (".ppt", "ppt"), (".pptx", "ppt"),
    ]
    for ext, ft in ext_map:
        if ext in path:
            return ft
    return "html"


def extract_domain(url: str) -> str:
    """提取域名"""
    try:
        return urlparse(url).netloc
    except Exception:
        return ""
