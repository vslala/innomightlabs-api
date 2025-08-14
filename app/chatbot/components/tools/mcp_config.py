from app.chatbot.components.mcp_clients.mcp_stdio_client import MCPServerConfig

# Example MCP server configurations
MCP_SERVERS = [
    # Hello World demo server
    MCPServerConfig(server_id="hello_world", command="python3", args=["hello_mcp_server.py"], env={}, timeout_sec=30),
]
