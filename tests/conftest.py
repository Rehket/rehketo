from __future__ import annotations

import base64
import secrets

import pytest


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Minimal env for building an app that does not touch the DB."""
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/d")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", key)
    monkeypatch.setenv("CSRF_SIGNING_KEY", "x" * 64)
    monkeypatch.setenv("ENTRA_TENANT_ID", "tid")
    monkeypatch.setenv("ENTRA_CLIENT_ID", "cid")
    monkeypatch.setenv("ENTRA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ENTRA_REDIRECT_URI", "http://localhost:8000/auth/callback")
    monkeypatch.setenv("UI_POST_LOGIN_URL", "http://localhost:5173/")
    monkeypatch.setenv("DEVONLY_LOGIN_ENABLED", "true")
    from rehketo.config import get_settings

    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()
