from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.deps import get_current_user
from app.schemas import AgentDefCreate, AgentDefOut
from app.services import agents as svc

router = APIRouter(prefix="/me/agents", tags=["my agents"])


def _to_out(doc: dict) -> AgentDefOut:
    return AgentDefOut(
        id=doc["_id"],
        name=doc["name"],
        instructions=doc.get("instructions", ""),
        selection=doc.get("selection", []),
        model=doc.get("model"),
        created_at=doc["created_at"],
    )


@router.post("", response_model=AgentDefOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentDefCreate,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    """Create (or overwrite by name) a saved agent: system prompt + tool selection."""
    return _to_out(await svc.create_agent(db, user_id, payload))


@router.get("", response_model=list[AgentDefOut])
async def list_agents(user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return [_to_out(a) for a in await svc.list_agents(db, user_id)]


@router.get("/{agent_id}", response_model=AgentDefOut)
async def get_agent(
    agent_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    agent = await svc.get_agent(db, user_id, str(agent_id))
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return _to_out(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    user_id: str = Depends(get_current_user),
    db=Depends(get_db),
):
    agent = await svc.get_agent(db, user_id, str(agent_id))
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    await svc.delete_agent(db, agent)
