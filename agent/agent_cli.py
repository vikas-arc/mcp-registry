"""An OpenAI Agents SDK agent driven by the MCP Registry catalog.

Flow:
  1. Pull the catalog from the registry.
  2. You pick which servers (or specific tools) to give the agent.
  3. It connects to those via the registry's per-server MCP endpoints
     (/mcp/<user>/<slug>) and builds an agent with exactly those tools.
  4. Chat loop — ask in plain language; the agent calls the tools to do things.

Env:
  OPENAI_API_KEY   required to actually run the agent (the LLM brain)
  REGISTRY_URL     default http://localhost:8000
  REGISTRY_USER    default vikas   (identity segment in /mcp/<user>/...)
  AGENT_MODEL      default gpt-4o

Run:
  pip install -r requirements.txt
  python agent_cli.py
"""
from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack

import httpx
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

REGISTRY = os.environ.get("REGISTRY_URL", "http://localhost:8000").rstrip("/")
USER = os.environ.get("REGISTRY_USER", "vikas")
MODEL = os.environ.get("AGENT_MODEL", "gpt-4o")


async def fetch_catalog() -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{REGISTRY}/catalog", headers={"X-User-Id": USER})
        r.raise_for_status()
        servers = [s for s in r.json() if s["status"] == "active"]
        for s in servers:
            tr = await c.get(f"{REGISTRY}/catalog/{s['id']}/tools")
            s["tools"] = tr.json() if tr.status_code == 200 else []
        return servers


def choose(servers: list[dict]) -> dict[str, set[str] | None]:
    """Return {slug: allowed_tool_names or None(=all)} from the user's selection."""
    print("\n=== Catalog ===")
    by_slug = {s["slug"]: s for s in servers}
    for i, s in enumerate(servers):
        names = ", ".join(t["namespaced_name"] for t in s["tools"]) or "no tools"
        print(f"  [{i}] {s['name']}  ({s['slug']})\n        {names}")

    raw = input(
        "\nSelect: server numbers (e.g. 0,2), 'all', and/or specific tool names\n"
        "(e.g. orders__get_order_status): "
    ).strip()

    selection: dict[str, set[str] | None] = {}
    if raw.lower() == "all" or not raw:
        return {s["slug"]: None for s in servers}

    for tok in (t.strip() for t in raw.split(",") if t.strip()):
        if tok.isdigit():
            idx = int(tok)
            if 0 <= idx < len(servers):
                selection[servers[idx]["slug"]] = None  # whole server
        elif "__" in tok:
            slug = tok.split("__", 1)[0]
            if slug in by_slug:
                cur = selection.get(slug)
                if cur is None and slug in selection:
                    continue  # whole server already selected
                selection.setdefault(slug, set())
                selection[slug].add(tok)  # type: ignore[union-attr]
        elif tok in by_slug:
            selection[tok] = None
    return selection


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY is not set — the agent can connect to tools but cannot think.")

    servers = await fetch_catalog()
    if not servers:
        print("No active servers in the catalog. Publish one first.")
        return

    selection = choose(servers)
    if not selection:
        print("Nothing selected.")
        return

    async with AsyncExitStack() as stack:
        mcp_servers = []
        for slug, allowed in selection.items():
            tf = create_static_tool_filter(allowed_tool_names=list(allowed)) if allowed else None
            srv = MCPServerStreamableHttp(
                name=slug,
                params={"url": f"{REGISTRY}/mcp/{USER}/{slug}"},
                tool_filter=tf,
                cache_tools_list=True,
            )
            await stack.enter_async_context(srv)
            mcp_servers.append(srv)

        agent = Agent(
            name="Registry Agent",
            model=MODEL,
            instructions=(
                "You are a helpful assistant. Use the available tools (provided by the "
                "user's selected MCP servers) to accomplish what they ask. Prefer calling "
                "a tool over guessing. Be concise."
            ),
            mcp_servers=mcp_servers,
        )

        connected = ", ".join(selection.keys())
        print(f"\n✅ Agent ready with: {connected}")
        print("Type a request, or 'quit' to exit.")
        while True:
            try:
                q = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q.lower() in ("quit", "exit", ""):
                break
            result = await Runner.run(agent, q)
            print(f"\nagent> {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
