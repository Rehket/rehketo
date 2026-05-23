# Monorepo, AGENTS.md & Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the rehketo polyrepo into one git monorepo and add a slipstream-style AGENTS.md + automated guardrail system that keeps coding agents aligned with the project's goals.

**Architecture:** One git repo at `rehketo/` with `rehketo-api/` (Python) and `rehketo-ui/` (Svelte) as subdirectories (history preserved via `git subtree`). A root umbrella `AGENTS.md` (North Star + charter) plus two restructured nested charters. Enforcement: `tools/agent_guards.py` (AST checks), `import-linter`, UI ESLint rules, an OpenAPI-snapshot contract check, a mirror generator (`tools/sync_agent_rules.py`), all wired into one pre-commit config and one CI workflow.

**Tech Stack:** git subtree; Python 3.14 stdlib (`ast`, `argparse`, `re`); `uv`, `ruff`, `mypy`, `bandit`, `import-linter`, `pytest`; `pnpm`, ESLint flat config, Vitest; `pre-commit`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-23-agents-and-guardrails-monorepo-design.md`

---

## Conventions for every commit in this plan

- **Conventional Commits** (`feat|fix|chore|docs|style|refactor|perf|test|build|ci`).
- **Stealth mode — NO AI attribution.** No `Co-Authored-By`, no "generated with" trailers. (This is itself enforced by Task 2.7.)
- Run from the monorepo root (`/Users/adama/workspace/rehketo`) unless a step says otherwise.

## File structure (end state)

```
rehketo/
  AGENTS.md                      # umbrella (Task 1.1)
  CLAUDE.md                      # generated (Task 1.5)
  .cursor/rules/main.mdc         # generated (Task 1.5)
  .github/
    copilot-instructions.md      # generated (Task 1.5)
    workflows/ci.yml             # Task 3.2
    dependabot.yml               # Task 3.2
  .pre-commit-config.yaml        # Task 3.1
  tools/
    agent_guards.py              # Tasks 2.1-2.7
    sync_agent_rules.py          # Task 1.4
    check_contract.py            # Task 2.11
    tests/
      test_agent_guards.py       # Tasks 2.1-2.7
      test_sync_agent_rules.py   # Task 1.4
  docs/superpowers/{specs,plans}/
  rehketo-api/
    AGENTS.md                    # restructured (Task 1.2)
    .importlinter                # Task 2.9
    rehketo/ ...                 # source (resource_id fix: Task 2.6)
  rehketo-ui/
    AGENTS.md                    # restructured (Task 1.3)
    eslint.config.js             # +custom rules (Task 2.10)
    openapi.snapshot.json        # baseline (Task 2.11)
    src/ ...
```

---

# Phase 0 — Monorepo migration (subtree merge)

> Preserves full history and `git blame`. Both subrepos are clean (`rehketo-api` on `feat/ui`, `rehketo-ui` on `main`).

### Task 0.1: Pre-flight verification

**Files:** none (read-only checks)

- [ ] **Step 1: Confirm both subrepo working trees are clean**

Run:
```bash
git -C rehketo-api status --porcelain && echo "API CLEAN" || echo "API DIRTY"
git -C rehketo-ui status --porcelain && echo "UI CLEAN" || echo "UI DIRTY"
```
Expected: no file lines printed, then `API CLEAN` / `UI CLEAN`. If dirty, stop and commit/stash inside the subrepo first.

- [ ] **Step 2: Confirm the monorepo root is clean and on `main`**

Run:
```bash
git -C /Users/adama/workspace/rehketo status --short
git -C /Users/adama/workspace/rehketo branch --show-current
```
Expected: no output from `status --short` (only ignored subrepos), branch `main`.

### Task 0.2: Move subrepos aside and drop the temporary ignores

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Move both subrepos out of the working tree**

Run:
```bash
mkdir -p /Users/adama/workspace/.rehketo-migrate
mv /Users/adama/workspace/rehketo/rehketo-api /Users/adama/workspace/.rehketo-migrate/rehketo-api
mv /Users/adama/workspace/rehketo/rehketo-ui /Users/adama/workspace/.rehketo-migrate/rehketo-ui
ls /Users/adama/workspace/rehketo
```
Expected: listing shows `AGENTS.md`, `docs`, `.gitignore` (no `rehketo-api`/`rehketo-ui`).

- [ ] **Step 2: Rewrite `.gitignore` to drop the subrepo exclusions**

Replace the entire file with:
```gitignore
# Editor
/.idea/

# Python
__pycache__/
*.pyc

