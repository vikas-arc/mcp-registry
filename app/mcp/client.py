from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from app.config import get_settings
from app.models import Transport

settings = get_settings()


@dataclass
class DiscoveredTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@contextlib.asynccontextmanager
async def open_session(
    base_url: str, transport: Transport, headers: dict[str, str]
) -> AsyncIterator[ClientSession]:
    """Open an initialized MCP client session against a remote server.

    A fresh session is opened per logical operation. This is simple and correct;
    if call latency matters, replace with a pooled long-lived session per
    connection (a background task owning the async context + a request queue).
    """
    timeout = timedelta(seconds=settings.upstream_call_timeout)
    if transport is Transport.sse:
        async with sse_client(base_url, headers=headers) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await session.initialize()
                yield session
    else:
        async with streamablehttp_client(base_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                await session.initialize()
                yield session


async def handshake_and_list_tools(
    base_url: str, transport: Transport, headers: dict[str, str]
) -> list[DiscoveredTool]:
    """Initialize + list tools. Raises on any connection/protocol failure."""
    async with open_session(base_url, transport, headers) as session:
        result = await session.list_tools()
        return [
            DiscoveredTool(
                name=t.name,
                description=t.description,
                input_schema=t.inputSchema or {},
            )
            for t in result.tools
        ]


async def call_tool(
    base_url: str,
    transport: Transport,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    """Invoke a tool on the upstream server. Returns (is_error, content[])."""
    if headers.get("Authorization"):
        import sys

        print(f"[registry] forwarding caller token -> {base_url} (tool={tool_name})", file=sys.stderr)
    async with open_session(base_url, transport, headers) as session:
        result = await session.call_tool(tool_name, arguments)
        content = [item.model_dump(mode="json") for item in result.content]
        return bool(result.isError), content
