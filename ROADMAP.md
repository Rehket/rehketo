# Rehketo Roadmap

What's shipped, what's next, and what's on the other side of it.

References:
- Design spec — `docs/superpowers/specs/2026-04-19-chat-and-agent-v1-design.md`
- Active plans — `docs/superpowers/plans/`
- Per-conversation conventions — `AGENTS.md`

---

## Shipped

- **Plan 1 — API foundation + auth + chat CRUD** (`2026-04-19-plan-1-api-foundation.md`).
  FastAPI 3.14 + SQLAlchemy async + Alembic. Entra OIDC Pattern B (cookie sessions, backend-held encrypted refresh tokens). Double-submit CSRF middleware. Canonical action vocabulary + `check_permission` RBAC gate. Full conversations CRUD, `/me`, `/me/capabilities`. Devonly login endpoint for local iteration.
- **Plan 2 — runs + agent + SSE** (`2026-04-20-plan-2-runs-agent-sse.md`).
  Runs as first-class entities. deepagents + LangGraph with postgres checkpointer. `InProcessEventBus` + process-local task registry. `POST /conversations/{id}/messages` kickoff, `GET /runs/{id}`, `GET /runs/{id}/events` SSE (with `?from_sequence=N` resume), `POST /runs/{id}/cancel`. Startup sweep for abandoned runs. Best-effort conversation-title generation. Custom `/docs` wired for cookie + CSRF. Ship-checked end-to-end against Bifrost → Claude Sonnet 4.6.

---

## Near-term polish (no dedicated plan — track inline)

Small items that don't warrant a full plan doc. Each should land as one or two commits.

- **Branch tidy-up.** Plan 1 + Plan 2 both live on `plan-1/api-foundation`. Either fast-forward to `main` or split Plan 2 to its own branch and PR individually — depends on how you want the git story to read.
- **Responses API reopener.** When Bifrost's Anthropic-to-Responses translation populates `response.output` on the `response.completed` event, flip `use_responses_api=True` in `rehketo/agent/llm.py`. Docstring in that file records the failure mode.
- **`asyncio.set_event_loop_policy` deprecation.** Python 3.16 will remove the API we use in `rehketo/main.py` and `rehketo/cli/serve.py`. Migrate to `asyncio.Runner(loop_factory=...)` before the runtime moves to 3.16.
- **Context compression / analysis for `_load_history`.** The agent feeds the full message history to the LLM on every turn. Fast-follow after v1 UI ships and we can kick the tires with real conversations — the right shape (summarization, rolling window with checkpoints, tokenizer-budgeted packing, retrieval-augmented, or a hybrid) is a design call, not a mechanical last-N truncation.

---

## Planned increments

Ordered by the spec's fast-follow sequence plus the v1-completing UI. Each is a separate plan doc written when we're ready to execute (see Plan 1/2 for the format).

### 1. Plan 3 — SvelteKit thin client  *(not started)*

Build `rehketo-ui` as a SvelteKit app with `adapter-static`. Cookies handle auth; no MSAL.js in the browser. EventSource consumes `/runs/{id}/events`. `/me/capabilities` drives UI affordances (hide/disable, never trust). Minimum v1 screens: login landing, conversation list (sidebar), chat view (messages + composer + live run stream), user menu.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-3-svelte-ui.md`.

### 2. Postgres event-bus cutover *(spec's fast-follow)*

Swap `InProcessEventBus` for a `PostgresEventBus` using `LISTEN/NOTIFY` on a `run_events` table (already in the v1 schema). Same `RunEventBus` interface — agent code, SSE handler, and UI contract don't change. Unlocks (a) multi-worker uvicorn, (b) durable events across restarts, (c) the separate agent-worker process.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-postgres-event-bus.md`.

### 3. Separate agent worker process *(requires #2)*

Move agent execution out of the API process. API handlers create `queued` runs and serve SSE; a worker process claims runs from postgres and drives the LangGraph loop. With the checkpointer already durable, restart-safe resumption becomes possible. UI contract unchanged.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-worker-process.md`.

### 4. First real tool

Validate the tool-calling path end-to-end: tool registry, tool-call event emission in SSE, tool execution surface, and a real useful tool. Web search (Tavily/Brave) is the canonical first pick; sets up the pattern for every tool after.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-first-tool.md`.