# Node
node_modules/
```

- [ ] **Step 3: Commit the clean pre-merge state**

Run:
```bash
git add .gitignore
git commit -m "build: drop pre-migration subrepo ignores"
```

### Task 0.3: Subtree-merge `rehketo-api`

**Files:** creates `rehketo-api/**` (with history)

- [ ] **Step 1: Add the api history under the `rehketo-api/` prefix**

Run:
```bash
git subtree add --prefix=rehketo-api /Users/adama/workspace/.rehketo-migrate/rehketo-api feat/ui
```
Expected: `git fetch` output then `Added dir 'rehketo-api'`.

- [ ] **Step 2: Verify files and history landed**

Run:
```bash
test -f rehketo-api/pyproject.toml && echo OK
git log --oneline -- rehketo-api/pyproject.toml | tail -3
```
Expected: `OK`, then several pre-existing api commits (proves history preserved).

### Task 0.4: Subtree-merge `rehketo-ui`

**Files:** creates `rehketo-ui/**` (with history)

- [ ] **Step 1: Add the ui history under the `rehketo-ui/` prefix**

Run:
```bash
git subtree add --prefix=rehketo-ui /Users/adama/workspace/.rehketo-migrate/rehketo-ui main
```
Expected: `Added dir 'rehketo-ui'`.

- [ ] **Step 2: Verify**

Run:
```bash
test -f rehketo-ui/package.json && echo OK
git log --oneline -- rehketo-ui/package.json | tail -3
```
Expected: `OK` then pre-existing ui commits.

### Task 0.5: Confirm single repo, verify blame, clean up

**Files:** none

- [ ] **Step 1: Confirm there is exactly one `.git` and blame works**

Run:
```bash
test ! -e rehketo-api/.git && test ! -e rehketo-ui/.git && echo "SINGLE REPO OK"
git blame -L 1,1 rehketo-api/pyproject.toml
git blame -L 1,1 rehketo-ui/package.json
```
Expected: `SINGLE REPO OK`; blame lines show the *original* commit/author, not the subtree merge.

- [ ] **Step 2: Remove the migration scratch copies**

Run:
```bash
rm -rf /Users/adama/workspace/.rehketo-migrate
git status --short
```
Expected: clean (nothing to commit; subtree already committed merges).

---

# Phase 1 — AGENTS.md set + mirror system

### Task 1.1: Write the root umbrella `AGENTS.md`

**Files:**
- Modify (replace placeholder): `AGENTS.md`

- [ ] **Step 1: Replace `AGENTS.md` with the umbrella charter**

Write `AGENTS.md` with exactly this content (the section headings are load-bearing — `tools/sync_agent_rules.py` validates them):
```markdown
# Rehketo — AGENTS.md

The canonical guide for working anywhere in this repo. It governs both subprojects;
each has a nested `AGENTS.md` with stack-specific rules (`rehketo-api/AGENTS.md`,
`rehketo-ui/AGENTS.md`). Tools read the nearest file plus this one. If a rule here
conflicts with an ad-hoc task prompt, this document wins unless the prompt explicitly
overrides it.

Tool mirrors at `CLAUDE.md`, `.github/copilot-instructions.md`, and
`.cursor/rules/main.mdc` are generated from this file by `tools/sync_agent_rules.py`.
Edit here, never there.

## What it is

Rehketo is a minimal, self-hostable agent harness: a chat UI (`rehketo-ui`, SvelteKit)
and an API (`rehketo-api`, FastAPI) for talking to LLMs. The API runs agent "runs"
(deepagents + LangGraph) and streams them to the UI over SSE. Auth is cookie-session
based (Entra OIDC, Pattern B). In production the built UI is served *inside* the API
via `StaticFiles` — they ship together.

## What it is for

To be a harness you can point at different model providers, extend with tools, and
connect to your own services — without being locked to one vendor, one tool surface,
or one identity provider. It removes the per-project boilerplate of auth, streaming,
permissions, and agent orchestration.

## The north star

These are the project's goals. They are **direction**, tied to seams that already exist
in the code. Build toward them through those seams — but do **not** build an abstraction
before the second concrete case demands it (see charter rule 3).

- **Provider-agnostic.** Today the API talks to one Bifrost model alias
  (`claude-sonnet-4-6`) behind the `AGENT_MODEL` seam in `rehketo-api`. New providers
  attach at that seam; model/provider choice is config/data. Never hardcode a vendor in
  a handler or the UI.
- **MCP integration.** Not built yet. The first real tool lands behind a tool-registry
  seam; when MCP arrives, it registers tools through that same registry — not a parallel
  path.
- **OAuth connections.** Today Entra is the sign-in IdP. Downstream service connections
  (Google / GitHub / MS Graph) attach via the planned `connections` table + a consent
  route pair. Every new provider follows that one pattern.

## The charter

Numbered rules with teeth. Several are enforced by `tools/agent_guards.py`; the rest are
honored on review.

1. **No archaeology.** Code reads clearly without `git blame`. Comment the non-obvious
   *why*, not the *what*.
2. **Edit > create.** Extend an existing file unless a new responsibility needs its own.
3. **No premature abstraction.** Three concrete lines beat a wrong helper. Honor the
   North Star with *seams*, not speculative frameworks.
4. **No speculative error handling.** Validate at boundaries; trust internal invariants.
5. **Verify before "done."** Run the validation block and quote real output. "Done"
   without it violates this rule.
6. **No escape hatches without specifics.** `# type: ignore` / `# noqa` carry a code;
   `# pragma: no cover` carries a reason. (Enforced: `check-escape-hatches`.)
7. **Stay in scope.** A bug fix doesn't refactor; a feature doesn't touch unrelated tests.
8. **No orphan code.** No unused imports, dead branches, or skipped tests without a
   reference.

## How to validate work

Run the checks for the area you touched and **quote the real output** when you claim a
step passed.

Repo-wide (from root):
```bash
python3 tools/agent_guards.py check
python3 tools/sync_agent_rules.py --check
```

rehketo-api (from `rehketo-api/`):
```bash
uv run ruff format --check
uv run ruff check
uv run mypy rehketo
uv run bandit -r rehketo
uv run lint-imports
uv run pytest
uv run python ../tools/check_contract.py
```

rehketo-ui (from `rehketo-ui/`):
```bash
pnpm run lint
pnpm run check
pnpm run test:unit -- --run
```

## Where things live

- `rehketo-api/` — FastAPI backend. See `rehketo-api/AGENTS.md`.
- `rehketo-ui/` — SvelteKit frontend. See `rehketo-ui/AGENTS.md`.
- `tools/` — repo guardrails (`agent_guards.py`), mirror generator
  (`sync_agent_rules.py`), contract check (`check_contract.py`), and their tests.
- `docs/superpowers/{specs,plans}/` — design specs and implementation plans.
- `AGENTS.md` + mirrors — this file and its generated copies.

## Conventions in force

- **Conventional Commits.** `feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert`.
- **Stealth mode.** No AI attribution / `Co-Authored-By` trailers. (Enforced:
  `check-no-ai-attribution`.)
- **One responsibility per file.** Split rather than stuff.
- Stack-specific conventions live in the nested `AGENTS.md` files.

## Don'ts

- Don't hardcode a model/provider/IdP where a seam exists (North Star).
- Don't hand-edit `CLAUDE.md`, `.github/copilot-instructions.md`, or
  `.cursor/rules/main.mdc` — edit `AGENTS.md` and run `tools/sync_agent_rules.py`.
- Don't bypass hooks with `--no-verify`.
- Don't add a config knob or code path "for later." YAGNI (charter rule 3).
```

- [ ] **Step 2: Commit**

Run:
```bash
git add AGENTS.md
git commit -m "docs: add umbrella AGENTS.md with north star and charter"
```

### Task 1.2: Restructure `rehketo-api/AGENTS.md` into the charter shape

**Files:**
- Modify: `rehketo-api/AGENTS.md`

> The existing file is excellent and detailed. **Preserve every existing subsection's prose verbatim** — this task only re-frames it into the charter shape and adds a validation block. Do not delete technical content.

- [ ] **Step 1: Reorder into these top-level sections, in this order**

1. `# Rehketo API — AGENTS.md` (title) + the existing one-paragraph intro ("This is the canonical conventions document…") and the "Reference docs" bullets.
2. `## What it is` — add (new, 2 sentences): "The rehketo-api backend: FastAPI 3.14 + async SQLAlchemy/psycopg3, Alembic, deepagents + LangGraph runs streamed over SSE, Entra OIDC Pattern B auth, and an RBAC permission gate built to swap to OpenFGA. It is one half of the rehketo monorepo; the root `AGENTS.md` holds the project North Star."
3. `## The charter` — reference the root charter, then keep the existing **"Don't do these"** items that are api-specific as numbered teeth (move that section's content here).
4. `## How to validate work` — insert the block from Step 2.
5. `## Where things live` — the existing "Project layout" tree and the "Rule: each file has one clear responsibility" line.
6. `## Conventions in force` — everything else, preserved verbatim under its existing `###`/`##` subheadings: *Python version and typing, Logging, Configuration, Database, Migrations, FastAPI conventions, Permissions gate, Sessions/cookies/CSRF, Testing, Style and lint, Security, Commits, Pre-commit, Error envelope, SSE, Architectural constraints, FastAPI + Pydantic typing gotchas.*
7. `## Don'ts` — the remaining general items from the old "Don't do these".

- [ ] **Step 2: Insert this `## How to validate work` block (verbatim)**

```markdown
## How to validate work

From `rehketo-api/`. Quote real output when you claim a step passed (charter rule 5).

```bash
uv run ruff format --check
uv run ruff check
uv run mypy rehketo
uv run bandit -r rehketo
uv run lint-imports          # import-linter layer contract (.importlinter)
uv run pytest
uv run python ../tools/check_contract.py   # OpenAPI snapshot vs. UI baseline
```

Repo guards also apply (run from the monorepo root): `python3 tools/agent_guards.py check`.
The honor-system rules below now have teeth — see the check name noted on each.
```

- [ ] **Step 3: Annotate the now-enforced rules**

In the preserved subsections, append the enforcing check name in parentheses to these rules:
- Logging "Never use `logging.getLogger` directly / use `get_logger(__name__)`" → `(enforced: check-logger-names)`
- Configuration "Never read `os.getenv` directly outside `config.py`" → `(enforced: check-getenv-outside-config)`
- Permissions "The ONLY permission surface is `check_permission`…" → `(enforced: check-single-permission-gate)`
- Permissions "Always pass `resource_id`…" → `(enforced: check-permission-resource-id)`
- Pre-commit "don't suppress with `# type: ignore`…" → `(enforced: check-escape-hatches — a specific code is required)`
- Commits "No AI attribution" → `(enforced: check-no-ai-attribution)`
- Architectural constraints (import-linter) → note the rules are now authored in `.importlinter` `(enforced: lint-imports)`

- [ ] **Step 4: Commit**

Run:
```bash
git add rehketo-api/AGENTS.md
git commit -m "docs(api): restructure AGENTS.md into charter shape"
```

### Task 1.3: Restructure `rehketo-ui/AGENTS.md` + make the hooks claim true

**Files:**
- Modify: `rehketo-ui/AGENTS.md`

> Preserve all existing content; reorganize + fix the false pre-commit claim.

- [ ] **Step 1: Reorder into the charter shape**

1. `# Rehketo UI — AGENTS.md` + existing intro line.
2. `## What it is` (new, 2 sentences): "The rehketo-ui frontend: a SvelteKit (adapter-static) thin client. Cookies carry auth; `/me/capabilities` drives UI affordances; EventSource consumes run SSE. One half of the rehketo monorepo — the root `AGENTS.md` holds the North Star."
3. `## How to validate work` — insert the block from Step 2.
4. `## Where things live` (new short list): `src/lib/api.ts` (only fetch wrapper), `src/lib/sse.ts` (only SSE consumer), `src/lib/types.ts` (hand-written backend contract), `src/lib/components/`, `src/routes/`.
5. `## Conventions in force` — preserve verbatim: *Commits, Stack rules, Backend contract, Dev flow, Testing.*
6. `## Don'ts` — preserve the existing "What NOT to do" list.

- [ ] **Step 2: Replace the false pre-commit claim with a real validation block**

In the existing "Commits" content, the line claiming "pre-commit hooks run `prettier --check`, `eslint`, `svelte-check`, and `vitest --run`" is now TRUE once Task 3.1 lands. Add this section:
```markdown
## How to validate work

From `rehketo-ui/`. Quote real output (charter rule 5).

```bash
pnpm run lint                 # prettier --check + eslint (incl. no-raw-fetch, no-user-markdown)
pnpm run check                # svelte-check
pnpm run test:unit -- --run   # vitest
```

These run in pre-commit (`.pre-commit-config.yaml`) and CI. The UI invariants below are
enforced as ESLint rules — see `eslint.config.js`.
```

- [ ] **Step 3: Annotate enforced UI invariants**

- "Don't bypass `apiFetch`" → `(enforced: eslint no-raw-fetch)`
- "Don't render markdown for user-authored text" → `(enforced: eslint no-user-markdown)`
- "Don't close the SSE stream on `run.status` alone" → `(covered by sse.spec.ts)`

- [ ] **Step 4: Commit**

Run:
```bash
git add rehketo-ui/AGENTS.md
git commit -m "docs(ui): restructure AGENTS.md into charter shape"
```

### Task 1.4: Write `tools/sync_agent_rules.py` (mirror generator) — TDD

**Files:**
- Create: `tools/sync_agent_rules.py`
- Test: `tools/tests/test_sync_agent_rules.py`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_sync_agent_rules.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_agent_rules as sync  # noqa: E402

COMPLETE = "\n".join(s + "\n\nbody\n" for s in sync.REQUIRED_SECTIONS)


def test_render_produces_three_targets():
    rendered = sync.render(body=COMPLETE)
    names = {p.name for p in rendered}
    assert names == {"CLAUDE.md", "copilot-instructions.md", "main.mdc"}


def test_render_rejects_missing_section():
    bad = COMPLETE.replace(sync.REQUIRED_SECTIONS[0], "## Something else")
    try:
        sync.render(body=bad)
    except SystemExit as e:
        assert "missing required sections" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_every_mirror_carries_the_generated_note():
    for content in sync.render(body=COMPLETE).values():
        assert sync.GENERATED_NOTE in content
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_sync_agent_rules.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync_agent_rules'`.

- [ ] **Step 3: Implement `tools/sync_agent_rules.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_sync_agent_rules.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

Run:
```bash
git add tools/sync_agent_rules.py tools/tests/test_sync_agent_rules.py
git commit -m "feat(tools): add AGENTS.md mirror generator"
```

### Task 1.5: Generate the mirrors

**Files:** creates `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/main.mdc`

- [ ] **Step 1: Generate and verify clean**

Run:
```bash
python3 tools/sync_agent_rules.py
python3 tools/sync_agent_rules.py --check && echo "MIRRORS FRESH"
```
Expected: second command prints nothing then `MIRRORS FRESH`.

- [ ] **Step 2: Commit**

Run:
```bash
git add CLAUDE.md .github/copilot-instructions.md .cursor/rules/main.mdc
git commit -m "docs: generate AGENTS.md tool mirrors"
```

---

# Phase 2 — Guardrails

### Task 2.1: `tools/agent_guards.py` skeleton + dispatch — TDD

**Files:**
- Create: `tools/agent_guards.py`
- Test: `tools/tests/test_agent_guards.py`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_agent_guards.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_guards as g  # noqa: E402


def test_check_runs_clean_on_real_tree():
    # The whole point: the real source must pass all file checks.
    assert g.main(["check"]) == 0


def test_violation_render_is_path_line_message():
    v = g.Violation(g.API_SRC / "x.py", 7, "boom")
    assert v.render() == "rehketo-api/rehketo/x.py:7: boom"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_guards'`.

- [ ] **Step 3: Implement the skeleton**

Create `tools/agent_guards.py`:
```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: 2 passed (no checks registered yet, so `check` is trivially clean).

- [ ] **Step 5: Commit**

Run:
```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): add agent_guards skeleton and dispatch"
```

### Task 2.2: `check-escape-hatches` — TDD

**Files:**
- Modify: `tools/agent_guards.py`
- Test: `tools/tests/test_agent_guards.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def test_escape_hatches_flags_blanket_but_allows_coded():
    src = (
        "x = 1  # type: ignore\n"            # blanket -> flag
        "y = 2  # type: ignore[arg-type]\n"  # coded -> ok
        "import z  # noqa\n"                  # blanket -> flag
        "import w  # noqa: F401\n"           # coded -> ok
        "a = 3  # pragma: no cover\n"        # no reason -> flag
        "b = 4  # pragma: no cover  # cli\n" # reason -> ok
    )
    v = g._check_escape_hatches_text(g.API_SRC / "x.py", src)
    assert [x.line for x in v] == [1, 3, 5]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_escape_hatches_flags_blanket_but_allows_coded -q`
Expected: FAIL — `AttributeError: module 'agent_guards' has no attribute '_check_escape_hatches_text'`.

- [ ] **Step 3: Implement (add to `agent_guards.py`, then register)**

```python
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?P<code>\[[^\]]*\])?(?P<rest>.*)$")
_NOQA = re.compile(r"#\s*noqa(?P<code>:[^\s#]+(?:,[^\s#]+)*)?(?P<rest>.*)$")
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
```

- [ ] **Step 4: Run tests to verify pass (incl. the clean-tree test)**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: all pass. (The real tree has only coded ignores, so `test_check_runs_clean_on_real_tree` still passes.)

- [ ] **Step 5: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): guard against blanket suppressions"
```

### Task 2.3: `check-logger-names` — TDD

**Files:** Modify `tools/agent_guards.py`; Test `tools/tests/test_agent_guards.py`

- [ ] **Step 1: Failing test (append)**

```python
import ast as _ast


def test_logger_names():
    bad = "import logging\nlogging.getLogger('x')\nget_logger('lit')\n"
    v = g._check_logger_names_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [2, 3]
    # logging.getLogger is allowed only inside core/logging.py
    ok = g._check_logger_names_tree(g.LOGGING_PY, _ast.parse("import logging\nlogging.getLogger('uvicorn')\n"))
    assert ok == []
    # get_logger(__name__) is fine anywhere
    fine = g._check_logger_names_tree(g.API_SRC / "api" / "foo.py", _ast.parse("get_logger(__name__)\n"))
    assert fine == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_logger_names -q`
Expected: FAIL — no attribute `_check_logger_names_tree`.

- [ ] **Step 3: Implement + register**

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: all pass (real tree: `logging.getLogger` only in `core/logging.py`).

- [ ] **Step 5: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): guard logger naming convention"
```

### Task 2.4: `check-getenv-outside-config` — TDD

**Files:** Modify `tools/agent_guards.py`; Test file

- [ ] **Step 1: Failing test (append)**

```python
def test_getenv_outside_config():
    bad = "import os\nx = os.getenv('A')\ny = os.environ['B']\n"
    v = g._check_getenv_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [2, 3]
    # config.py is exempt
    assert g._check_getenv_tree(g.CONFIG_PY, _ast.parse(bad)) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_getenv_outside_config -q`
Expected: FAIL — no attribute `_check_getenv_tree`.

- [ ] **Step 3: Implement + register**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: all pass (real tree has zero `os.getenv`/`os.environ`).

- [ ] **Step 5: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): guard env access outside config.py"
```

### Task 2.5: `check-single-permission-gate` — TDD

**Files:** Modify `tools/agent_guards.py`; Test file

- [ ] **Step 1: Failing test (append)**

```python
def test_single_permission_gate():
    bad = "check_permission(roles, 'a', resource_type=None, resource_id=None)\nx = ROLE_PERMISSIONS\n"
    v = g._check_permission_gate_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [1, 2]
    # inside permissions/ it is allowed
    assert g._check_permission_gate_tree(g.PERMISSIONS_DIR / "check.py", _ast.parse(bad)) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_single_permission_gate -q`
Expected: FAIL — no attribute `_check_permission_gate_tree`.

- [ ] **Step 3: Implement + register**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: all pass (real tree: `check_permission`/`ROLE_PERMISSIONS` only under `permissions/`; `me.py` uses `perms.can`).

- [ ] **Step 5: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): guard the single permission gate"
```

### Task 2.6: `check-permission-resource-id` + fix two call sites — TDD

**Files:**
- Modify: `tools/agent_guards.py`, `tools/tests/test_agent_guards.py`
- Modify: `rehketo-api/rehketo/api/conversations.py:80,93`

- [ ] **Step 1: Failing test (append)**

```python
def test_permission_resource_id():
    bad = "perms.require('a', resource_type='conversation')\n"
    v = g._check_resource_id_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [1]
    ok = "perms.require('a', resource_type='conversation', resource_id=None)\n"
    assert g._check_resource_id_tree(g.API_SRC / "api" / "foo.py", _ast.parse(ok)) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_permission_resource_id -q`
Expected: FAIL — no attribute `_check_resource_id_tree`.

- [ ] **Step 3: Implement + register**

```python
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
```

- [ ] **Step 4: Run the full guard against the real tree to surface the two violations**

Run: `python3 tools/agent_guards.py check-permission-resource-id`
Expected:
```
rehketo-api/rehketo/api/conversations.py:80: permission call passes resource_type but not resource_id ...
rehketo-api/rehketo/api/conversations.py:93: permission call passes resource_type but not resource_id ...
```

- [ ] **Step 5: Fix the two collection-level calls in `conversations.py`**

At `rehketo-api/rehketo/api/conversations.py:80` change:
```python
    perms.require("chat.create_conversation", resource_type="conversation")
```
to:
```python
    perms.require("chat.create_conversation", resource_type="conversation", resource_id=None)
```
At `rehketo-api/rehketo/api/conversations.py:93` change:
```python
    perms.require("chat.view_conversation", resource_type="conversation")
```
to:
```python
    perms.require("chat.view_conversation", resource_type="conversation", resource_id=None)
```

- [ ] **Step 6: Re-run guard + the unit tests, both clean**

Run:
```bash
python3 tools/agent_guards.py check-permission-resource-id && echo "GUARD CLEAN"
cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q && uv run pytest tests -q
```
Expected: `GUARD CLEAN`; guard tests pass; api tests still pass.

- [ ] **Step 7: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py rehketo-api/rehketo/api/conversations.py
git commit -m "feat(tools): guard resource_id threading; thread it on collection routes"
```

### Task 2.7: `check-no-ai-attribution` (commit-msg) — TDD

**Files:** Modify `tools/agent_guards.py`, `tools/tests/test_agent_guards.py`

- [ ] **Step 1: Failing test (append)**

```python
def test_no_ai_attribution(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("feat: do a thing\n\nReal body.\n")
    assert g.check_no_ai_attribution(good) == []

    bad = tmp_path / "bad.txt"
    bad.write_text("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n")
    out = g.check_no_ai_attribution(bad)
    assert len(out) == 1

    gen = tmp_path / "gen.txt"
    gen.write_text("fix: y\n\n\U0001f916 Generated with Claude Code\n")
    assert len(g.check_no_ai_attribution(gen)) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py::test_no_ai_attribution -q`
Expected: FAIL (current stub returns `[]` for the bad cases).

- [ ] **Step 3: Replace the stub `check_no_ai_attribution`**

Replace the placeholder body added in Task 2.1 with:
```python
_AI_TRAILER = re.compile(
    r"(?im)^\s*(?:"
    r"co-authored-by:\s*.*(?:claude|anthropic|openai|gpt|copilot|cursor)"
    r"|.*generated\s+with\s+.*claude"
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
```

- [ ] **Step 4: Run tests**

Run: `cd rehketo-api && uv run pytest ../tools/tests/test_agent_guards.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/agent_guards.py tools/tests/test_agent_guards.py
git commit -m "feat(tools): commit-msg guard against AI attribution"
```

### Task 2.9: Author the import-linter contract

**Files:**
- Create: `rehketo-api/.importlinter`

> import-linter is already a dev dependency. It builds the graph by *importing* the
> package; `rehketo.db` reads settings at import, so the verify step sets dummy env.

- [ ] **Step 1: Create `rehketo-api/.importlinter`**

```ini
[importlinter]
root_package = rehketo

[importlinter:contract:auth-permissions-never-import-api]
name = auth and permissions never depend on api
type = forbidden
source_modules =
    rehketo.auth
    rehketo.permissions
forbidden_modules =
    rehketo.api

[importlinter:contract:db-isolated]
name = db does not depend on app layers
type = forbidden
source_modules =
    rehketo.db
forbidden_modules =
    rehketo.api
    rehketo.auth
    rehketo.permissions

[importlinter:contract:core-foundational]
name = core is foundational
type = forbidden
source_modules =
    rehketo.core
forbidden_modules =
    rehketo.api
    rehketo.auth
    rehketo.permissions
    rehketo.db
    rehketo.config
```

- [ ] **Step 2: Verify the contract holds**

Run:
```bash
cd rehketo-api && \
DATABASE_URL='postgresql+psycopg://u:p@localhost:5432/r' \
SESSION_ENCRYPTION_KEY="$(uv run python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')" \
CSRF_SIGNING_KEY='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \
ENTRA_TENANT_ID=t ENTRA_CLIENT_ID=c ENTRA_CLIENT_SECRET=s \
ENTRA_REDIRECT_URI='http://localhost:8000/auth/callback' \
UI_POST_LOGIN_URL='http://localhost:5173/' \
uv run lint-imports
```
Expected: `Contracts: 3 kept, 0 broken.` If a contract is broken, that is a real layering violation — fix the offending import, do not weaken the contract.

- [ ] **Step 3: Commit**

```bash
git add rehketo-api/.importlinter
git commit -m "feat(api): author import-linter layer contract"
```

### Task 2.10: UI invariant ESLint rules

**Files:**
- Modify: `rehketo-ui/eslint.config.js`

- [ ] **Step 1: Append two config blocks to the `defineConfig(...)` array**

Add, before the closing `)` of `defineConfig`, after the existing final block:
```javascript
	{
		// Invariant: all data access goes through apiFetch (CSRF, 401/403,
		// envelope). Raw fetch is allowed ONLY in src/lib/api.ts.
		files: ['**/*.ts', '**/*.svelte', '**/*.svelte.ts'],
		rules: {
			'no-restricted-syntax': [
				'error',
				{
					selector: "CallExpression[callee.name='fetch']",
					message: 'Use apiFetch from $lib/api — raw fetch is only allowed in src/lib/api.ts.'
				},
				{
					selector: "CallExpression[callee.property.name='fetch']",
					message: 'Use apiFetch from $lib/api — raw fetch is only allowed in src/lib/api.ts.'
				}
			]
		}
	},
	{
		files: ['src/lib/api.ts'],
		rules: { 'no-restricted-syntax': 'off' }
	},
	{
		// Invariant (spec §5.5): user-authored text is NEVER markdown-rendered.
		// UserBubble renders plain text only.
		files: ['src/lib/components/UserBubble.svelte'],
		rules: {
			'no-restricted-imports': [
				'error',
				{
					patterns: [
						{
							group: ['**/MarkdownView.svelte', '**/markdown', '$lib/markdown'],
							message: 'User text must never be markdown-rendered (spec §5.5).'
						}
					]
				}
			]
		}
	}
