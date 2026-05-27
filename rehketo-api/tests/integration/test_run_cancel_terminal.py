"""Integration test — POST /runs/{id}/cancel on an already-terminal run
returns 409, not 204. Prevents the UI from silently "succeeding" a cancel
against a run that finished a moment ago."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, Run, User, UserRole
from rehketo.main import create_app

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_terminal_run(db: AsyncSession, status: str) -> tuple[str, str, str]:
    u = User(id=uuid4(), display_name="A", email="a@x")
    db.add(u)
    db.add(UserRole(user_id=u.id, role="User"))
    await db.commit()
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add(conv)
    await db.commit()
    run = Run(
        id=uuid4(),
        conversation_id=conv.id,
        user_id=u.id,
        status=status,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        model="claude-sonnet-4-6",
    )
    db.add(run)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )
    csrf = issue_csrf_token(str(sid))
    return str(run.id), str(sid), csrf


async def test_cancel_succeeded_run_returns_409(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    run_id, sid, csrf = await _seed_terminal_run(db, "succeeded")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/runs/{run_id}/cancel",
            cookies={SESSION_COOKIE: sid, CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
    assert r.status_code == 409
    assert "already succeeded" in r.json()["error"]["message"]


async def test_cancel_failed_run_returns_409(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    run_id, sid, csrf = await _seed_terminal_run(db, "failed")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/runs/{run_id}/cancel",
            cookies={SESSION_COOKIE: sid, CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
    assert r.status_code == 409


async def test_cancel_already_cancelled_run_returns_409(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    run_id, sid, csrf = await _seed_terminal_run(db, "cancelled")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/runs/{run_id}/cancel",
            cookies={SESSION_COOKIE: sid, CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
    assert r.status_code == 409
