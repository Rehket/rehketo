from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from rehketo.api.errors import install_error_handlers
from rehketo.auth.cookies import SESSION_COOKIE
from rehketo.auth.dependencies import AuthContext, resolve_session
from rehketo.auth.sessions import create_session
from rehketo.db.models import User


def _mini_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/whoami")
    async def whoami(
        ctx: Annotated[AuthContext, Depends(resolve_session)],
    ) -> dict[str, str]:
        return {"user_id": str(ctx.user_id)}

    return app


async def test_resolve_session_happy_path(settings_env, db_url, db) -> None:
    u = User(id=uuid4(), display_name="Al", email="al@example.com")
    db.add(u)
    await db.commit()
    sid = await create_session(
        db,
        user_id=u.id,
        identity_provider="entra",
        refresh_token="rt",
        ttl_minutes=60,
    )

    app = _mini_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/whoami", cookies={SESSION_COOKIE: str(sid)})
    assert r.status_code == 200
    assert r.json() == {"user_id": str(u.id)}


async def test_resolve_session_missing_cookie(settings_env, db_url) -> None:
    app = _mini_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/whoami")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


async def test_resolve_session_invalid_cookie(settings_env, db_url) -> None:
    app = _mini_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/whoami", cookies={SESSION_COOKIE: str(uuid4())})
    assert r.status_code == 401
