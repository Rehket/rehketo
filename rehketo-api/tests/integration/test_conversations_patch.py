from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app


async def _seed(db):
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add_all([u, UserRole(user_id=u.id, role="User")])
    await db.commit()
    conv = Conversation(id=uuid4(), user_id=u.id, title="old")
    db.add(conv)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    return conv, sid, issue_csrf_token(str(sid))


async def test_rename(settings_env, db_url, db) -> None:
    conv, sid, csrf = await _seed(db)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.patch(
            f"/conversations/{conv.id}",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"title": "new"},
        )
    assert r.status_code == 200
    # Re-query via a fresh session — the handler committed in its own
    # AsyncSession, and our test session's identity map would otherwise
    # return the cached pre-update instance.
    fresh_engine = create_async_engine(db_url, future=True)
    fresh_maker = async_sessionmaker(fresh_engine, expire_on_commit=False)
    async with fresh_maker() as fresh:
        row = (
            await fresh.execute(
                select(Conversation).where(Conversation.id == conv.id)
            )
        ).scalar_one()
    await fresh_engine.dispose()
    assert row.title == "new"


async def test_archive(settings_env, db_url, db) -> None:
    conv, sid, csrf = await _seed(db)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.patch(
            f"/conversations/{conv.id}",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"archived": True},
        )
    assert r.status_code == 200
    # Re-query via a fresh session — the handler committed in its own
    # AsyncSession, and our test session's identity map would otherwise
    # return the cached pre-update instance.
    fresh_engine = create_async_engine(db_url, future=True)
    fresh_maker = async_sessionmaker(fresh_engine, expire_on_commit=False)
    async with fresh_maker() as fresh:
        row = (
            await fresh.execute(
                select(Conversation).where(Conversation.id == conv.id)
            )
        ).scalar_one()
    await fresh_engine.dispose()
    assert row.archived_at is not None
