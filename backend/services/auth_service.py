import os
import sqlite3
import time
from datetime import datetime, timedelta
from threading import Lock

import bcrypt
import jwt

from config import DB_PATH

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

_lock = Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_users_table() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                password    TEXT    NOT NULL,
                role        TEXT    DEFAULT 'user',
                avatar      TEXT    DEFAULT '',
                created_at  REAL    NOT NULL,
                updated_at  REAL    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN can_chat INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN can_admin INTEGER DEFAULT 0")
        except Exception:
            pass
        conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: int, username: str, role: str, can_chat: int = 1, can_admin: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "can_chat": can_chat,
        "can_admin": can_admin,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def register_user(username: str, password: str, can_chat: int = 1, can_admin: int = 0) -> dict:
    init_users_table()
    now = time.time()
    hashed = hash_password(password)
    with _lock:
        with _get_conn() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password, role, avatar, can_chat, can_admin, created_at, updated_at) VALUES (?, ?, 'user', '', ?, ?, ?, ?)",
                    (username, hashed, can_chat, can_admin, now, now),
                )
                conn.commit()
                user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                return {"ok": False, "detail": "用户名已被注册"}
    return {"ok": True, "user_id": user_id, "username": username}


def authenticate_user(username: str, password: str) -> dict:
    init_users_table()
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, username, password, role, avatar, can_chat, can_admin FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return {"ok": False, "detail": "用户名或密码错误"}
    if not verify_password(password, row["password"]):
        return {"ok": False, "detail": "用户名或密码错误"}
    token = create_token(row["id"], row["username"], row["role"], row["can_chat"] or 1, row["can_admin"] or 0)
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "avatar": row["avatar"] or "",
            "can_chat": row["can_chat"] or 1,
            "can_admin": row["can_admin"] or 0,
        },
    }


def get_user_by_id(user_id: int) -> dict | None:
    init_users_table()
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, username, role, avatar, can_chat, can_admin FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "avatar": row["avatar"] or "",
        "can_chat": row["can_chat"] or 1,
        "can_admin": row["can_admin"] or 0,
    }