```

- [ ] **Step 2: Verify ESLint passes on the current tree**

Run: `cd rehketo-ui && pnpm install --frozen-lockfile && pnpm exec eslint .`
Expected: no errors. (`api.ts`'s `fetch` is exempted; `sse.ts` uses `EventSource`, not `fetch`; `UserBubble.svelte` imports no markdown.)

> If ESLint flags a SvelteKit `load`-provided `fetch`, that file genuinely bypasses
> `apiFetch` — replace the call with `apiFetch`. Do not broaden the exemption.

- [ ] **Step 3: Verify the rules actually bite (temporary smoke test)**

Run:
```bash
cd rehketo-ui
printf "\nexport const _x = () => fetch('/x');\n" >> src/lib/types.ts
pnpm exec eslint src/lib/types.ts; echo "exit=$?"
git checkout -- src/lib/types.ts
```
Expected: an error citing the `no-restricted-syntax` message and `exit=1`, then the file is reverted.

- [ ] **Step 4: Commit**

```bash
git add rehketo-ui/eslint.config.js
git commit -m "feat(ui): enforce apiFetch-only and no-user-markdown via eslint"
```

### Task 2.11: `check_contract.py` (OpenAPI snapshot)

**Files:**
- Create: `tools/check_contract.py`
- Create: `rehketo-ui/openapi.snapshot.json` (baseline)

- [ ] **Step 1: Implement `tools/check_contract.py`**

```python
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
```

- [ ] **Step 2: Generate the baseline and confirm it then passes clean**

Run:
```bash
cd rehketo-api && uv run python ../tools/check_contract.py --update
uv run python ../tools/check_contract.py && echo "CONTRACT CLEAN"
```
Expected: `wrote rehketo-ui/openapi.snapshot.json`, then `CONTRACT CLEAN`.

> If Step 2 errors during `create_app()` for a missing setting, add that field's env
> var to `_set_dummy_env` (match `rehketo-api/rehketo/config.py`) and retry.

- [ ] **Step 3: Commit**

```bash
git add tools/check_contract.py rehketo-ui/openapi.snapshot.json
git commit -m "feat(tools): add best-effort OpenAPI contract snapshot"
```

### Task 2.12: Verify existing SSE-close coverage (no new test)

**Files:** none (verification only)

- [ ] **Step 1: Confirm the invariant is already tested**

Run: `cd rehketo-ui && pnpm run test:unit -- --run src/lib/sse.spec.ts`
Expected: pass, including the assertion at `sse.spec.ts` that `src.closed === false` after `run.status=succeeded` (the "succeeded alone does NOT close" case). No new test is needed (spec §6).

---

# Phase 3 — Wiring (pre-commit + CI)

### Task 3.1: One root `.pre-commit-config.yaml`

**Files:**
- Create: `.pre-commit-config.yaml`
- Delete: `rehketo-api/.pre-commit-config.yaml` (superseded; carried the stale `apex-search-service` header)

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

```yaml
# Rehketo monorepo pre-commit hooks.
# Install: pre-commit install --hook-type pre-commit --hook-type commit-msg
# Run all: pre-commit run --all-files
minimum_pre_commit_version: "3.5.0"
repos:
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.0.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert]

  - repo: local
    hooks:
      # ---- commit hygiene ----
      - id: no-ai-attribution
        name: no-ai-attribution
        entry: python3 tools/agent_guards.py commit-msg
        language: system
        stages: [commit-msg]

      # ---- repo-wide guards ----
      - id: agent-guards
        name: agent-guards
        entry: python3 tools/agent_guards.py check
        language: system
        pass_filenames: false
        always_run: true
      - id: sync-agent-rules
        name: sync-agent-rules
        entry: python3 tools/sync_agent_rules.py
        language: system
        pass_filenames: false
        always_run: true

      # ---- rehketo-api (Python) ----
      - id: api-ruff
        name: api-ruff
        entry: bash -c 'cd rehketo-api && uv run ruff check'
        language: system
        files: ^rehketo-api/
        types: [python]
        pass_filenames: false
      - id: api-mypy
        name: api-mypy
        entry: bash -c 'cd rehketo-api && uv run mypy rehketo'
        language: system
        files: ^rehketo-api/
        types: [python]
        pass_filenames: false
      - id: api-bandit
        name: api-bandit
        entry: bash -c 'cd rehketo-api && uv run bandit -r rehketo'
        language: system
        files: ^rehketo-api/
        types: [python]
        pass_filenames: false

      # ---- rehketo-ui (Node) ----
      - id: ui-prettier
        name: ui-prettier
        entry: bash -c 'cd rehketo-ui && pnpm exec prettier --check .'
        language: system
        files: ^rehketo-ui/
        pass_filenames: false
      - id: ui-eslint
        name: ui-eslint
        entry: bash -c 'cd rehketo-ui && pnpm exec eslint .'
        language: system
        files: ^rehketo-ui/
        pass_filenames: false
      - id: ui-svelte-check
        name: ui-svelte-check
        entry: bash -c 'cd rehketo-ui && pnpm run check'
        language: system
        files: ^rehketo-ui/
        pass_filenames: false
      - id: ui-vitest
        name: ui-vitest
        entry: bash -c 'cd rehketo-ui && pnpm run test:unit -- --run'
        language: system
        files: ^rehketo-ui/
        pass_filenames: false
