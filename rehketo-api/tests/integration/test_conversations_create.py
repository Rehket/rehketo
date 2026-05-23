from __future__ import annotations

from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app


async def _seed_user_and_session(db, *, roles: tuple[str, ...] = ("User",)):
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(u)
    for r in roles:
        db.add(UserRole(user_id=u.id, role=r))
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    return u, sid, issue_csrf_token(str(sid))


async def test_create_conversation_happy(settings_env, db_url, db) -> None:
    u, sid, csrf = await _seed_user_and_session(db)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/conversations",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={},
        )
    assert r.status_code == 201
    body = r.json()
    assert "id" in body and UUID(body["id"])
    row = (await db.execute(select(Conversation))).scalar_one()
    assert row.user_id == u.id
    assert row.title is None


async def test_create_conversation_denied_for_user_without_role(
    settings_env, db_url, db
) -> None:
    _u, sid, csrf = await _seed_user_and_session(db, roles=())
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/conversations",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={},
        )
    assert r.status_code == 403
