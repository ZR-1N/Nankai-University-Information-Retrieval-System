"""
高亮与摘要模块

对搜索结果生成带关键词高亮的摘要
"""
import re


def highlight_keywords(text: str, keywords: list[str], tag: str = "mark") -> str:
    """
    在文本中高亮关键词
    使用 <mark> 标签包裹匹配的关键词
    """
    if not text or not keywords:
        return text or ""

    # 按关键词长度降序排序，避免短关键词被长关键词部分替换
    sorted_kw = sorted(set(keywords), key=len, reverse=True)

    # 构建正则模式
    escaped = [re.escape(kw) for kw in sorted_kw]
    pattern = re.compile("(" + "|".join(escaped) + ")", re.IGNORECASE)

    result = pattern.sub(f"<{tag}>\\1</{tag}>", text)
    return result


def generate_snippet(content: str, keywords: list[str], max_len: int = 300) -> str:
    """
    生成带高亮的摘要片段
    从正文中截取包含关键词的片段，并高亮关键词
    """
    if not content:
        return ""

    if not keywords:
        # 无关键词时返回前 max_len 字符
        return content[:max_len] + ("..." if len(content) > max_len else "")

    # 查找第一个关键词的位置
    first_pos = len(content)
    for kw in keywords:
        pos = content.lower().find(kw.lower())
        if pos != -1 and pos < first_pos:
            first_pos = pos

    if first_pos == len(content):
        # 没有找到任何关键词，返回开头
        snippet = content[:max_len]
        if len(content) > max_len:
            snippet += "..."
    else:
        # 从关键词前 50 字符开始截取
        start = max(0, first_pos - 50)
        end = min(len(content), start + max_len)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet += "..."

    # 高亮关键词
    return highlight_keywords(snippet, keywords)


def generate_title_highlight(title: str, keywords: list[str]) -> str:
    """生成高亮标题"""
    return highlight_keywords(title, keywords)


def extract_match_explanation(doc: dict, query_terms: list[str]) -> str:
    """
    生成"为什么匹配"的解释信息
    """
    reasons = []
    title = doc.get("title", "")
    content = doc.get("content", "")
    source = doc.get("source_site", "")

    # 检查标题匹配
    title_matches = [t for t in query_terms if t.lower() in title.lower()]
    if title_matches:
        reasons.append(f"标题命中: {', '.join(title_matches)}")

    # 检查正文匹配
    content_matches = [t for t in query_terms if t.lower() in (content or "").lower()]
    if content_matches:
        reasons.append(f"正文命中: {', '.join(content_matches)}")

    # 检查来源匹配
    source_matches = [t for t in query_terms if t.lower() in source.lower()]
    if source_matches:
        reasons.append(f"来源匹配: {', '.join(source_matches)}")

    if not reasons:
        reasons.append("模糊匹配")

    return " | ".join(reasons)
