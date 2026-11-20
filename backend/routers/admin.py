"""管理后台 API 路由：Agent 配置 + 账号管理 + 后台维护智能体 + Context 批次。"""

import asyncio
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from database import get_db
from dependencies.auth import require_admin
from services.agent_config_service import get_file_content, get_file_tree
from services.agent_service import agent_loop_stream, empty_stream, truncate_messages
from services.admin_service import (
    create_account,
    get_username_by_id,
    list_accounts,
    update_password,
    update_permissions,
)
from services.context_admin_service import (
    ConflictError,
    ValidationError,
    admin_agent_enabled,
    apply_batch,
    discard_batch,
    list_batches,
    rollback_batch,
)
from services.session_service import get_session_store
from services.skill_service import get_system_messages
from services.title_service import (
    cancel_title_trigger,
    chat_stream_with_title,
    generate_and_store_title,
    should_generate_title,
)

router = APIRouter(prefix="/api/admin")


def _require_admin_agent(admin: dict = Depends(require_admin)) -> dict:
    """灰度开关二次校验：关闭时后台智能体相关接口统一 403（见 §12 P12）。"""
    if not admin_agent_enabled():
        raise HTTPException(status_code=403, detail="后台维护助手未启用")
    return admin


# ====== Agent 配置 ======

@router.get("/agent-config/tree")
async def agent_config_tree(admin: dict = Depends(require_admin)):
    tree = get_file_tree()
    return {"ok": True, "data": {"tree": tree}}


@router.get("/agent-config/file")
async def agent_config_file(
    path: str = Query(...),
    admin: dict = Depends(require_admin),
):
    content = get_file_content(path)
    if content is None:
        raise HTTPException(status_code=404, detail="文件不存在或不可预览")
    return {"ok": True, "data": {"path": path, "content": content}}


# ====== 账号管理 ======

@router.get("/accounts")
async def get_accounts(
    search: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    users, total = list_accounts(search=search, offset=offset, limit=limit)
    return {
        "ok": True,
        "data": {
            "users": users,
            "total": total,
            "offset": offset,
            "limit": limit,
        },
    }


class CreateAccountRequest(BaseModel):
    username: str
    password: str
    can_chat: int = 1
    can_admin: int = 0


@router.post("/accounts", status_code=201)
async def add_account(
    body: CreateAccountRequest,
    admin: dict = Depends(require_admin),
):
    result = create_account(
        body.username,
        body.password,
        body.can_chat,
        body.can_admin,
    )
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["detail"])
    return {
        "ok": True,
        "message": "账号添加成功",
        "data": {
            "user_id": result["user_id"],
            "username": result["username"],
        },
    }


class UpdatePasswordRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("请输入新密码")
        if len(v) < 8:
            raise ValueError("密码至少需要8位")
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("密码需包含字母和数字")
        return v


@router.patch("/accounts/{user_id}/password")
async def change_password(
    user_id: int,
    body: UpdatePasswordRequest,
    admin: dict = Depends(require_admin),
):
    result = update_password(user_id, body.password)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result["detail"])
    return {"ok": True, "message": "密码修改成功"}


class UpdatePermissionsRequest(BaseModel):
    can_chat: int
    can_admin: int


@router.patch("/accounts/{user_id}/permissions")
async def change_permissions(
    user_id: int,
    body: UpdatePermissionsRequest,
    admin: dict = Depends(require_admin),
):
    username = get_username_by_id(user_id)
    if username is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    result = update_permissions(user_id, body.can_chat, body.can_admin, username)
    if not result["ok"]:
        raise HTTPException(status_code=403, detail=result["detail"])
    return {"ok": True, "message": "权限修改成功"}


# ====== 后台维护智能体对话 ======

class AdminChatRequest(BaseModel):
    session_id: str
    message: str


