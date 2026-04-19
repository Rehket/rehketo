import base64
import secrets

from rehketo.config import Settings


def test_settings_load_from_env(monkeypatch):
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/d")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", key)
    monkeypatch.setenv("CSRF_SIGNING_KEY", "x" * 64)
    monkeypatch.setenv("ENTRA_TENANT_ID", "tid")
    monkeypatch.setenv("ENTRA_CLIENT_ID", "cid")
    monkeypatch.setenv("ENTRA_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ENTRA_REDIRECT_URI", "http://localhost:8000/auth/callback")
    monkeypatch.setenv("UI_POST_LOGIN_URL", "http://localhost:5173/")

    s = Settings()

    assert s.app_env == "test"
    assert s.cookie_secure is False
    assert s.devonly_login_enabled is False
    assert s.session_ttl_minutes == 10080
