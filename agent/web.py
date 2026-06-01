"""Web UI for the Registry Agent (OpenAI Agents SDK).

A small FastAPI service that:
  - lists the registry catalog (GET /api/catalog)
  - starts an agent session bound to selected servers/tools (POST /api/start)
  - chats with that agent, keeping conversation memory (POST /api/chat)
  - tears the session down (POST /api/stop)
and serves a chat page at /.

Env:
  OPENAI_API_KEY   required to actually run the agent
  REGISTRY_URL     default http://localhost:8000
  AGENT_MODEL      default gpt-4o

Run:
  uvicorn web:app --port 8800        # then open http://localhost:8800
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import AsyncExitStack

import httpx
from agents import Agent, Runner, SQLiteSession
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

REGISTRY = os.environ.get("REGISTRY_URL", "http://localhost:8000").rstrip("/")
MODEL = os.environ.get("AGENT_MODEL", "gpt-4o")
_HERE = os.path.dirname(__file__)

app = FastAPI(title="Registry Agent")

# session_id -> {stack, agent, session, servers, tools}  (web UI sessions)
SESSIONS: dict[str, dict] = {}

# agent_id -> {sig, stack, agent, tools, sessions}  (cached invoke-API agents)
AGENT_CACHE: dict[str, dict] = {}


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    """If AGENT_API_KEY is set, require it on the public invoke API. Open otherwise."""
    expected = os.environ.get("AGENT_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "Invalid or missing X-API-Key")


class StartReq(BaseModel):
    user: str = "vikas"
    selection: list[str]  # slugs and/or namespaced tool names; ["all"] for everything
    instructions: str | None = None  # system prompt override (from a saved agent)
    model: str | None = None
    # Per-server tokens {slug: token} forwarded to that server only (BYOT).
    # Never persisted — lives only for this run's MCP connections.
    tokens: dict[str, str] = {}


class AgentDef(BaseModel):
    name: str
    instructions: str = ""
    selection: list[str] = []
    model: str | None = None


DEFAULT_INSTRUCTIONS = (
    "You are a helpful assistant. Use the available tools (from the user's selected "
    "MCP servers) to accomplish what they ask. Prefer calling a tool over guessing. "
    "Be concise."
)


class ChatReq(BaseModel):
    session_id: str
    message: str


async def _catalog(user: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{REGISTRY}/catalog", headers={"X-User-Id": user})
        r.raise_for_status()
        servers = [s for s in r.json() if s["status"] == "active"]
        for s in servers:
            tr = await c.get(f"{REGISTRY}/catalog/{s['id']}/tools")
            s["tools"] = tr.json() if tr.status_code == 200 else []
        return servers


def _parse_selection(selection: list[str], servers: list[dict]) -> dict[str, set | None]:
    by_slug = {s["slug"]: s for s in servers}
    if any(tok.lower() == "all" for tok in selection) or not selection:
        return {s["slug"]: None for s in servers}
    out: dict[str, set | None] = {}
    for tok in selection:
        tok = tok.strip()
        if "__" in tok:
            slug = tok.split("__", 1)[0]
            if slug not in by_slug:
                continue
            if out.get(slug) is None and slug in out:
                continue  # whole server already selected — it covers this tool
            out.setdefault(slug, set()).add(tok)  # type: ignore[union-attr]
        elif tok in by_slug:
            out[tok] = None  # whole server
    return out


@app.get("/api/catalog")
async def api_catalog(user: str = "vikas"):
    return await _catalog(user)


# ---- saved agents: thin proxy to the registry's /me/agents ----

@app.get("/api/agents")
async def api_list_agents(user: str = "vikas"):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{REGISTRY}/me/agents", headers={"X-User-Id": user})
        r.raise_for_status()
        return r.json()


@app.post("/api/agents")
async def api_create_agent(payload: AgentDef, user: str = "vikas"):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{REGISTRY}/me/agents",
            headers={"X-User-Id": user},
            json=payload.model_dump(),
        )
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        return r.json()


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str, user: str = "vikas"):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.delete(f"{REGISTRY}/me/agents/{agent_id}", headers={"X-User-Id": user})
        if r.status_code >= 400 and r.status_code != 404:
            raise HTTPException(r.status_code, r.text)
        return {"ok": True}


async def _build_agent(
    user: str,
    selection: list[str],
    instructions: str | None,
    model: str | None,
    tokens: dict[str, str] | None = None,
):
    """Connect to the selected servers and build an Agent. Returns (stack, agent, servers, tools)."""
    servers = await _catalog(user)
    if not servers:
        raise HTTPException(400, "Catalog is empty / no active servers.")
    sel = _parse_selection(selection, servers)
    if not sel:
        raise HTTPException(400, "Nothing selected.")
    tokens = tokens or {}

    stack = AsyncExitStack()
    mcp_servers, tool_names = [], []
    try:
        for slug, allowed in sel.items():
            tf = create_static_tool_filter(allowed_tool_names=list(allowed)) if allowed else None
            # Each server gets ONLY its own token (if provided), as its connection header.
            headers = {"Authorization": f"Bearer {tokens[slug]}"} if tokens.get(slug) else {}
            srv = MCPServerStreamableHttp(
                name=slug,
                params={"url": f"{REGISTRY}/mcp/{user}/{slug}", "headers": headers},
                tool_filter=tf,
                cache_tools_list=True,
            )
            await stack.enter_async_context(srv)
            mcp_servers.append(srv)
            for t in await srv.list_tools():
                tool_names.append(t.name)
    except Exception as exc:  # noqa: BLE001
        await stack.aclose()
        raise HTTPException(502, f"Could not connect to selected servers: {exc}")

    agent = Agent(
        name="Registry Agent",
        model=model or MODEL,
        instructions=instructions or DEFAULT_INSTRUCTIONS,
        mcp_servers=mcp_servers,
    )
    return stack, agent, list(sel.keys()), tool_names


@app.post("/api/start")
async def api_start(req: StartReq):
    stack, agent, servers, tools = await _build_agent(
        req.user, req.selection, req.instructions, req.model, req.tokens
    )
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {
        "stack": stack,
        "agent": agent,
        "session": SQLiteSession(sid, ":memory:"),
        "servers": servers,
        "tools": tools,
    }
    return {"session_id": sid, "servers": servers, "tools": tools}


@app.post("/api/chat")
async def api_chat(req: ChatReq):
    s = SESSIONS.get(req.session_id)
    if not s:
        raise HTTPException(404, "Session not found — start a new one.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(400, "OPENAI_API_KEY is not set on the agent service.")
    result = await Runner.run(s["agent"], req.message, session=s["session"])
    return {"reply": result.final_output}


@app.post("/api/stop")
async def api_stop(req: ChatReq):
    s = SESSIONS.pop(req.session_id, None)
    if s:
        await s["stack"].aclose()
    return {"ok": True}


# ---- public invoke API: call a saved agent by id or name ----

class InvokeReq(BaseModel):
    message: str
    user: str = "vikas"
    conversation_id: str | None = None  # omit for a one-shot; reuse to keep memory


async def _resolve_agent(user: str, ref: str) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{REGISTRY}/me/agents", headers={"X-User-Id": user})
        r.raise_for_status()
        for a in r.json():
            if a["id"] == ref or a["name"] == ref:
                return a
    return None


def _sig(a: dict) -> str:
    return json.dumps(
        {"i": a["instructions"], "s": sorted(a["selection"]), "m": a["model"]}, sort_keys=True
    )


@app.post("/v1/agents/{ref}/invoke")
async def invoke(ref: str, body: InvokeReq, _=Depends(require_key)):
    """Run a saved agent by id or name. Returns its reply.

    Pass a stable conversation_id to keep multi-turn memory; omit for a one-shot.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(400, "OPENAI_API_KEY is not set on the agent service.")
    a = await _resolve_agent(body.user, ref)
    if a is None:
        raise HTTPException(404, f"Agent '{ref}' not found for user '{body.user}'.")

    sig = _sig(a)
    cached = AGENT_CACHE.get(a["id"])
    if cached is None or cached["sig"] != sig:
        if cached:
            await cached["stack"].aclose()  # def changed — rebuild
        stack, agent, servers, tools = await _build_agent(
            body.user, a["selection"], a["instructions"], a["model"]
        )
        cached = AGENT_CACHE[a["id"]] = {
            "sig": sig, "stack": stack, "agent": agent, "tools": tools, "sessions": {}
        }

    conv = body.conversation_id or uuid.uuid4().hex
    sess = cached["sessions"].get(conv)
    if sess is None:
        sess = cached["sessions"][conv] = SQLiteSession(f"{a['id']}:{conv}", ":memory:")

    result = await Runner.run(cached["agent"], body.message, session=sess)
    return {
        "agent": a["name"],
        "conversation_id": conv,
        "tools": cached["tools"],
        "reply": result.final_output,
    }


@app.get("/")
async def index():
    return FileResponse(os.path.join(_HERE, "static", "chat.html"))
