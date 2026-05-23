from __future__ import annotations

from uuid import uuid4

from rehketo.auth import sessions
from rehketo.db.models import User


async def test_create_and_lookup_session(settings_env, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(u)
    await db.commit()

    sid = await sessions.create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt-123",
        ttl_minutes=60,
    )
    assert sid is not None

    loaded = await sessions.get_active_session(db, sid)
    assert loaded is not None
    assert loaded.user_id == u.id
    assert loaded.revoked_at is None


async def test_revoke_session(settings_env, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(u)
    await db.commit()

    sid = await sessions.create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    await sessions.revoke_session(db, sid)
    loaded = await sessions.get_active_session(db, sid)
    assert loaded is None


async def test_expired_session_not_active(settings_env, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(u)
    await db.commit()

    sid = await sessions.create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=-1,  # already expired
    )
    loaded = await sessions.get_active_session(db, sid)
    assert loaded is None
