#!/usr/bin/env python3
"""Repo guardrails: semantic invariants that linters can't see.

  python tools/agent_guards.py check                 # run all file checks
  python tools/agent_guards.py check-logger-names    # run one
  python tools/agent_guards.py commit-msg <file>     # commit-msg hook
"""
from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_SRC = ROOT / "rehketo-api" / "rehketo"

LOGGING_PY = API_SRC / "core" / "logging.py"
CONFIG_PY = API_SRC / "config.py"
PERMISSIONS_DIR = API_SRC / "permissions"


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def render(self) -> str:
        try:
            shown: Path | str = self.path.relative_to(ROOT)
        except ValueError:
            shown = self.path
        return f"{shown}:{self.line}: {self.message}"


def _py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# Registry of file-scanning checks. Populated as each is implemented.
FILE_CHECKS: dict[str, Callable[[], list[Violation]]] = {}


def _run(checks: Iterable[Callable[[], list[Violation]]]) -> int:
    violations: list[Violation] = []
    for fn in checks:
        violations.extend(fn())
    for v in violations:
        print(v.render())
    if violations:
        print(f"\n{len(violations)} guard violation(s).")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_guards")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    for name in FILE_CHECKS:
        sub.add_parser(name)
    cm = sub.add_parser("commit-msg")
    cm.add_argument("msg_file")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        return _run(FILE_CHECKS.values())
    if args.cmd == "commit-msg":
        found = check_no_ai_attribution(Path(args.msg_file))
        for v in found:
            print(v.render())
        return 1 if found else 0
    return _run([FILE_CHECKS[args.cmd]])


# commit-msg check lives here so it is importable before its task; see Task 2.7.
def check_no_ai_attribution(msg_path: Path) -> list[Violation]:
    return []


if __name__ == "__main__":
    raise SystemExit(main())
