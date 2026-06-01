from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.models import CatalogStatus, Transport


# ---------- catalog (admin) ----------

class CatalogCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_url: HttpUrl
    transport: Transport = Transport.http
    description: str | None = None
    # If true, forward the caller's Authorization header to this upstream server
    # (BYOT pass-through, e.g. the Atlassian write-server). Default: never forward.
    forward_auth: bool = False


class ToolOut(BaseModel):
    name: str
    namespaced_name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)


class CatalogOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    base_url: str
    transport: Transport
    status: CatalogStatus
    last_error: str | None = None
    last_handshake_at: datetime | None = None
    created_at: datetime
    tool_count: int = 0
    connected: bool = False  # has the current teammate connected this one?
    forward_auth: bool = False

    model_config = {"from_attributes": True}


# ---------- connections (teammate) ----------

class ConnectRequest(BaseModel):
    catalog_id: uuid.UUID


class ConnectionOut(BaseModel):
    id: uuid.UUID
    catalog_id: uuid.UUID
    name: str           # mirrored from the catalog server for convenience
    slug: str
    enabled: bool
    created_at: datetime


# ---------- gateway (REST) ----------

class ToolCallRequest(BaseModel):
    namespaced_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    is_error: bool = False
    content: list[dict[str, Any]] = Field(default_factory=list)


# ---------- saved agents ----------

class AgentDefCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    selection: list[str] = Field(default_factory=list)  # slugs / namespaced tools / ["all"]
    model: str | None = None


class AgentDefOut(BaseModel):
    id: uuid.UUID
    name: str
    instructions: str
    selection: list[str]
    model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
