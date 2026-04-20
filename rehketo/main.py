from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

# psycopg3 async cannot use Windows's default ProactorEventLoop. Force the
# SelectorEventLoop policy at import time so uvicorn picks it up when it
# creates the app's loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
    )

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from rehketo.agent.sweep import sweep_abandoned_runs
from rehketo.api.errors import install_error_handlers
from rehketo.auth.csrf_middleware import CSRFMiddleware
from rehketo.config import get_settings
from rehketo.core.logging import get_logger
from rehketo.runs.event_bus import InProcessEventBus
from rehketo.runs.registry import get_registry

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    logger.info("rehketo-api starting app_env=%s", settings.app_env)
    await sweep_abandoned_runs()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rehketo API",
        version="0.1.0",
        lifespan=_lifespan,
        # Stock /docs assumes Bearer auth; we serve a Pattern B-aware replacement
        # from rehketo.api.docs that threads cookies + the CSRF header for us.
        docs_url=None,
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(CSRFMiddleware)

    app.state.event_bus = InProcessEventBus()
    app.state.task_registry = get_registry()

    from rehketo.api import auth_routes
    from rehketo.api import conversations as conversations_api
    from rehketo.api import docs as docs_api
    from rehketo.api import me as me_api
    from rehketo.api import messages as messages_api
    from rehketo.api import runs as runs_api

    app.include_router(auth_routes.router)
    app.include_router(conversations_api.router)
    app.include_router(docs_api.router)
    app.include_router(me_api.router)
    app.include_router(messages_api.router)
    app.include_router(runs_api.router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rehketo.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104  # nosec B104
