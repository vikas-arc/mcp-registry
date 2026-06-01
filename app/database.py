from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_settings = get_settings()

client: AsyncIOMotorClient = AsyncIOMotorClient(_settings.mongo_url)
database: AsyncIOMotorDatabase = client[_settings.mongo_db]


async def get_db() -> AsyncIOMotorDatabase:
    return database
