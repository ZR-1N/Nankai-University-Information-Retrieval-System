"""
HTML 解析器 - 提取标题、正文、发布时间、链接、分页、page_role
优化版 v3.0.0：多级标题 fallback + 精确 list/detail 分类 + 内容质量评估 + 附件发现
"""
import re
import hashlib
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ============================================================
# 标题提取相关常量
# ============================================================

# 优先尝试的 CSS class/id 选择器（用于标题）
TITLE_SELECTORS = [
    ".article-title", ".news-title", ".content-title",
    ".arti_title", ".Article_Title", ".main-title",
    ".con_title", ".wp_articleTitle", ".wp_article_title",
    ".v_news_title", ".title", ".tit",
    "#title", "#ArticleTitle", "#vsb_title",
    ".bt", ".wzbt", ".newstitle", ".infotitle",
    ".artTitle", ".newsTitle", ".detail-title",
]

# 正文容器选择器
CONTENT_SELECTORS = [
    "#vsb_content", ".v_news_content", ".v_news_content_2",
    ".wp_articlecontent", ".wp_articleContent",
    ".article--content", ".article-content", ".news-content", ".content",
    ".main-content", ".con",
    "article", "main",
    ".TRS_Editor", ".TRS_PreAppend", ".zoom",
    ".newscontent", ".nr", ".detail-content",
    ".post-content", ".entry-content", ".post-body",
    # yzb.nankai.edu.cn 专用选择器
    ".column-news-con", ".wp-column-news", ".list-content",
    ".article", ".artCon", ".main-content",
]

# 需要跳过的 HTML 标签
# 注意：不跳过 form 标签，因为部分 CMS（如 AI 学院）将正文内容嵌套在 form 内
SKIP_TAGS = ["script", "style", "nav", "footer", "header", "aside",
             "noscript", "iframe", "select", "option", "button"]

# class/id 含以下关键词的区域应删除（导航噪声）
NOISE_CLASS_KEYWORDS = [
    "nav", "menu", "header", "footer", "sidebar",
    "breadcrumb", "copyright", "search", "login",
    "banner", "toolbar", "sitemap", "link",
    "toplink", "top_link", "topnav",
]

# 正文中应删除的噪声行/短语
NOISE_LINES = [
    "上一条", "下一条", "打印", "关闭", "返回列表", "返回",
    "作者：", "来源：", "点击数：", "发布时间：",
    "版权所有", "津ICP备", "津公网安备", "津教备",
    "地址：", "电话：", "邮编：", "邮箱：",
    "首页", "末页", "尾页", "下一页", "上一页",
    "设为首页", "加入收藏", "联系我们",
]

# 导航栏噪声短语（应完整清理）
NAV_BAR_PHRASES = [
    "新闻中心 最新动态 学院公告 学生之窗 科研信息 本科生教学 党团园地 研究生招生 研究生教学 就业信息 国际交流",
    "信息公开 图书馆 服务指南 登录邮箱 办公网",
    "首 页 学校概况 学校简介",
    "首页 学院概况 师资队伍 人才培养 科学研究 国际交流 党建工作 学生工作 招生就业 校友之家",
    "学院首页 师资队伍 学科建设 科学研究 本科教学 研究生培养 党建工作 学生工作 招生就业",
]

# 栏目名（用于 list 页面标题识别）
COLUMN_NAMES = {
    "最新动态", "学院公告", "学生之窗", "科研信息",
    "本科生教学", "研究生教学", "研究生招生", "党团园地",
    "就业信息", "国际交流", "境外交流", "学生工作通知",
    "南开新闻", "南开要闻", "综合新闻", "媒体南开",
    "硕士招生", "博士招生", "院系机构", "人才师资",
    "教育教学", "科学研究", "学校简介", "光影南开",
    "视频", "广播", "南开故事", "南开大学报",
    "新闻中心", "通知公告", "学术活动", "校园生活",
}