### 5. Connections + first downstream-API capability

Build the `connections` table's consent flow: a new route pair that initiates OAuth to a downstream provider, stores the refresh token in `connections`, and exposes it to the agent. First capability to prove the model: MS Graph `Mail.Read` via Entra OBO ("summarize my inbox"). Establishes the pattern for Google/GitHub/etc.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-connections-msgraph.md`.

### 6. OpenFGA migration

Introduce OpenFGA as a sidecar service (with its own postgres database). Upload the authorization model sketched in the spec's §5. Run a one-time migration that writes existing `conversations.user_id` ownership as OpenFGA tuples. Swap `check_permission`'s body to delegate; swap `/me/capabilities` to use `batch-check`. Handlers, agent code, and UI contract unchanged.

Triggered by the first resource-scoped need — shared conversations, workspace hierarchies, or per-resource overrides.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-openfga-migration.md`.

### 7. Elevation cookie (`session_elevated`) + `requires_elevation` dep

Bundled with the first action whose blast radius warrants it (admin ops, destructive account actions, permission grants, connection revocation affecting others). Adds a second cookie, `session_elevated`, `SameSite=Strict`, short TTL, obtained through a re-authentication step. A `requires_elevation` FastAPI dependency declared on those endpoints. Orthogonal to `check_permission`: both gates must pass.

Memory: `project_elevation_for_dangerous_actions.md` in the auto-memory store.

Plan file target: `docs/superpowers/plans/YYYY-MM-DD-plan-elevation.md` (written alongside the first action that needs it — don't anticipate).

---

## Operational / infra backlog

Not application features, but things rehketo-api needs before it faces real users at scale.

- **Observability.** Structured JSON logs (already half-done via `rehketo.core.logging`), request IDs in every response header, metrics via Prometheus or OpenTelemetry, tracing spans across the request → run-agent boundary.
- **CI pipeline.** Run `uv sync` + `ruff` + `mypy` + `bandit` + `pytest` on every push. Probably GitHub Actions given the existing `.github/` folder.
- **Production hardening.** TLS at the edge, HTTP/2 (matters for SSE at scale), rotating `SESSION_ENCRYPTION_KEY` with an envelope scheme that survives rotation, `cookie_secure=true` in prod, proper secret management (Vault/Key Vault/AWS Secrets Manager — not `.env`).
- **Admin UI.** Once there are roles to manage and connections to revoke, an admin surface makes sense. Probably a page in `rehketo-ui` gated behind `admin.*` permissions rather than a separate app.
- **Import-linter rules.** Dev dep is declared but no `.importlinter` config exists. Lock down the `rehketo.api.* → rehketo.auth/permissions/db/core/config` dependency direction so new modules can't accidentally route through the wrong layer.
- **Background task lifecycle.** Title generation is fire-and-forget `asyncio.create_task` with `# noqa: RUF006`. If we grow more of these, consider a small in-process scheduler with done-callback logging so failures don't die silently.

---

## Open technical risks worth tracking

- **Bifrost schema drift.** Bifrost's config format evolved during v1 (YAML → JSON at `/app/data/config.json`). Provider registration is UI-managed, not IaC-friendly. If you ever want reproducible Bifrost config across environments, a seeding script or Terraform provider is the right shape.
- **LangGraph checkpointer table drift.** Migration 0003 wraps `AsyncPostgresSaver.setup()`. If LangGraph renames its tables upstream, our `test_database_is_migrated` catches it, but we'd need to write a follow-up migration — not just bump the LangGraph pin.
- **Single-worker correctness.** A lot of v1 works because there's one API process with one in-memory bus and one task registry. Multi-worker requires Plan-3-item #2 before it's safe. Document this clearly before any prod deploy.
- **Responses API behavior under load.** Chat Completions is our current path; when we go back to Responses, verify the streaming parser behavior against real traffic, not just smoke tests.