```

- [ ] **Step 2: Remove the old per-repo config and install hooks**

Run:
```bash
git rm rehketo-api/.pre-commit-config.yaml
pre-commit install --hook-type pre-commit --hook-type commit-msg
```
Expected: hooks installed at `.git/hooks/pre-commit` and `.git/hooks/commit-msg`.

- [ ] **Step 3: Run the whole hook suite once**

Run: `pre-commit run --all-files`
Expected: all hooks pass (Phase 2 already made the tree clean). Fix any real failure surfaced; re-run until green.

- [ ] **Step 4: Commit (exercises the commit-msg hooks)**

Run:
```bash
git add .pre-commit-config.yaml
git commit -m "build: add monorepo pre-commit config"
```
Expected: `conventional-pre-commit` and `no-ai-attribution` pass.

### Task 3.2: One root CI workflow + dependabot

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`
- Delete: `rehketo-api/.github/workflows/python-lint.yml`, `rehketo-api/.github/dependabot.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.f.outputs.api }}
      ui: ${{ steps.f.outputs.ui }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: f
        with:
          filters: |
            api:
              - 'rehketo-api/**'
              - 'tools/**'
              - 'AGENTS.md'
            ui:
              - 'rehketo-ui/**'
              - 'tools/**'

  guards:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: rehketo-api/.python-version
      - name: agent guards
        run: python tools/agent_guards.py check
      - name: guard + sync tests
        run: |
          python -m pip install --quiet pytest
          python -m pytest tools/tests -q
      - name: mirror drift
        run: |
          python tools/sync_agent_rules.py
          git diff --exit-code AGENTS.md CLAUDE.md \
            .github/copilot-instructions.md .cursor/rules/main.mdc

  api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: rehketo-api
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: rehketo-api/.python-version
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --locked --dev
      - run: uv run ruff format --check
      - run: uv run ruff check
      - run: uv run mypy rehketo
      - run: uv run bandit -r rehketo
      - name: import-linter
        env:
          DATABASE_URL: postgresql+psycopg://u:p@localhost:5432/rehketo
          SESSION_ENCRYPTION_KEY: ZmFrZS1mZXJuZXQta2V5LWZvci1jaS1vbmx5LXBhZGRpbmc9
          CSRF_SIGNING_KEY: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
          ENTRA_TENANT_ID: t
          ENTRA_CLIENT_ID: c
          ENTRA_CLIENT_SECRET: s
          ENTRA_REDIRECT_URI: http://localhost:8000/auth/callback
          UI_POST_LOGIN_URL: http://localhost:5173/
        run: uv run lint-imports
      - run: uv run pytest
      - name: contract snapshot
        run: uv run python ../tools/check_contract.py

  ui:
    needs: changes
    if: needs.changes.outputs.ui == 'true'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: rehketo-ui
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: pnpm
          cache-dependency-path: rehketo-ui/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm run lint
      - run: pnpm run check
      - run: pnpm run test:unit -- --run
```

