"""MCP Client 管理：连接外部 MCP Server，聚合工具目录，供 Agent 调度调用。

支持三种传输：
  - stdio：本地子进程（配置含 command）
  - Streamable HTTP：远程（配置含 url，type 缺省或为 http/streamable-http）
  - SSE：远程兼容（配置 type: "sse"）

任一 Server 连接失败时降级跳过，不影响其余 Server 与原有客服问答。
"""

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

import httpx2
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from config import DEBUG, MCP_CALL_TIMEOUT_SECONDS, MCP_SERVERS_PATH

# 目录渲染限制
_CATALOG_MAX_CHARS = 4096
_DESC_MAX_CHARS = 200


@dataclass(frozen=True)
class MCPTool:
    """对外暴露的 MCP 工具元信息。

    name 统一为 `{server}.{tool_name}`，与内置 skill 天然隔离。
    """

    name: str
    server: str
    tool_name: str
    description: str
    input_schema: dict


@dataclass
class _ServerConnection:
    server_name: str
    stack: AsyncExitStack = field(default_factory=AsyncExitStack)
    session: Optional[ClientSession] = None


@asynccontextmanager
async def _streamable_http_transport(url: str, headers: Optional[dict]):
    """Streamable HTTP 传输封装。

    mcp 2.x 的 streamable_http_client 通过 http_client 传入 headers，
    此处自行创建/关闭 httpx2.AsyncClient，避免连接泄漏。
    """
    client = httpx2.AsyncClient(headers=headers) if headers else None
    try:
        if client is not None:
            transport = streamable_http_client(url, http_client=client, terminate_on_close=False)
        else:
            transport = streamable_http_client(url)
        async with transport as streams:
            yield streams
    finally:
        if client is not None:
            await client.aclose()


