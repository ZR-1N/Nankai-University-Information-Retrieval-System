"""
数据库初始化模块
"""
import sqlite3
import os
from config.settings import DB_FILE, DATABASE_DIR


def init_database():
    """初始化 SQLite 数据库，创建表结构"""
    os.makedirs(DATABASE_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 查询日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            query TEXT NOT NULL,
            search_type TEXT DEFAULT 'normal',
            filters TEXT DEFAULT '',
            result_count INTEGER DEFAULT 0,
            search_time TEXT NOT NULL
        )
    """)

    # 点击日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS click_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT DEFAULT 'default',
            query TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            url TEXT DEFAULT '',
            click_time TEXT NOT NULL
        )
    """)

    # 为常用查询创建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_logs_user
        ON search_logs(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_logs_time
        ON search_logs(search_time)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_logs_query
        ON search_logs(query)
    """)

    conn.commit()
    conn.close()

    print(f"数据库初始化完成: {DB_FILE}")


if __name__ == "__main__":
    init_database()
