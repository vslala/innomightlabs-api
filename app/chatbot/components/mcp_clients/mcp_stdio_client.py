import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass(frozen=True)
class MCPServerConfig:
    server_id: str
    command: str
    args: List[str]
    env: Dict[str, str]
    timeout_sec: int = 60  # per call timeout


class MCPStdioClient:
    """Generic MCP client for any stdio server."""

    def __init__(self, cfg: MCPServerConfig):
        self.cfg = cfg
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tool_cache: Optional[List[Dict[str, Any]]] = None

    async def start(self) -> None:
        """
        Starts the MCP server process using Standard input and output
        """
        if self._session:
            return
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        env = {**os.environ, **(self.cfg.env or {})}
        transport = await self._stack.enter_async_context(stdio_client(StdioServerParameters(command=self.cfg.command, args=self.cfg.args, env=env)))
        r, w = transport
        self._session = await self._stack.enter_async_context(ClientSession(r, w))
        await self._session.initialize()
        self._tool_cache = None

    async def stop(self) -> None:
        if self._stack:
            await self._stack.__aexit__(None, None, None)
        self._stack = None
        self._session = None
        self._tool_cache = None

    async def ensure_started(self) -> None:
        if not self._session:
            await self.start()

    async def list_tools(self) -> List[Dict[str, Any]]:
        await self.ensure_started()
        if self._tool_cache is None:
            resp = await self._session.list_tools()  # type: ignore
            self._tool_cache = [{"name": t.name, "description": t.description, "parameters": t.inputSchema} for t in resp.tools]
        return self._tool_cache

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        await self.ensure_started()
        try:
            coro = self._session.call_tool(name, arguments)  # type: ignore
            result = await asyncio.wait_for(coro, timeout=self.cfg.timeout_sec)
        except asyncio.TimeoutError:
            return {"content": [{"text": f"timeout after {self.cfg.timeout_sec}s"}], "isError": True}
        # MCP “content array”: [{"json": {...}}] or [{"text": "..."}] or images, etc.
        return {"content": [c.model_dump() for c in result.content], "isError": getattr(result, "isError", False)}
