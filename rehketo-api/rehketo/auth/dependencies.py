from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Response, Security
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)

from rehketo.auth.cookies import SESSION_COOKIE, set_session_cookie
from rehketo.auth.sessions import get_active_session, renew_if_past_halfway
from rehketo.config import get_settings
from rehketo.db import get_session

# APIKeyCookie(...) surfaces the cookie as a security requirement in the
# generated OpenAPI schema, so /docs shows routes as auth-gated and tools
# that consume openapi.json (codegen, Postman, etc.) see the dependency.
# auto_error=False preserves our custom 401 body instead of Starlette's 403.
_session_cookie = APIKeyCookie(
    name=SESSION_COOKIE,
    description="Session cookie set by /auth/login or /auth/devonly/login.",
    auto_error=False,
)


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    session_id: UUID
    identity_provider: str


async def resolve_session(
    db: Annotated[AsyncSession, Depends(get_session)],
    response: Response,
    rehketo_session: Annotated[str | None, Security(_session_cookie)] = None,
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

    # Sliding renewal: past-halfway sessions get a fresh expiry + cookie max_age,
    # so a user who checks in regularly stays logged in across days. Idle
    # sessions still expire at their original expires_at (get_active_session
    # enforces it above).
    settings = get_settings()
    renewed = await renew_if_past_halfway(
        db, row, ttl_minutes=settings.session_ttl_minutes
    )
    if renewed:
        set_session_cookie(
            response,
            str(row.id),
            max_age_seconds=settings.session_ttl_minutes * 60,
        )

    return AuthContext(
        user_id=row.user_id,
        session_id=row.id,
        identity_provider=row.identity_provider,
    )
