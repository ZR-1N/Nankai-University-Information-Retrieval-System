"""
下载器 - 负责 HTTP 请求和文件下载
"""
import os
import time
import hashlib
import requests
from typing import Optional, Tuple
from config.settings import USER_AGENT, CRAWL_TIMEOUT, MAX_RETRIES, RAW_HTML_DIR, DOCUMENTS_DIR


class Downloader:
    """HTTP 下载器：支持 HTML 页面和附件下载，含重试逻辑"""

    def __init__(self, delay: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        })
        self.delay = delay
        self.last_request_time = 0

    def _rate_limit(self):
        """请求频率控制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def fetch_html(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        下载 HTML 页面
        返回 (html_content, error_message)
        """
        self._rate_limit()
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    timeout=CRAWL_TIMEOUT,
                    allow_redirects=True,
                )
                resp.raise_for_status()

                # 检测内容类型
                content_type = resp.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    # 可能是附件，交由 download_file 处理
                    return None, f"Non-HTML content: {content_type}"

                # 自动检测编码
                resp.encoding = resp.apparent_encoding or "utf-8"
                return resp.text, None

            except requests.exceptions.Timeout:
                error = f"Timeout after {CRAWL_TIMEOUT}s"
            except requests.exceptions.ConnectionError as e:
                error = f"Connection error: {e}"
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "unknown"
                error = f"HTTP {status}: {e}"
                if status in (403, 404, 410):
                    return None, error  # 不可恢复
            except Exception as e:
                error = f"Unexpected error: {e}"

            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

        return None, error

    def download_file(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        下载文件（PDF/DOC/DOCX/XLS/XLSX 等）
        返回 (local_path, content_type, error_message)
        """
        self._rate_limit()
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    timeout=CRAWL_TIMEOUT * 2,  # 文件下载超时加倍
                    allow_redirects=True,
                    stream=True,
                )
                resp.raise_for_status()

                content_type = resp.headers.get("Content-Type", "").lower()

                # 如果返回的是 HTML，说明可能是错误页或需重定向
                if "text/html" in content_type:
                    return None, None, "Received HTML instead of file"

                # 生成文件名
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                # 尝试从 URL 或 Content-Disposition 获取扩展名
                ext = self._get_extension(url, resp.headers)
                filename = f"{url_hash}{ext}"
                local_path = os.path.join(DOCUMENTS_DIR, filename)

                # 按块写入文件
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                return local_path, content_type, None

            except requests.exceptions.Timeout:
                error = f"Timeout"
            except requests.exceptions.ConnectionError as e:
                error = f"Connection error: {e}"
            except Exception as e:
                error = f"Download error: {e}"

            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

        return None, None, error

    def save_html(self, content: str, doc_id: str) -> str:
        """保存 HTML 内容到本地文件"""
        filepath = os.path.join(RAW_HTML_DIR, f"{doc_id}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    @staticmethod
    def _get_extension(url: str, headers: dict) -> str:
        """从 URL 或响应头获取文件扩展名"""
        # 从 URL 获取
        url_lower = url.lower()
        known_exts = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip", ".rar", ".ppt", ".pptx"]
        for ext in known_exts:
            if ext in url_lower:
                # 截取扩展名，去除查询参数
                idx = url_lower.find(ext)
                return url_lower[idx:idx + len(ext)]

        # 从 Content-Disposition 获取
        cd = headers.get("Content-Disposition", "")
        if "filename=" in cd:
            # 简单提取
            import re
            match = re.search(r'filename[^;=\n]*=["\']?([^"\';\n]*)', cd, re.I)
            if match:
                fname = match.group(1)
                _, ext = os.path.splitext(fname)
                if ext:
                    return ext

        return ".unknown"
