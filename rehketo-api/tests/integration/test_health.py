from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from rehketo.main import create_app

if TYPE_CHECKING:
    import pytest


async def test_health_endpoint(settings_env: pytest.MonkeyPatch) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_error_envelope_on_404(settings_env: pytest.MonkeyPatch) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/no-such-route")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
