"""对话路由：SSE 流式对话 + 会话 CRUD。"""

import os
import re
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

_TASK_RESULT_RE = re.compile(
    r"<type>(.*?)</type>\s*<result>(.*?)</result>",
    re.DOTALL,
)


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

    # `<task_result>` 是 Skill 回注给模型的内部消息，不能作为对话气泡展示。
    # 新消息的「思考过程」已由 agent_loop_stream 结构化落库到 steps（含交错顺序），
    # 直接使用；只有旧数据（无 steps）才从 <task_result> 反推出 tasks 兼容回退。
    visible: list[dict] = []
    pending_tasks: list[dict] = []
    for m in messages:
        if m["role"] == "user" and m["content"].startswith("<task_result>"):
            matched = _TASK_RESULT_RE.search(m["content"])
            if matched:
                pending_tasks.append({
                    "type": matched.group(1).strip(),
                    "result": matched.group(2).strip(),
                })
            continue
        if m["role"] == "user":
            # 新一轮用户提问：上一轮残留的内部结果不再归属本轮回复
            pending_tasks = []
        item = dict(m)
        if m["role"] == "assistant":
            if item.get("steps"):
                pending_tasks = []
            elif pending_tasks:
                item["tasks"] = pending_tasks
                pending_tasks = []
        visible.append(item)

    # 兜底：流被中断时结果之后没有 assistant 消息，挂到最后一条旧格式 assistant 上
    if (pending_tasks and visible and visible[-1]["role"] == "assistant"
            and not visible[-1].get("steps")):
        visible[-1]["tasks"] = visible[-1].get("tasks", []) + pending_tasks

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
