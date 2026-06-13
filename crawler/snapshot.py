"""
网页快照模块 - 对代表性页面保存快照，自动注入 <base href> 修复资源路径
"""
import os
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from config.settings import SNAPSHOTS_DIR


class SnapshotManager:
    """网页快照管理器（优化版：自动修复资源 404）"""

    def __init__(self, max_snapshots: int = 50):
        self.max_snapshots = max_snapshots
        self.snapshot_count = 0
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

    def should_save_snapshot(self, metadata: dict) -> bool:
        """判断是否应该为此页面保存快照"""
        if self.snapshot_count >= self.max_snapshots:
            return False
        # 优先保存 detail 页面
        if metadata.get("page_role") == "detail":
            return True
        # HTML 页面
        if metadata.get("file_type") == "html":
            return True
        return False

    def save_snapshot(self, html_content: str, doc_id: str,
                      original_url: str = "") -> str:
        """
        保存网页快照，自动注入 <base href> 修复资源路径
        返回快照文件路径
        """
        if self.snapshot_count >= self.max_snapshots:
            return ""

        # 注入 <base href> 使相对路径资源可以正确加载
        if original_url:
            html_content = self._inject_base_href(html_content, original_url)

        filepath = os.path.join(SNAPSHOTS_DIR, f"{doc_id}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.snapshot_count += 1
        return filepath

    def _inject_base_href(self, html: str, original_url: str) -> str:
        """
        在 <head> 中注入 <base href="..."> 使相对路径资源正确加载。
        base href 设为原网页所在目录。
        """
        # 计算 base href（目录 URL）
        parsed = urlparse(original_url)
        path = parsed.path
        # 提取目录部分（去掉文件名）
        if "." in os.path.basename(path):
            dir_path = os.path.dirname(path)
        else:
            dir_path = path
        base_url = f"{parsed.scheme}://{parsed.netloc}{dir_path}/"

        # 在 </head> 前插入 <base> 标签
        base_tag = f'<base href="{base_url}">'
        if "</head>" in html.lower():
            html = re.sub(
                r'(<head[^>]*>)', f'\\1\n{base_tag}',
                html, count=1, flags=re.IGNORECASE
            )
        else:
            # 没有 head 标签，在开头插入
            html = f"<!DOCTYPE html>\n<html><head>{base_tag}</head><body>\n{html}\n</body></html>"

        return html

    def get_snapshot(self, doc_id: str) -> str | None:
        """获取快照内容"""
        filepath = os.path.join(SNAPSHOTS_DIR, f"{doc_id}.html")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def has_snapshot(self, doc_id: str) -> bool:
        """检查是否有快照"""
        return os.path.exists(os.path.join(SNAPSHOTS_DIR, f"{doc_id}.html"))
