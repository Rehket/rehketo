from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select, update

from rehketo.auth.crypto import encrypt_token
from rehketo.db.models import Session as SessionRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_session(
    db: AsyncSession,
    *,
    user_id: UUID,
    identity_provider: str,
    refresh_token: str,
    ttl_minutes: int,
) -> UUID:
    now = datetime.now(UTC)
    row = SessionRow(
        id=uuid4(),
        user_id=user_id,
        identity_provider=identity_provider,
        refresh_token_ct=encrypt_token(refresh_token),
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    db.add(row)
    await db.commit()
    return row.id


async def get_active_session(
    db: AsyncSession, session_id: UUID | str
) -> SessionRow | None:
    now = datetime.now(UTC)
    stmt = select(SessionRow).where(
        SessionRow.id == session_id,
        SessionRow.expires_at > now,
        SessionRow.revoked_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, session_id: UUID | str) -> None:
    now = datetime.now(UTC)
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == session_id)
        .values(revoked_at=now)
    )
    await db.commit()


async def renew_if_past_halfway(
    db: AsyncSession, session: SessionRow, *, ttl_minutes: int
) -> bool:
    """Sliding-window renewal: if more than half the original TTL has elapsed
    since session creation, push expires_at out to now + ttl_minutes and
    commit. Returns True when a renewal happened (so the caller can re-issue
    the cookie's max_age), False otherwise.

    Keeps actively-using users logged in across days without giving an
    attacker an unbounded sliding window — idle sessions still expire at
    their original expires_at.
    """
    if session.created_at is None:
        return False
    now = datetime.now(UTC)
    original_ttl = session.expires_at - session.created_at
    if original_ttl.total_seconds() <= 0:
        return False
    elapsed = now - session.created_at
    if elapsed * 2 <= original_ttl:
        return False
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == session.id)
        .values(expires_at=now + timedelta(minutes=ttl_minutes))
    )
    await db.commit()
    return True
