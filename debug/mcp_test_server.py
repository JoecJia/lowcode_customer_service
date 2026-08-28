"""最小 MCP 测试 Server：暴露 add 工具，用于验证 MCP Client 接入链路。

运行：venv/bin/python debug/mcp_test_server.py（默认 stdio 传输）
也可用 SSE 传输：venv/bin/python debug/mcp_test_server.py sse
"""

import sys

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("mcp-test")


@mcp.tool()
def add(a: int, b: int) -> int:
    """将两个整数相加。"""
    return a + b


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport)  # type: ignore[arg-type]
