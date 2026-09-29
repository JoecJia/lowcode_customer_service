"""数据库连接与 DDL 管理。

统一入口：get_db() 返回 sqlite3.Connection，init_db() 负责建表和迁移。
各 service 层通过 database.get_db() 获取连接，不再各自管理连接和 DDL。
"""

import os
import sqlite3

from config import DB_PATH

_db_initialized = False


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动建表/迁移）。"""
    global _db_initialized
    if not _db_initialized:
        _init_db()
        _db_initialized = True

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db() -> None:
    """建表 + 迁移（幂等）。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        # ========== 建表 ==========
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                password    TEXT    NOT NULL,
                role        TEXT    DEFAULT 'user',
                avatar      TEXT    DEFAULT '',
                can_chat    INTEGER DEFAULT 1,
                can_admin   INTEGER DEFAULT 0,
                created_at  REAL    NOT NULL,
                updated_at  REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT DEFAULT '',
                status      TEXT DEFAULT 'active',
                user_id     INTEGER REFERENCES users(id),
                deleted_at  REAL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT NOT NULL,
                role             TEXT NOT NULL,
                content          TEXT NOT NULL,
                reasoning_content TEXT DEFAULT '',
                created_at       REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);

            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                user_id     INTEGER NOT NULL,
                created_at  REAL    NOT NULL,
                status      TEXT    DEFAULT 'pending',
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback(session_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_user_session ON feedback(user_id, session_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_unique ON feedback(user_id, session_id);
        """)

        conn.commit()

    # ========== 迁移（ALTER TABLE 必须独立事务） ==========
    _run_migrations()


def _run_migrations() -> None:
    """列迁移（幂等，通过 try/except 保证重复执行安全）。"""
    migrations = [
        # sessions 表补列
        ("sessions", "user_id", "INTEGER REFERENCES users(id)"),
        ("sessions", "deleted_at", "REAL"),
        # users 表补列
        ("users", "can_chat", "INTEGER DEFAULT 1"),
        ("users", "can_admin", "INTEGER DEFAULT 0"),
    ]

    with sqlite3.connect(DB_PATH) as conn:
        for table, column, col_def in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在

        # 补齐可能缺失的索引
        index_sql = [
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_deleted ON sessions(user_id, deleted_at)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)",
        ]
        for sql in index_sql:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()
