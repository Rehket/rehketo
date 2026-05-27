"""Session-scoped uvicorn-in-thread fixture for the fake Bifrost.

Uvicorn runs on its own asyncio loop inside a daemon thread. We share
no in-process state with the api server — only HTTP requests, just like
production. Clean shutdown via `server.should_exit = True`.
"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import uvicorn

from tests.e2e.fake_bifrost import make_app
from tests.e2e.fixtures.ports import free_port

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class BifrostHandle:
    """Handle to the running fake Bifrost: port + ready-to-use base_url."""

    port: int
    base_url: str  # http://127.0.0.1:<port>/v1


def _wait_http_200(url: str, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_err: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:  # noqa: S310 -- hardcoded 127.0.0.1 test health endpoint
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError) as exc:
            last_err = exc
        time.sleep(0.1)
    raise TimeoutError(
        f"{url} did not return 200 within {timeout_s}s; last={last_err!r}"
    )


@pytest.fixture(scope="session")
def fake_bifrost() -> Iterator[BifrostHandle]:
    port = free_port()
    config = uvicorn.Config(
        make_app(),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="fake-bifrost")
    thread.start()
    try:
        _wait_http_200(f"http://127.0.0.1:{port}/healthz")
        yield BifrostHandle(port=port, base_url=f"http://127.0.0.1:{port}/v1")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
