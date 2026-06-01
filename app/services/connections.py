from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import CATALOG, CONNECTIONS


async def connect(db: AsyncIOMotorDatabase, user_id: str, catalog_id: str) -> dict | None:
    """Teammate connects a catalog server. Idempotent (re-enables if previously off).

    Returns None if the catalog server doesn't exist.
    """
    catalog = await db[CATALOG].find_one({"_id": catalog_id}, {"name": 1, "slug": 1})
    if catalog is None:
        return None

    existing = await db[CONNECTIONS].find_one({"user_id": user_id, "catalog_id": catalog_id})
    if existing is not None:
        await db[CONNECTIONS].update_one({"_id": existing["_id"]}, {"$set": {"enabled": True}})
        existing["enabled"] = True
        existing["catalog"] = catalog
        return existing

    doc = {
        "_id": _new_id(),
        "user_id": user_id,
        "catalog_id": catalog_id,
        "enabled": True,
        "created_at": datetime.now(timezone.utc),
    }
    await db[CONNECTIONS].insert_one(doc)
    doc["catalog"] = catalog
    return doc


def _new_id() -> str:
    import uuid

    return str(uuid.uuid4())


async def list_connections(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    conns = (
        await db[CONNECTIONS]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .to_list(length=None)
    )
    # attach catalog name/slug for display
    for c in conns:
        cat = await db[CATALOG].find_one({"_id": c["catalog_id"]}, {"name": 1, "slug": 1})
        c["catalog"] = cat or {"name": "(deleted)", "slug": "deleted"}
    return conns


async def connected_catalog_ids(db: AsyncIOMotorDatabase, user_id: str) -> set[str]:
    cursor = db[CONNECTIONS].find({"user_id": user_id, "enabled": True}, {"catalog_id": 1})
    return {c["catalog_id"] async for c in cursor}


async def disconnect(db: AsyncIOMotorDatabase, user_id: str, catalog_id: str) -> bool:
    result = await db[CONNECTIONS].delete_one({"user_id": user_id, "catalog_id": catalog_id})
    return result.deleted_count > 0
