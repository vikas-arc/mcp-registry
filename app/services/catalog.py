from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.mcp import client as mcp_client
from app.models import CATALOG, CONNECTIONS, CatalogStatus, Transport
from app.schemas import CatalogCreate
from app.security.ssrf import validate_outbound_url

_slug_re = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    slug = _slug_re.sub("_", name.lower()).strip("_")
    return slug[:64] or "server"


def _tool_docs(slug: str, tools: list[mcp_client.DiscoveredTool]) -> list[dict]:
    return [
        {
            "tool_name": t.name,
            "namespaced_name": f"{slug}__{t.name}",
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]


async def publish_server(db: AsyncIOMotorDatabase, payload: CatalogCreate) -> dict:
    """Admin adds a custom server: SSRF-check, handshake, embed its tools, insert."""
    base_url = str(payload.base_url)
    validate_outbound_url(base_url)
    slug = _slugify(payload.name)

    doc: dict = {
        "_id": str(uuid.uuid4()),
        "name": payload.name,
        "slug": slug,
        "description": payload.description,
        "base_url": base_url,
        "transport": payload.transport.value,
        "forward_auth": payload.forward_auth,
        "status": CatalogStatus.error.value,
        "last_error": None,
        "last_handshake_at": None,
        "created_at": datetime.now(timezone.utc),
        "tools": [],
    }
    try:
        tools = await mcp_client.handshake_and_list_tools(base_url, payload.transport, {})
        doc["status"] = CatalogStatus.active.value
        doc["last_handshake_at"] = datetime.now(timezone.utc)
        doc["tools"] = _tool_docs(slug, tools)
    except Exception as exc:  # noqa: BLE001 — surface upstream failure to the admin
        doc["last_error"] = str(exc)

    await db[CATALOG].insert_one(doc)
    return doc


async def refresh_server(db: AsyncIOMotorDatabase, catalog: dict) -> dict:
    try:
        tools = await mcp_client.handshake_and_list_tools(
            catalog["base_url"], Transport(catalog["transport"]), {}
        )
        update = {
            "status": CatalogStatus.active.value,
            "last_error": None,
            "last_handshake_at": datetime.now(timezone.utc),
            "tools": _tool_docs(catalog["slug"], tools),
        }
    except Exception as exc:  # noqa: BLE001
        update = {"status": CatalogStatus.error.value, "last_error": str(exc)}

    await db[CATALOG].update_one({"_id": catalog["_id"]}, {"$set": update})
    catalog.update(update)
    return catalog


async def list_catalog(db: AsyncIOMotorDatabase) -> list[dict]:
    return await db[CATALOG].find().sort("name", 1).to_list(length=None)


async def get_server(db: AsyncIOMotorDatabase, catalog_id: str) -> dict | None:
    return await db[CATALOG].find_one({"_id": catalog_id})


async def delete_server(db: AsyncIOMotorDatabase, catalog: dict) -> None:
    await db[CATALOG].delete_one({"_id": catalog["_id"]})
    # cascade: drop everyone's connections to this server
    await db[CONNECTIONS].delete_many({"catalog_id": catalog["_id"]})
