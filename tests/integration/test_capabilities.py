from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.sessions import create_session
from rehketo.db.models import User, UserRole
from rehketo.main import create_app


async def test_capabilities_for_user(settings_env, db_url, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add_all([u, UserRole(user_id=u.id, role="User")])
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/me/capabilities", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    caps = set(r.json()["actions"])
    assert "chat.write" in caps
    assert "admin.manage_users" not in caps


async def test_capabilities_for_admin(settings_env, db_url, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add_all([u, UserRole(user_id=u.id, role="Admin")])
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/me/capabilities", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    caps = set(r.json()["actions"])
    assert {"chat.write", "admin.manage_users"}.issubset(caps)
