"""MCP Client 接入自测：parse_tasks 参数透传 + stdio 全链路调度。

运行：venv/bin/python debug/test_mcp_chain.py
"""

import asyncio
import json
import os
import sys
import tempfile

# 先设置 MCP_SERVERS_PATH 再导入 backend 模块
test_cfg = {
    "mcpServers": {
        "mcp-test": {
            "command": sys.executable,
            "args": [os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_test_server.py")],
            "env": {},
        }
    }
}
cfg_path = os.path.join(tempfile.gettempdir(), "mcp_test_servers.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(test_cfg, f)
os.environ["MCP_SERVERS_PATH"] = cfg_path

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND)

from services.agent_service import clean_task_blocks
from services.llm_service import Task, parse_tasks
from services.mcp_service import mcp_manager
from services.skill_service import dispatch_skill


async def main():
    # 1. parse_tasks 标签形式 + arguments
    raw = '<task><type>mcp-test.add</type><arguments>{"a": 1, "b": 2}</arguments></task>'
    tasks = parse_tasks(raw)
    assert len(tasks) == 1 and tasks[0].task_type == "mcp-test.add"
    assert tasks[0].arguments == {"a": 1, "b": 2}, tasks[0].arguments
    print("PASS parse_tasks tag+arguments:", tasks[0])

    # 2. parse_tasks JSON 数组形式 + arguments（JSON 数组需包在 <task> 内）
    raw2 = '<task>[{"name": "mcp-test.add", "arguments": {"a": 3, "b": 4}}]</task>'
    tasks2 = parse_tasks(raw2)
    assert len(tasks2) == 1 and tasks2[0].arguments == {"a": 3, "b": 4}
    print("PASS parse_tasks json+arguments:", tasks2[0])

    # 3. 旧格式兼容（query/top_k，JSON 数组包在 <task> 内）
    raw3 = '<task>[{"name": "knowledge_retrieval", "query": "表单", "top_k": 3}]</task>'
    tasks3 = parse_tasks(raw3)
    assert tasks3[0].query == "表单" and tasks3[0].top_k == 3
    print("PASS parse_tasks legacy:", tasks3[0])

    # 4. MCP start + list_tools + catalog
    await mcp_manager.start()
    assert mcp_manager.is_ready()
    tools = mcp_manager.list_tools()
    print("tools:", [t.name for t in tools])
    assert any(t.name == "mcp-test.add" for t in tools)
    catalog = mcp_manager.render_tool_catalog()
    assert "mcp-test.add" in catalog
    print("PASS start/list/catalog")

    # 5. dispatch_skill 全链路（MCP 分支）：1+2=3
    task = tasks[0]
    result = await dispatch_skill(BACKEND, task)
    print("call result:", repr(result))
    assert result.strip() == "3", result
    print("PASS dispatch_skill -> mcp call (1+2=3)")

    # 6. 未知工具名 → Unsupported
    unknown = Task(task_type="mcp-test.no_such_tool", raw="")
    r2 = await dispatch_skill(BACKEND, unknown)
    print("unknown:", r2)
    assert "Unsupported" in r2

    # 7. clean_task_blocks 过滤 MCP JSON 数组（不泄漏到前端）
    leaked = clean_task_blocks('回答内容 [{"name":"mcp-test.add","arguments":{"a":1,"b":2}}] 结束')
    print("filtered:", repr(leaked))
    assert leaked == "回答内容  结束", leaked
    print("PASS clean_task_blocks filters mcp json")

    await mcp_manager.close()
    print("\nALL TESTS PASSED")


asyncio.run(main())
