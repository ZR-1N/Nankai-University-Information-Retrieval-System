"""
爬虫工具函数 + 数据质量检查
v3.0.0：增强数据质量报告（content_quality 分布、CSV 导出、WARNING 检测）
"""
import json
import os
import re
import csv
from datetime import datetime
from collections import Counter, defaultdict
from config.settings import CRAWL_STATS_FILE, METADATA_FILE, DATA_DIR


def generate_doc_id(index: int, file_type: str = "html") -> str:
    """生成文档 ID"""
    if file_type and file_type != "html":
        return f"nk_file_{index:06d}"
    return f"nk_{index:06d}"


def save_metadata(metadata: dict):
    """追加一条元数据到 metadata.jsonl"""
    with open(METADATA_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(metadata, ensure_ascii=False) + "\n")


def load_metadata() -> list[dict]:
    """加载所有元数据"""
    if not os.path.exists(METADATA_FILE):
        return []
    records = []
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def compute_stats(preserve_process_stats: bool = True) -> dict:
    """从 metadata.jsonl 计算爬取统计

    Args:
        preserve_process_stats: 若为 True，从现有 crawl_stats.json 中保留爬取过程统计
                                （failed_urls, duplicate_urls, crawl_elapsed, crawl_speed）
    """
    records = load_metadata()
    stats = {
        "total_docs": len(records),
        "html_pages": 0,
        "pdf_files": 0,
        "doc_files": 0,
        "docx_files": 0,
        "xls_files": 0,
        "xlsx_files": 0,
        "zip_files": 0,
        "ppt_files": 0,
        "other_files": 0,
        "source_sites": {},
        "page_roles": {},
        "content_quality": {},
        "failed_urls": 0,
        "duplicate_urls": 0,
        "crawl_elapsed": 0.0,
        "crawl_speed": 0.0,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # 从已有 crawl_stats.json 保留爬取过程统计（这些只能由爬虫运行时产生）
    if preserve_process_stats and os.path.exists(CRAWL_STATS_FILE):
        try:
            with open(CRAWL_STATS_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
            stats["failed_urls"] = old.get("failed_urls", 0)
            stats["duplicate_urls"] = old.get("duplicate_urls", 0)
            stats["crawl_elapsed"] = old.get("crawl_elapsed", 0.0)
            stats["crawl_speed"] = old.get("crawl_speed", 0.0)
            stats["balanced_mode"] = old.get("balanced_mode", True)
            stats["max_source_ratio"] = old.get("max_source_ratio", 0.30)
            stats["source_crawled"] = old.get("source_crawled", {})
            stats["source_quota_info"] = old.get("source_quota_info", {})
        except (json.JSONDecodeError, Exception):
            pass
    for rec in records:
        ft = rec.get("file_type", "html")
        if ft == "html":
            stats["html_pages"] += 1
        elif ft == "pdf":
            stats["pdf_files"] += 1
        elif ft == "doc":
            stats["doc_files"] += 1
        elif ft == "docx":
            stats["docx_files"] += 1
        elif ft == "xls":
            stats["xls_files"] += 1
        elif ft == "xlsx":
            stats["xlsx_files"] += 1
        elif ft in ("zip", "rar"):
            stats["zip_files"] += 1
        elif ft in ("ppt", "pptx"):
            stats["ppt_files"] += 1
        else:
            stats["other_files"] += 1

        source = rec.get("source_site", "未知")
        stats["source_sites"][source] = stats["source_sites"].get(source, 0) + 1

        role = rec.get("page_role", "unknown")
        stats["page_roles"][role] = stats["page_roles"].get(role, 0) + 1

        cq = rec.get("content_quality", "unknown")
        stats["content_quality"][cq] = stats["content_quality"].get(cq, 0) + 1

        ps = rec.get("parse_status", "ok")
        stats["parse_status"] = stats.get("parse_status", {})
        stats["parse_status"][ps] = stats["parse_status"].get(ps, 0) + 1

    return stats


def save_stats(stats: dict):
    """保存爬取统计到 crawl_stats.json"""
    with open(CRAWL_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def extract_site_name(url: str, sources_config: list) -> str:
    """根据 URL 匹配站点名称"""
    for source in sources_config:
        base_url = source.get("base_url", "")
        if base_url and base_url in url:
            return source["name"]
    return "未知站点"


def clean_text(text: str) -> str:
    """清理文本"""
    if not text:
        return ""
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


# ============================================================
# 数据质量检查
# ============================================================

# 疑似导航噪声的关键词
NAVIGATION_NOISE_KEYWORDS = [
    "信息公开", "图书馆", "服务指南", "登录邮箱", "办公网",
    "新闻中心", "最新动态", "学院公告", "学生工作通知",
    "首 页", "学校概况", "学校简介",
    "上一条", "下一条", "打印", "关闭",
    "设为首页", "加入收藏", "联系我们",
    "版权所有", "津ICP备", "津公网安备",
]


def run_data_validation() -> dict:
    """
    运行数据质量验证
    返回质量报告字典
    """
    records = load_metadata()
    total = len(records)

    if total == 0:
        return {"error": "无数据", "total_docs": 0}

    # 标题统计
    no_title = [r for r in records
                if not r.get("title") or r.get("title") in ("无标题", "")]
    no_title_count = len(no_title)

    # 正文统计
    empty_content = [r for r in records
                     if not r.get("content", "").strip()]
    short_content = [r for r in records
                     if 0 < len(r.get("content", "")) < 100]
    avg_content_len = sum(len(r.get("content", "")) for r in records) // max(total, 1)

    # page_role 分布
    role_counts = Counter(r.get("page_role", "unknown") for r in records)

    # source_site 分布
    site_counts = Counter(r.get("source_site", "未知") for r in records)

    # file_type 分布
    type_counts = Counter(r.get("file_type", "html") for r in records)

    # content_quality 分布
    cq_counts = Counter(r.get("content_quality", "unknown") for r in records)

    # parse_status 分布
    ps_counts = Counter(r.get("parse_status", "ok") for r in records)

    # failed 按 source_site 分布
    failed_records = [r for r in records if r.get("content_quality") == "failed"]
    failed_by_source = Counter(r.get("source_site", "未知") for r in failed_records)
    # failed 按 file_type 分布
    failed_by_type = Counter(r.get("file_type", "html") for r in failed_records)
    # failed 按 URL pattern 分布
    failed_by_pattern = Counter()
    for r in failed_records:
        url = r.get("url", "")
        import re as re_mod
        m = re_mod.search(r'https?://[^/]+(/[^/]+/[^/]+/?)', url)
        pattern = m.group(1) if m else "other"
        failed_by_pattern[pattern] += 1

    # 重复检查
    urls = [r.get("url", "") for r in records]
    url_dupes = len(urls) - len(set(urls))

    hashes = [r.get("content_hash", "") for r in records]
    hash_dupes = len(hashes) - len(set(h for h in hashes if h))

    # 最大 source_site 占比
    max_source_site = ""
    max_source_pct = 0.0
    if site_counts:
        max_source_site = site_counts.most_common(1)[0][0]
        max_source_pct = round(site_counts[max_source_site] / total * 100, 1)

    # 疑似导航噪声
    noise_docs = []
    nav_noise_samples = []
    for r in records:
        title = r.get("title", "")
        content = r.get("content", "")
        noise_score = sum(1 for kw in NAVIGATION_NOISE_KEYWORDS
                          if kw in title or kw in content)
        if noise_score >= 5:
            noise_docs.append(r["doc_id"])
        if r.get("content_quality") == "nav_noise":
            nav_noise_samples.append({
                "doc_id": r["doc_id"],
                "url": r.get("url", ""),
                "title": r.get("title", "")[:100],
                "content_preview": r.get("content", "")[:200],
                "source_site": r.get("source_site", ""),
            })

    # 短正文样本（按 page_role 和 source_site 分组）
    short_content_samples = []
    for r in short_content:
        short_content_samples.append({
            "doc_id": r["doc_id"],
            "url": r.get("url", ""),
            "title": r.get("title", "")[:100],
            "content_length": len(r.get("content", "")),
            "content_preview": r.get("content", "")[:150],
            "page_role": r.get("page_role", "unknown"),
            "source_site": r.get("source_site", "未知"),
        })

    # 短正文按 page_role 分布
    short_by_role = Counter(
        r.get("page_role", "unknown") for r in short_content
    )
    # 短正文按 source_site 分布
    short_by_source = Counter(
        r.get("source_site", "未知") for r in short_content
    )

    # list 误判风险样本（标题是栏目名但被判定为 detail）
    COLUMN_NAMES = {
        "最新动态", "学院公告", "学生之窗", "科研信息",
        "本科生教学", "研究生教学", "研究生招生", "党团园地",
        "就业信息", "国际交流", "境外交流", "学生工作通知",
        "新闻中心", "通知公告", "学术活动", "校园生活",
    }
    list_misclassify = []
    for r in records:
        if r.get("page_role") == "detail" and r.get("title", "") in COLUMN_NAMES:
            list_misclassify.append({
                "doc_id": r["doc_id"],
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "source_site": r.get("source_site", ""),
            })

    # document 数量和比例
    doc_count = role_counts.get("document", 0)
    doc_pct = round(doc_count / total * 100, 1) if total else 0

    # 随机抽样
    import random
    sample_size = min(20, total)
    sample = random.sample(records, sample_size)

    # WARNING 列表
    warnings = []
    if max_source_pct > 50:
        warnings.append(f"最大 source_site [{max_source_site}] 占比 {max_source_pct}% > 50%")
    if doc_count == 0:
        warnings.append("document 数量为 0，无法支撑文档查询与下载功能")
    if short_content and len(short_content) / total > 0.50:
        warnings.append(f"短正文比例 {round(len(short_content)/total*100,1)}% > 50%")
    if len(nav_noise_samples) > total * 0.2:
        warnings.append(f"nav_noise 样本过多: {len(nav_noise_samples)} 条")
    if len(list_misclassify) > 0:
        warnings.append(f"疑似 list 误判为 detail: {len(list_misclassify)} 条")

    report = {
        "total_docs": total,
        "no_title_count": no_title_count,
        "no_title_ratio": round(no_title_count / total * 100, 1) if total else 0,
        "empty_content_count": len(empty_content),
        "empty_content_ratio": round(len(empty_content) / total * 100, 1) if total else 0,
        "short_content_count": len(short_content),
        "short_content_ratio": round(len(short_content) / total * 100, 1) if total else 0,
        "avg_content_length": avg_content_len,
        "page_role_distribution": dict(role_counts),
        "source_site_distribution": dict(site_counts),
        "file_type_distribution": dict(type_counts),
        "content_quality_distribution": dict(cq_counts),
        "parse_status_distribution": dict(ps_counts),
        "duplicate_urls": url_dupes,
        "duplicate_content_hashes": hash_dupes,
        "suspected_noise_docs": len(noise_docs),
        "max_source_site": max_source_site,
        "max_source_site_pct": max_source_pct,
        "document_count": doc_count,
        "document_pct": doc_pct,
        "list_misclassify_count": len(list_misclassify),
        "nav_noise_count": len(nav_noise_samples),
        "failed_count": len(failed_records),
        "failed_pct": round(len(failed_records) / total * 100, 1) if total else 0,
        "failed_by_source": dict(failed_by_source.most_common(10)),
        "failed_by_type": dict(failed_by_type),
        "failed_by_pattern": dict(failed_by_pattern.most_common(15)),
        "warnings": warnings,
        "short_content_by_role": dict(short_by_role),
        "short_content_by_source": dict(short_by_source),
        "sample_docs": [
            {
                "doc_id": r["doc_id"],
                "title": r.get("title", "")[:100],
                "source_site": r.get("source_site", ""),
                "file_type": r.get("file_type", ""),
                "page_role": r.get("page_role", "unknown"),
                "content_quality": r.get("content_quality", "unknown"),
                "content_length": r.get("content_length", len(r.get("content", ""))),
                "content_preview": r.get("content", "")[:150],
            }
            for r in sample
        ],
    }
    return report


def print_validation_report(report: dict):
    """打印数据质量报告"""
    print("\n" + "=" * 60)
    print("  数据质量报告 (Data Quality Report) v3.1")
    print("  统计来源：metadata.jsonl")
    print("=" * 60)

    if "error" in report:
        print(f"  {report['error']}")
        return

    print(f"  总文档数: {report['total_docs']}")
    print(f"  无标题: {report['no_title_count']} ({report['no_title_ratio']}%)")
    print(f"  空正文: {report['empty_content_count']} ({report['empty_content_ratio']}%)")
    print(f"  短正文 (<100字): {report['short_content_count']} ({report['short_content_ratio']}%)")
    print(f"  平均正文长度: {report['avg_content_length']} 字符")
    print(f"  重复 URL: {report['duplicate_urls']}")
    print(f"  重复 content_hash: {report['duplicate_content_hashes']}")
    print(f"  疑似导航噪声文档: {report['suspected_noise_docs']}")
    print(f"  最大 source_site: {report['max_source_site']} ({report['max_source_site_pct']}%)")
    print(f"  document 数量: {report['document_count']} ({report['document_pct']}%)")
    print(f"  疑似 list 误判: {report['list_misclassify_count']} 条")
    print(f"  nav_noise 样本: {report['nav_noise_count']} 条")
    print(f"  content_quality failed: {report.get('failed_count', 0)} ({report.get('failed_pct', 0)}%)")

    print(f"\n  page_role 分布:")
    for role, count in sorted(report.get("page_role_distribution", {}).items()):
        pct = round(count / report["total_docs"] * 100, 1)
        print(f"    {role}: {count} ({pct}%)")

    print(f"\n  source_site 分布:")
    for site, count in sorted(report.get("source_site_distribution", {}).items(),
                               key=lambda x: x[1], reverse=True):
        pct = round(count / report["total_docs"] * 100, 1)
        print(f"    {site}: {count} ({pct}%)")

    print(f"\n  file_type 分布:")
    for ft, count in sorted(report.get("file_type_distribution", {}).items()):
        print(f"    {ft}: {count}")

    print(f"\n  content_quality 分布:")
    for cq, count in sorted(report.get("content_quality_distribution", {}).items()):
        pct = round(count / report["total_docs"] * 100, 1)
        print(f"    {cq}: {count} ({pct}%)")

    print(f"\n  parse_status 分布:")
    for ps, count in sorted(report.get("parse_status_distribution", {}).items()):
        pct = round(count / report["total_docs"] * 100, 1)
        print(f"    {ps}: {count} ({pct}%)")

    # failed 分析
    failed_by_source = report.get("failed_by_source", {})
    if failed_by_source:
        print(f"\n  content_quality failed 按 source_site 分布:")
        for site, count in failed_by_source.items():
            pct = round(count / max(report.get("failed_count", 1), 1) * 100, 1)
            print(f"    {site}: {count} ({pct}%)")

    failed_by_pattern = report.get("failed_by_pattern", {})
    if failed_by_pattern:
        print(f"\n  content_quality failed 按 URL pattern 分布 (top 10):")
        for pattern, count in list(failed_by_pattern.items())[:10]:
            print(f"    {pattern}: {count}")

    print(f"\n  短正文按 page_role 分布:")
    for role, count in sorted(report.get("short_content_by_role", {}).items()):
        print(f"    {role}: {count}")

    print(f"\n  质量判定:")
    issues = []
    if report["no_title_ratio"] > 5:
        issues.append(f"[FAIL] 无标题比例 {report['no_title_ratio']}% > 5% 阈值")
    else:
        issues.append(f"[PASS] 无标题比例 {report['no_title_ratio']}% <= 5% 阈值")

    if report["empty_content_ratio"] > 10:
        issues.append(f"[FAIL] 空正文比例 {report['empty_content_ratio']}% > 10% 阈值")
    else:
        issues.append(f"[PASS] 空正文比例 {report['empty_content_ratio']}% <= 10% 阈值")

    roles = report.get("page_role_distribution", {})
    detail_pct = (roles.get("detail", 0) + roles.get("document", 0)) / report["total_docs"] * 100
    issues.append(f"[INFO] detail+document 占比: {round(detail_pct, 1)}%")

    if report["document_count"] == 0:
        issues.append(f"[WARNING] document 数量为 0")

    for issue in issues:
        print(f"    {issue}")

    # WARNING
    if report.get("warnings"):
        print(f"\n  [WARNING] 警告:")
        for w in report["warnings"]:
            print(f"    ! {w}")

    print(f"\n  抽样文档 (前 10 条):")
    print(f"  {'-' * 55}")
    for i, doc in enumerate(report.get("sample_docs", [])[:10], 1):
        title = doc["title"][:60]
        role = doc["page_role"]
        cq = doc.get("content_quality", "?")
        cl = doc.get("content_length", 0)
        print(f"  {i}. [{role}/{cq}/{cl}] {title}")
        print(f"     {doc['source_site']} | {doc['file_type']} | {doc['doc_id']}")


def save_validation_report(report: dict):
    """保存数据质量报告到文件（增强版：CSV + 多文件导出）"""
    data_dir = os.path.dirname(METADATA_FILE)

    # ============================================================
    # Markdown 报告
    # ============================================================
    md_path = os.path.join(data_dir, "data_quality_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 数据质量报告\n\n")
        f.write(f"> 统计来源：metadata.jsonl\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        if "error" in report:
            f.write(f"**错误:** {report['error']}\n")
            return

        f.write("## 概览\n\n")
        f.write(f"| 指标 | 值 |\n")
        f.write(f"|------|----|\n")
        f.write(f"| 总文档数 | {report['total_docs']} |\n")
        f.write(f"| 无标题数量 | {report['no_title_count']} ({report['no_title_ratio']}%) |\n")
        f.write(f"| 空正文数量 | {report['empty_content_count']} ({report['empty_content_ratio']}%) |\n")
        f.write(f"| 短正文数量 | {report['short_content_count']} ({report['short_content_ratio']}%) |\n")
        f.write(f"| 平均正文长度 | {report['avg_content_length']} 字符 |\n")
        f.write(f"| 重复 URL | {report['duplicate_urls']} |\n")
        f.write(f"| 重复 content_hash | {report['duplicate_content_hashes']} |\n")
        f.write(f"| 疑似噪声文档 | {report['suspected_noise_docs']} |\n")
        f.write(f"| 最大 source_site | {report['max_source_site']} ({report['max_source_site_pct']}%) |\n")
        f.write(f"| document 数量 | {report['document_count']} ({report['document_pct']}%) |\n")
        f.write(f"| 疑似 list 误判 | {report['list_misclassify_count']} 条 |\n")
        f.write(f"| nav_noise 样本 | {report['nav_noise_count']} 条 |\n")

        # WARNING
        if report.get("warnings"):
            f.write("\n## WARNING\n\n")
            for w in report["warnings"]:
                f.write(f"- **{w}**\n")

        f.write("\n## page_role 分布\n\n")
        for role, count in sorted(report.get("page_role_distribution", {}).items()):
            pct = round(count / report["total_docs"] * 100, 1)
            f.write(f"- **{role}**: {count} ({pct}%)\n")

        f.write("\n## 来源分布\n\n")
        for site, count in sorted(report.get("source_site_distribution", {}).items(),
                                   key=lambda x: x[1], reverse=True):
            pct = round(count / report["total_docs"] * 100, 1)
            f.write(f"- {site}: {count} ({pct}%)\n")

        f.write("\n## file_type 分布\n\n")
        for ft, count in sorted(report.get("file_type_distribution", {}).items()):
            f.write(f"- {ft}: {count}\n")

        f.write("\n## content_quality 分布\n\n")
        for cq, count in sorted(report.get("content_quality_distribution", {}).items()):
            pct = round(count / report["total_docs"] * 100, 1)
            f.write(f"- **{cq}**: {count} ({pct}%)\n")

        f.write("\n## parse_status 分布\n\n")
        for ps, count in sorted(report.get("parse_status_distribution", {}).items()):
            pct = round(count / report["total_docs"] * 100, 1)
            f.write(f"- **{ps}**: {count} ({pct}%)\n")

        # failed 分析
        failed_by_source = report.get("failed_by_source", {})
        if failed_by_source:
            f.write(f"\n## content_quality failed 分析\n\n")
            f.write(f"总计 failed: {report.get('failed_count', 0)} ({report.get('failed_pct', 0)}%)\n\n")
            f.write("### 按 source_site 分布\n\n")
            for site, count in failed_by_source.items():
                pct = round(count / max(report.get("failed_count", 1), 1) * 100, 1)
                f.write(f"- {site}: {count} ({pct}%)\n")
            failed_by_pattern = report.get("failed_by_pattern", {})
            if failed_by_pattern:
                f.write("\n### 按 URL pattern 分布 (top 15)\n\n")
                for pattern, count in list(failed_by_pattern.items())[:15]:
                    f.write(f"- `{pattern}`: {count}\n")

        f.write("\n## 短正文按 page_role 分布\n\n")
        for role, count in sorted(report.get("short_content_by_role", {}).items()):
            f.write(f"- {role}: {count}\n")

    print(f"\n报告已保存到: {md_path}")

    # ============================================================
    # JSON 样本
    # ============================================================
    sample_path = os.path.join(data_dir, "sample_docs.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(report.get("sample_docs", []), f, ensure_ascii=False, indent=2)
    print(f"样本已保存到: {sample_path}")

    # ============================================================
    # 短正文样本
    # ============================================================
    short_path = os.path.join(data_dir, "short_content_samples.json")
    records = load_metadata()
    short_content_samples = []
    for r in records:
        cl = len(r.get("content", ""))
        if 0 < cl < 100:
            short_content_samples.append({
                "doc_id": r["doc_id"],
                "url": r.get("url", ""),
                "title": r.get("title", "")[:100],
                "content_length": cl,
                "content_preview": r.get("content", "")[:150],
                "page_role": r.get("page_role", "unknown"),
                "source_site": r.get("source_site", "未知"),
                "content_quality": r.get("content_quality", "unknown"),
            })
    with open(short_path, "w", encoding="utf-8") as f:
        json.dump(short_content_samples[:50], f, ensure_ascii=False, indent=2)
    print(f"短正文样本已保存到: {short_path} (共 {len(short_content_samples)} 条，取前 50)")

    # ============================================================
    # 导航噪声样本
    # ============================================================
    noise_path = os.path.join(data_dir, "nav_noise_samples.json")
    nav_noise_samples = []
    for r in records:
        if r.get("content_quality") == "nav_noise":
            nav_noise_samples.append({
                "doc_id": r["doc_id"],
                "url": r.get("url", ""),
                "title": r.get("title", "")[:100],
                "content_preview": r.get("content", "")[:200],
                "source_site": r.get("source_site", ""),
            })
    with open(noise_path, "w", encoding="utf-8") as f:
        json.dump(nav_noise_samples[:50], f, ensure_ascii=False, indent=2)
    print(f"导航噪声样本已保存到: {noise_path} (共 {len(nav_noise_samples)} 条，取前 50)")

    # ============================================================
    # content_quality failed 样本
    # ============================================================
    failed_path = os.path.join(data_dir, "failed_content_samples.json")
    failed_samples = []
    for r in records:
        if r.get("content_quality") == "failed":
            url = r.get("url", "")
            import re as re_mod2
            m = re_mod2.search(r'https?://[^/]+(/[^/]+/[^/]+/?)', url)
            url_pattern = m.group(1) if m else "other"
            failed_samples.append({
                "doc_id": r["doc_id"],
                "url": url,
                "url_pattern": url_pattern,
                "title": r.get("title", "")[:100],
                "content_length": len(r.get("content", "")),
                "content_preview": r.get("content", "")[:200],
                "page_role": r.get("page_role", "unknown"),
                "source_site": r.get("source_site", "未知"),
                "file_type": r.get("file_type", "html"),
            })
    with open(failed_path, "w", encoding="utf-8") as f:
        json.dump(failed_samples[:100], f, ensure_ascii=False, indent=2)
    print(f"failed 样本已保存到: {failed_path} (共 {len(failed_samples)} 条，取前 100)")

    # ============================================================
    # CSV 导出
    # ============================================================

    # source_distribution.csv
    source_csv = os.path.join(data_dir, "source_distribution.csv")
    with open(source_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source_site", "count", "percentage"])
        for site, count in sorted(
            report.get("source_site_distribution", {}).items(),
            key=lambda x: x[1], reverse=True
        ):
            pct = round(count / report["total_docs"] * 100, 1)
            writer.writerow([site, count, pct])
    print(f"来源分布 CSV 已保存到: {source_csv}")

    # file_type_distribution.csv
    ft_csv = os.path.join(data_dir, "file_type_distribution.csv")
    with open(ft_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["file_type", "count", "percentage"])
        for ft, count in sorted(
            report.get("file_type_distribution", {}).items()
        ):
            pct = round(count / report["total_docs"] * 100, 1)
            writer.writerow([ft, count, pct])
    print(f"文件类型分布 CSV 已保存到: {ft_csv}")

    # page_role_distribution.csv
    pr_csv = os.path.join(data_dir, "page_role_distribution.csv")
    with open(pr_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["page_role", "count", "percentage"])
        for role, count in sorted(
            report.get("page_role_distribution", {}).items()
        ):
            pct = round(count / report["total_docs"] * 100, 1)
            writer.writerow([role, count, pct])
    print(f"页面角色分布 CSV 已保存到: {pr_csv}")
