import os
import sqlite3
import time
from datetime import datetime, timedelta
from threading import Lock

import bcrypt
import jwt

from database import get_db

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
# 超星 passport 登录：本地 JWT 有效期 1 天
JWT_EXPIRATION_DAYS = 1

_lock = Lock()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_token(
    user_id: int,
    username: str,
    role: str,
    can_chat: int = 1,
    can_admin: int = 0,
    uid: str | None = None,
    fid: str | None = None,
) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "can_chat": can_chat,
        "can_admin": can_admin,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS),
        "iat": datetime.utcnow(),
    }
    # 超星 passport 身份标识：供快路径校验时与 Cookie 中的 UID/fid 做篡改比对
    if uid is not None:
        payload["uid"] = str(uid)
    if fid is not None:
        payload["fid"] = str(fid)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def register_user(username: str, password: str, can_chat: int = 1, can_admin: int = 0) -> dict:
    now = time.time()
    hashed = hash_password(password)
    with _lock:
        with get_db() as conn:
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
    with get_db() as conn:
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


def _row_to_user(row: sqlite3.Row) -> dict:
    """users 行 → 对外用户字典。"""
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "avatar": row["avatar"] or "",
        "can_chat": row["can_chat"] or 1,
        "can_admin": row["can_admin"] or 0,
        "uid": row["uid"] or "",
        "fid": row["fid"] or "",
        "realname": row["realname"] or "",
    }


_USER_COLUMNS = "id, username, role, avatar, can_chat, can_admin, uid, fid, realname"


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return _row_to_user(row)


def get_user_by_uid(uid: str) -> dict | None:
    """按超星 passport uid 查询本地用户。"""
    with get_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE uid = ?",
            (str(uid),),
        ).fetchone()
    if not row:
        return None
    return _row_to_user(row)


def upsert_passport_user(uid: str, fid: str | None, realname: str | None) -> dict | None:
    """超星 passport 登录用户落库：不存在则插入，姓名变化才更新。

    约束：绝不覆盖 role / can_chat / can_admin，避免把已配置的管理员权限冲掉。
    """
    uid = str(uid)
    fid = "" if fid is None else str(fid)
    realname = realname or ""
    now = time.time()

    with _lock:
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, realname, fid FROM users WHERE uid = ?", (uid,)
            ).fetchone()

            if row is None:
                cursor = conn.execute(
                    """INSERT INTO users
                       (username, password, role, avatar, can_chat, can_admin,
                        created_at, updated_at, uid, fid, realname)
                       VALUES (?, '', 'user', '', 1, 0, ?, ?, ?, ?, ?)""",
                    (uid, now, now, uid, fid, realname),
                )
                conn.commit()
                user_id = cursor.lastrowid
            else:
                user_id = row["id"]
                name_changed = bool(realname) and realname != (row["realname"] or "")
                fid_changed = bool(fid) and fid != (row["fid"] or "")
                if name_changed or fid_changed:
                    conn.execute(
                        "UPDATE users SET realname = ?, fid = ?, updated_at = ? WHERE id = ?",
                        (realname or (row["realname"] or ""), fid or (row["fid"] or ""), now, user_id),
                    )
                    conn.commit()

    return get_user_by_id(user_id)
