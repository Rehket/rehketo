from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, Message, Run, User, UserRole
from rehketo.main import create_app


@respx.mock
async def test_posting_a_message_creates_row_and_kicks_off_run(
    settings_env, db_url, db
) -> None:
    # Mock Bifrost so the agent request resolves immediately with an empty stream
    respx.post("http://bifrost-mock/v1/responses").mock(
        return_value=Response(200, json={"output": [{"content": [{"text": "hi"}]}]})
    )

    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add(u)
    await db.flush()
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add_all([UserRole(user_id=u.id, role="User"), conv])
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
        r = await c.post(
            f"/conversations/{conv.id}/messages",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"content": "hello"},
        )
    assert r.status_code == 202
    body = r.json()
    assert UUID(body["message_id"])
    assert UUID(body["run_id"])

    # Give the background task a moment to transition the run
    await asyncio.sleep(0.2)

    # User message was persisted
    msgs = (
        await db.execute(select(Message).where(Message.conversation_id == conv.id))
    ).scalars().all()
    assert any(m.role == "user" and m.content.get("text") == "hello" for m in msgs)

    # Run row exists
    runs = (
        await db.execute(select(Run).where(Run.conversation_id == conv.id))
    ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status in ("queued", "running", "succeeded", "failed")
