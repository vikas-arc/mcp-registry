from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.deps import get_current_user
from app.schemas import CatalogCreate, CatalogOut, ToolOut
from app.services import catalog as svc
from app.services import connections as conn_svc

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _to_out(catalog: dict, connected_ids: set) -> CatalogOut:
    return CatalogOut(
        id=catalog["_id"],
        name=catalog["name"],
        slug=catalog["slug"],
        description=catalog.get("description"),
        base_url=catalog["base_url"],
        transport=catalog["transport"],
        status=catalog["status"],
        last_error=catalog.get("last_error"),
        last_handshake_at=catalog.get("last_handshake_at"),
        created_at=catalog["created_at"],
        tool_count=len(catalog.get("tools", [])),
        connected=catalog["_id"] in connected_ids,
        forward_auth=catalog.get("forward_auth", False),
    )


def _tools_out(catalog: dict) -> list[ToolOut]:
    return [
        ToolOut(
            name=t["tool_name"],
            namespaced_name=t["namespaced_name"],
            description=t.get("description"),
            input_schema=t.get("input_schema") or {},
        )
        for t in catalog.get("tools", [])
    ]


@router.post("", response_model=CatalogOut, status_code=status.HTTP_201_CREATED)
async def publish_server(payload: CatalogCreate, db=Depends(get_db)):
    """ADMIN: add a custom MCP server to the team catalog."""
    return _to_out(await svc.publish_server(db, payload), set())


@router.get("", response_model=list[CatalogOut])
async def browse_catalog(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Everyone: browse all servers, with a flag for which ones you've connected."""
    connected_ids = await conn_svc.connected_catalog_ids(db, user_id)
    return [_to_out(c, connected_ids) for c in await svc.list_catalog(db)]


async def _load(db, catalog_id: uuid.UUID) -> dict:
    catalog = await svc.get_server(db, str(catalog_id))
    if catalog is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found in catalog")
    return catalog


@router.get("/{catalog_id}/tools", response_model=list[ToolOut])
async def list_server_tools(catalog_id: uuid.UUID, db=Depends(get_db)):
    return _tools_out(await _load(db, catalog_id))


@router.post("/{catalog_id}/refresh", response_model=CatalogOut)
async def refresh_server(catalog_id: uuid.UUID, db=Depends(get_db)):
    """ADMIN: re-handshake a server and refresh its cached tools."""
    catalog = await _load(db, catalog_id)
    return _to_out(await svc.refresh_server(db, catalog), set())


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(catalog_id: uuid.UUID, db=Depends(get_db)):
    """ADMIN: remove a server from the catalog (also drops everyone's connections)."""
    await svc.delete_server(db, await _load(db, catalog_id))
