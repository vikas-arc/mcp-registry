"""Exposes the registry itself as an MCP server.

An MCP client (GitHub Copilot, Claude, Cursor) connects to:

    http://<registry>/mcp/<user_id>

and sees exactly the tools that teammate has connected from the catalog. When it
calls a tool, we route it to the right upstream custom server via the gateway.

We build a fresh MCP server per request whose handlers close over the user_id
parsed from the path. (A shared server + contextvar doesn't work here: the
session manager runs each request in a task that wouldn't inherit the contextvar.)

No auth yet: the teammate is identified by the {user_id} path segment. When real
auth lands, derive the user from a verified token instead of the URL.
"""
from __future__ import annotations

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from app.database import database
from app.services import gateway


def build_server(user_id: str, slug: str | None = None, auth: str | None = None) -> Server:
    """Build an MCP server for a request.

    slug=None  -> aggregate: every server the user has connected (/mcp/<user>)
    slug="x"   -> single catalog server x          (/mcp/<user>/x)
    """
    server: Server = Server(f"mcp-registry/{slug}" if slug else "mcp-registry")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        tools = (
            await gateway.server_tools(database, slug)
            if slug
            else await gateway.aggregate_tools(database, user_id)
        )
        return [
            types.Tool(
                name=t.namespaced_name,
                description=t.description or "",
                inputSchema=t.input_schema or {"type": "object", "properties": {}},
            )
            for t in tools
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
        result = (
            await gateway.route_server_tool_call(database, slug, name, arguments or {}, auth)
            if slug
            else await gateway.route_tool_call(database, user_id, name, arguments or {}, auth)
        )
        blocks: list[types.ContentBlock] = []
        for item in result.content:
            if item.get("type") == "text":
                blocks.append(types.TextContent(type="text", text=item.get("text", "")))
            else:
                blocks.append(types.TextContent(type="text", text=str(item)))
        return blocks

    return server


async def handle_user_mcp(scope, receive, send) -> None:
    """ASGI app mounted at /mcp. Path here is /<user_id> (prefix already stripped)."""
    # Mount keeps the full path and sets root_path to the mount prefix ("/mcp"),
    # so strip the prefix before reading the user segment.
    path = scope["path"]
    root = scope.get("root_path", "")
    rel = path[len(root):] if path.startswith(root) else path
    parts = rel.strip("/").split("/")
    user_id = parts[0]
    slug = parts[1] if len(parts) > 1 and parts[1] else None  # /mcp/<user>/<slug>
    # Caller's token, for BYOT pass-through to forward_auth servers (e.g. Atlassian write).
    hdrs = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    auth = hdrs.get("authorization")
    server = build_server(user_id, slug, auth)
    manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)

    inner = dict(scope)
    inner["path"] = "/"
    inner["raw_path"] = b"/"
    async with manager.run():
        await manager.handle_request(inner, receive, send)
