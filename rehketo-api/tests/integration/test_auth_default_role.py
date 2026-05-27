from __future__ import annotations

import base64
import json

import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # used in fixture sig

from rehketo.auth.entra import authority
from rehketo.db.models import User, UserRole
from rehketo.main import create_app


def _fake_id_token(
    sub: str = "sub-1", oid: str = "oid-1", email: str = "al@example.com"
) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": sub, "oid": oid, "email": email, "name": "Al"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}."


def _token_response(sub: str = "sub-1", oid: str = "oid-1") -> dict[str, object]:
    return {
        "access_token": "at",
        "refresh_token": "rt",
        "id_token": _fake_id_token(sub=sub, oid=oid),
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.mark.asyncio
@respx.mock
async def test_new_entra_user_receives_default_user_role(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    token_url = f"{authority()}/oauth2/v2.0/token"
    respx.post(token_url).mock(
        return_value=respx.MockResponse(200, json=_token_response())
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

    users = (await db.execute(select(User))).scalars().all()
    assert len(users) == 1
    user_id = users[0].id

    roles = (
        (await db.execute(select(UserRole).where(UserRole.user_id == user_id)))
        .scalars()
        .all()
    )
    assert [r.role for r in roles] == ["User"]


@pytest.mark.asyncio
async def test_returning_user_not_granted_duplicate_role(
    settings_env: pytest.MonkeyPatch, db_url: str, db: AsyncSession
) -> None:
    token_url = f"{authority()}/oauth2/v2.0/token"

    with respx.mock:
        respx.post(token_url).mock(
            return_value=respx.MockResponse(200, json=_token_response())
        )
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            await c.get(
                "/auth/callback",
                params={"code": "abc", "state": "s1"},
                cookies={
                    "rehketo_oauth_state": "s1",
                    "rehketo_oauth_verifier": "v1",
                },
            )

    with respx.mock:
        respx.post(token_url).mock(
            return_value=respx.MockResponse(200, json=_token_response())
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            await c.get(
                "/auth/callback",
                params={"code": "abc2", "state": "s2"},
                cookies={
                    "rehketo_oauth_state": "s2",
                    "rehketo_oauth_verifier": "v1",
                },
            )

    users = (await db.execute(select(User))).scalars().all()
    assert len(users) == 1

    roles = (
        (await db.execute(select(UserRole).where(UserRole.user_id == users[0].id)))
        .scalars()
        .all()
    )
    assert [r.role for r in roles] == ["User"]
