"""对话路由：SSE 流式对话 + 会话 CRUD。"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dependencies.auth import get_current_user
from services.agent_service import (
    agent_loop_stream,
    clean_task_blocks,
    empty_stream,
    truncate_messages,
)
from services.session_service import get_session_store
from services.skill_service import get_system_messages

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    session_id: str
    message: str
    new_session: bool = False


@router.post("/chat")
async def chat(request: ChatRequest, current_user: Optional[dict] = Depends(get_current_user)):
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ARK_API_KEY not configured")

    store = get_session_store()
    user_id = int(current_user["sub"]) if current_user else None

    if request.new_session:
        session_id = store.create_session(user_id=user_id)
        return StreamingResponse(
            empty_stream(session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-Id": session_id,
            },
        )

    session_id = request.session_id
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    # 校验会话存在且未被软删除
    owner = store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="session not found")
    if store.is_session_deleted(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    store.append_message(session_id, "user", request.message)

    system_msgs = get_system_messages()
    history_msgs = store.get_messages(session_id)[0]  # (messages, has_more)
    # 截断上下文
    truncated = truncate_messages(
        system_msgs,
        [{"role": m["role"], "content": m["content"]} for m in history_msgs],
    )

    return StreamingResponse(
        agent_loop_stream(api_key, truncated, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: Optional[dict] = Depends(get_current_user),
):
    store = get_session_store()
    user_id = int(current_user["sub"]) if current_user else None
    sessions, total, has_more = store.list_sessions(
        limit=limit,
        offset=offset,
        user_id=user_id,
    )
    return {"sessions": sessions, "total": total, "has_more": has_more}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: Optional[int] = Query(default=None),
):
    store = get_session_store()
    messages, has_more = store.get_messages(session_id, limit=limit, before_id=before_id)

    # 过滤 <task_result> 用户消息
    visible = [m for m in messages if not (
        m["role"] == "user" and m["content"].startswith("<task_result>")
    )]
    return {"session_id": session_id, "messages": visible, "has_more": has_more}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    store = get_session_store()
    user_id = int(current_user["sub"]) if current_user else None

    # 校验会话存在且属于当前用户
    owner = store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user_id and owner != user_id:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 检查是否已删除
    if store.is_session_deleted(session_id):
        raise HTTPException(status_code=409, detail="会话已删除")

    store.delete_session(session_id)
    return {"ok": True}


class UpdateTitleRequest(BaseModel):
    title: str


@router.patch("/sessions/{session_id}")
async def update_session_title(session_id: str, body: UpdateTitleRequest):
    store = get_session_store()
    store.update_session_title(session_id, body.title)
    return {"ok": True}
