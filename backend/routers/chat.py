import json
import os
import re
import sys
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import DEBUG, MAX_AGENT_TURNS, MAX_TASK_CALLS, REPO_DIR
from dependencies.auth import get_current_user
from services.llm_service import build_ssl_context, parse_tasks, stream_chat_completions
from services.session_service import get_session_store
from services.skill_service import dispatch_skill, format_task_result, get_system_messages

router = APIRouter(prefix="/api")

# 上下文截断阈值
MAX_CONTEXT_CHARS = 64000
MIN_RETAIN_ROUNDS = 10


class ChatRequest(BaseModel):
    session_id: str
    message: str
    new_session: bool = False


_RAW_TASK_JSON_RE = re.compile(
    r'\[\s*\{\s*"(?:name|type|task_type)"\s*:\s*"[^"]*"\s*,\s*"query"\s*:\s*"(?:[^"\\]|\\.)*?"'
    r'(?:\s*,\s*"(?:top_k|k)"\s*:\s*\d+)?\s*\}'
    r'(?:\s*,\s*\{\s*"(?:name|type|task_type)"\s*:\s*"[^"]*"\s*,\s*"query"\s*:\s*"(?:[^"\\]|\\.)*?"'
    r'(?:\s*,\s*"(?:top_k|k)"\s*:\s*\d+)?\s*\})*'
    r'\s*\]',
)
_START_RAW_JSON = re.compile(r'\[\s*\{\s*"(?:name|type|task_type)"\s*:\s*"')


_TAIL_PARTIAL_JSON = re.compile(r'^\[[^\]()]*$')


def _truncate_messages(system_msgs: list[dict], history_msgs: list[dict]) -> list[dict]:
    """上下文截断：从头部丢弃旧消息，保留最近轮次"""
    total = sum(len(m.get("content", "")) for m in system_msgs + history_msgs)
    if total <= MAX_CONTEXT_CHARS:
        return system_msgs + history_msgs

    min_retain = MIN_RETAIN_ROUNDS * 2
    truncated = list(history_msgs)
    while len(truncated) > min_retain:
        total = sum(len(m.get("content", "")) for m in system_msgs + truncated)
        if total <= MAX_CONTEXT_CHARS:
            break
        truncated = truncated[2:]

    return system_msgs + truncated


def _partial_tag_len_at_end(s: str) -> int:
    """检测字符串末尾是否有 <task> 或 </task> 的片段前缀，返回长度。

    豆包模型的 content 以单字符增量流式输出，<task> 和 </task> 可能被
    拆分为多个 delta（如 '<', 'task', '>' 或 '<', '/', 'task', '>'），
    必须在 pending 中保留这些片段以便后续拼合识别。
    """
    # <task> 各前缀: <, <t, <ta, <tas, <task
    for i in range(1, 6):  # <task> 全长 6，检查前缀长度 1~5
        if s.endswith("<task>"[:i]):
            return i
    # </task> 各前缀: <, </, </t, </ta, </tas, </task
    for i in range(1, 7):  # </task> 全长 7，检查前缀长度 1~6
        if s.endswith("</task>"[:i]):
            return i
    return 0


