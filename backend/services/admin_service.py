"""管理后台服务：账号管理"""

import re
import sqlite3
import time
from threading import Lock

from database import get_db
from services.auth_service import hash_password

_lock = Lock()



def list_accounts(search: str = "", offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        if search:
            where = "WHERE username LIKE ?"
            params = (f"%{search}%",)
        else:
            where = ""
            params = ()

        count_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM users {where}", params
        ).fetchone()
        total = count_row["cnt"] if count_row else 0

        rows = conn.execute(
            f"""SELECT id, username, can_chat, can_admin, created_at
                FROM users {where}
                ORDER BY id ASC
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        ).fetchall()

    users = [
        {
            "id": r["id"],
            "username": r["username"],
            "can_chat": r["can_chat"] or 0,
            "can_admin": r["can_admin"] or 0,
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return users, total


def create_account(username: str, password: str, can_chat: int = 1, can_admin: int = 0) -> dict:
    if not username or not username.strip():
        return {"ok": False, "detail": "请输入用户名"}
    username = username.strip()
    if len(username) < 4:
        return {"ok": False, "detail": "用户名至少4位字符"}
    if len(username) > 20:
        return {"ok": False, "detail": "用户名最多20位字符"}
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return {"ok": False, "detail": "用户名只能包含字母、数字和下划线"}
    if not password:
        return {"ok": False, "detail": "请输入密码"}
    if len(password) < 8:
        return {"ok": False, "detail": "密码至少需要8位"}
    if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
        return {"ok": False, "detail": "密码需包含字母和数字"}

    now = time.time()
    hashed = hash_password(password)
    with _lock:
        with get_db() as conn:
            try:
                cursor = conn.execute(
                    """INSERT INTO users (username, password, role, avatar, can_chat, can_admin, created_at, updated_at)
                       VALUES (?, ?, 'user', '', ?, ?, ?, ?)""",
                    (username, hashed, can_chat, can_admin, now, now),
                )
                conn.commit()
                user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                return {"ok": False, "detail": "用户名已被注册"}

    return {"ok": True, "user_id": user_id, "username": username}


def get_username_by_id(user_id: int) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None


def update_password(user_id: int, password: str) -> dict:
    if not password:
        return {"ok": False, "detail": "请输入新密码"}
    if len(password) < 8:
        return {"ok": False, "detail": "密码至少需要8位"}
    if not re.search(r"[a-zA-Z]", password) or not re.search(r"[0-9]", password):
        return {"ok": False, "detail": "密码需包含字母和数字"}

    hashed = hash_password(password)
    now = time.time()
    with _lock:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET password = ?, updated_at = ? WHERE id = ?",
                (hashed, now, user_id),
            )
            conn.commit()

    return {"ok": True}


def update_permissions(user_id: int, can_chat: int, can_admin: int, username: str = "") -> dict:
    # admin 账号的 can_admin 不可取消
    if username == "admin" and can_admin != 1:
        return {"ok": False, "detail": "admin 账号不可取消后台管理权限"}

    now = time.time()
    with _lock:
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET can_chat = ?, can_admin = ?, updated_at = ? WHERE id = ?",
                (can_chat, can_admin, now, user_id),
            )
            conn.commit()

    return {"ok": True}
