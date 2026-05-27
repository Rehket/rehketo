"""Session fixture: builds the SvelteKit UI bundle once for UI_STATIC_DIR mount.

The api can serve the prebuilt SPA on `/` via the existing `UI_STATIC_DIR`
mount in `rehketo.main`. That gives the e2e suite SAME-ORIGIN UI + API
(no Vite proxy, no CORS, no PUBLIC_API_BASE) — cookies and CSRF just
work. We rebuild every session to catch packaging regressions; the
cost is ~5s on a warm pnpm cache.
"""

# ruff: noqa: S607 -- shells out to corepack/pnpm via user PATH (test infra)

from __future__ import annotations

import os
import pathlib
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

# rehketo-api/tests/e2e/fixtures/ui_build.py
#   parents[0] = fixtures, [1] = e2e, [2] = tests, [3] = rehketo-api, [4] = repo root
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
UI_ROOT = REPO_ROOT / "rehketo-ui"
UI_BUILD_DIR = UI_ROOT / "build"


@pytest.fixture(scope="session")
def ui_build() -> Iterator[pathlib.Path]:
    """Return the absolute path to the freshly-built SvelteKit `build/` dir.

    Skips the entire e2e suite if pnpm/corepack isn't available or the UI
    project isn't present (e.g., a sparse checkout).
    """
    if not UI_ROOT.is_dir():
        pytest.skip(f"rehketo-ui not found at {UI_ROOT}")

    env = {**os.environ}
    # `--ignore-scripts` skips Playwright browser install; e2e tests run
    # browsers via `playwright install` in their own setup, not here.
    install = subprocess.run(
        ["corepack", "pnpm", "install", "--frozen-lockfile", "--ignore-scripts"],
        cwd=UI_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pytest.skip(
            "corepack pnpm install failed (is Node + corepack available?):\n"
            + install.stderr[-500:]
        )

    build = subprocess.run(
        ["corepack", "pnpm", "build"],
        cwd=UI_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        raise RuntimeError(
            "corepack pnpm build failed:\n" + build.stdout + "\n" + build.stderr
        )

    assert UI_BUILD_DIR.is_dir(), (
        f"build output dir missing: {UI_BUILD_DIR} (adapter-static config changed?)"
    )
    assert (UI_BUILD_DIR / "index.html").is_file(), (
        f"build output has no index.html: {UI_BUILD_DIR}"
    )
    yield UI_BUILD_DIR
