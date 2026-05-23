"""Integration test — UI_STATIC_DIR mount serves the built bundle with SPA
fallback, and API routes still take precedence over the catch-all."""
from __future__ import annotations

from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from rehketo.main import create_app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


async def _write_fake_bundle(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text("<html><body>INDEX</body></html>")
    (root / "favicon.png").write_bytes(b"\x89PNG fake")
    assets = root / "_app" / "immutable"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "main-abc.js").write_text("console.log('bundle');")


async def test_mount_serves_index_root_and_unknown_paths(
    settings_env: pytest.MonkeyPatch,
    db_url: str,
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "ui-build"
    await _write_fake_bundle(bundle)
    settings_env.setenv("UI_STATIC_DIR", str(bundle))
    from rehketo.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r_root = await c.get("/")
        assert r_root.status_code == 200
        assert "INDEX" in r_root.text

        # Unknown client-side route falls back to index.html.
        r_spa = await c.get("/c/not-a-uuid-but-whatever")
        assert r_spa.status_code == 200
        assert "INDEX" in r_spa.text

        # Real asset served directly.
        r_asset = await c.get("/_app/immutable/main-abc.js")
        assert r_asset.status_code == 200
        assert "console.log" in r_asset.text

        r_fav = await c.get("/favicon.png")
        assert r_fav.status_code == 200


async def test_api_routes_win_over_catchall(
    settings_env: pytest.MonkeyPatch,
    db_url: str,
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "ui-build"
    await _write_fake_bundle(bundle)
    settings_env.setenv("UI_STATIC_DIR", str(bundle))
    from rehketo.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        # /healthz is an API route; must return JSON, not index.html.
        r = await c.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

        # /me is auth-gated; without a session it 401s — still wins over catchall.
        r = await c.get("/me")
        assert r.status_code == 401


async def test_mount_is_noop_when_env_unset(
    settings_env: pytest.MonkeyPatch, db_url: str
) -> None:
    """With UI_STATIC_DIR unset, a GET to an unknown path 404s rather than
    serving some fallback HTML — the dev contract."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/not-a-route-at-all")
    assert r.status_code == 404
