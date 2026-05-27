"""Regression test: when a sliding session renewal fires, the CSRF cookie
must be reissued alongside the session cookie.

Today `rehketo/auth/dependencies.py:resolve_session` calls `set_session_cookie`
when `renew_if_past_halfway` returns True, but DOES NOT call
`set_csrf_cookie`. The CSRF token VALUE remains valid (signed with the
unchanged session_id), but the browser-side cookie keeps its original
`max_age` — so the browser may drop the CSRF cookie while the session
itself is still fresh. The next POST then has the session cookie but no
CSRF cookie, fails the double-submit check, and 403s.

This test is marked `xfail(strict=True)` so:
- CI stays green while the bug is documented in code.
- When someone fixes `resolve_session` to also reissue the CSRF cookie,
  the test will turn from xfail to xpassed → strict makes that a failure,
  prompting the fixer to remove the marker.

Fix is one line in `rehketo/auth/dependencies.py:60-64`: also call
`set_csrf_cookie(response, issue_csrf_token(str(row.id)), max_age_seconds=...)`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  # fixture annotation

from rehketo.auth.cookies import CSRF_COOKIE, SESSION_COOKIE
from rehketo.db.models import Session as SessionRow
from rehketo.main import create_app
from tests.integration._helpers import seed_user_and_conv


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CSRF cookie not reissued on sliding session renewal — see plan's "
        "'Discovered during planning' section. Fix in resolve_session() to "
        "also call set_csrf_cookie when renew_if_past_halfway returns True."
    ),
)
@pytest.mark.asyncio
async def test_csrf_cookie_reissued_on_sliding_renewal(
    settings_env: pytest.MonkeyPatch,
    db_url: str,
    db: AsyncSession,
) -> None:
    # 60-min TTL — easy to push past halfway via direct DB update.
    _user, _conv, sid, csrf = await seed_user_and_conv(db, ttl_minutes=60)

    # Backdate the session so elapsed > ttl/2 → renewal will fire on the
    # next authenticated request.
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == sid)
        .values(created_at=datetime.now(UTC) - timedelta(minutes=31))
    )
    await db.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # /me is an authenticated GET; it goes through resolve_session →
        # renew_if_past_halfway. The response should set BOTH cookies if the
        # bug is fixed.
        r = await c.get(
            "/me",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
        )
        assert r.status_code == 200, r.text

    # httpx exposes multi-valued headers via Headers.get_list (case-insensitive).
    set_cookies = r.headers.get_list("set-cookie", split_commas=False)
    session_set = any(c.startswith(SESSION_COOKIE + "=") for c in set_cookies)
    csrf_set = any(c.startswith(CSRF_COOKIE + "=") for c in set_cookies)

    assert session_set, (
        f"renewal should have reissued the session cookie; set-cookie={set_cookies}"
    )
    assert csrf_set, (
        f"renewal should ALSO reissue the CSRF cookie (bug); set-cookie={set_cookies}"
    )
