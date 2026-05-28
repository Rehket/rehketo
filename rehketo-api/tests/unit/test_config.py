import base64
import secrets

from rehketo.config import Settings


def _base_env(monkeypatch) -> None:
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


def test_settings_load_from_env(monkeypatch):
    _base_env(monkeypatch)

    # _env_file=None bypasses the .env file declared on SettingsConfigDict so
    # the test exercises only the env-var path. Without this, a developer's
    # local rehketo-api/.env (with values like DEVONLY_LOGIN_ENABLED=true)
    # bleeds into the default-value assertions below.
    s = Settings(_env_file=None)

    assert s.app_env == "test"
    assert s.cookie_secure is False
    assert s.devonly_login_enabled is False
    assert s.session_ttl_minutes == 10080


def test_agent_settings_load_from_env(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("BIFROST_BASE_URL", "http://bifrost-mock/v1")
    monkeypatch.setenv("BIFROST_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4-6")

    s = Settings(_env_file=None)

    assert s.bifrost_base_url == "http://bifrost-mock/v1"
    assert s.bifrost_api_key.get_secret_value() == "test-key"
    assert s.agent_model == "claude-sonnet-4-6"
