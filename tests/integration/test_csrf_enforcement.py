from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from rehketo.main import create_app


async def test_post_without_csrf_is_rejected(settings_env) -> None:
    """Any POST to a non-exempt path with no CSRF cookie/header returns 403."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # /auth/login and /auth/devonly/login are CSRF-exempt (bootstrap).
        # Middleware runs before routing, so 403 from CSRF fires before 404
        # even for nonsense paths.
        r = await c.post("/any-non-exempt-path", json={})
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "forbidden"
    assert "csrf" in body["error"]["message"].lower()
