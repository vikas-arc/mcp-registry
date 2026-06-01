from __future__ import annotations

from fastapi import Header, HTTPException, status


async def get_current_user(x_user_id: str | None = Header(default=None)) -> str:
    """Resolve the calling user.

    STUB: trusts an `X-User-Id` header so the registry is runnable out of the box.
    Replace with real auth (verify your platform's JWT / session and return the
    subject) before exposing this service.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id (replace this stub with real auth)",
        )
    return x_user_id
