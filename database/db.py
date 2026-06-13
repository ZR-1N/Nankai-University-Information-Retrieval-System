"""
数据库操作模块 - 查询日志和点击日志的读写
"""
import sqlite3
import os
from datetime import datetime
from config.settings import DB_FILE


class Database:
    """数据库操作封装"""

    def __init__(self):
        self.db_file = DB_FILE

    def _get_conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_file)

    def log_search(self, user_id: str, query: str, search_type: str,
                   filters: str = "", result_count: int = 0):
        """记录查询日志"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO search_logs (user_id, query, search_type, filters,
                   result_count, search_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, query, search_type, filters, result_count,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] 记录查询日志失败: {e}")

    def log_click(self, user_id: str, query: str, doc_id: str,
                  title: str = "", url: str = ""):
        """记录点击日志"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO click_logs (user_id, query, doc_id, title, url, click_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, query, doc_id, title, url,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DB] 记录点击日志失败: {e}")

    def get_search_logs(self, user_id: str = None, limit: int = 100,
                        offset: int = 0) -> list[dict]:
        """获取查询日志"""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id:
                cursor.execute(
                    """SELECT * FROM search_logs WHERE user_id = ?
                       ORDER BY search_time DESC LIMIT ? OFFSET ?""",
                    (user_id, limit, offset)
                )
            else:
                cursor.execute(
                    """SELECT * FROM search_logs
                       ORDER BY search_time DESC LIMIT ? OFFSET ?""",
                    (limit, offset)
                )

            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[DB] 获取查询日志失败: {e}")
            return []

    def get_click_logs(self, user_id: str = None, limit: int = 100) -> list[dict]:
        """获取点击日志"""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id:
                cursor.execute(
                    """SELECT * FROM click_logs WHERE user_id = ?
                       ORDER BY click_time DESC LIMIT ?""",
                    (user_id, limit)
                )
            else:
                cursor.execute(
                    """SELECT * FROM click_logs
                       ORDER BY click_time DESC LIMIT ?""",
                    (limit,)
                )

            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[DB] 获取点击日志失败: {e}")
            return []

    def get_popular_queries(self, limit: int = 10) -> list[dict]:
        """获取热门查询"""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT query, COUNT(*) as cnt
                   FROM search_logs
                   GROUP BY query
                   ORDER BY cnt DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[DB] 获取热门查询失败: {e}")
            return []

    def get_search_count(self) -> int:
        """获取查询总数"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM search_logs")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