def _filter_task_stream(stream):
    out = ""
    pending = ""
    in_block = 0
    depth = 0

    def _continue_after_block():
        nonlocal out, pending, in_block, depth
        # 先处理 </task> 闭合标签（可能是上一步块退出后的碎片残留）
        end_idx = pending.lower().find("</task>")
        if end_idx != -1:
            out += pending[:end_idx]
            pending = pending[end_idx + 7:]
            _continue_after_block()
            return
        task_idx = pending.lower().find("<task>")
        raw_m = _START_RAW_JSON.search(pending)
        raw_idx = raw_m.start() if raw_m else -1
        if task_idx == -1 and raw_idx == -1:
            # 检查 pending 末尾是否有待拼接的标签片段
            partial = _partial_tag_len_at_end(pending)
            if partial:
                out += pending[:-partial]
                pending = pending[-partial:]
            else:
                out += pending
                pending = ""
            return
        if task_idx != -1 and (raw_idx == -1 or task_idx < raw_idx):
            out += pending[:task_idx]
            pending = pending[task_idx + 6:]
            in_block = 1
            # 检查 </task> 是否也在同一个 pending 中
            end_idx = pending.lower().find("</task>")
            if end_idx != -1:
                pending = pending[end_idx + 7:]
                in_block = 0
                _continue_after_block()
        else:
            out += pending[:raw_idx]
            pending = pending[raw_idx + 1:]
            depth = 1
            for idx, ch in enumerate(pending):
                if ch in '[{':
                    depth += 1
                elif ch in ']}':
                    depth -= 1
                    if depth == 0:
                        pending = pending[idx + 1:]
                        in_block = 0
                        _continue_after_block()
                        return
            in_block = 2

    for delta_type, text in stream:
        if delta_type != "content":
            if out:
                yield "content", out
                out = ""
            if pending and in_block == 0:
                yield "content", pending
                pending = ""
            yield delta_type, text
            continue

        if DEBUG:
            print(f"[filter] raw content delta: len={len(text)} {repr(text[:120])}", file=sys.stderr)

        if in_block == 0:
            pending += text
            # 先检查 </task> 闭合标签（上一步块退出后的碎片残留）
            end_idx = pending.lower().find("</task>")
            if end_idx != -1:
                # 查找是否有配对的 <task> 起始标记
                task_start = pending.lower().rfind("<task>", 0, end_idx)
                if task_start != -1:
                    # 完整块: <task>...</task>，全部消费
                    out += pending[:task_start]
                    pending = pending[end_idx + 7:]
                else:
                    # 只有 </task>（碎片：前序 delta 中 <task> 已被消费）
                    out += pending[:end_idx]
                    pending = pending[end_idx + 7:]
                _continue_after_block()
                continue
            task_idx = pending.lower().find("<task>")
            raw_m = _START_RAW_JSON.search(pending)
            raw_idx = raw_m.start() if raw_m else -1

            if task_idx == -1 and raw_idx == -1:
                # 检查末尾是否有待拼接的 <task> 或 </task> 标签片段
                partial = _partial_tag_len_at_end(pending)
                if partial:
                    # 部分标签之前的干净内容：即时 yield 以实现流式输出
                    if out:
                        yield "content", out
                        out = ""
                    yield "content", pending[:-partial]
                    pending = pending[-partial:]
                    continue
                last_bracket = pending.rfind('[')
                if last_bracket != -1:
                    tail = pending[last_bracket:]
                    if _TAIL_PARTIAL_JSON.match(tail):
                        # JSON 数组之前的内容即时 yield
                        if out:
                            yield "content", out
                            out = ""
                        yield "content", pending[:last_bracket]
                        pending = pending[last_bracket:]
                        continue
                # 干净内容：即时 yield 实现逐 token 流式输出
                if out:
                    yield "content", out
                    out = ""
                yield "content", pending
                pending = ""
                continue

            if task_idx != -1 and (raw_idx == -1 or task_idx < raw_idx):
                out += pending[:task_idx]
                pending = pending[task_idx + 6:]
                in_block = 1
                # 检查 </task> 是否也在同一个 pending 中（单 delta 含完整 task 块）
                end_idx = pending.lower().find("</task>")
                if end_idx != -1:
                    pending = pending[end_idx + 7:]
                    in_block = 0
                    _continue_after_block()
            else:
                out += pending[:raw_idx]
                pending = pending[raw_idx + 1:]
                depth = 1
                for idx, ch in enumerate(pending):
                    if ch in '[{':
                        depth += 1
                    elif ch in ']}':
                        depth -= 1
                        if depth == 0:
                            pending = pending[idx + 1:]
                            in_block = 0
                            _continue_after_block()
                            break
                else:
                    in_block = 2

        elif in_block == 1:
            pending += text
            idx = pending.lower().find("</task>")
            if idx == -1:
                if len(pending) > 7:
                    pending = pending[-7:]
                continue
            pending = pending[idx + 7:]
            in_block = 0
            _continue_after_block()

        elif in_block == 2:
            for i, ch in enumerate(text):
                if ch in '[{':
                    depth += 1
                elif ch in ']}':
                    depth -= 1
                    if depth == 0:
                        pending = text[i + 1:]
                        in_block = 0
                        _continue_after_block()
                        break
            if in_block == 2:
                pending += text
                if len(pending) > 7:
                    pending = pending[-7:]

    if out:
        yield "content", out
    if pending and in_block == 0:
        yield "content", pending
    if DEBUG:
        print(f"[filter] end: out={repr(out[:80])} pending={repr(pending[:80])} in_block={in_block}", file=sys.stderr)


