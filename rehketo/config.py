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


@lru_cache
def get_settings() -> Settings:
    return Settings()
