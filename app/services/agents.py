from __future__ import annotations

import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import AGENTS
from app.schemas import AgentDefCreate


async def create_agent(
    db: AsyncIOMotorDatabase, user_id: str, payload: AgentDefCreate
) -> dict:
    """Create or overwrite (by name) a saved agent for the user."""
    existing = await db[AGENTS].find_one({"user_id": user_id, "name": payload.name})
    if existing is not None:
        update = {
            "instructions": payload.instructions,
            "selection": payload.selection,
            "model": payload.model,
        }
        await db[AGENTS].update_one({"_id": existing["_id"]}, {"$set": update})
        existing.update(update)
        return existing

    doc = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": payload.name,
        "instructions": payload.instructions,
        "selection": payload.selection,
        "model": payload.model,
        "created_at": datetime.now(timezone.utc),
    }
    await db[AGENTS].insert_one(doc)
    return doc


async def list_agents(db: AsyncIOMotorDatabase, user_id: str) -> list[dict]:
    return (
        await db[AGENTS]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .to_list(length=None)
    )


async def get_agent(db: AsyncIOMotorDatabase, user_id: str, agent_id: str) -> dict | None:
    return await db[AGENTS].find_one({"_id": agent_id, "user_id": user_id})


async def delete_agent(db: AsyncIOMotorDatabase, agent: dict) -> None:
    await db[AGENTS].delete_one({"_id": agent["_id"]})
