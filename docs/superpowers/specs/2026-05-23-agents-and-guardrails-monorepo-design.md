# Rehketo — Monorepo, AGENTS.md & Guardrails Design

- **Status:** Approved (design), pending implementation plan
- **Date:** 2026-05-23
- **Pattern source:** `slipstream` (single-repo AGENTS.md + `tools/agent_guards.py` + `tools/sync_agent_rules.py`)
- **Supersedes:** the 139-byte placeholder `rehketo/AGENTS.md`

## 1. Context

Rehketo is a self-hostable, minimal agent harness — a chat UI plus an API — for talking
to LLMs. Its north star is to stay **provider-agnostic**, support **MCP** tool integration,
and use **OAuth** for both sign-in and downstream service connections.

Today the repo is three layers:

- `rehketo/` — a non-git parent folder with a placeholder `AGENTS.md`.
- `rehketo-api/` — its own git repo (Python 3.14, `uv`, FastAPI, async SQLAlchemy + psycopg3,
  Alembic, deepagents + LangGraph, Bifrost→Claude, Entra OIDC). Already has a detailed 16.8KB
  `AGENTS.md`, a `.pre-commit-config.yaml` (conventional-commit, uv-sync, ruff, mypy, bandit),
  CI (`python-lint.yml`), and a `docs/superpowers/` specs+plans workflow.
- `rehketo-ui/` — its own git repo (Svelte 5 + runes, SvelteKit, strict TS, Vite, Vitest,
  Playwright, ESLint, Prettier, Tailwind). Has a 3.9KB `AGENTS.md` that *claims* pre-commit
  hooks which are not actually wired (no husky/pre-commit/lefthook config exists).

**Purpose of this work:** give coding agents (and humans) a single, enforced source of
intent so contributions stay aligned with the harness's goals — encoded as human-readable
intent (`AGENTS.md`) backed by automated enforcement (guardrails), in the slipstream style.

### 1.1 Decisions taken (brainstorming)

1. **Goals treatment → North Star section.** Encode provider-agnosticism, MCP, and OAuth
   connections as *direction tied to existing seams*, not as abstractions to build now.
2. **Existing docs → restructure to the charter shape.** Preserve all current content;
   reorganize into slipstream's canonical sections and add a "How to validate work" block.
3. **Guardrails → full custom guard runner** (`tools/agent_guards.py`) in pre-commit + CI.
4. **Structure → monorepo.** One git repo; `rehketo-api/` and `rehketo-ui/` become plain
   subdirectories (names kept).
5. **Mirrors → all three** (`CLAUDE.md`, `.github/copilot-instructions.md`,
   `.cursor/rules/main.mdc`) generated from the root `AGENTS.md`.
6. **Git history → preserve via subtree merge.** `git blame` survives in both subtrees.

### 1.2 Why monorepo fits rehketo specifically

- **They already deploy together.** In prod the built UI bundle is served *through* FastAPI's
  `StaticFiles` via `UI_STATIC_DIR`. The UI ships inside the API.
- **They're bound by a hand-maintained contract.** `rehketo-ui/src/lib/types.ts` must track the
  API spec; today that reference crosses a repo boundary and nothing can enforce it. A monorepo
  pulls it inside a single enforcement boundary.
- **Atomic cross-cutting changes.** A backend field change and its UI type update land in one
  commit/PR instead of two repos that silently drift.
- **1:1 fit with the slipstream pattern**, which was designed for a single repo. Eliminates the
  cross-repo config-sharing, submodule-friction, and per-repo-CI awkwardness of a polyrepo.

## 2. Target structure

