from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.deps import get_current_user
from app.schemas import ToolCallRequest, ToolCallResult, ToolOut
from app.services import gateway as svc

router = APIRouter(prefix="/gateway", tags=["gateway"])


@router.get("/tools", response_model=list[ToolOut])
async def list_all_tools(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    """Aggregated, namespaced tool list across the user's active connections."""
    return await svc.aggregate_tools(db, user_id)


@router.post("/tools/call", response_model=ToolCallResult)
async def call_tool(
    payload: ToolCallRequest,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        return await svc.route_tool_call(db, user_id, payload.namespaced_name, payload.arguments)
    except svc.ToolNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Unknown or inactive tool: {payload.namespaced_name}",
        )
    except Exception as exc:  # noqa: BLE001 — upstream failures become 502s
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Upstream MCP error: {exc}")
