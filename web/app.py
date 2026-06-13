"""
Flask Web 应用 - 搜索首页、结果页、日志页、快照页、下载、API
"""
import os
import json
from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, make_response,
)
from search_engine.search import SearchEngine
from search_engine.suggest import SuggestEngine
from search_engine.personalized_rank import PersonalizedRanker
from search_engine.inverted_index import InvertedIndex
from database.db import Database
from database.init_db import init_database
from crawler.snapshot import SnapshotManager
from config.settings import METADATA_FILE, CRAWL_STATS_FILE


# 全局实例
search_engine = SearchEngine()
suggest_engine = None
db = Database()
snapshot_manager = SnapshotManager(max_snapshots=50)


def create_app() -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "nankai-ir-system-2024"

    # 初始化数据库
    init_database()

    # 初始化搜索引擎（尝试加载索引）
    try:
        search_engine._ensure_initialized()
    except RuntimeError:
        print("[警告] 索引未构建，搜索功能不可用。请先运行: python run.py build-index")

    # 初始化搜索联想
    global suggest_engine
    suggest_engine = SuggestEngine(search_engine.index)

    # ==================== 注册路由 ====================

    @app.route("/")
    def index():
        """搜索首页"""
        profiles = PersonalizedRanker.get_profile_names()
        # 尝试获取统计信息
        stats = _get_stats_safe()
        return render_template(
            "index.html",
            profiles=profiles,
            stats=stats,
        )

    @app.route("/search")
    def search():
        """搜索结果页"""
        query = request.args.get("q", "").strip()
        if not query:
            return redirect(url_for("index"))

        search_type = request.args.get("type", "normal")
        user_id = request.args.get("user_id", "default")
        page = int(request.args.get("page", 1))
        match_mode = request.args.get("match_mode", "or")

        # 筛选参数
        filters = {}
        source_filter = request.args.get("source", "")
        file_type_filter = request.args.get("file_type", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")

        if source_filter:
            filters["source"] = source_filter
        if file_type_filter:
            filters["file_type"] = file_type_filter
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        try:
            results = search_engine.search(
                query=query,
                search_type=search_type,
                user_id=user_id,
                page=page,
                page_size=20,
                filters=filters,
                match_mode=match_mode,
            )

            # 记录查询日志
            db.log_search(
                user_id=user_id,
                query=query,
                search_type=search_type,
                filters=json.dumps(filters, ensure_ascii=False),
                result_count=results["total"],
            )

            # 获取筛选选项
            sources = search_engine.get_sources()
            file_types = search_engine.get_file_types()
            profiles = PersonalizedRanker.get_profile_names()

            return render_template(
                "results.html",
                query=query,
                search_type=search_type,
                user_id=user_id,
                match_mode=match_mode,
                results=results,
                sources=sources,
                file_types=file_types,
                profiles=profiles,
                filters=filters,
            )
        except RuntimeError as e:
            return render_template(
                "results.html",
                query=query,
                error=str(e),
                results={"total": 0, "results": [], "elapsed": 0},
            )

    @app.route("/logs")
    def logs():
        """查询日志页"""
        user_filter = request.args.get("user_id", "")
        page = int(request.args.get("page", 1))
        per_page = 50
        offset = (page - 1) * per_page

        logs_data = db.get_search_logs(
            user_id=user_filter or None,
            limit=per_page,
            offset=offset,
        )
        total_count = db.get_search_count()
        total_pages = max(1, -(-total_count // per_page))  # 向上取整

        # 热门查询
        popular = db.get_popular_queries(10)

        # 所有用户 ID
        all_users = set()
        for log in logs_data:
            all_users.add(log.get("user_id", ""))

        return render_template(
            "logs.html",
            logs=logs_data,
            popular=popular,
            user_filter=user_filter,
            all_users=sorted(all_users),
            page=page,
            total_pages=total_pages,
            total_count=total_count,
        )

    @app.route("/snapshot/<doc_id>")
    def snapshot(doc_id):
        """查看网页快照"""
        content = snapshot_manager.get_snapshot(doc_id)
        if content is None:
            return "快照不存在", 404
        # 直接返回 HTML 内容
        return content

    @app.route("/download/<doc_id>")
    def download(doc_id):
        """下载文档附件"""
        # 查找文档路径
        meta = search_engine.index.get_doc_meta(doc_id)
        if meta is None:
            return "文档不存在", 404

        download_path = meta.get("download_path", "")
        if not download_path or not os.path.exists(download_path):
            return "文件不存在", 404

        return send_file(
            download_path,
            as_attachment=True,
            download_name=os.path.basename(download_path),
        )

    @app.route("/api/suggest")
    def api_suggest():
        """搜索联想 API"""
        query = request.args.get("q", "")
        user_id = request.args.get("user_id", "default")

        if not suggest_engine:
            return jsonify([])

        suggestions = suggest_engine.get_suggestions(query, user_id, max_results=10)
        return jsonify(suggestions)

    @app.route("/api/click")
    def api_click():
        """记录点击"""
        doc_id = request.args.get("doc_id", "")
        query = request.args.get("query", "")
        user_id = request.args.get("user_id", "default")
        title = request.args.get("title", "")
        url = request.args.get("url", "")

        db.log_click(user_id, query, doc_id, title, url)
        return jsonify({"status": "ok"})

    @app.route("/api/stats")
    def api_stats():
        """系统统计 API"""
        stats = _get_stats_safe()
        try:
            search_engine._ensure_initialized()
            stats["index_docs"] = search_engine.index.get_total_docs()
        except RuntimeError:
            stats["index_docs"] = 0
        stats["search_count"] = db.get_search_count()
        return jsonify(stats)

    @app.route("/stats")
    def stats_page():
        """数据统计页"""
        return _render_stats_page()

    @app.route("/crawl-status")
    def crawl_status_page():
        """爬取状态页"""
        stats = _get_stats_safe()
        return render_template("crawl_status.html", stats=stats)

    @app.route("/api/crawl-status")
    def api_crawl_status():
        """爬取状态 API"""
        stats = _get_stats_safe()
        # 读取 checkpoint 信息
        checkpoint_path = "data/url_manager_checkpoint.json"
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    cp = json.load(f)
                # 只返回摘要信息
                stats["checkpoint"] = {
                    "total_seen": len(cp.get("seen_urls", [])),
                    "source_queues": {
                        k: sum(len(q) for q in v.values() if isinstance(v, dict))
                        for k, v in cp.get("source_queues", {}).items()
                    },
                    "total_crawled_estimate": cp.get("total_crawled", 0),
                }
            except Exception:
                stats["checkpoint"] = None
        return jsonify(stats)

    # 错误处理
    @app.errorhandler(404)
    def not_found(e):
        return render_template("index.html", error="页面不存在"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("index.html", error="服务器内部错误"), 500

    return app


def _render_stats_page():
    """渲染数据统计页"""
    from crawler.utils import run_data_validation
    stats = _get_stats_safe()
    try:
        search_engine._ensure_initialized()
        stats["index_docs"] = search_engine.index.get_total_docs()
        stats["index_terms"] = len(search_engine.index.get_content_terms_set())
    except RuntimeError:
        stats["index_docs"] = 0
        stats["index_terms"] = 0
    stats["search_count"] = db.get_search_count()

    # 尝试获取验证报告
    try:
        report = run_data_validation()
        stats["validation"] = report
    except Exception:
        stats["validation"] = None

    return render_template("stats.html", stats=stats)


def _get_stats_safe() -> dict:
    """安全地获取爬取统计"""
    stats = {"total_docs": 0, "html_pages": 0, "pdf_files": 0}
    if os.path.exists(CRAWL_STATS_FILE):
        try:
            with open(CRAWL_STATS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception:
            pass
    return stats


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