def _strip_raw_task_arrays(text: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        m = _START_RAW_JSON.search(text, i)
        if not m:
            result.append(text[i:])
            break
        start = m.start()
        result.append(text[i:start])
        i = start + 1
        depth = 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch in '[{':
                depth += 1
            elif ch in ']}':
                depth -= 1
            i += 1
    return ''.join(result)


def _clean_task_blocks(text: str) -> str:
    text = re.sub(r'<task>[\s\S]*?</task>', '', text, flags=re.IGNORECASE)
    text = _strip_raw_task_arrays(text)
    return text.strip()


def _tee_collect(source, collected: list):
    """包装一个迭代器，使其在遍历时同步收集所有产出的元素到 collected 列表中。

    用于在流式传输的同时收集原始 delta，避免 list() 全量缓冲导致流式失效。
    """
    for item in source:
        collected.append(item)
        yield item


async def _agent_loop_stream(
    api_key: str,
    messages: list[dict],
    session_id: str,
) -> AsyncGenerator[str, None]:
    ssl_context = build_ssl_context()
    store = get_session_store()
    task_calls = 0
    last_task_fingerprints: list[str] = []

    # 跨轮次累积：将多轮 agent 循环中的思考过程和最终回答分别累积
    all_content_parts: list[str] = []
    all_reasoning_parts: list[str] = []

    for turn in range(MAX_AGENT_TURNS):
        payload = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "thinking": {"type": "enabled"},
        }

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        # raw_content_parts: 保存未经 _filter_task_stream 过滤的原始内容，用于 task 解析
        raw_content_parts: list[str] = []
        saw_think = False

        try:
            # 直接流式处理，不缓冲所有 delta
            # 使用 TeeCollector 在流式传输的同时收集原始 delta 用于 task 解析
            collected: list[tuple[str, str]] = []
            llm_stream = stream_chat_completions(api_key, payload, ssl_context)

            for delta_type, text in _filter_task_stream(_tee_collect(llm_stream, collected)):
                if delta_type == "reasoning":
                    reasoning_parts.append(text)
                    if not saw_think:
                        saw_think = True
                        yield f"event: reasoning\ndata: {json.dumps({'content': '<THINK_V2>'})}\n\n"
                    yield f"event: reasoning\ndata: {json.dumps({'content': text})}\n\n"
                elif delta_type == "content":
                    if DEBUG:
                        print(f"[agent] content delta: len={len(text)} {repr(text[:80])}", file=sys.stderr)
                    content_parts.append(text)
                    if saw_think:
                        saw_think = False
                        yield f"event: reasoning\ndata: {json.dumps({'content': '</think>'})}\n\n"
                    yield f"event: content\ndata: {json.dumps({'content': text})}\n\n"
                elif delta_type == "error":
                    yield f"event: error\ndata: {json.dumps({'content': text})}\n\n"
                    if all_content_parts or all_reasoning_parts:
                        store.append_message(
                            session_id,
                            "assistant",
                            _clean_task_blocks("".join(all_content_parts)),
                            "".join(all_reasoning_parts),
                        )
                    return

            # 从收集的原始 delta 中提取 raw content（含 <task> 标签，用于 task 解析）
            for dt, text in collected:
                if dt == "content":
                    raw_content_parts.append(text)

            if saw_think:
                yield f"event: reasoning\ndata: {json.dumps({'content': '</think>'})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"
            # 出错前保存已累积的内容
            if all_content_parts or all_reasoning_parts:
                store.append_message(
                    session_id,
                    "assistant",
                    _clean_task_blocks("".join(all_content_parts)),
                    "".join(all_reasoning_parts),
                )
            return

        assistant_content = "".join(content_parts)
        assistant_reasoning = "".join(reasoning_parts)

        # 累积内容：content 中的任务块已被 _filter_task_stream 过滤，直接累积
        if assistant_content:
            all_content_parts.append(assistant_content)
        if assistant_reasoning:
            all_reasoning_parts.append(assistant_reasoning)

        # 使用 raw_content + reasoning 进行 task 解析
        # raw_content_parts 包含未过滤的 <task> 标签，parse_tasks 需要它们
        raw_content = "".join(raw_content_parts)
        combined = raw_content + "\n" + assistant_reasoning
        tasks = parse_tasks(combined)

        if DEBUG:
            print(
                f"\n[debug] turn={turn} content_len={len(assistant_content)} "
                f"reasoning_len={len(assistant_reasoning)} tasks={len(tasks)}",
                file=sys.stderr,
            )

        if not tasks:
            # 所有任务已完成，保存最终结果：一条 assistant 消息
            final_content = _clean_task_blocks("".join(all_content_parts))
            final_reasoning = "".join(all_reasoning_parts)
            if final_content or final_reasoning:
                store.append_message(
                    session_id,
                    "assistant",
                    final_content,
                    final_reasoning,
                )
            yield "event: done\ndata: {}\n\n"
            return

        for task in tasks:
            task_calls += 1
            if task_calls > MAX_TASK_CALLS:
                yield f"event: warning\ndata: {json.dumps({'content': 'Too many task calls, stopping.'})}\n\n"
                final_content = _clean_task_blocks("".join(all_content_parts))
                final_reasoning = "".join(all_reasoning_parts)
                if final_content or final_reasoning:
                    store.append_message(session_id, "assistant", final_content, final_reasoning)
                yield "event: done\ndata: {}\n\n"
                return

            fingerprint = f"{task.task_type}|{task.query}|{task.top_k}"
            last_task_fingerprints.append(fingerprint)
            if len(last_task_fingerprints) >= 4 and len(set(last_task_fingerprints[-3:])) == 1:
                yield f"event: warning\ndata: {json.dumps({'content': 'Repeated task detected, stopping.'})}\n\n"
                final_content = _clean_task_blocks("".join(all_content_parts))
                final_reasoning = "".join(all_reasoning_parts)
                if final_content or final_reasoning:
                    store.append_message(session_id, "assistant", final_content, final_reasoning)
                yield "event: done\ndata: {}\n\n"
                return

            result_text = dispatch_skill(REPO_DIR, task)

            yield f"event: task\ndata: {json.dumps({'type': task.task_type, 'status': 'executed', 'result': result_text})}\n\n"

            task_msg = format_task_result(task.task_type, result_text)
            messages.append(task_msg)
            store.append_message(session_id, task_msg["role"], task_msg["content"])

        if turn >= MAX_AGENT_TURNS - 1 and task_calls > 0:
            yield f"event: warning\ndata: {json.dumps({'content': 'Max turns reached.'})}\n\n"

    # 循环结束（达到最大轮次）
    final_content = _clean_task_blocks("".join(all_content_parts))
    final_reasoning = "".join(all_reasoning_parts)
    if final_content or final_reasoning:
        store.append_message(session_id, "assistant", final_content, final_reasoning)
    yield "event: done\ndata: {}\n\n"


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
            _empty_stream(session_id),
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
    truncated = _truncate_messages(
        system_msgs,
        [{"role": m["role"], "content": m["content"]} for m in history_msgs],
    )

    return StreamingResponse(
        _agent_loop_stream(api_key, truncated, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


async def _empty_stream(session_id: str) -> AsyncGenerator[str, None]:
    yield f"event: done\ndata: {{}}\n\n"


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
