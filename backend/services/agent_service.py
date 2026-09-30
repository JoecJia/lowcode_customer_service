"""Agent 核心服务：SSE 流过滤、上下文截断、Agent 多轮循环调度。"""

import json
import os
import re
import sys
import time
import urllib.error
from typing import AsyncGenerator

from config import (
    DEBUG,
    MAX_AGENT_TURNS,
    MAX_IDENTICAL_TASK_CALLS,
    MAX_SAME_SKILL_CALLS,
    MAX_TASK_CALLS,
    REPO_DIR,
)

# ── 调试追踪 ──
# ARK_DEBUG=1 打开追踪；若同时设置 ARK_TRACE_PATH，则同时落盘便于离线分析
_TRACE_PATH = os.environ.get("ARK_TRACE_PATH", "").strip()
_TASK_BLOCK_RE = re.compile(r"<task>[\s\S]*?</task>", re.IGNORECASE)


def _trace(msg: str) -> None:
    """DEBUG 模式下打印追踪信息；配置了 ARK_TRACE_PATH 时同时追加写入文件。"""
    if not DEBUG:
        return
    print(msg, file=sys.stderr)
    if _TRACE_PATH:
        try:
            with open(_TRACE_PATH, "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
        except OSError:
            pass
from services.llm_service import build_ssl_context, parse_tasks, stream_chat_completions
from services.session_service import get_session_store
from services.skill_service import dispatch_skill, format_task_result, get_system_messages

# ── 上下文截断阈值 ──
MAX_CONTEXT_CHARS = 64000
MIN_RETAIN_ROUNDS = 10

# ── Task JSON 流式过滤正则 ──
_RAW_TASK_JSON_RE = re.compile(
    r'\[\s*\{\s*"(?:name|type|task_type)"\s*:\s*"[^"]*"'
    r'(?:\s*,\s*"(?:query|arguments|top_k|k)"\s*:\s*[^,}]+)*\s*\}'
    r'(?:\s*,\s*\{\s*"(?:name|type|task_type)"\s*:\s*"[^"]*"'
    r'(?:\s*,\s*"(?:query|arguments|top_k|k)"\s*:\s*[^,}]+)*\s*\})*'
    r'\s*\]',
)
_START_RAW_JSON = re.compile(r'\[\s*\{\s*"(?:name|type|task_type)"\s*:\s*"')
_TAIL_PARTIAL_JSON = re.compile(r'^\[[^\]()]*$')


# ── 上下文截断 ──

def truncate_messages(system_msgs: list[dict], history_msgs: list[dict]) -> list[dict]:
    """上下文截断：从头部丢弃旧消息，保留最近轮次。"""
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


# ── Task 流式过滤 ──

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


def filter_task_stream(stream):
    """过滤流式 content 中的 <task>...</task> 块和裸 JSON 数组，防止泄漏到前端。"""
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


# ── Task 文本清理 ──

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


def clean_task_blocks(text: str) -> str:
    """清除文本中所有 <task>...</task> 块和裸 JSON 数组。"""
    text = re.sub(r'<task>[\s\S]*?</task>', '', text, flags=re.IGNORECASE)
    text = _strip_raw_task_arrays(text)
    return text.strip()


# ── 工具函数 ──

def _tee_collect(source, collected: list):
    """包装一个迭代器，使其在遍历时同步收集所有产出的元素到 collected 列表中。

    用于在流式传输的同时收集原始 delta，避免 list() 全量缓冲导致流式失效。
    """
    for item in source:
        collected.append(item)
        yield item


# ── Agent 多轮循环 ──

async def agent_loop_stream(
    api_key: str,
    messages: list[dict],
    session_id: str,
) -> AsyncGenerator[str, None]:
    """Agent 多轮对话循环：流式调用 LLM，解析 Task，调度 Skill，输出 SSE 事件。"""
    ssl_context = build_ssl_context()
    store = get_session_store()
    task_calls = 0
    # 重复调用检测：分别统计「完全相同的任务」与「同一技能」的累计调用次数
    identical_task_counts: dict[str, int] = {}
    skill_call_counts: dict[str, int] = {}

    # 跨轮次累积：将多轮 agent 循环中的思考过程和最终回答分别累积
    all_content_parts: list[str] = []
    all_reasoning_parts: list[str] = []

    async def close_out(warning: str | None = None) -> AsyncGenerator[str, None]:
        """异常退出时的统一收尾，保证用户始终能拿到最终回答。

        背景：模型在前几轮通常只输出思考 + 被 <task> 过滤掉的规划文本，可见 content 为空。
        一旦在「收敛轮」之前耗尽轮次/工具次数，原来的
        `if final_content or final_reasoning` 就会跳过落库，
        用户看到的是「思考过程滚了半天，最终回答一片空白」。

        处理策略：
          - 已有可见回答 → 直接落库结束（保持原有行为）
          - 尚无可见回答 → 追加一轮「禁止调用工具」的指令，强制模型基于已获得的信息作答
        """
        if warning:
            yield f"event: warning\ndata: {json.dumps({'content': warning})}\n\n"

        existing = clean_task_blocks("".join(all_content_parts)).strip()
        if existing:
            store.append_message(
                session_id, "assistant", existing, "".join(all_reasoning_parts)
            )
            yield "event: done\ndata: {}\n\n"
            return

        forced_messages = messages + [
            {
                "role": "user",
                "content": (
                    "【系统指令】工具调用已达上限。请立即停止调用任何技能或工具，"
                    "不要输出 <task> 标签，直接基于上文已经获得的信息给出最终回答。"
                ),
            }
        ]
        forced_payload = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": forced_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0,
            "thinking": {"type": "enabled", "reasoning_effort": "medium"},
        }

        answer_parts: list[str] = []
        extra_reasoning: list[str] = []
        try:
            for delta_type, text in stream_chat_completions(api_key, forced_payload, ssl_context):
                if delta_type == "content":
                    answer_parts.append(text)
                    yield f"event: content\ndata: {json.dumps({'content': text})}\n\n"
                elif delta_type == "reasoning":
                    extra_reasoning.append(text)
                elif delta_type == "error":
                    _trace(f"[debug]   收尾作答出错：{text}")
                    break
        except Exception as exc:
            _trace(f"[debug]   收尾作答异常：{exc}")

        answer = clean_task_blocks("".join(answer_parts)).strip()
        if not answer:
            # 极端兜底：连强制作答都为空，也要给用户一句可读的回应
            answer = (
                "抱歉，本次未能整理出完整答复。"
                "您可以换个问法或补充一些关键信息，我再为您解答。"
            )
            yield f"event: content\ndata: {json.dumps({'content': answer})}\n\n"

        if DEBUG:
            _trace(f"[debug] 收尾作答完成：{len(answer)} 字")

        store.append_message(
            session_id,
            "assistant",
            answer,
            "".join(all_reasoning_parts + extra_reasoning),
        )
        yield "event: done\ndata: {}\n\n"

    for turn in range(MAX_AGENT_TURNS):
        if DEBUG:
            _trace(f"\n[debug] ===== turn {turn} 开始 =====")
        payload = {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            # 任务规划环节需要确定性输出，固定为贪心解码
            "temperature": 0,
            "thinking": {"type": "enabled", "reasoning_effort": "medium"},
        }

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        # raw_content_parts: 保存未经 filter_task_stream 过滤的原始内容，用于 task 解析
        raw_content_parts: list[str] = []
        saw_think = False

        try:
            # 直接流式处理，不缓冲所有 delta
            # 使用 TeeCollector 在流式传输的同时收集原始 delta 用于 task 解析
            collected: list[tuple[str, str]] = []
            llm_stream = stream_chat_completions(api_key, payload, ssl_context)

            for delta_type, text in filter_task_stream(_tee_collect(llm_stream, collected)):
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
                            clean_task_blocks("".join(all_content_parts)),
                            "".join(all_reasoning_parts),
                        )
                    return

            # 从收集的原始 delta 中提取 raw content（含 <task> 标签，用于 task 解析）
            for dt, text in collected:
                if dt == "content":
                    raw_content_parts.append(text)

            if saw_think:
                yield f"event: reasoning\ndata: {json.dumps({'content': '</think>'})}\n\n"

        except urllib.error.URLError as e:
            yield f"event: error\ndata: {json.dumps({'content': f'网络连接失败: {e.reason}'})}\n\n"
            if all_content_parts or all_reasoning_parts:
                store.append_message(
                    session_id,
                    "assistant",
                    clean_task_blocks("".join(all_content_parts)),
                    "".join(all_reasoning_parts),
                )
            return
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'content': f'请求异常: {e}'})}\n\n"
            # 出错前保存已累积的内容
            if all_content_parts or all_reasoning_parts:
                store.append_message(
                    session_id,
                    "assistant",
                    clean_task_blocks("".join(all_content_parts)),
                    "".join(all_reasoning_parts),
                )
            return

        assistant_content = "".join(content_parts)
        assistant_reasoning = "".join(reasoning_parts)

        # 累积内容：content 中的任务块已被 filter_task_stream 过滤，直接累积
        if assistant_content:
            all_content_parts.append(assistant_content)
        if assistant_reasoning:
            all_reasoning_parts.append(assistant_reasoning)

        # 使用 raw_content + reasoning 进行 task 解析
        # raw_content_parts 包含未过滤的 <task> 标签，parse_tasks 需要它们
        raw_content = "".join(raw_content_parts)
        combined = raw_content + "\n" + assistant_reasoning
        _t_parse = time.perf_counter()
        tasks = parse_tasks(combined)
        parse_ms = (time.perf_counter() - _t_parse) * 1000

        # 去重：模型经常在 content 与 reasoning 中各写一遍相同的 <task>，
        # 合并解析会让同一个任务被执行多次，虚增 task 计数并提前撞上轮次上限。
        _seen_keys: set[tuple] = set()
        _deduped = []
        for _tk in tasks:
            _key = (
                _tk.task_type,
                (_tk.query or "").strip(),
                _tk.top_k,
                json.dumps(_tk.arguments or {}, sort_keys=True, ensure_ascii=False),
            )
            if _key in _seen_keys:
                continue
            _seen_keys.add(_key)
            _deduped.append(_tk)
        _dropped = len(tasks) - len(_deduped)
        tasks = _deduped
        if DEBUG and _dropped:
            _trace(f"[debug]   去重：丢弃 {_dropped} 个重复 task，{len(tasks) + _dropped} → {len(tasks)}")

        if DEBUG:
            raw_blocks = _TASK_BLOCK_RE.findall(raw_content)
            reason_blocks = _TASK_BLOCK_RE.findall(assistant_reasoning)
            _trace(
                f"[debug] turn={turn} | 可见content={len(assistant_content)}字 | "
                f"raw_content={len(raw_content)}字(<task>块 {len(raw_blocks)}个) | "
                f"reasoning={len(assistant_reasoning)}字(<task>块 {len(reason_blocks)}个) | "
                f"→ 解析出 tasks={len(tasks)} (parse {parse_ms:.0f}ms)"
            )
            for _i, _tk in enumerate(tasks, 1):
                _trace(
                    f"[debug]   task#{_i} type={_tk.task_type} top_k={_tk.top_k} "
                    f"query={(_tk.query or '')[:70]!r}"
                )
            for _j, _blk in enumerate(raw_blocks, 1):
                _trace(f"[debug]   raw_content<task>块#{_j}: {_blk[:260]!r}")

        # 回填 assistant 本轮的实际输出，让模型能感知自己的规划历史
        # （用过哪些 query、当时打算做什么），从而判断「这个方向已经试过了」。
        # 必须用未过滤的 raw_content：过滤后的 content 里 <task> 已被剥掉，
        # 模型就看不到自己请求过什么了。
        # 注意：只写入 messages（模型上下文），不写数据库——
        # raw_content 含 <task> 标签，落库会直接泄漏给用户。
        reply_text = raw_content.strip()
        if reply_text:
            messages.append({"role": "assistant", "content": reply_text})

        if not tasks:
            # 所有任务已完成，保存最终结果：一条 assistant 消息
            final_content = clean_task_blocks("".join(all_content_parts))
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
                async for chunk in close_out("工具调用次数已达上限，正在为您整理答复…"):
                    yield chunk
                return

            fingerprint = (
                f"{task.task_type}|{task.query}|{task.top_k}|"
                f"{json.dumps(task.arguments or {}, ensure_ascii=False)}"
            )
            identical_task_counts[fingerprint] = identical_task_counts.get(fingerprint, 0) + 1
            skill_call_counts[task.task_type] = skill_call_counts.get(task.task_type, 0) + 1

            # 原实现要求「最近 3 个指纹完全相同」才判定死循环，实际永远触发不了：
            #   - 同轮内的重复是成对出现（#1 == #2，但 #3 换了新 query），连续计数到不了 3
            #   - 跨轮重复时 query 每轮都不一样，指纹天然不同，完全检测不到
            # 改为按累计次数判定，并区分「完全相同任务」与「同一技能」两个维度。
            if identical_task_counts[fingerprint] > MAX_IDENTICAL_TASK_CALLS:
                async for chunk in close_out("检测到完全相同的任务被重复执行，正在为您整理答复…"):
                    yield chunk
                return
            if skill_call_counts[task.task_type] > MAX_SAME_SKILL_CALLS:
                async for chunk in close_out(
                    f"技能 {task.task_type} 调用次数过多，正在为您整理答复…"
                ):
                    yield chunk
                return

            _t_dispatch = time.perf_counter()
            result_text = await dispatch_skill(REPO_DIR, task)
            if DEBUG:
                _trace(
                    f"[debug]   dispatch {task.task_type} 耗时 "
                    f"{(time.perf_counter() - _t_dispatch) * 1000:.0f}ms，返回 {len(result_text)} 字"
                )

            yield f"event: task\ndata: {json.dumps({'type': task.task_type, 'status': 'executed', 'result': result_text})}\n\n"

            task_msg = format_task_result(task.task_type, result_text)
            messages.append(task_msg)
            store.append_message(session_id, task_msg["role"], task_msg["content"])

    # 循环结束（达到最大轮次）
    async for chunk in close_out("已达到最大推理轮次，正在为您整理答复…"):
        yield chunk


async def empty_stream(session_id: str) -> AsyncGenerator[str, None]:
    """空流响应，用于新建会话时仅返回 session_id。"""
    yield "event: done\ndata: {}\n\n"
