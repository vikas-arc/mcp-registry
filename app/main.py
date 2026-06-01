from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.mcp_server import handle_user_mcp
from app.routers import agents, catalog, connections, gateway

app = FastAPI(title="MCP Registry", version="0.3.0")

# REST API
app.include_router(catalog.router)
app.include_router(connections.router)
app.include_router(gateway.router)
app.include_router(agents.router)

# MCP protocol endpoint: clients connect to /mcp/<user_id>[/<slug>]
app.mount("/mcp", handle_user_mcp)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# Web UI (browse catalog + connect). Served at /ui/
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
