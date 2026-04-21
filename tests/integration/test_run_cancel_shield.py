"""Integration test — second cancel during finalizer is absorbed by asyncio.shield().

Models ``test_run_cancel.py``. The additional guarantee checked here:
after ``run_agent`` enters the ``CancelledError`` branch, a *second* cancel
delivered while the shielded finalizer is running does not strand the run
in ``running`` status — the DB update + bus publish inside
``asyncio.shield(_finalize_cancel())`` both complete.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app
from rehketo.runs.registry import get_registry, reset_registry_for_tests

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession


class _NeverStreamingAgent:
    async def astream(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any]:
        await asyncio.sleep(30)
        if False:
            yield  # pragma: no cover


async def _fake_build_agent(run_id: str) -> AsyncIterator[_NeverStreamingAgent]:
    yield _NeverStreamingAgent()


async def test_second_cancel_during_finalizer_still_cancels(
    settings_env: object,
    db_url: str,
    db: object,
    monkeypatch: object,
) -> None:
    db_session: AsyncSession = db  # type: ignore[assignment]
    mp: pytest.MonkeyPatch = monkeypatch  # type: ignore[assignment]

    reset_registry_for_tests()

    import rehketo.agent.run as run_mod

    mp.setattr(run_mod, "build_agent", _fake_build_agent)

    u = User(id=uuid4(), display_name="A", email="a@x")
    db_session.add(u)
    await db_session.commit()
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db_session.add_all([UserRole(user_id=u.id, role="User"), conv])
    await db_session.commit()
    sid = await create_session(
        db_session,
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
            json={"content": "hang please"},
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]

        await asyncio.sleep(0.3)

        # First cancel — HTTP endpoint.
        r2 = await c.post(
            f"/runs/{run_id}/cancel",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
        assert r2.status_code == 204

        # Second cancel — directly through the registry, racing the shielded
        # finalizer. Returns False once the task has finished; True while the
        # task is still settling. Either outcome is acceptable: the invariant
        # under test is that the run still ends in 'cancelled'.
        get_registry().cancel(UUID(run_id))

        await asyncio.sleep(3.0)

        r3 = await c.get(f"/runs/{run_id}", cookies={SESSION_COOKIE: str(sid)})

    assert r3.json()["status"] == "cancelled"