@router.post("/chat")
async def admin_chat(
    body: AdminChatRequest,
    admin: dict = Depends(_require_admin_agent),
):
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ARK_API_KEY not configured")

    store = get_session_store()
    session_id = body.session_id
    message = body.message

    # scope 校验：必须是后台会话；不泄露前台会话存在性
    # 注意：admin 会话为共享会话、user_id=None，不能用 owner 判空代表不存在
    if not store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    if store.is_session_deleted(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    if store.get_session_scope(session_id) != "admin":
        raise HTTPException(status_code=404, detail="会话不存在")
    if not message.strip():
        raise HTTPException(status_code=422, detail="message is required")

    operator = str(admin.get("username") or admin.get("sub") or "admin")
    title_expected = should_generate_title(session_id, message)
    store.append_message(session_id, "user", message)

    system_msgs = get_system_messages(profile="admin")
    history_msgs = store.get_messages(session_id)[0]
    history_for_model: list[dict] = []
    for m in history_msgs:
        # 旧数据兼容：<task_result> 曾是 role=user 的假用户消息，不进入模型上下文。
        if m["role"] == "user" and "<task_result>" in str(m.get("content") or ""):
            continue
        if m["role"] == "tool":
            continue
        history_for_model.append({"role": m["role"], "content": m["content"]})
    truncated = truncate_messages(system_msgs, history_for_model)

    title_task = None
    if title_expected is not None:
        title_task = asyncio.create_task(
            generate_and_store_title(api_key, session_id, message, title_expected)
        )

    return StreamingResponse(
        chat_stream_with_title(
            agent_loop_stream(
                api_key, truncated, session_id, profile="admin", operator=operator,
            ),
            title_task,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


# ====== 后台会话 CRUD（历史记录） ======

@router.get("/sessions")
async def list_admin_sessions(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(_require_admin_agent),
):
    store = get_session_store()
    sessions, total, has_more = store.list_sessions(limit=limit, offset=offset, scope="admin")
    return {
        "ok": True,
        "data": {"sessions": sessions, "total": total, "has_more": has_more},
    }


@router.post("/sessions", status_code=201)
async def create_admin_session(admin: dict = Depends(_require_admin_agent)):
    store = get_session_store()
    session_id = store.create_session(scope="admin")
    return {"ok": True, "data": {"session_id": session_id}}


@router.get("/sessions/{session_id}/messages")
async def get_admin_session_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None),
    admin: dict = Depends(_require_admin_agent),
):
    store = get_session_store()
    if not store.session_exists(session_id) or store.get_session_scope(session_id) != "admin":
        raise HTTPException(status_code=404, detail="会话不存在")
    messages, has_more = store.get_messages(session_id, limit=limit, before_id=before_id)
    # 过滤内部 user 消息（<task_result> 开头）
    visible = [m for m in messages if not (m["role"] == "user" and m["content"].startswith("<task_result>"))]
    return {
        "ok": True,
        "data": {"session_id": session_id, "messages": visible, "has_more": has_more},
    }


class AdminRenameRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("请输入会话名称")
        if len(v) > 50:
            raise ValueError("名称过长")
        return v


@router.patch("/sessions/{session_id}")
async def rename_admin_session(
    session_id: str,
    body: AdminRenameRequest,
    admin: dict = Depends(_require_admin_agent),
):
    store = get_session_store()
    if not store.session_exists(session_id) or store.get_session_scope(session_id) != "admin":
        raise HTTPException(status_code=404, detail="会话不存在")
    store.update_session_title(session_id, body.title)
    return {"ok": True, "message": "重命名成功"}


@router.delete("/sessions/{session_id}")
async def delete_admin_session(
    session_id: str,
    admin: dict = Depends(_require_admin_agent),
):
    store = get_session_store()
    if not store.session_exists(session_id) or store.get_session_scope(session_id) != "admin":
        raise HTTPException(status_code=404, detail="会话不存在")
    if store.is_session_deleted(session_id):
        raise HTTPException(status_code=409, detail="会话已删除")
    store.delete_session(session_id)
    return {"ok": True}


# ====== Context 批次接口 ======

@router.get("/context/batches")
async def get_context_batches(
    session_id: str | None = Query(default=None),
    status: str | None = Query(default=None, description="逗号分隔多状态，如 applied,rolled_back"),
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(_require_admin_agent),
):
    statuses = [s.strip() for s in status.split(",") if s.strip()] if status else None
    batches = list_batches(session_id=session_id, statuses=statuses, limit=limit)
    return {"ok": True, "data": {"batches": batches}}


@router.post("/context/batches/{batch_id}/apply")
async def apply_context_batch(
    batch_id: int,
    admin: dict = Depends(_require_admin_agent),
):
    with get_db() as conn:
        row = conn.execute("SELECT batch_no FROM context_change_batch WHERE id = ?", (batch_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="批次不存在")
    operator = str(admin.get("username") or admin.get("sub") or "admin")
    try:
        result = await apply_batch(row["batch_no"], operator)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "message": "已并入知识库并更新索引",
        "data": result,
    }


@router.post("/context/batches/{batch_id}/discard")
async def discard_context_batch(
    batch_id: int,
    admin: dict = Depends(_require_admin_agent),
):
    with get_db() as conn:
        row = conn.execute("SELECT batch_no FROM context_change_batch WHERE id = ?", (batch_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="批次不存在")
    try:
        discard_batch(row["batch_no"])
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/context/batches/{batch_id}/rollback")
async def rollback_context_batch(
    batch_id: int,
    admin: dict = Depends(_require_admin_agent),
):
    operator = str(admin.get("username") or admin.get("sub") or "admin")
    try:
        result = await rollback_batch(batch_id, operator)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "message": "已回滚并更新索引", "data": result}
