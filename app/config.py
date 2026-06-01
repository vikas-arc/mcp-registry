from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB connection
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "mcp_registry"

    # Fernet key for envelope-encrypting per-user MCP credentials at rest.
    # Only needed once per-user auth/credentials are added; unused in the
    # current no-auth catalog model, so optional for now.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    master_encryption_key: str | None = None

    # SSRF controls. Keep private networks OFF in production — users supply URLs.
    allow_private_networks: bool = False

    # Timeouts (seconds) for talking to upstream MCP servers.
    upstream_connect_timeout: float = 10.0
    upstream_call_timeout: float = 60.0

    # Cap on a single tool-call response payload returned to callers (bytes).
    max_tool_response_bytes: int = 1_000_000

    # Create tables on startup instead of running Alembic (dev convenience only).
    auto_create_tables: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
