#!/usr/bin/env python3
"""Best-effort API/UI contract guard: snapshot the API OpenAPI schema and fail on
drift from the checked-in baseline. NOT a type-equivalence proof — it surfaces backend
API changes so the UI's hand-written types (rehketo-ui/src/lib/types.ts) get a look.

Run via the api env:
    cd rehketo-api && uv run python ../tools/check_contract.py            # compare
    cd rehketo-api && uv run python ../tools/check_contract.py --update    # rebaseline
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "rehketo-ui" / "openapi.snapshot.json"


def _set_dummy_env() -> None:
    from cryptography.fernet import Fernet

    defaults = {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/rehketo",
        "SESSION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "CSRF_SIGNING_KEY": "x" * 48,
        "ENTRA_TENANT_ID": "t",
        "ENTRA_CLIENT_ID": "c",
        "ENTRA_CLIENT_SECRET": "s",
        "ENTRA_REDIRECT_URI": "http://localhost:8000/auth/callback",
        "UI_POST_LOGIN_URL": "http://localhost:5173/",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def _current_schema() -> str:
    _set_dummy_env()
    # Run via `uv run` (deps) but the script lives in tools/, so the api package
    # dir isn't on sys.path — add it explicitly.
    import sys

    sys.path.insert(0, str(ROOT / "rehketo-api"))
    from rehketo.main import create_app

    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args(argv)

    current = _current_schema()
    if args.update or not BASELINE.exists():
        BASELINE.write_text(current, encoding="utf-8")
        print(f"wrote {BASELINE.relative_to(ROOT)}")
        return 0

    if BASELINE.read_text(encoding="utf-8") == current:
        return 0

    import difflib

    diff = difflib.unified_diff(
        BASELINE.read_text(encoding="utf-8").splitlines(True),
        current.splitlines(True),
        fromfile="baseline", tofile="current",
    )
    print("".join(diff))
    print("\nAPI OpenAPI schema drifted from the baseline.")
    print("If intended, update rehketo-ui/src/lib/types.ts to match, then run:")
    print("  cd rehketo-api && uv run python ../tools/check_contract.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
