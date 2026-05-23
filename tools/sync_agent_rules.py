#!/usr/bin/env python3
"""Generate tool-specific mirrors from the root AGENTS.md (single source of truth).

  python tools/sync_agent_rules.py            # write mirrors
  python tools/sync_agent_rules.py --check    # exit 1 if any mirror is stale
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"

REQUIRED_SECTIONS = (
    "## What it is",
    "## What it is for",
    "## The north star",
    "## The charter",
    "## How to validate work",
    "## Where things live",
    "## Conventions in force",
    "## Don'ts",
)

GENERATED_NOTE = (
    "<!-- GENERATED from AGENTS.md by tools/sync_agent_rules.py — do not edit by hand. -->"
)


def _claude(body: str) -> str:
    return (
        f"{GENERATED_NOTE}\n\n# CLAUDE.md\n\n"
        "The canonical guide for this repo is **AGENTS.md**, reproduced below.\n\n---\n\n"
        f"{body}"
    )


def _copilot(body: str) -> str:
    return (
        f"{GENERATED_NOTE}\n\n"
        "Copilot reads this on every Chat session. The canonical source is `AGENTS.md`.\n\n"
        f"---\n\n{body}"
    )


def _cursor(body: str) -> str:
    return (
        "---\n"
        "description: Rehketo project rules (generated from AGENTS.md)\n"
        "alwaysApply: true\n"
        f"---\n{GENERATED_NOTE}\n\n{body}"
    )


TARGETS = {
    ROOT / "CLAUDE.md": _claude,
    ROOT / ".github" / "copilot-instructions.md": _copilot,
    ROOT / ".cursor" / "rules" / "main.mdc": _cursor,
}


def render(body: str | None = None) -> dict[Path, str]:
    if body is None:
        body = AGENTS.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    if missing:
        raise SystemExit("AGENTS.md missing required sections: " + ", ".join(missing))
    return {path: fn(body) for path, fn in TARGETS.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if any mirror is stale")
    args = ap.parse_args(argv)

    stale: list[Path] = []
    for path, content in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    if args.check and stale:
        for p in stale:
            print(f"stale mirror: {p.relative_to(ROOT)}")
        print("Run: python3 tools/sync_agent_rules.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
