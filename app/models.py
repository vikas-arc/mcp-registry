"""Shared enums + Mongo collection names. (No ORM — persistence is MongoDB via motor.)

Document shapes (collections in `database`):

  catalog:     { _id, name, slug, description, base_url, transport, status,
                 last_error, last_handshake_at, created_at,
                 tools: [ {tool_name, namespaced_name, description, input_schema} ] }
  connections: { _id, user_id, catalog_id, enabled, created_at }
  agents:      { _id, user_id, name, instructions, selection: [str], model, created_at }
"""
from __future__ import annotations

import enum


class Transport(str, enum.Enum):
    http = "http"   # streamable HTTP
    sse = "sse"     # legacy server-sent events


class CatalogStatus(str, enum.Enum):
    active = "active"   # handshake ok, tools cached
    error = "error"     # last handshake failed


# Collection names
CATALOG = "catalog"
CONNECTIONS = "connections"
AGENTS = "agents"
