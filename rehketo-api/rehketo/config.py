import os
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = Field(default="dev")
    database_url: str

    session_encryption_key: SecretStr
    csrf_signing_key: SecretStr
    session_ttl_minutes: int = 10080
    cookie_secure: bool = False
    cookie_domain: str | None = None

    entra_tenant_id: str
    entra_client_id: str
    entra_client_secret: SecretStr
    entra_redirect_uri: str
    ui_post_login_url: str

    devonly_login_enabled: bool = False

    bifrost_base_url: str = "http://localhost:8088/v1"
    bifrost_api_key: SecretStr = SecretStr("dev-noop")
    agent_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_ui_static_dir() -> str | None:
    """Direct env read, deliberately bypassing Settings(). The UI mount runs
    inside create_app() at import time; instantiating Settings there would
    require all 8 production secrets and break test collection plus
    tools/check_contract.py. UI_STATIC_DIR is a deployment knob (set in
    deploy/docker-compose.yaml, unset in dev), not application config."""
    return os.environ.get("UI_STATIC_DIR")
