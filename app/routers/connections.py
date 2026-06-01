from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.deps import get_current_user
from app.schemas import ConnectRequest, ConnectionOut
from app.services import connections as svc

router = APIRouter(prefix="/me/connections", tags=["my connections"])


def _to_out(conn: dict) -> ConnectionOut:
    cat = conn.get("catalog") or {}
    return ConnectionOut(
        id=conn["_id"],
        catalog_id=conn["catalog_id"],
        name=cat.get("name", "(deleted)"),
        slug=cat.get("slug", "deleted"),
        enabled=conn["enabled"],
        created_at=conn["created_at"],
    )


@router.post("", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def connect(
    payload: ConnectRequest,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    """Teammate connects a catalog server to their personal set."""
    conn = await svc.connect(db, user_id, str(payload.catalog_id))
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found in catalog")
    return _to_out(conn)


@router.get("", response_model=list[ConnectionOut])
async def my_connections(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return [_to_out(c) for c in await svc.list_connections(db, user_id)]


@router.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    catalog_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    if not await svc.disconnect(db, user_id, str(catalog_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not connected")
