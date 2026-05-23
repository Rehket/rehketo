from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore")

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

    # Absolute path to the built SvelteKit static bundle (index.html + assets).
    # When set, FastAPI mounts it at / with SPA fallback. Unset in dev — the
    # UI runs under the Vite dev server on :5173 and proxies /auth, /conversations,
    # /runs, /me, etc. to the backend.
    ui_static_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