class MCPClientManager:
    """聚合管理多个 MCP Server 连接与工具目录。"""

    def __init__(self) -> None:
        self._connections: dict[str, _ServerConnection] = {}
        self._tools: dict[str, MCPTool] = {}
        self._server_cfgs: dict[str, dict] = {}
        self._started = False

    # ── 生命周期 ──

    async def start(self) -> None:
        """读取 mcp_servers.json，逐个连接 Server 并聚合工具目录。

        连接失败仅告警并跳过，不影响其他 Server。
        """
        if self._started:
            return
        self._started = True

        servers = self._load_config()
        if not servers:
            if DEBUG:
                print("[mcp] 无 MCP Server 配置，跳过启动", file=sys.stderr)
            return

        for name, cfg in servers.items():
            self._server_cfgs[name] = cfg
            await self._connect_server(name, cfg)

    async def close(self) -> None:
        """关闭所有 Server 连接。"""
        for conn in self._connections.values():
            try:
                await conn.stack.aclose()
            except Exception as e:
                if DEBUG:
                    print(f"[mcp] 关闭 server {conn.server_name} 失败: {e}", file=sys.stderr)
        self._connections.clear()
        self._tools.clear()
        self._started = False

    def _load_config(self) -> dict:
        try:
            if not os.path.exists(MCP_SERVERS_PATH):
                return {}
            with open(MCP_SERVERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[mcp] 读取配置失败: {e}", file=sys.stderr)
            return {}
        if not isinstance(data, dict):
            return {}
        servers = data.get("mcpServers", {})
        return servers if isinstance(servers, dict) else {}

    async def _connect_server(self, name: str, cfg: dict) -> None:
        if not isinstance(cfg, dict):
            return
        try:
            conn = _ServerConnection(server_name=name)
            headers = await self._with_auth_headers(cfg, cfg.get("headers"))
            transport_ctx = self._build_transport(cfg, headers)
            if transport_ctx is None:
                return
            read, write = await conn.stack.enter_async_context(transport_ctx)
            session = await conn.stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result = await session.list_tools()
            tool_count = 0
            for tool in result.tools:
                external_name = f"{name}.{tool.name}"
                self._tools[external_name] = MCPTool(
                    name=external_name,
                    server=name,
                    tool_name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.input_schema or {},
                )
                tool_count += 1

            conn.session = session
            self._connections[name] = conn
            print(
                f"[mcp] 已连接 server '{name}'，发现 {tool_count} 个工具",
                file=sys.stderr,
            )
        except Exception as e:
            try:
                await conn.stack.aclose()
            except Exception:
                pass
            print(f"[mcp] 连接 server '{name}' 失败（已降级跳过）: {e}", file=sys.stderr)

    async def _reconnect_server(self, name: str) -> None:
        """断开并重连指定 Server（用于 token 过期后刷新连接）。"""
        old = self._connections.pop(name, None)
        if old is not None:
            try:
                await old.stack.aclose()
            except Exception:
                pass
        self._tools = {k: v for k, v in self._tools.items() if v.server != name}
        cfg = self._server_cfgs.get(name)
        if cfg:
            await self._connect_server(name, cfg)

    async def _with_auth_headers(self, cfg: dict, base_headers: Optional[dict]) -> Optional[dict]:
        """若配置了 token 鉴权，注入 Authorization: Bearer <token>。"""
        token_cfg = cfg.get("token")
        if not isinstance(token_cfg, dict):
            return base_headers
        kind = (token_cfg.get("kind") or "").strip().lower()
        if kind == "chaoxing-mcp":
            import services.mcp_token_service as token_service

            token = await token_service.get_bearer_token()
            headers = dict(base_headers or {})
            headers["Authorization"] = f"Bearer {token}"
            return headers
        return base_headers

    @staticmethod
    def _build_transport(cfg: dict, headers: Optional[dict] = None):
        """依据配置 type/url/command 判定传输方式，返回 async 上下文管理器。

        - type == "sse" → SSE
        - 有 url 且 type 非 stdio → Streamable HTTP
        - 有 command → stdio
        """
        t = (cfg.get("type") or "").strip().lower()
        if headers is None:
            headers = cfg.get("headers")
            headers = headers if isinstance(headers, dict) else None

        if t == "sse":
            url = cfg.get("url")
            if not url:
                return None
            return sse_client(url=url, headers=headers)

        if cfg.get("url"):
            return _streamable_http_transport(cfg["url"], headers)

        if cfg.get("command"):
            params = StdioServerParameters(
                command=str(cfg["command"]),
                args=cfg.get("args") or [],
                env=cfg.get("env"),
            )
            return stdio_client(params)

        return None

    # ── 工具访问 ──

    def list_tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    def is_ready(self) -> bool:
        return bool(self._tools)

    def find_tool(self, name: str) -> Optional[MCPTool]:
        return self._tools.get(name)

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP 工具，返回序列化文本结果。带超时保护。

        token 鉴权的 server 在调用前校验 token 有效期，过期则自动重连刷新。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"MCP tool not found: {name}"

        if self._needs_token_refresh(tool.server):
            if DEBUG:
                print(f"[mcp] server '{tool.server}' token 过期，重连刷新", file=sys.stderr)
            await self._reconnect_server(tool.server)
            tool = self._tools.get(name)
            if tool is None:
                return f"MCP tool unavailable after reconnect: {name}"

        conn = self._connections.get(tool.server)
        if conn is None or conn.session is None:
            return f"MCP server not connected: {tool.server}"

        try:
            result = await asyncio.wait_for(
                conn.session.call_tool(tool.tool_name, arguments or {}),
                timeout=MCP_CALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return f"MCP tool call timed out after {MCP_CALL_TIMEOUT_SECONDS}s: {name}"
        except Exception as e:
            return f"MCP tool call failed: {name} ({e})"

        return self._format_call_result(name, result)

    def _needs_token_refresh(self, server_name: str) -> bool:
        """判断 server 是否配置了 token 鉴权且当前 token 已过期。"""
        cfg = self._server_cfgs.get(server_name) or {}
        token_cfg = cfg.get("token")
        if not isinstance(token_cfg, dict):
            return False
        kind = (token_cfg.get("kind") or "").strip().lower()
        if kind == "chaoxing-mcp":
            import services.mcp_token_service as token_service

            return not token_service.token_is_fresh()
        return False

    @staticmethod
    def _format_call_result(name: str, result) -> str:
        parts: list[str] = []
        content = getattr(result, "content", None) or []
        for item in content:
            item_type = getattr(item, "type", "")
            if item_type == "text":
                text = getattr(item, "text", "")
                if text:
                    parts.append(text)
            elif item_type == "image":
                mime = getattr(item, "mimeType", "image/*")
                parts.append(f"[MCP image result: {mime}]")
            else:
                parts.append(str(item))

        if not parts:
            return f"[{name}] 无返回内容"
        return "\n".join(parts)

    # ── 目录渲染 ──

    def render_tool_catalog(self) -> str:
        """生成注入 TOOL_PROTOCOL 的紧凑工具目录文本，整体 ≤ 4KB。"""
        if not self._tools:
            return ""
        lines = ["\n[可用 MCP 工具]"]
        total = 0
        for tool in self._tools.values():
            required = (tool.input_schema or {}).get("required") or []
            desc = (tool.description or "").strip().replace("\n", " ")
            if len(desc) > _DESC_MAX_CHARS:
                desc = desc[:_DESC_MAX_CHARS] + "…"
            line = f"- {tool.name}: {desc or '无描述'}"
            if required:
                line += f"（必填参数: {', '.join(map(str, required))}）"
            total += len(line) + 1
            if total > _CATALOG_MAX_CHARS:
                lines.append("- …（工具较多，已截断）")
                break
            lines.append(line)
        return "\n".join(lines)


# 全局单例：main.py / skill_service.py 共享，避免重复连接
mcp_manager = MCPClientManager()
