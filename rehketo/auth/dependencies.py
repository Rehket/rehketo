from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.sessions import get_active_session
from rehketo.db import get_session


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    session_id: UUID
    identity_provider: str


async def resolve_session(
    db: Annotated[AsyncSession, Depends(get_session)],
    rehketo_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthContext:
    if not rehketo_session:
        raise HTTPException(status_code=401, detail="missing session")
    try:
        session_uuid = UUID(rehketo_session)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid session") from exc
    row = await get_active_session(db, session_uuid)
    if row is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return AuthContext(
        user_id=row.user_id,
        session_id=row.id,
        identity_provider=row.identity_provider,
    )
