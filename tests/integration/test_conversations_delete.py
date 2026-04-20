from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app


async def test_soft_delete(settings_env, db_url, db) -> None:
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add_all([u, UserRole(user_id=u.id, role="User")])
    await db.commit()
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add(conv)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    csrf = issue_csrf_token(str(sid))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.delete(
            f"/conversations/{conv.id}",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
    assert r.status_code == 204

    # Still exists (soft-delete) but is archived
    row = (
        await db.execute(select(Conversation).where(Conversation.id == conv.id))
    ).scalar_one()
    assert row.archived_at is not None

    # Not returned by default list
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/conversations", cookies={SESSION_COOKIE: str(sid)})
    assert r.json()["items"] == []
