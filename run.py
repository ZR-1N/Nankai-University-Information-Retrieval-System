#!/usr/bin/env python3
"""
南开大学信息检索系统 - 统一命令行入口

用法:
    python run.py crawl --limit 100
    python run.py crawl --limit 100 --fresh
    python run.py crawl --limit 1000 --balanced
    python run.py crawl --limit 1000 --fresh --balanced
    python run.py build-index
    python run.py search "南开大学"
    python run.py search "南开*" --type wildcard
    python run.py search "奖学今" --type fuzzy
    python run.py search "研究生 复试" --match-mode and
    python run.py validate-data
    python run.py stats
    python run.py web
"""
import argparse
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_crawl(args):
    """命令行：爬取"""
    from crawler.crawler import Crawler
    crawler = Crawler(
        limit=args.limit,
        resume=args.resume,
        delay=args.delay,
        fresh=args.fresh,
        balanced=not args.no_balanced,  # 默认启用 balanced
    )
    crawler.run()
    print("\n爬取完成！运行 'python run.py stats' 查看统计。")


def cmd_build_index(args):
    """命令行：构建索引"""
    from indexer.build_index import IndexBuilder
    builder = IndexBuilder()
    builder.run()
    print("\n索引构建完成！运行 'python run.py web' 启动Web服务。")


def cmd_search(args):
    """命令行：搜索"""
    from search_engine.search import SearchEngine
    engine = SearchEngine()

    search_type = args.type or "normal"
    user_id = args.user or "default"

    # 确定 match_mode
    match_mode = args.match_mode
    if not match_mode:
        # 自动推断：含空格默认 and
        if " " in args.query and search_type in ("normal", "multi"):
            match_mode = "and"
        else:
            match_mode = "or"

    results = engine.search(
        query=args.query,
        search_type=search_type,
        user_id=user_id,
        page=1,
        page_size=args.limit or 20,
        match_mode=match_mode,
    )
    print(f"\n查询: {args.query}")
    print(f"类型: {search_type}")
    print(f"用户: {user_id}")
    print(f"匹配模式: {match_mode}")
    print(f"结果数量: {results['total']}")
    print(f"耗时: {results['elapsed']:.3f}s")
    print("-" * 60)
    for i, doc in enumerate(results.get("results", []), 1):
        print(f"\n{i}. {doc['title']}")
        print(f"   来源: {doc['source_site']} | 类型: {doc['file_type']} | "
              f"角色: {doc.get('page_role', '?')} | "
              f"质量: {doc.get('content_quality', '?')} | "
              f"分数: {doc.get('final_score', doc.get('score', 0)):.3f}")
        if doc.get("snippet"):
            print(f"   摘要: {doc['snippet'][:120]}...")
        elif doc.get("summary"):
            print(f"   摘要: {doc['summary'][:120]}...")
        print(f"   URL: {doc['url']}")


def cmd_validate_data(args):
    """命令行：数据质量验证"""
    from crawler.utils import (
        run_data_validation, print_validation_report, save_validation_report
    )
    report = run_data_validation()
    print_validation_report(report)
    save_validation_report(report)


