from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
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


async def test_rename_moves_conversation_to_top(settings_env, db_url, db) -> None:
    """Rename bumps conversation.updated_at so the sidebar re-orders."""
    alice = User(id=uuid4(), display_name="A", email="a@x")
    db.add_all([alice, UserRole(user_id=alice.id, role="User")])
    await db.commit()
    older_id = uuid4()
    newer_id = uuid4()
    now = datetime.now(UTC)
    db.add(
        Conversation(
            id=older_id,
            user_id=alice.id,
            title="older",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
    )
    db.add(
        Conversation(
            id=newer_id,
            user_id=alice.id,
            title="newer",
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
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
    csrf = issue_csrf_token(str(sid))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r0 = await c.get("/conversations", cookies={SESSION_COOKIE: str(sid)})
        assert [item["title"] for item in r0.json()["items"]] == ["newer", "older"]

        r1 = await c.patch(
            f"/conversations/{older_id}",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"title": "older (renamed)"},
        )
        assert r1.status_code == 200

        r2 = await c.get("/conversations", cookies={SESSION_COOKIE: str(sid)})
        assert [item["title"] for item in r2.json()["items"]] == [
            "older (renamed)",
            "newer",
        ]


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
