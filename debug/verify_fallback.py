r"""验证「轮次耗尽时是否仍有最终回答」的兜底逻辑。

背景
----
模型在前几轮通常只输出思考过程 + 被 <task> 过滤掉的规划文本，可见 content 为 0。
若在「收敛轮」之前耗尽 MAX_AGENT_TURNS / MAX_TASK_CALLS，旧实现只落库已有内容，
于是用户看到「思考滚了半天，最终回答一片空白」。

本脚本把 MAX_AGENT_TURNS 压到 1 强制触发该分支，并直接调用 agent_loop_stream
（绕过 HTTP 服务与前端），检查是否仍产出可见回答。

用法
----
    venv\Scripts\python.exe debug\verify_fallback.py

注意：会真实调用一次大模型（1 轮 + 1 次收尾作答），并写入一条测试会话记录。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

# 必须在导入 config 之前设置：把轮次压到 1，强制走「轮次耗尽」分支
os.environ["MAX_AGENT_TURNS"] = "1"

from config import MAX_AGENT_TURNS, MAX_TASK_CALLS  # noqa: E402
from services.agent_service import agent_loop_stream  # noqa: E402
from services.session_service import get_session_store  # noqa: E402
from services.skill_service import get_system_messages  # noqa: E402

QUESTION = "如何配置审批流程的节点条件"


def parse_event(chunk: str) -> tuple[str, dict]:
    """把一段 SSE 文本解析为 (event_type, data)。"""
    event_type = ""
    data: dict = {}
    for line in chunk.splitlines():
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            raw = line[5:].strip()
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {}
    return event_type, data


async def main() -> int:
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        print("[x] .env 缺少 ARK_API_KEY", file=sys.stderr)
        return 2

    print("=" * 60)
    print(f"兜底作答验证  MAX_AGENT_TURNS={MAX_AGENT_TURNS}  MAX_TASK_CALLS={MAX_TASK_CALLS}")
    print("=" * 60)

    store = get_session_store()
    session_id = store.create_session(user_id=None)
    print(f"测试会话：{session_id}")

    messages = get_system_messages()
    messages.append({"role": "user", "content": QUESTION})

    content_chars = 0
    content_preview = ""
    reasoning_chars = 0
    warnings: list[str] = []
    task_types: list[str] = []

    started = time.perf_counter()
    async for chunk in agent_loop_stream(api_key, messages, session_id):
        event_type, data = parse_event(chunk)
        if event_type == "content":
            text = str(data.get("content") or "")
            if text:
                content_chars += len(text)
                if not content_preview:
                    content_preview = text[:60].replace("\n", " ")
        elif event_type == "reasoning":
            text = str(data.get("content") or "")
            if text not in ("<THINK_V2>", "</think>"):
                reasoning_chars += len(text)
        elif event_type == "warning":
            warnings.append(str(data.get("content") or ""))
        elif event_type == "task":
            task_types.append(str(data.get("type") or "?"))
        elif event_type == "error":
            print(f"[x] 流内错误：{data.get('content')}", file=sys.stderr)
            return 1

    elapsed = time.perf_counter() - started

    print(f"耗时        : {elapsed:.1f}s")
    print(f"task 执行   : {len(task_types)} 次 → {', '.join(task_types) or '无'}")
    print(f"reasoning   : {reasoning_chars} 字")
    print(f"warning     : {len(warnings)} 条 → {'; '.join(warnings) or '无'}")
    print(f"最终回答    : {content_chars} 字")
    if content_preview:
        print(f"回答开头    : {content_preview}…")
    print("-" * 60)

    if content_chars > 0:
        print("[√] 轮次耗尽时仍产出了最终回答 —— 兜底生效")
        return 0
    print("[x] 仍然没有最终回答 —— 兜底未生效")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
