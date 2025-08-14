# mcp_tools.py
from __future__ import annotations
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.common.utils import tool, SimpleTool as BaseTool
from app.chatbot.chatbot_models import ActionResult, AgentState
from app.chatbot.components.mcp_clients.mcp_stdio_client import (
    MCPServerConfig,
    MCPStdioClient,
)

# 1) Configure your MCP servers here (or load from JSON and build the list)
MCP_SERVERS_CONFIG: List[MCPServerConfig] = [
    MCPServerConfig(
        server_id="my_text_editor",
        command="uv",
        args=["run", "/Users/vslala/src/code/projects/innomightlabs/innomightlabs-api/app/mcp_servers/mcp_text_editor.py"],
        env={},
        timeout_sec=30,
    ),
    MCPServerConfig(
        server_id="playwright_official",
        command="npx",
        args=["@playwright/mcp@0.0.33"],
        env={},
        timeout_sec=30,
    ),
]

# 2) One client per server_id (lazy-started)
_clients: dict[str, MCPStdioClient] = {cfg.server_id: MCPStdioClient(cfg=cfg) for cfg in MCP_SERVERS_CONFIG}


# 3) Generic input schema: the model picks a remote tool and its arguments
class MCPDispatchParams(BaseModel):
    tool: str = Field(..., description="Tool name exposed by this MCP server")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the selected tool")


def _normalize_content(content: List[Dict[str, Any]]) -> str:
    """Flatten MCP content array to a string for ActionResult.result."""
    parts: List[str] = []
    for c in content or []:
        if "text" in c:
            parts.append(c["text"])
        elif "json" in c:
            parts.append(json.dumps(c["json"], ensure_ascii=False))
        else:
            parts.append(json.dumps(c, ensure_ascii=False))
    return "\n".join(parts) if parts else ""


def _make_server_tool(server_id: str) -> BaseTool:
    client = _clients[server_id]

    @tool(
        name=f"mcp_{server_id}",
        description=f"Call a tool on MCP server '{server_id}'. "
        f"Use 'tool' to select the remote tool and 'arguments' for its params. "
        f"Tip: call mcp_list_tools for available tool names.",
        args_schema=MCPDispatchParams,
        return_direct=True,
    )
    async def mcp_server_dispatch(state: AgentState, input: MCPDispatchParams) -> ActionResult:
        # Lazy start
        await client.ensure_started()
        # Dispatch to remote tool
        res = await client.call_tool(input.tool, input.arguments)
        result_text = _normalize_content(res.get("content") or [])
        status = "error" if res.get("isError") else "success"
        return ActionResult(
            thought=f"Dispatched to {server_id}:{input.tool} [{status}]",
            action=f"mcp_{server_id}",
            result=result_text or f"{server_id}:{input.tool} returned no content",
        )

    return mcp_server_dispatch  # BaseTool


# Optional helper tool to enumerate remote tool names per server
class ListToolsParams(BaseModel):
    server_id: str = Field(..., description="MCP server id")


@tool(
    name="mcp_list_tools",
    description="List tools exposed by an MCP server",
    args_schema=ListToolsParams,
    return_direct=True,
)
async def mcp_list_tools(state: AgentState, input: ListToolsParams) -> ActionResult:
    server_id = input.server_id
    if server_id not in _clients:
        return ActionResult(thought="Lookup failed", action="mcp_list_tools", result=f"unknown server_id: {server_id}")
    client = _clients[server_id]
    await client.ensure_started()
    tools = await client.list_tools()
    names = [t["name"] for t in tools]
    return ActionResult(thought="Listed tools", action="mcp_list_tools", result=json.dumps(names))


# 4) Export: one BaseTool per MCP server + the optional lister
mcp_actions: List[BaseTool] = [_make_server_tool(cfg.server_id) for cfg in MCP_SERVERS_CONFIG] + [mcp_list_tools]