> The `SESSION_ENCRYPTION_KEY` above is a syntactically valid Fernet key for CI only.
> If `lint-imports` reports a settings error, align the env block with `config.py`.

- [ ] **Step 2: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: uv
    directory: /rehketo-api
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: /rehketo-ui
    schedule:
      interval: weekly
```

- [ ] **Step 3: Remove the superseded api CI files**

Run:
```bash
git rm rehketo-api/.github/workflows/python-lint.yml rehketo-api/.github/dependabot.yml
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/dependabot.yml
git commit -m "ci: add unified monorepo pipeline and dependabot"
```

### Task 3.3: Full-repo green pass

**Files:** none (verification)

- [ ] **Step 1: Run every validation surface from a clean tree**

Run:
```bash
python3 tools/agent_guards.py check && echo "GUARDS OK"
python3 tools/sync_agent_rules.py --check && echo "MIRRORS FRESH"
( cd rehketo-api && uv run ruff format --check && uv run ruff check && uv run mypy rehketo && uv run bandit -r rehketo && uv run pytest -q )
( cd rehketo-ui && pnpm run lint && pnpm run check && pnpm run test:unit -- --run )
pre-commit run --all-files
```
Expected: `GUARDS OK`, `MIRRORS FRESH`, api suite green, ui suite green, all pre-commit hooks pass.

- [ ] **Step 2: Confirm a clean working tree**

Run: `git status --short`
Expected: empty.

---

## Self-Review (completed during planning)

**Spec coverage:** §2 migration → Phase 0. §3 AGENTS.md set → Tasks 1.1–1.3. §4.1 guard runner → Tasks 2.1–2.7. §4.2 import-linter → Task 2.9. §4.3 contract → Task 2.11. §4.4 pre-commit → Task 3.1. §4.5 CI → Task 3.2. §5 mirrors → Tasks 1.4–1.5. §6 SSE-already-tested → Task 2.12. §8 deliverables 1–11 all mapped.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to". Every code step has full code; the only conditional notes ("if a setting is missing", "if a SvelteKit fetch is flagged") give the exact corrective action.

**Type/name consistency:** `Violation`, `_py_files`, `_parse`, `FILE_CHECKS`, `check_no_ai_attribution`, `_check_*_tree`/`_check_*_text` helpers, `render(body=...)`, `REQUIRED_SECTIONS`, `GENERATED_NOTE`, `BASELINE` are used consistently across tasks. The root `AGENTS.md` headings exactly match `sync_agent_rules.REQUIRED_SECTIONS`.

**Note on numbering:** there is no Task 2.8 (the slipstream `check-skip-todo-tickets` was cut per the spec); guard tasks run 2.1–2.7 then 2.9–2.12.
