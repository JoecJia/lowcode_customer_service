"""对话路由：SSE 流式对话 + 会话 CRUD。"""

import asyncio
import os
import re
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from dependencies.auth import get_current_user
from services.agent_service import (
    agent_loop_stream,
    clean_task_blocks,
    empty_stream,
    truncate_messages,
)
from services.attachment_service import (
    AttachmentError,
    attachment_exists,
    persist_attachment,
    prepare_attachments,
    resolve_attachment_path,
)
from services.message_content import build_user_content, has_multimodal_part
from services.session_service import get_session_store
from services.skill_service import get_system_messages
from services.title_service import (
    cancel_title_trigger,
    chat_stream_with_title,
    generate_and_store_title,
    should_generate_title,
)

router = APIRouter(prefix="/api")

_TASK_RESULT_RE = re.compile(
    r"<type>(.*?)</type>\s*<result>(.*?)</result>",
    re.DOTALL,
)


class ChatAttachmentIn(BaseModel):
    kind: Literal["image", "pdf"]
    name: str
    mime: str
    size: int
    data_url: Optional[str] = None
    base64: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    new_session: bool = False
    attachments: list[ChatAttachmentIn] = Field(default_factory=list)


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
    if not request.message.strip() and not request.attachments:
        raise HTTPException(status_code=422, detail="消息内容不能为空")

    # 校验会话存在且未被软删除
    owner = store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="session not found")
    if store.is_session_deleted(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    try:
        prepared = prepare_attachments([a.model_dump() for a in request.attachments])
    except AttachmentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 标题生成判定需在写 user 消息之前（依据「是否已有含文本的用户消息」）
    # 返回值是触发瞬间的标题快照，用于乐观回写；None 表示本次不触发
    title_expected = should_generate_title(session_id, request.message)

    # 先落一条占位消息拿到 message_id，再落盘附件并回填元数据
    message_id = store.append_message(session_id, "user", request.message)
    try:
        metas = [persist_attachment(session_id, message_id, item) for item in prepared]
        if metas:
            store.update_message_attachments(message_id, metas)
    except Exception:
        store.delete_message_by_id(message_id)
        if title_expected is not None:
            cancel_title_trigger(session_id)
        raise

    system_msgs = get_system_messages()
    history_msgs = store.get_messages(session_id)[0]  # (messages, has_more)
    history_for_model: list[dict] = []
    for m in history_msgs:
        # 旧数据兼容：<task_result> 曾是 role=user 的假用户消息，不进入模型上下文。
        if m["role"] == "user" and "<task_result>" in str(m.get("content") or ""):
            continue
        if m["role"] == "tool":
            continue
        attachments = m.get("attachments") or []
        content = build_user_content(m["content"], attachments) if attachments else m["content"]
        history_for_model.append({"role": m["role"], "content": content})

    # 截断上下文
    truncated = truncate_messages(system_msgs, history_for_model)

    # 标题生成作为后台任务并行执行，不阻塞主回复流
    title_task = None
    if title_expected is not None:
        title_task = asyncio.create_task(
            generate_and_store_title(
                api_key,
                session_id,
                request.message,
                title_expected,
                has_multimodal_part(history_for_model),
            )
        )

    return StreamingResponse(
        chat_stream_with_title(
            agent_loop_stream(api_key, truncated, session_id), title_task
        ),
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
        if item.get("attachments"):
            item["attachments"] = [
                {
                    **att,
                    "preview_url": f"/api/messages/{m['id']}/attachments/{att.get('id')}/content",
                }
                for att in item["attachments"]
            ]
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


@router.get("/messages/{message_id}/attachments/{attachment_id}/content")
async def get_attachment_content(
    message_id: int,
    attachment_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """带鉴权读取附件原始内容，供历史消息中的附件卡片预览。"""
    store = get_session_store()
    msg = store.get_message_by_id(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message not found")

    owner = store.get_session_owner(msg["session_id"])
    user_id = int(current_user["sub"]) if current_user else None
    if user_id and owner and owner != user_id:
        raise HTTPException(status_code=403, detail="forbidden")

    meta = next((a for a in msg["attachments"] if a.get("id") == attachment_id), None)
    if meta is None:
        raise HTTPException(status_code=404, detail="attachment not found")
    if not attachment_exists(meta):
        raise HTTPException(status_code=410, detail="attachment expired")

    try:
        path = resolve_attachment_path(meta["storage"]["ref"])
    except (KeyError, AttachmentError) as exc:
        raise HTTPException(status_code=404, detail="attachment not found") from exc

    safe_name = quote(meta.get("name") or "attachment", safe="")
    return FileResponse(
        path,
        media_type=meta.get("mime") or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_name}"},
    )


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
