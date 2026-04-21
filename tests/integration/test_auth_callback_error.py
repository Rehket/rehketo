from __future__ import annotations

import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # used in fixture sig

from rehketo.auth.entra import authority
from rehketo.db.models import Session, User
from rehketo.main import create_app


@pytest.mark.asyncio
@respx.mock
async def test_callback_token_exchange_4xx_redirects_with_auth_error(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    token_url = f"{authority()}/oauth2/v2.0/token"
    respx.post(token_url).mock(
        return_value=respx.MockResponse(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "AADSTS70008: expired code",
            },
        )
    )

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        follow_redirects=False,
    ) as c:
        r = await c.get(
            "/auth/callback",
            params={"code": "abc", "state": "s1"},
            cookies={
                "rehketo_oauth_state": "s1",
                "rehketo_oauth_verifier": "v1",
            },
        )

    assert r.status_code == 302
    assert "auth_error=invalid_grant" in r.headers["location"]

    set_cookie = r.headers.get("set-cookie", "")
    assert "rehketo_oauth_state=" in set_cookie
    assert "rehketo_oauth_verifier=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie

    assert "rehketo_session" not in set_cookie
    users = (await db.execute(select(User))).scalars().all()
    assert users == []
    sessions = (await db.execute(select(Session))).scalars().all()
    assert sessions == []


@pytest.mark.asyncio
@respx.mock
async def test_callback_token_exchange_non_json_body_falls_back(
    settings_env: pytest.MonkeyPatch, db_url: str
) -> None:
    token_url = f"{authority()}/oauth2/v2.0/token"
    respx.post(token_url).mock(
        return_value=respx.MockResponse(
            500,
            text="<html>gateway error</html>",
        )
    )

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        follow_redirects=False,
    ) as c:
        r = await c.get(
            "/auth/callback",
            params={"code": "abc", "state": "s1"},
            cookies={
                "rehketo_oauth_state": "s1",
                "rehketo_oauth_verifier": "v1",
            },
        )

    assert r.status_code == 302
    assert "auth_error=token_exchange_failed" in r.headers["location"]
