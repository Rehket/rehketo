from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from rehketo.api.errors import install_error_handlers
from rehketo.config import get_settings
from rehketo.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    logger.info("rehketo-api starting app_env=%s", settings.app_env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Rehketo API", version="0.1.0", lifespan=_lifespan)
    install_error_handlers(app)

    from rehketo.api import auth_routes

    app.include_router(auth_routes.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rehketo.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104  # nosec B104
