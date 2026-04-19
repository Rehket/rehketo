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
