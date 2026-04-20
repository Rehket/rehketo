from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app


async def test_list_returns_only_user_own(settings_env, db_url, db) -> None:
    alice = User(id=uuid4(), display_name="A", email="a@x")
    bob = User(id=uuid4(), display_name="B", email="b@x")
    db.add_all([alice, bob, UserRole(user_id=alice.id, role="User")])
    await db.commit()
    db.add(Conversation(id=uuid4(), user_id=alice.id, title="t1"))
    db.add(Conversation(id=uuid4(), user_id=alice.id, title="t2"))
    db.add(Conversation(id=uuid4(), user_id=bob.id, title="t3"))
    await db.commit()

    sid = await create_session(
        db,
        user_id=alice.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/conversations", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    titles = {item["title"] for item in r.json()["items"]}
    assert titles == {"t1", "t2"}


async def test_list_excludes_archived_by_default(settings_env, db_url, db) -> None:
    alice = User(id=uuid4(), display_name="A", email="a@x")
    db.add_all([alice, UserRole(user_id=alice.id, role="User")])
    await db.commit()
    db.add(Conversation(id=uuid4(), user_id=alice.id, title="live"))
    db.add(
        Conversation(
            id=uuid4(),
            user_id=alice.id,
            title="archived",
            archived_at=datetime.now(UTC),
        )
    )
    await db.commit()
    sid = await create_session(
        db,
        user_id=alice.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/conversations", cookies={SESSION_COOKIE: str(sid)})
    titles = {item["title"] for item in r.json()["items"]}
    assert titles == {"live"}