def cmd_stats(args):
    """命令行：查看统计"""
    import json
    from config.settings import CRAWL_STATS_FILE, METADATA_FILE
    from crawler.utils import load_metadata, compute_stats, save_stats

    # 直接从 metadata.jsonl 重新计算所有统计（确保一致性）
    print("统计来源：metadata.jsonl（实时计算）")
    stats = compute_stats()

    # 同步写入 crawl_stats.json
    save_stats(stats)

    print("=" * 50)
    print("  爬取统计")
    print("=" * 50)
    print(f"  总文档数: {stats.get('total_docs', 0)}")
    print(f"  HTML 页面: {stats.get('html_pages', 0)}")
    print(f"  PDF 文件: {stats.get('pdf_files', 0)}")
    print(f"  DOC 文件: {stats.get('doc_files', 0)}")
    print(f"  DOCX 文件: {stats.get('docx_files', 0)}")
    print(f"  XLS 文件: {stats.get('xls_files', 0)}")
    print(f"  XLSX 文件: {stats.get('xlsx_files', 0)}")
    print(f"  ZIP/RAR: {stats.get('zip_files', 0)}")
    print(f"  PPT 文件: {stats.get('ppt_files', 0)}")
    print(f"  失败 URL: {stats.get('failed_urls', 0)}")
    print(f"  重复 URL: {stats.get('duplicate_urls', 0)}")

    print(f"\n  来源分布:")
    total = stats.get("total_docs", 1)
    for site, count in sorted(stats.get("source_sites", {}).items(),
                               key=lambda x: x[1], reverse=True):
        pct = round(count / max(total, 1) * 100, 1)
        print(f"    - {site}: {count} ({pct}%)")

    print(f"\n  页面角色分布:")
    for role, count in stats.get("page_roles", {}).items():
        pct = round(count / max(total, 1) * 100, 1)
        print(f"    - {role}: {count} ({pct}%)")

    print(f"\n  内容质量分布:")
    for cq, count in stats.get("content_quality", {}).items():
        pct = round(count / max(total, 1) * 100, 1)
        print(f"    - {cq}: {count} ({pct}%)")

    # 索引统计
    index_dir = os.path.join(os.path.dirname(__file__), "data", "index")
    if os.path.exists(os.path.join(index_dir, "index_stats.json")):
        with open(os.path.join(index_dir, "index_stats.json"), "r",
                  encoding="utf-8") as f:
            idx_stats = json.load(f)
        print("\n" + "=" * 50)
        print("  索引统计")
        print("=" * 50)
        print(f"  文档总数: {idx_stats.get('doc_count', 0)}")
        print(f"  词条总数: {idx_stats.get('term_count', 0)}")


def cmd_web(args):
    """命令行：启动 Web 服务"""
    from web.app import create_app
    app = create_app()
    host = args.host or "127.0.0.1"
    port = args.port or 5000
    debug = not args.no_debug
    print(f"\n启动 Web 服务: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


def main():
    parser = argparse.ArgumentParser(
        description="南开大学信息检索系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py crawl --limit 100
  python run.py crawl --limit 100 --fresh
  python run.py crawl --limit 1000 --fresh --balanced
  python run.py build-index
  python run.py search "南开大学"
  python run.py search "南开*" --type wildcard
  python run.py search "奖学今" --type fuzzy
  python run.py search "研究生 复试" --match-mode and
  python run.py validate-data
  python run.py stats
  python run.py web
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # crawl
    crawl_parser = subparsers.add_parser("crawl", help="爬取网页")
    crawl_parser.add_argument("--limit", type=int, default=100,
                              help="爬取数量限制")
    crawl_parser.add_argument("--resume", action="store_true",
                              help="断点续爬")
    crawl_parser.add_argument("--delay", type=float, default=1.0,
                              help="请求间隔（秒）")
    crawl_parser.add_argument("--fresh", action="store_true",
                              help="清除旧数据重新爬取")
    crawl_parser.add_argument("--balanced", action="store_true",
                              default=True,
                              help="启用多源均衡爬取（默认启用）")
    crawl_parser.add_argument("--no-balanced", action="store_true",
                              help="关闭多源均衡爬取")

    # build-index
    build_parser = subparsers.add_parser("build-index", help="构建索引")

    # search
    search_parser = subparsers.add_parser("search", help="搜索")
    search_parser.add_argument("query", type=str, help="查询词")
    search_parser.add_argument("--type", type=str, default="normal",
                               choices=["normal", "exact", "multi",
                                        "wildcard", "fuzzy", "doc"],
                               help="查询类型")
    search_parser.add_argument("--user", type=str, default="default",
                               help="用户画像")
    search_parser.add_argument("--limit", type=int, default=10,
                               help="显示数量")
    search_parser.add_argument("--match-mode", type=str,
                               choices=["and", "or"],
                               help="多关键词匹配模式（默认：含空格自动 and）")

    # validate-data
    validate_parser = subparsers.add_parser("validate-data",
                                             help="数据质量验证")

    # stats
    stats_parser = subparsers.add_parser("stats", help="查看统计")

    # web
    web_parser = subparsers.add_parser("web", help="启动Web服务")
    web_parser.add_argument("--host", type=str, default="127.0.0.1",
                            help="监听地址")
    web_parser.add_argument("--port", type=int, default=5000,
                            help="监听端口")
    web_parser.add_argument("--no-debug", action="store_true",
                            help="关闭调试模式")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "crawl": cmd_crawl,
        "build-index": cmd_build_index,
        "search": cmd_search,
        "validate-data": cmd_validate_data,
        "stats": cmd_stats,
        "web": cmd_web,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
