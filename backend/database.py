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
                uid         TEXT,
                fid         TEXT,
                realname    TEXT    DEFAULT '',
                role        TEXT    DEFAULT 'user',
                avatar      TEXT    DEFAULT '',
                can_chat    INTEGER DEFAULT 1,
                can_admin   INTEGER DEFAULT 0,
                created_at  REAL    NOT NULL,
                updated_at  REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            -- 注意：idx_users_uid 必须放在 _run_migrations() 里创建。
            -- 老库的 users 表已存在，CREATE TABLE IF NOT EXISTS 不会补 uid 列，
            -- 此处直接建索引会报 "no such column: uid"。

            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT DEFAULT '',
                scope       TEXT DEFAULT 'frontend',
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
                steps            TEXT DEFAULT '',
                attachments      TEXT DEFAULT '[]',
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

            -- Context 变更批次（确认/回滚的唯一原子单元，见开发文档 §2.2）
            CREATE TABLE IF NOT EXISTS context_change_batch (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_no       TEXT NOT NULL UNIQUE,
                session_id     TEXT NOT NULL,
                operator       TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'pending',
                item_count     INTEGER NOT NULL DEFAULT 0,
                summary        TEXT DEFAULT '',
                source         TEXT DEFAULT 'agent',
                restored_from  INTEGER,
                created_at     REAL NOT NULL,
                applied_at     REAL,
                closed_at      REAL
            );

            CREATE INDEX IF NOT EXISTS idx_batch_session_status
                ON context_change_batch(session_id, status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_batch_created
                ON context_change_batch(created_at DESC);

            -- 批次内文件变更明细（审计 + 回滚内容依据，见开发文档 §2.3）
            CREATE TABLE IF NOT EXISTS context_audit_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id     INTEGER NOT NULL,
                item_index   INTEGER NOT NULL DEFAULT 0,
                operator     TEXT NOT NULL,
                action       TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT 'agent',
                target       TEXT NOT NULL,
                base_hash    TEXT,
                new_hash     TEXT,
                backup_path  TEXT DEFAULT '',
                created_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_context_audit_batch
                ON context_audit_log(batch_id, item_index);
            CREATE INDEX IF NOT EXISTS idx_context_audit_created
                ON context_audit_log(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_context_audit_target
                ON context_audit_log(target, id DESC);
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
        ("sessions", "scope", "TEXT DEFAULT 'frontend'"),
        # users 表补列
        ("users", "can_chat", "INTEGER DEFAULT 1"),
        ("users", "can_admin", "INTEGER DEFAULT 0"),
        # users 表补列（超星 passport 登录）
        ("users", "uid", "TEXT"),
        ("users", "fid", "TEXT"),
        ("users", "realname", "TEXT DEFAULT ''"),
        # messages 表补列：思考过程的结构化步骤序列（JSON）
        ("messages", "steps", "TEXT DEFAULT ''"),
        # messages 表补列：用户上传的图片/PDF 元数据（JSON）
        ("messages", "attachments", "TEXT DEFAULT '[]'"),
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
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uid ON users(uid)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_scope_updated ON sessions(scope, updated_at DESC)",
        ]
        for sql in index_sql:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        conn.commit()
