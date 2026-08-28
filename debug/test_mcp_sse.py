"""MCP SSE 传输自测：连接以 SSE 暴露的测试 Server，验证 list_tools + call_tool。

前置：先启动 SSE 测试 server：venv/bin/python debug/mcp_test_server.py sse
运行：venv/bin/python debug/test_mcp_sse.py
"""

import asyncio
import json
import os
import sys
import tempfile

SSE_URL = os.environ.get("MCP_SSE_TEST_URL", "http://127.0.0.1:8000/sse")

cfg = {"mcpServers": {"mcp-test": {"type": "sse", "url": SSE_URL, "headers": {}}}}
cfg_path = os.path.join(tempfile.gettempdir(), "mcp_sse_servers.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f)
os.environ["MCP_SERVERS_PATH"] = cfg_path

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND)

from services.llm_service import Task
from services.mcp_service import mcp_manager
from services.skill_service import dispatch_skill


async def main():
    await mcp_manager.start()
    assert mcp_manager.is_ready(), "SSE 连接失败"
    tools = [t.name for t in mcp_manager.list_tools()]
    print("SSE tools:", tools)
    assert "mcp-test.add" in tools

    t = Task(task_type="mcp-test.add", raw="", arguments={"a": 10, "b": 32})
    r = await dispatch_skill(BACKEND, t)
    print("SSE call result:", repr(r))
    assert r.strip() == "42"

    await mcp_manager.close()
    print("PASS SSE 全链路 (10+32=42)")


asyncio.run(main())