# 分页列表页 URL 特征模式
LIST_URL_PATTERNS = [
    re.compile(r'/list\d*\.htm', re.I),
    re.compile(r'/index[._]\d+\.(?:htm|shtml)', re.I),
    re.compile(r'/page[._]\d+\.(?:htm|shtml)', re.I),
    # AI 学院分页: /xwzx/zxdt/16.htm 等
    re.compile(r'/xwzx/[^/]+/\d+\.htm', re.I),
    # 通用栏目分页: /xxx/xxx/\d+\.htm (最后一段是数字)
    re.compile(r'/[^/]+/\d+\.htm', re.I),
    # index.shtml 栏目页
    re.compile(r'/index\.shtml', re.I),
]


class HTMLParser:
    """HTML 页面解析器（优化版 v3.0.0）"""

    def __init__(self, html: str, url: str,
                 anchor_text: str = "",
                 source_site: str = "",
                 seed_category: str = ""):
        self.html = html
        self.url = url
        self.anchor_text = anchor_text.strip() if anchor_text else ""
        self.source_site = source_site
        self.seed_category = seed_category
        self.soup = BeautifulSoup(html, "lxml")
        self._attachment_anchor_map: dict[str, str] = {}  # url → anchor_text

        # 清理脚本和样式（保留其他标签供解析用）
        for tag in self.soup(["script", "style", "noscript"]):
            tag.decompose()

    # ============================================================
    # 标题提取（多级 fallback）
    # ============================================================

    def extract_title(self) -> str:
        """
        提取网页标题，多级 fallback：
        1. og:title / meta title
        2. CSS 选择器（常见标题 class/id）
        3. h1 标签
        4. <title> 标签（清理后）
        5. h2 标签
        6. anchor_text（来自列表页链接文本）
        7. seed 配置中的 source + category 组合
        8. URL fallback
        """
        title = ""

        # Level 1: 元数据
        title = self._try_meta_title()
        if self._is_good_title(title):
            return title

        # Level 2: CSS 选择器
        title = self._try_css_selectors()
        if self._is_good_title(title):
            return title

        # Level 3: h1
        title = self._try_h1()
        if self._is_good_title(title):
            return title

        # Level 4: <title> 标签
        title = self._try_title_tag()
        if self._is_good_title(title):
            return title

        # Level 5: h2
        title = self._try_h2()
        if self._is_good_title(title):
            return title

        # Level 6: anchor_text
        if self.anchor_text and len(self.anchor_text) >= 3:
            return self.anchor_text[:200]

        # Level 7: seed 配置
        if self.source_site and self.seed_category:
            return f"{self.source_site}-{self.seed_category}"

        # Level 8: URL fallback
        return self._url_fallback_title()

    def _try_meta_title(self) -> str:
        """尝试从 og:title、meta name=title 获取标题"""
        for attr in ["property", "name"]:
            for val in ["og:title", "title", "Title", "dc.title"]:
                meta = self.soup.find("meta", attrs={attr: val})
                if meta and meta.get("content", "").strip():
                    title = meta["content"].strip()
                    if len(title) >= 3:
                        return self._clean_title(title)

        meta = self.soup.find("meta", attrs={"name": "twitter:title"})
        if meta and meta.get("content", "").strip():
            return self._clean_title(meta["content"].strip())

        return ""

    def _try_css_selectors(self) -> str:
        """从常见 CSS class/id 中提取标题"""
        candidates = []

        for selector in TITLE_SELECTORS:
            try:
                for elem in self.soup.select(selector):
                    text = elem.get_text(strip=True)
                    if text and len(text) >= 2:
                        candidates.append((len(text), text))
            except Exception:
                continue

        if not candidates:
            return ""

        valid = [(l, t) for l, t in candidates if 2 <= l <= 200]
        if valid:
            valid.sort(key=lambda x: x[0], reverse=True)
            return self._clean_title(valid[0][1])

        return ""

    def _try_h1(self) -> str:
        """尝试 h1 标签"""
        for h1 in self.soup.find_all("h1"):
            text = h1.get_text(strip=True)
            if text and 2 <= len(text) <= 200:
                return self._clean_title(text)
        return ""

    def _try_title_tag(self) -> str:
        """尝试 <title> 标签并智能清理"""
        if not self.soup.title or not self.soup.title.string:
            return ""
        raw = self.soup.title.string.strip()
        if not raw:
            return ""

        cleaned = re.split(r'\s*[-–—|_]\s*', raw)[0].strip()

        if len(cleaned) < 3:
            cleaned = raw

        generic_titles = {
            "南开大学", "计算机学院", "人工智能学院", "新闻网",
            "教务部", "研究生招生网", "首页", "主页", "欢迎",
            "Welcome", "Index", "index",
        }
        if cleaned in generic_titles and self.source_site and self.seed_category:
            return f"{self.source_site}-{self.seed_category}"

        return self._clean_title(cleaned)

    def _try_h2(self) -> str:
        """尝试 h2 标签"""
        for h2 in self.soup.find_all("h2", limit=3):
            text = h2.get_text(strip=True)
            if text and 3 <= len(text) <= 200:
                return self._clean_title(text)
        return ""

    def _url_fallback_title(self) -> str:
        """从 URL 最后一段生成标题"""
        parsed = urlparse(self.url)
        path = parsed.path.strip("/")
        if path:
            segments = path.split("/")
            last = segments[-1]
            last = re.sub(r'\.(htm|html|shtml|php|jsp|aspx?)$', '', last)
            last = last.replace("-", " ").replace("_", " ")
            if len(last) >= 2:
                return last[:200]
        if self.source_site:
            return self.source_site
        return parsed.netloc

    def _clean_title(self, title: str) -> str:
        """清理标题文本"""
        if not title:
            return ""
        title = re.sub(r'\s+', ' ', title).strip()
        title = title.strip("-–—|_•·")
        return title[:200]

    @staticmethod
    def _is_good_title(title: str) -> bool:
        """判断标题是否足够好"""
        if not title or len(title) < 3:
            return False
        if re.match(r'^[\d\W_]+$', title):
            return False
        return True

    # ============================================================
    # 页面角色识别（优化版：精确区分 list/detail）
    # ============================================================

    def classify_page_role(self) -> str:
        """
        识别页面角色：
        - portal：主页、门户页
        - list：栏目页、列表页、分页列表页
        - detail：详情页、内容页
        - document：附件文档
        """
        url_lower = self.url.lower()

        # 附件
        if any(ext in url_lower for ext in
               [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"]):
            return "document"

        # ================================================================
        # 规则 1: URL 匹配明显分页列表页模式 → list
        # ================================================================
        if self._url_matches_list_pattern():
            return "list"

        # ================================================================
        # 规则 2: URL 匹配详情页模式 → 倾向 detail
        # ================================================================
        if self._url_matches_detail_pattern():
            # 二次确认：内容是否真的像详情页
            if not self._looks_like_list():
                return "detail"
            # 即使 URL 像 detail，内容像 list 则优先 list
            return "list"

        # ================================================================
        # 规则 3: 门户/首页特征
        # ================================================================
        if self._url_matches_portal_pattern():
            if self._looks_like_portal():
                return "portal"

        # ================================================================
        # 规则 4: 内容特征判断
        # ================================================================
        if self._looks_like_list():
            return "list"
        if self._looks_like_detail():
            return "detail"

        # 默认为 detail（有 URL 路径深度的优先当详情页）
        parsed = urlparse(self.url)
        if len(parsed.path.strip("/").split("/")) >= 2:
            return "detail"

        return "list"

    def _url_matches_list_pattern(self) -> bool:
        """检查 URL 是否匹配已知的分页列表页模式"""
        for pat in LIST_URL_PATTERNS:
            if pat.search(self.url):
                # 排除 /info/ 模式（那是详情页）
                if "/info/" in self.url.lower():
                    return False
                # 排除 /system/ 模式（新闻详情页）
                if "/system/" in self.url.lower():
                    return False
                return True
        return False

    def _url_matches_detail_pattern(self) -> bool:
        """检查 URL 是否匹配详情页模式"""
        url_lower = self.url.lower()
        # /info/xxxx/xxxx.htm 是详情页
        if "/info/" in url_lower:
            return True
        # /system/....shtml 是新闻详情页
        if "/system/" in url_lower and url_lower.endswith(".shtml"):
            return True
        # /content/... 模式
        if "/content/" in url_lower:
            return True
        # /article/... 模式
        if "/article/" in url_lower:
            return True
        # yzb.nankai.edu.cn: /YYYY/MMDD/cXXXXaXXXXX/page.htm
        if re.search(r'/\d{4}/\d{4}/c\d+a\d+/page\.htm', url_lower):
            return True
        # yzb / 主站: /YYYY/MMDD/cXXXXXaXXXXX/page.htm
        if re.search(r'/\d{4}/\d{4}/c\d{5}a\d+/page\.htm', url_lower):
            return True
        # 通用: /cXXXXaXXXXX/page.htm (数字a数字/page.htm)
        if re.search(r'/c\d+a\d+/page\.htm', url_lower):
            return True
        # /page.htm 结尾的非列表页
        if url_lower.endswith(".htm") and "/list" not in url_lower:
            # 有日期路径段的
            if re.search(r'/\d{4}/\d{2,4}/', url_lower):
                return True
        # WordPress 单篇文章: ?p=NNNN
        if re.search(r'[?&]p=\d+', url_lower):
            return True
        return False

    def _url_matches_portal_pattern(self) -> bool:
        """检查 URL 是否像门户/首页"""
        url_clean = self.url.rstrip("/")
        portal_pats = [
            r'/$', r'/index\.(htm|html|shtml|php)$', r'/main\.htm$',
        ]
        for pat in portal_pats:
            if re.search(pat, url_clean):
                return True
        return False

    def _looks_like_portal(self) -> bool:
        """判断页面是否像门户/首页"""
        a_tags = self.soup.find_all("a", href=True)
        if len(a_tags) > 80:
            return True
        body = self.soup.find("body")
        if body:
            paragraphs = body.find_all(["p", "div"])
            long_texts = sum(1 for p in paragraphs
                           if len(p.get_text(strip=True)) > 200)
            if long_texts < 2:
                return True
        return False

    def _looks_like_list(self) -> bool:
        """
        判断页面是否像列表页（多重证据）
        特征：
        1. 大量 li 标签（>12）
        2. 标题是栏目名
        3. 正文包含多组日期+标题组合
        4. 详情类链接数量多
        5. 缺乏长正文段落
        """
        evidence = 0

        # 证据1: 多条 li
        list_items = self.soup.find_all("li")
        if len(list_items) > 12:
            evidence += 2

        # 证据2: 多个带日期的列表项
        body_text = self.soup.get_text() if self.soup.body else ""
        date_pattern = re.compile(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?')
        date_matches = date_pattern.findall(body_text)
        if len(date_matches) >= 5:
            evidence += 3

        # 证据3: 多个详情类链接
        a_tags = self.soup.find_all("a", href=True)
        detail_link_count = sum(1 for a in a_tags
                               if re.search(r'(detail|content|info|article|read|view)',
                                           a.get("href", "").lower()))
        if detail_link_count >= 5:
            evidence += 2

        # 证据4: 缺乏长段落
        body = self.soup.find("body")
        long_para_count = 0
        if body:
            for p in body.find_all(["p", "div"]):
                if len(p.get_text(strip=True)) > 150:
                    long_para_count += 1
        if long_para_count < 2:
            evidence += 2

        # 证据5: 标题是栏目名
        title = self.extract_title()
        if title in COLUMN_NAMES:
            evidence += 3

        return evidence >= 5

    def _looks_like_detail(self) -> bool:
        """判断页面是否像详情页"""
        # 有发布时间
        if self.extract_publish_time():
            return True
        # 有长正文段落
        body = self.soup.find("body")
        if body:
            paragraphs = body.find_all(["p", "div"])
            long_paras = [p for p in paragraphs
                         if len(p.get_text(strip=True)) > 100]
            if len(long_paras) >= 2:
                return True
        # 有明确的文章容器
        for sel in CONTENT_SELECTORS:
            if self.soup.select(sel):
                return True
        return False

    # ============================================================
    # 正文提取（优化版 v3：导航噪声清理 + 内容质量评估）
    # ============================================================

    def extract_content(self) -> str:
        """提取网页正文（优化版 v3）"""
        # 先移除噪声元素
        self._remove_noise_elements()

        # 策略1: 使用正文选择器
        for selector in CONTENT_SELECTORS:
            try:
                elems = self.soup.select(selector)
                for elem in elems:
                    # 排除伪正文（导航栏伪装成正文容器）
                    text = self._extract_clean_text(elem)
                    if len(text) > 100 and not self._is_nav_noise(text):
                        return text
            except Exception:
                continue

        # 策略2: <article> 或 <main>
        for tag_name in ["article", "main"]:
            tag = self.soup.find(tag_name)
            if tag:
                text = self._extract_clean_text(tag)
                if len(text) > 100 and not self._is_nav_noise(text):
                    return text

        # 策略3: body 下最大的 div（排除噪声区域后）
        body = self.soup.find("body")
        if body:
            for noise in body.find_all(["footer", "header", "nav", "aside"]):
                noise.decompose()

            # 进一步移除明显的导航 div
            for div in body.find_all("div", class_=re.compile(
                r"nav|menu|sidebar|toplink|top_link", re.I)):
                div.decompose()

            best_text = ""
            best_len = 0
            for div in body.find_all("div", limit=50):
                text = self._extract_clean_text(div)
                if len(text) > best_len and not self._is_nav_noise(text):
                    best_len = len(text)
                    best_text = text
            if best_text and len(best_text) > 80:
                return best_text

        # 策略4: 取整个 body
        if body:
            return self._extract_clean_text(body)

        return ""

    def _remove_noise_elements(self):
        """移除页面中的导航/噪声元素"""
        for tag_name in SKIP_TAGS:
            for tag in self.soup.find_all(tag_name):
                tag.decompose()

        for keyword in NOISE_CLASS_KEYWORDS:
            for tag in self.soup.find_all(class_=re.compile(keyword, re.I)):
                tag.decompose()
            for tag in self.soup.find_all(id=re.compile(keyword, re.I)):
                tag.decompose()

    def _extract_clean_text(self, element) -> str:
        """从元素中提取文本并清理噪声行"""
        if element is None:
            return ""
        text = element.get_text(separator="\n", strip=True)
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            skip = False
            for noise in NOISE_LINES:
                if noise in line:
                    skip = True
                    break
            if not skip:
                # 跳过纯导航链接行（很多短链接挤在一起）
                if len(line) < 5:
                    skip = True
                if not skip:
                    clean_lines.append(line)

        result = "\n".join(clean_lines)

        # 清理导航栏噪声短语
        for nav_phrase in NAV_BAR_PHRASES:
            result = result.replace(nav_phrase, "")

        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)
        return result.strip()

    @staticmethod
    def _is_nav_noise(text: str) -> bool:
        """检查文本是否为导航栏噪声"""
        if not text:
            return False
        # 导航栏特征：包含大量短链接文本和栏目名
        noise_score = 0
        for phrase in NAV_BAR_PHRASES:
            # 检查是否大部分是导航短语
            if phrase[:50] in text:
                noise_score += 5
        # 检查栏目名密度
        col_count = sum(1 for col in COLUMN_NAMES if col in text)
        if col_count >= 4:
            noise_score += col_count
        return noise_score >= 5

    def assess_content_quality(self, content: str, title: str,
                               page_role: str) -> str:
        """
        评估内容质量
        返回: good / short / nav_noise / fallback / failed
        """
        if not content:
            return "failed"

        content_len = len(content)

        # 检查导航噪声
        if self._is_nav_noise(content):
            return "nav_noise"

        # 太短
        if content_len < 50:
            return "failed"
        if content_len < 100:
            return "short"

        # list 页面的短内容是正常的
        if page_role == "list" and content_len < 200:
            return "short"

        return "good"

    # ============================================================
    # 发布时间提取
    # ============================================================

    def extract_publish_time(self) -> str:
        """提取发布时间"""
        for meta_name in ["pubdate", "publishdate", "dc.date", "citation_date",
                          "date", "article:published_time", "release_date",
                          "PubDate", "publish_date"]:
            meta = self.soup.find("meta", attrs={"name": meta_name})
            if meta and meta.get("content"):
                return self._parse_date(meta["content"])
            meta = self.soup.find("meta", property=meta_name)
            if meta and meta.get("content"):
                return self._parse_date(meta["content"])

        date_patterns = [
            r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?',
            r'发布时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'发布日期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'日期[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, self.html)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    y, m, d = groups[0], groups[1], groups[2]
                    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                elif len(groups) == 1:
                    return groups[0]
        return ""

    # ============================================================
    # 链接提取
    # ============================================================

    def extract_links(self) -> list[dict]:
        """
        提取页面中所有链接，返回带 anchor_text 的列表
        """
        links = []
        for a_tag in self.soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            try:
                full_url = urljoin(self.url, href)
            except (ValueError, Exception):
                # 跳过无法解析的 URL（如含非法字符的 netloc）
                continue
            anchor = a_tag.get_text(strip=True)[:200]
            is_detail = self._looks_like_detail_link(full_url)
            links.append({
                "url": full_url,
                "anchor_text": anchor,
                "is_detail": is_detail,
            })
        return links

    def _looks_like_detail_link(self, url: str) -> bool:
        """判断链接是否像详情页"""
        url_lower = url.lower()
        # 排除列表页
        for pat in LIST_URL_PATTERNS:
            if pat.search(url):
                return False

        # yzb 专用：/YYYY/MMDD/cXXXXaXXXXX/page.htm 是强信号详情页
        if re.search(r'/\d{4}/\d{2,4}/c\d+a\d+/page\.htm', url_lower):
            return True

        # WordPress 单篇文章: ?p=NNNN
        if re.search(r'[?&]p=\d+', url_lower):
            return True

        # WordPress 单页面: ?page_id=NNNN
        if re.search(r'[?&]page_id=\d+', url_lower):
            return True

        # WordPress 分类/Category 不是详情，跳过
        if re.search(r'[?&]cat=\d+', url_lower):
            return False

        # 含明显内容页标记
        detail_markers = [
            "content", "detail", "info", "article", "read", "view",
            "page", "show", "display",
        ]
        for marker in detail_markers:
            if marker in url_lower:
                # /info/ 是强信号
                if f"/{marker}/" in url_lower:
                    return True

        # 有路径深度
        try:
            parsed = urlparse(url)
        except (ValueError, Exception):
            return False
        segments = [s for s in parsed.path.strip("/").split("/") if s]
        if len(segments) >= 2:
            last = segments[-1].lower()
            if re.search(r'\d{4}', last):  # 含年份
                return True
            if last.endswith((".htm", ".html", ".shtml")) and not last.startswith(
                ("index", "list")
            ):
                return True
            # 含日期路径段 /YYYY/MMDD/ 的页面
            if len(segments) >= 2 and re.search(r'^\d{4}$', segments[0]):
                return True

        return False

    def extract_pagination_links(self) -> list[str]:
        """提取分页链接"""
        pagination_links = []
        next_texts = ["下一页", "下页", "尾页", "末页", "next", "»", "›"]
        for a_tag in self.soup.find_all("a", href=True):
            text = a_tag.get_text(strip=True).lower()
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:")):
                continue
            for nt in next_texts:
                if nt.lower() == text or nt in text:
                    try:
                        full_url = urljoin(self.url, href)
                    except (ValueError, Exception):
                        continue
                    if full_url not in pagination_links:
                        pagination_links.append(full_url)
                    break

        page_containers = self.soup.find_all(class_=re.compile(r"page", re.I))
        for container in page_containers:
            for a_tag in container.find_all("a", href=True):
                text = a_tag.get_text(strip=True)
                if text.isdigit():
                    try:
                        full_url = urljoin(self.url, a_tag["href"])
                    except (ValueError, Exception):
                        continue
                    if full_url not in pagination_links:
                        pagination_links.append(full_url)

        page_patterns = [
            r'/list(\d+)\.htm',
            r'/index[._](\d+)\.(?:htm|shtml)',
            r'/page[._](\d+)\.(?:htm|shtml)',
        ]
        for pat in page_patterns:
            match = re.search(pat, self.url)
            if match:
                current_page = int(match.group(1))
                for offset in range(-5, 6):
                    if offset == 0:
                        continue
                    new_page = current_page + offset
                    if new_page > 0:
                        new_url = re.sub(
                            pat,
                            lambda m, cp=current_page, np=new_page:
                                m.group(0).replace(str(cp), str(np)),
                            self.url
                        )
                        if new_url not in pagination_links:
                            pagination_links.append(new_url)
                break

        return pagination_links

    # ============================================================
    # 附件链接提取（优化版 v3）
    # ============================================================

    def extract_attachment_links(self) -> list[str]:
        """提取附件下载链接（支持 URL 参数 + 链接文本判断）"""
        attachment_links = []
        ext_patterns = [".pdf", ".doc", ".docx", ".xls", ".xlsx",
                       ".zip", ".rar", ".ppt", ".pptx"]

        # 附件关键词（用于从链接文本判断）
        attachment_keywords = [
            "附件", "下载", "申请表", "汇总表", "申报书",
            "材料", "PDF", "DOC", "XLS", "表格", "模板",
            "通知", "规定", "办法", "章程", "手册", "指南",
            "培养方案", "教学计划", "培养计划",
        ]

        for a_tag in self.soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            href_lower = href.lower()
            anchor_text = a_tag.get_text(strip=True)
            is_attachment = False

            # 方法1: URL 扩展名匹配
            for ext in ext_patterns:
                # 检查 path 部分（不含 query）
                try:
                    path = urlparse(href).path.lower() if "://" in href else href_lower
                except (ValueError, Exception):
                    continue
                if ext in path:
                    is_attachment = True
                    break

            # 方法2: 链接文本关键词判断
            if not is_attachment:
                for kw in attachment_keywords:
                    if kw in anchor_text:
                        is_attachment = True
                        break

            if is_attachment:
                try:
                    full_url = urljoin(self.url, href)
                except (ValueError, Exception):
                    continue
                if full_url not in attachment_links:
                    attachment_links.append(full_url)
                    self._attachment_anchor_map[full_url] = anchor_text

        return attachment_links

    def _get_attachment_anchor_text(self, url: str) -> str:
        """获取附件链接的 anchor text"""
        return self._attachment_anchor_map.get(url, "")

    # ============================================================
    # 摘要生成
    # ============================================================

    def extract_summary(self, content: str, max_len: int = 200) -> str:
        """生成摘要"""
        if not content:
            return ""
        text = re.sub(r'\s+', ' ', content).strip()
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    def _parse_date(self, date_str: str) -> str:
        """解析日期字符串为 YYYY-MM-DD"""
        if not date_str:
            return ""
        date_str = date_str.strip()
        match = re.search(r'(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})[日]?', date_str)
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            return date_str[:10]
        return date_str
