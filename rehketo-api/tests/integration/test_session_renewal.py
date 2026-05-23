"""Integration test — sessions renew when past the halfway point on their TTL.

Actively-using users stay logged in across days without an unbounded sliding
window. Idle sessions still expire at their original expires_at.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.sessions import create_session
from rehketo.db.models import Session as SessionRow
from rehketo.db.models import User, UserRole
from rehketo.main import create_app

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed(db: AsyncSession) -> tuple[User, str]:
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add(u)
    db.add(UserRole(user_id=u.id, role="User"))
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,  # 1-hour session TTL for fast test arithmetic
    )
    return u, str(sid)


async def test_session_past_halfway_renews_expires_at(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    settings_env.setenv("SESSION_TTL_MINUTES", "60")
    from rehketo.config import get_settings

    get_settings.cache_clear()

    _u, sid = await _seed(db)

    # Move session creation_time back so it's ~40 minutes old (past halfway
    # on a 60-minute TTL) and expires_at to match.
    old_created = datetime.now(UTC) - timedelta(minutes=40)
    old_expires = old_created + timedelta(minutes=60)
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == UUID(sid))
        .values(created_at=old_created, expires_at=old_expires)
    )
    await db.commit()

    original = (
        await db.execute(select(SessionRow).where(SessionRow.id == UUID(sid)))
    ).scalar_one()
    old_expires_persisted = original.expires_at

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/me", cookies={SESSION_COOKIE: sid})
    assert r.status_code == 200

    # Cookie should have been re-issued with a fresh max_age.
    set_cookie = r.headers.get("set-cookie", "")
    assert SESSION_COOKIE in set_cookie
    assert "Max-Age=3600" in set_cookie or "max-age=3600" in set_cookie

    # DB expires_at moved forward to approximately now + 60m. Expire the
    # test session's identity map so the re-fetch returns the updated row,
    # not the cached pre-update snapshot.
    db.expire_all()
    refreshed = (
        await db.execute(select(SessionRow).where(SessionRow.id == UUID(sid)))
    ).scalar_one()
    assert refreshed.expires_at > old_expires_persisted
    expected_expiry = datetime.now(UTC) + timedelta(minutes=60)
    assert abs((refreshed.expires_at - expected_expiry).total_seconds()) < 30


async def test_session_before_halfway_does_not_renew(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    settings_env.setenv("SESSION_TTL_MINUTES", "60")
    from rehketo.config import get_settings

    get_settings.cache_clear()

    _u, sid = await _seed(db)

    # Only 10 minutes old (well before halfway on a 60-minute TTL).
    created = datetime.now(UTC) - timedelta(minutes=10)
    expires = created + timedelta(minutes=60)
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == UUID(sid))
        .values(created_at=created, expires_at=expires)
    )
    await db.commit()

    original_expires = (
        await db.execute(select(SessionRow).where(SessionRow.id == UUID(sid)))
    ).scalar_one().expires_at

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/me", cookies={SESSION_COOKIE: sid})
    assert r.status_code == 200

    # No renewal: cookie is NOT re-issued and expires_at is unchanged.
    set_cookie = r.headers.get("set-cookie", "")
    assert SESSION_COOKIE not in set_cookie

    refreshed_expires = (
        await db.execute(select(SessionRow).where(SessionRow.id == UUID(sid)))
    ).scalar_one().expires_at
    assert refreshed_expires == original_expires