```
rehketo/                              # ONE git repo (the only .git)
  AGENTS.md                           # umbrella: North Star + charter + "where things live"
  CLAUDE.md                           # generated mirror (root)
  .cursor/rules/main.mdc              # generated mirror
  .github/
    copilot-instructions.md           # generated mirror
    workflows/ci.yml                  # one pipeline: api + ui + guards + mirror-drift jobs
    dependabot.yml                    # merged from rehketo-api
  .pre-commit-config.yaml             # one config; hooks scoped by path
  tools/
    agent_guards.py                   # AST checks (api) + shells out to the ui check
    sync_agent_rules.py               # generates all three mirrors; validates required sections
    check_ui_invariants.mjs           # node-side UI checks not expressible as ESLint rules (if any)
  docs/superpowers/specs/             # this spec lives here
  rehketo-api/
    AGENTS.md                         # api charter (Python/FastAPI), nested
    .importlinter                     # NEW: layer-boundary contract
    pyproject.toml, rehketo/, tests/, alembic/, deploy/, ...
  rehketo-ui/
    AGENTS.md                         # ui charter (Svelte), nested
    eslint.config.js                  # + custom no-raw-fetch / no-user-markdown rules
    package.json, src/, ...
```

`AGENTS.md` is read hierarchically by Claude Code / Cursor / Copilot: the nearest file to the
edited path plus the root. So a root umbrella + two nested per-stack charters is idiomatic, and
generated mirrors only need to exist at the root.

### 2.1 Migration approach (detail belongs in the implementation plan)

- Subtree-merge each existing repo under its prefix (`rehketo-api/`, `rehketo-ui/`) so full
  history and `git blame` are preserved; remove the nested `.git` dirs; one root `.git` remains.
- Mechanics (move dirs aside, `git subtree add --prefix=…`, etc.) are specified in the plan.
- Until the merge runs, the root `.gitignore` excludes `rehketo-api/` and `rehketo-ui/` so the
  initial commit (this spec) does not capture them as embedded gitlinks.

## 3. The AGENTS.md set

All three files use the charter shape:
*What it is / What it's for / The charter / How to validate work / Where things live / Conventions in force / Don'ts.*

### 3.1 Root `AGENTS.md` (new, umbrella)

