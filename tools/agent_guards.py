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


# --- escape hatches: suppressions must not be blanket -----------------------

_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?P<code>\s*\[[^\]]*\])?(?P<rest>.*)$")
_NOQA = re.compile(r"#\s*noqa(?P<code>:\s*[A-Za-z0-9]+(?:\s*,\s*[A-Za-z0-9]+)*)?")
_PRAGMA = re.compile(r"#\s*pragma:\s*no cover(?P<rest>.*)$")


def _check_escape_hatches_text(path: Path, text: str) -> list[Violation]:
    out: list[Violation] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = _TYPE_IGNORE.search(line)
        if m and not m.group("code"):
            out.append(Violation(path, i, "blanket '# type: ignore' — add a code, e.g. [arg-type]"))
        m = _NOQA.search(line)
        if m and not m.group("code"):
            out.append(Violation(path, i, "blanket '# noqa' — add a code, e.g. : F401"))
        m = _PRAGMA.search(line)
        if m and not m.group("rest").strip():
            out.append(Violation(path, i, "'# pragma: no cover' needs a reason comment"))
    return out


def check_escape_hatches() -> list[Violation]:
    out: list[Violation] = []
    for path in _py_files(API_SRC):
        out.extend(_check_escape_hatches_text(path, path.read_text(encoding="utf-8")))
    return out


FILE_CHECKS["check-escape-hatches"] = check_escape_hatches


# --- logger names: get_logger(__name__) only --------------------------------


def _check_logger_names_tree(path: Path, tree: ast.Module) -> list[Violation]:
    out: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "getLogger":
            if path != LOGGING_PY:
                out.append(Violation(path, node.lineno,
                    "use rehketo.core.logging.get_logger, not logging.getLogger"))
        elif isinstance(func, ast.Name) and func.id == "get_logger":
            first = node.args[0] if node.args else None
            if not (isinstance(first, ast.Name) and first.id == "__name__"):
                out.append(Violation(path, node.lineno, "call get_logger(__name__), not a literal"))
    return out


def check_logger_names() -> list[Violation]:
    out: list[Violation] = []
    for path in _py_files(API_SRC):
        out.extend(_check_logger_names_tree(path, _parse(path)))
    return out


FILE_CHECKS["check-logger-names"] = check_logger_names


# --- env access: only via rehketo.config ------------------------------------


def _check_getenv_tree(path: Path, tree: ast.Module) -> list[Violation]:
    if path == CONFIG_PY:
        return []
    out: list[Violation] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "os" and node.attr in {"getenv", "environ"}):
            out.append(Violation(path, node.lineno,
                f"read settings via rehketo.config.Settings, not os.{node.attr} outside config.py"))
    return out


def check_getenv_outside_config() -> list[Violation]:
    out: list[Violation] = []
    for path in _py_files(API_SRC):
        out.extend(_check_getenv_tree(path, _parse(path)))
    return out


FILE_CHECKS["check-getenv-outside-config"] = check_getenv_outside_config


# --- single permission gate -------------------------------------------------


def _check_permission_gate_tree(path: Path, tree: ast.Module) -> list[Violation]:
    if PERMISSIONS_DIR in path.parents:
        return []
    out: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "ROLE_PERMISSIONS":
            out.append(Violation(path, node.lineno,
                "ROLE_PERMISSIONS is internal to rehketo.permissions; gate via ResolvedPermissions"))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "check_permission"):
            out.append(Violation(path, node.lineno,
                "call ResolvedPermissions.can/require, not check_permission directly"))
    return out


def check_single_permission_gate() -> list[Violation]:
    out: list[Violation] = []
    for path in _py_files(API_SRC):
        out.extend(_check_permission_gate_tree(path, _parse(path)))
    return out


FILE_CHECKS["check-single-permission-gate"] = check_single_permission_gate


# --- permission calls thread resource_id ------------------------------------


def _check_resource_id_tree(path: Path, tree: ast.Module) -> list[Violation]:
    out: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kw = {k.arg for k in node.keywords if k.arg is not None}
        if "resource_type" in kw and "resource_id" not in kw:
            out.append(Violation(path, node.lineno,
                "permission call passes resource_type but not resource_id "
                "(thread it, even as resource_id=None — the OpenFGA contract)"))
    return out


def check_permission_resource_id() -> list[Violation]:
    out: list[Violation] = []
    for path in _py_files(API_SRC):
        out.extend(_check_resource_id_tree(path, _parse(path)))
    return out


FILE_CHECKS["check-permission-resource-id"] = check_permission_resource_id


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


# commit-msg check: stealth mode — no AI attribution trailers.
_AI_TRAILER = re.compile(
    r"(?i)(?:"
    r"co-authored-by:\s*.*(?:claude|anthropic|openai|gpt|copilot|cursor)"
    r"|generated\s+with\s+.*claude"
    r"|\U0001f916\s*generated)"
)


def check_no_ai_attribution(msg_path: Path) -> list[Violation]:
    out: list[Violation] = []
    for i, line in enumerate(msg_path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("# ------------------------ >8"):
            break  # git's verbose-commit scissors; everything below is a diff
        if line.lstrip().startswith("#"):
            continue  # comment lines aren't part of the message
        if _AI_TRAILER.search(line):
            out.append(Violation(msg_path, i,
                "stealth mode: remove AI attribution / Co-Authored-By trailer"))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
