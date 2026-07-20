import sqlite3
import time
import uuid
from threading import Lock
from typing import Optional

from config import SESSION_TTL_SECONDS
from database import get_db


class SessionStore:
    def __init__(self):
        self._lock = Lock()
        self._temp_sessions: dict[str, dict] = {}



    def create_session(self, title: str = "", user_id: int | None = None) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        welcome_msg = {"role": "assistant", "content": "我是低代码平台智能客服，请问我有什么可以帮您？"}
        with self._lock:
            self._temp_sessions[sid] = {
                "messages": [welcome_msg],
                "created_at": now,
                "last_active": now,
            }
        with get_db() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, status, user_id, created_at, updated_at) VALUES (?, ?, 'active', ?, ?, ?)",
                (sid, title, user_id, now, now),
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, reasoning_content, created_at) VALUES (?, ?, ?, ?, ?)",
                (sid, "assistant", welcome_msg["content"], "", now),
            )
            conn.commit()
        return sid

    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        before_id: int | None = None,
    ) -> tuple[list[dict], bool]:
        """获取消息列表，返回 (messages, has_more)"""
        self._touch_temp(session_id)
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            if before_id is not None:
                rows = conn.execute(
                    "SELECT id, role, content, reasoning_content, created_at "
                    "FROM messages WHERE session_id = ? AND id < ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, before_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, role, content, reasoning_content, created_at "
                    "FROM messages WHERE session_id = ? "
                    "ORDER BY created_at ASC LIMIT ?",
                    (session_id, limit + 1),
                ).fetchall()

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        # before_id 模式下返回的是倒序，需要反转
        if before_id is not None:
            rows = list(reversed(rows))

        messages = []
        for row in rows:
            msg = {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "reasoning_content": row["reasoning_content"] or "",
                "created_at": row["created_at"],
            }
            messages.append(msg)

        # 同步到内存缓存
        now = time.time()
        with self._lock:
            cached = [{"role": m["role"], "content": m["content"],
                       "reasoning_content": m.get("reasoning_content", "")} for m in messages]
            self._temp_sessions[session_id] = {
                "messages": cached,
                "created_at": now,
                "last_active": now,
            }
        return messages, has_more

    def append_message(self, session_id: str, role: str, content: str, reasoning_content: str = "") -> None:
        now = time.time()
        msg = {"role": role, "content": content}
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content

        with self._lock:
            if session_id in self._temp_sessions:
                self._temp_sessions[session_id]["messages"].append(msg)
                self._temp_sessions[session_id]["last_active"] = now
            else:
                self._temp_sessions[session_id] = {
                    "messages": [msg],
                    "created_at": now,
                    "last_active": now,
                }

        with get_db() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, reasoning_content, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, reasoning_content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            conn.commit()

    def archive_session(self, session_id: str) -> None:
        with get_db() as conn:
            conn.execute(
                "UPDATE sessions SET status = 'archived', updated_at = ? WHERE id = ?",
                (time.time(), session_id),
            )
            conn.commit()
        self._evict_temp(session_id)

    def delete_session(self, session_id: str) -> None:
        """软删除：设置 deleted_at 时间戳，保留消息数据"""
        now = time.time()
        with get_db() as conn:
            conn.execute(
                "UPDATE sessions SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, session_id),
            )
            conn.commit()
        self._evict_temp(session_id)

    def get_session_owner(self, session_id: str) -> int | None:
        """获取会话的 user_id，用于鉴权"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT user_id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row:
                return row["user_id"]
        return None

    def is_session_deleted(self, session_id: str) -> bool:
        """检查会话是否已被软删除"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT deleted_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row and row[0] is not None:
                return True
        return False

    def update_session_title(self, session_id: str, title: str) -> None:
        with get_db() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, time.time(), session_id),
            )
            conn.commit()

    def list_sessions(
        self,
        limit: int = 10,
        offset: int = 0,
        user_id: int | None = None,
    ) -> tuple[list[dict], int, bool]:
        """返回 (sessions, total, has_more)，按 updated_at 倒序，仅返回未删除的会话"""
        with get_db() as conn:
            conn.row_factory = sqlite3.Row

            # 查询条件和参数
            if user_id is not None:
                where = "WHERE user_id = ? AND deleted_at IS NULL"
                params_base = (user_id,)
            else:
                where = "WHERE deleted_at IS NULL"
                params_base = ()

            # 总数
            total_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM sessions {where}",
                params_base,
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            # 分页查询（含 last_message 子查询）
            rows = conn.execute(
                f"""SELECT
                    s.id,
                    s.title,
                    s.status,
                    s.user_id,
                    s.created_at,
                    s.updated_at,
                    (SELECT m.content
                     FROM messages m
                     WHERE m.session_id = s.id
                       AND (m.role = 'user' OR m.role = 'assistant')
                     ORDER BY m.created_at DESC
                     LIMIT 1
                    ) AS last_message
                FROM sessions s
                {where}
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?""",
                (*params_base, limit + 1, offset),
            ).fetchall()

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return [dict(row) for row in rows], total, has_more

    def _touch_temp(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._temp_sessions:
                self._temp_sessions[session_id]["last_active"] = time.time()

    def _evict_temp(self, session_id: str) -> None:
        with self._lock:
            self._temp_sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = []
        with self._lock:
            for sid, sess in list(self._temp_sessions.items()):
                if now - sess["last_active"] > SESSION_TTL_SECONDS:
                    expired.append(sid)
            for sid in expired:
                self._temp_sessions.pop(sid, None)
        return len(expired)


class FeedbackService:
    """不满意反馈业务逻辑"""

    def submit_feedback(self, session_id: str, user_id: int) -> tuple[bool, str]:
        """提交反馈。返回 (ok, message)"""
        with get_db() as conn:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT id FROM feedback WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
            if existing:
                return False, "当前对话已反馈管理员，请勿重复点击～"

            now = time.time()
            conn.execute(
                "INSERT INTO feedback (session_id, user_id, created_at, status) VALUES (?, ?, ?, 'pending')",
                (session_id, user_id, now),
            )
            conn.commit()
        return True, "反馈已提交"

    def check_feedback(self, session_id: str, user_id: int) -> bool:
        """检查用户是否已对某会话提交过反馈"""
        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM feedback WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return row is not None


_session_store: Optional[SessionStore] = None
_feedback_service: Optional[FeedbackService] = None


def get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def get_feedback_service() -> FeedbackService:
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
    