Distinctive section — **The North Star** — encodes goals as direction tied to existing seams,
reconciled with the YAGNI charter ("build toward these via the named seams; do **not** build the
abstraction before the second concrete case"):

- **Providers.** Today: Bifrost gateway + the single `claude-sonnet-4-6` alias behind the
  `AGENT_MODEL` seam. Direction: provider/model choice is config/data; new providers attach at
  that seam; handlers never hardcode a vendor.
- **MCP.** Today: none. Direction: the first real tool (roadmap #4) lands behind a **tool-registry
  seam**; when MCP arrives it registers through that same registry, not a parallel path.
- **OAuth / connections.** Today: Entra as the IdP. Direction: downstream OAuth (roadmap #5)
  attaches via the `connections` table + a consent-flow route pair; Google/GitHub/MS Graph all
  follow that one pattern.

Plus cross-cutting **Principles** (single source of truth for contracts; capability-gated UI never
trusts the client; one permission gate; seams over speculative abstractions), the cross-cutting
**Charter** (no archeology, edit > create, no premature abstraction, verify before "done", escape
hatches need rationale, stay in scope, no orphan code), a monorepo-aware **How to validate work**
block, **Where things live** (the map above), **Conventions** (Conventional Commits; stealth mode —
no AI attribution), and **Don'ts** (incl. "don't hand-edit generated mirrors").

### 3.2 `rehketo-api/AGENTS.md` (restructured)

All existing Python/FastAPI/pydantic/DB/permissions/CSRF content **preserved**, reorganized into
the charter shape. Adds a copy-paste **How to validate work** block:

```bash
uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo
uv run lint-imports                       # import-linter contract
uv run pytest
python ../tools/agent_guards.py check     # repo guards (run from root in CI/pre-commit)
```

"Quote real output when claiming a step passed." Each honor-system rule that now has a guard is
cross-referenced to its check name.

### 3.3 `rehketo-ui/AGENTS.md` (restructured)

Existing Svelte content preserved + reorganized. The false "pre-commit runs prettier/eslint/
svelte-check/vitest" claim is made true (see §4.4). Adds a validation block:

```bash
pnpm lint           # prettier --check + eslint (incl. custom invariant rules)
pnpm check          # svelte-check
pnpm test:unit -- --run
```

## 4. Guardrails

**Philosophy:** guards enforce *semantic invariants linters can't see*. Anything ruff/eslint already
covers (print statements, import order, complexity) is **not** duplicated in a guard.

### 4.1 Canonical runner: `tools/agent_guards.py`

Python, slipstream-style: independent subcommands plus a `check` meta-command that runs all and
exits non-zero on any violation. It checks Python directly (AST). UI invariants are enforced as
ESLint rules so they run in the UI lint hook/job (not re-run by `agent_guards`); a
`check_ui_invariants.mjs` script exists only for any invariant that can't be expressed as an ESLint
rule, and `agent_guards check` invokes it when present. Final check set:

**Python / API invariants:**

| Check | Rule enforced |
|---|---|
| `check-single-permission-gate` | No code reads roles / `ROLE_PERMISSIONS` directly; the only permission surface is `check_permission` / `ResolvedPermissions.can/require`. No second check path. |
| `check-permission-resource-id` | `.require(...)` / `.can(...)` calls pass `resource_id=` (the OpenFGA migration contract). |
| `check-getenv-outside-config` | `os.getenv` / `os.environ` only in `rehketo/config.py`. |
| `check-logger-names` | `get_logger(__name__)` only — never a string literal. |
| `check-escape-hatches` | Bans *blanket* suppressions: `# type: ignore` and `# noqa` must carry a specific code (e.g. `# type: ignore[arg-type]`, `# noqa: TC002`); `# pragma: no cover` must carry a prose reason. (Adapted from slipstream's prose-reason rule to fit this codebase's existing coded suppressions — zero retroactive churn; the 13 current code-only ignores already pass.) |

**Commit hygiene:**

| Check | Rule enforced |
|---|---|
| `check-no-ai-attribution` | Commit messages carry no `Co-Authored-By`/AI/generated-with trailers (stealth mode). Runs at `commit-msg`. |

**UI invariants** (ESLint `no-restricted-imports` / `no-restricted-syntax` where expressible;
`tools/check_ui_invariants.mjs` otherwise):

| Check | Rule enforced |
|---|---|
| `no-raw-fetch` | No `fetch(` outside `src/lib/api.ts`; everything goes through `apiFetch`. |
| `no-user-markdown` | User-authored text is never routed through the markdown renderer. |

### 4.2 Layer-boundary contract: `rehketo-api/.importlinter`

Authors the contract the api doc + roadmap call "declared but unwritten" (uses the existing
`import-linter` dev dep, not a reimplementation):

- `rehketo.api.*` may depend on `rehketo.auth`, `rehketo.permissions`, `rehketo.db`,
  `rehketo.core`, `rehketo.config`.
- `rehketo.auth`, `rehketo.permissions` must **not** import `rehketo.api`.
- `rehketo.db.models` is isolated (stdlib + SQLAlchemy only).
- `rehketo.core.logging` is foundational (imports nothing from `rehketo`).

### 4.3 Cross-repo contract: `check-contract` (best-effort)

**Not** a type-equivalence proof. CI dumps the API's OpenAPI schema and fails if it drifts from a
checked-in snapshot, surfacing UI/API mismatch to a human reviewer. Cheap insurance against the
`types.ts` ↔ spec drift that the monorepo finally makes observable.

### 4.4 Pre-commit: one root `.pre-commit-config.yaml`

- `commit-msg`: `conventional-pre-commit` + `check-no-ai-attribution`.
- API hooks (`files: ^rehketo-api/`): uv-sync, ruff, mypy, bandit, `lint-imports`.
- UI hooks (`files: ^rehketo-ui/`): prettier `--check`, eslint, svelte-check, vitest `--run`
  (**finally wired**).
- Repo-wide: `agent_guards check` (always run), `sync_agent_rules` (regenerate mirrors).
- The stale `# Pre-commit hooks for apex-search-service` header is removed.

### 4.5 CI: one `.github/workflows/ci.yml`

Path-filtered jobs so a UI-only change doesn't run the Python suite and vice-versa:

- `api` — uv + ruff + mypy + bandit + `lint-imports` + pytest.
- `ui` — pnpm lint + check + test.
- `guards` — `agent_guards check`.
- `mirror-drift` — run `sync_agent_rules`, then `git diff --exit-code` on `AGENTS.md` + mirrors.
- `contract` — OpenAPI snapshot diff (§4.3).

Existing `rehketo-api/.github/dependabot.yml` is merged into the root.

## 5. Mirrors / sync — `tools/sync_agent_rules.py`

Root `AGENTS.md` is the single source of truth. The script:

- Validates that `AGENTS.md` contains all required charter sections before generating.
- Generates `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/main.mdc` at the root.
- Is idempotent; drift is caught by the `mirror-drift` CI job and the pre-commit hook.

Nested `rehketo-api/AGENTS.md` and `rehketo-ui/AGENTS.md` stay hand-written (mirrors at root only,
since tools read hierarchically).

## 6. Non-goals (explicit YAGNI)

- **No** provider / MCP-client / connection abstraction layers built ahead of a second concrete
  case. Only the *seams* and the *direction* are documented.
- `check-contract` is **not** a structural type-equivalence check.
- The SSE-close invariant ("don't close on `run.status` alone; wait for `run.ended`") is enforced
  by a **test**, not a guard (too fragile to detect statically). This coverage **already exists** in
  `rehketo-ui/src/lib/sse.spec.ts` (asserts `src.closed === false` after `run.status=succeeded`), so
  no new test is required — the plan only verifies it.
- **Cut** for now: `check-skip-todo-tickets` (no issue tracker referenced yet — revisit when one is
  adopted) and `check-actions-naming` (low value over existing tooling).
- No renaming of `rehketo-api/` / `rehketo-ui/` (avoids rewriting cross-references).

## 7. Risks & open questions

- **Subtree merge mechanics** — must move the existing dirs aside before `git subtree add` so the
  prefixes are free; verify `git blame` resolves post-merge. (Plan detail.)
- **Two toolchains in one repo** (`uv` + `pnpm`) — contributors/CI need both; CI installs both.
- **CI path filters** — ensure the `paths:` filters are correct so neither stack's job is skipped on
  shared changes (e.g., root `AGENTS.md` edits should trigger `mirror-drift` + `guards`).
- **Future split cost** — splitting a stack back into its own repo later is possible via
  `git filter-repo` but non-free; acceptable at this stage.

## 8. Deliverables checklist (for the implementation plan)

1. Monorepo created; both repos subtree-merged with history; nested `.git` removed.
2. Root `AGENTS.md` (umbrella + North Star) written.
3. `rehketo-api/AGENTS.md` and `rehketo-ui/AGENTS.md` restructured to charter shape.
4. `tools/agent_guards.py` with the §4.1 checks + a `check` meta-command + unit tests.
5. `rehketo-api/.importlinter` contract.
6. UI invariant checks (ESLint rules + optional `check_ui_invariants.mjs`).
7. `check-contract` OpenAPI snapshot + checked-in baseline.
8. `tools/sync_agent_rules.py` + the three generated mirrors.
9. One root `.pre-commit-config.yaml` (path-scoped) — stale header removed.
10. One root `.github/workflows/ci.yml` + merged `dependabot.yml`.
11. Verify the existing SSE-close coverage in `rehketo-ui/src/lib/sse.spec.ts` (already present;
    no new test needed).
