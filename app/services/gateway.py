from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.mcp import client as mcp_client
from app.models import CATALOG, CONNECTIONS, CatalogStatus, Transport
from app.schemas import ToolCallResult, ToolOut
from app.services.connections import connected_catalog_ids


class ToolNotFoundError(LookupError):
    pass


def _tool_out(catalog: dict) -> list[ToolOut]:
    return [
        ToolOut(
            name=t["tool_name"],
            namespaced_name=t["namespaced_name"],
            description=t.get("description"),
            input_schema=t.get("input_schema") or {},
        )
        for t in catalog.get("tools", [])
    ]


async def _call(
    catalog: dict, tool_name: str, arguments: dict, auth: str | None = None
) -> ToolCallResult:
    # Pass the caller's token through ONLY to servers flagged forward_auth (BYOT).
    headers = {"Authorization": auth} if (catalog.get("forward_auth") and auth) else {}
    is_error, content = await mcp_client.call_tool(
        catalog["base_url"], Transport(catalog["transport"]), headers, tool_name, arguments
    )
    return ToolCallResult(is_error=is_error, content=content)


# ---------- aggregate: all servers a user connected ----------

async def _active_connected(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    ids = await connected_catalog_ids(db, user_id)
    if not ids:
        return []
    return await db[CATALOG].find(
        {"_id": {"$in": list(ids)}, "status": CatalogStatus.active.value}
    ).to_list(length=None)


async def aggregate_tools(db: AsyncIOMotorDatabase, user_id: str) -> list[ToolOut]:
    tools: list[ToolOut] = []
    for cat in await _active_connected(db, user_id):
        tools.extend(_tool_out(cat))
    tools.sort(key=lambda t: t.namespaced_name)
    return tools


async def route_tool_call(
    db: AsyncIOMotorDatabase,
    user_id: str,
    namespaced_name: str,
    arguments: dict,
    auth: str | None = None,
) -> ToolCallResult:
    for cat in await _active_connected(db, user_id):
        for t in cat.get("tools", []):
            if t["namespaced_name"] == namespaced_name:
                return await _call(cat, t["tool_name"], arguments, auth)
    raise ToolNotFoundError(namespaced_name)


# ---------- single server by slug ----------

async def _active_server(db: AsyncIOMotorDatabase, slug: str) -> dict | None:
    return await db[CATALOG].find_one({"slug": slug, "status": CatalogStatus.active.value})


async def server_tools(db: AsyncIOMotorDatabase, slug: str) -> list[ToolOut]:
    cat = await _active_server(db, slug)
    return _tool_out(cat) if cat else []


async def route_server_tool_call(
    db: AsyncIOMotorDatabase,
    slug: str,
    namespaced_name: str,
    arguments: dict,
    auth: str | None = None,
) -> ToolCallResult:
    cat = await _active_server(db, slug)
    if cat:
        for t in cat.get("tools", []):
            if t["namespaced_name"] == namespaced_name:
                return await _call(cat, t["tool_name"], arguments, auth)
    raise ToolNotFoundError(namespaced_name)
