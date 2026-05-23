# Rehketo Chat + Agent v1 — Design

**Date:** 2026-04-19
**Status:** Design approved, pending implementation plan.
**Scope:** First deliverable of rehketo — a chat UI backed by a single unified API that runs agentic turns against an LLM via Bifrost, with persistent conversations and a run-lifecycle model ready for long-running background agents in later increments.

## 1. Goals and non-goals

### Goals
- Deliver a working chat experience: Svelte UI, FastAPI backend, Bifrost-routed LLM calls (Claude Sonnet 4.6 via the Responses API), persistent conversations.
- Establish the architectural spine (one backend, thin client, runs-as-first-class, durable checkpointer, SSE streaming) that lets long-running agentic tasks, tools, and fine-grained permissions land later as additive changes rather than rewrites.
- Use Entra as the identity provider with a Pattern B (cookie session + backend-held refresh tokens) auth flow that supports delegated downstream calls without exposing tokens to the browser.

### Non-goals (v1)
- Any registered agent tools. Tool-calling infrastructure exists in code; the tool registry is empty.
- Long-running background agents (architecture-ready, not built).
- Fine-grained / ReBAC authorization (designed for, not built — v1 uses role-based permissions).
- Agent memory across conversations.
- Multiple LLM providers (Bifrost is configured with one; fallbacks arrive when justified).
- Multiple identity providers (Entra only; the `identities` / `connections` split prepares for more).
- A production deployment. v1 targets local docker-compose development; production hardening is a follow-up.

## 2. High-level architecture

```
                              ┌─────────────────────────────┐
                              │  browser                     │
                              │  rehketo-ui                  │
                              │  (SvelteKit, static adapter) │
                              │                              │
                              │  - httpOnly cookie           │
                              │  - SSE subscriber per run    │
                              └────────────┬─────────────────┘
                                           │  HTTPS, cookie auth
                                           ▼
                              ┌─────────────────────────────┐
                              │  rehketo-api (FastAPI 3.14) │
                              │                             │
                              │  - auth: OIDC callback,     │
                              │    sessions, connections    │
                              │  - chat: conversations,     │
                              │    messages, runs           │
                              │  - agent: deepagents +      │
                              │    LangGraph + postgres     │
                              │    checkpointer             │
                              │  - SSE: per-run event stream│
                              │  - permissions:             │
                              │    check_permission()       │
                              │  - RunEventBus abstraction  │
                              └──────┬──────────────┬───────┘
                                     │              │
                      Responses API  │              │  SQL
                                     ▼              ▼
                          ┌──────────────────┐  ┌───────────────┐
                          │  Bifrost gateway │  │  postgres     │
                          │  (self-hosted,   │  │               │
                          │  docker)         │  │  - rehketo DB │
                          │                  │  │  - bifrost DB │
                          │  → Anthropic     │  │               │
                          │  Claude Sonnet   │  │               │
                          └──────────────────┘  └───────────────┘
                                     │
                                     ▼
                           ┌──────────────────┐
                           │ Entra (identity) │
                           │ + Graph (future  │
                           │  via connections)│
                           └──────────────────┘
```

### Deployment shape

Docker Compose lives under `rehketo-api/deploy/` (tracked in the rehketo-api git repo, which owns local-dev orchestration for v1). Services:

- `postgres` — single instance. Two databases: `rehketo` for the app (schema plus LangGraph checkpointer tables), `bifrost` for Bifrost's governance and state. Named volume `pgdata`. No cross-database foreign keys.
- `bifrost` — self-hosted Bifrost image. Config file mounted read-only. Named volume for any persistent state it keeps outside postgres.
- `rehketo-api` — FastAPI + uvicorn. Dev mode mounts `rehketo-api/` for hot reload. Production image builds the frozen dependency set via `uv`.
- `rehketo-ui` — dev: Vite dev server. Prod: static bundle served by rehketo-api under `/` (or by a CDN / nginx in a later production setup). No Node runtime in production.

Production note: enable HTTP/2 at the edge (reverse proxy or uvicorn with `h2` support) so SSE streams aren't capped by browser per-origin HTTP/1.1 connection limits.

### Process model

- **v1:** rehketo-api is a single uvicorn worker. The agent loop runs as a background `asyncio.Task` within that process, writing LangGraph checkpoints to postgres as it goes. The POST that starts a run returns `{run_id}` in milliseconds; the browser subscribes to SSE for live events.
- **Fast-follow (v1.1):** event bus moves from in-process to postgres LISTEN/NOTIFY (see §6.2). This enables (a) multiple uvicorn workers, (b) moving agent execution into a separate worker process with zero change to API handlers, agent code, or the UI contract.

## 3. Auth architecture (Pattern B)

### App registrations

Two Entra app registrations:

- **rehketo-ui** — SPA / public client, PKCE, no client secret. Its only job is to initiate login by redirecting to rehketo-api's `/auth/login`. It does not hold tokens.
- **rehketo-api** — confidential client. Handles the Entra callback, exchanges authorization code for tokens, stores the refresh token server-side, sets the session cookie. Exposes scopes under `api://rehketo-api/...` for any future external API consumers.

### Session model

- `httpOnly`, `Secure`, `SameSite=Lax` cookie with an opaque session id. `Lax` (not `Strict`) is chosen because the OAuth callback redirect is a cross-site top-level navigation, and because deep links to rehketo from email / messaging clients should land the user in their session. The residual CSRF attack surface (top-level navigation CSRF) is covered by the double-submit CSRF tokens required on state-changing endpoints.
- **Elevation for dangerous operations (committed, not v1).** When rehketo gains actions with significant blast radius — admin operations, destructive account actions, permission grants, connection revocation that affects others — the auth model adds a second cookie, `session_elevated`, set to `SameSite=Strict` and scoped to endpoints that require it. Elevation is granted via a short re-authentication step (OIDC prompt or MFA challenge) and has its own, shorter TTL independent of the main session. Endpoints that require elevation declare it via a FastAPI dependency, analogous to `resolve_permissions`. This is orthogonal to permissions: `check_permission` asks "is this user allowed?"; elevation asks "has this user recently proven their identity strongly enough to do this *right now*?" Both gates must pass. Elevation is **not** part of v1 (no dangerous actions exist yet) but ships as part of the same increment that introduces the first such action.
- Session rows live in postgres; the refresh token column is encrypted at rest (envelope encryption with an app key, or `pgcrypto`).
- Access tokens are short-lived and held only in in-memory cache keyed by session, refreshed on demand using the stored refresh token.
- Cookie rotates on elevation events: login, connection-consent grant, explicit rotation.
- CSRF protection: double-submit cookie token for state-changing endpoints.

### Identities vs Connections

Authorization to downstream APIs is modeled separately from identity. This keeps login minimal and makes adding providers or capabilities additive.

- **Identity** = "who is logged in." One primary provider per user, resolved from the session cookie.
- **Connection** = "what external account has the user linked, and with what scopes?" Zero or more per user. Each connection holds its own refresh token tagged with provider + scopes.

v1 has identities (Entra). v1 has no connections yet; the tables exist and the code paths for consent and refresh are scaffolded but not exercised.

### Permission checks

Every endpoint depends on `Depends(resolve_permissions)`, which returns a `ResolvedPermissions` object with a single method:

```python
permissions.can(action: str, resource_id: str | None = None) -> bool
```

Handlers and agent code call `permissions.can("chat.write", conversation_id)` before touching a resource. The agent runs **as the user** — when it reads or writes any rehketo data on behalf of a user, it calls `check_permission` with the user's identity. The agent cannot exceed user permissions.

### Delegation to downstream APIs

When v1.x adds its first connection-using feature (for example, "summarize my inbox" calling Microsoft Graph), the agent looks up the user's connection row for the required provider and scopes, refreshes the access token if needed, and calls the downstream API. Tokens never touch the browser.

## 4. Data model

All tables in the `rehketo` postgres database unless noted. LangGraph checkpointer tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) are managed by LangGraph's migrations and live in the same database but isolated from app tables. Bifrost's tables live in the separate `bifrost` database.

```sql
-- Identity
users (
  id uuid primary key,
  display_name text,
  email citext,
  created_at timestamptz not null default now()
)

identities (
  provider text not null,           -- 'entra', later 'google', etc.
  provider_subject text not null,   -- oid / sub from the IdP
  user_id uuid not null references users(id),
  created_at timestamptz not null default now(),
  primary key (provider, provider_subject)
)

sessions (
  id uuid primary key,              -- cookie value
  user_id uuid not null references users(id),
  identity_provider text not null,
  refresh_token_ct bytea not null,  -- encrypted
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
)

connections (
  id uuid primary key,
  user_id uuid not null references users(id),
  provider text not null,
  provider_account_id text not null,
  scopes text[] not null,
  refresh_token_ct bytea not null,       -- encrypted
  access_token_cache_ct bytea,           -- optional short-lived cache
  expires_at timestamptz,
  status text not null,                  -- 'active','expired','revoked'
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (user_id, provider, provider_account_id)
)

-- Authorization (v1: role-based behind the check_permission gate)
user_roles (
  user_id uuid not null references users(id),
  role text not null,
  primary key (user_id, role)
)

-- Chat domain
conversations (
  id uuid primary key,
  user_id uuid not null references users(id),
  title text,                            -- null until first run completes
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
)

runs (
  id uuid primary key,
  conversation_id uuid not null references conversations(id),
  user_id uuid not null references users(id),   -- denormalized for authz
  status text not null,                          -- 'queued','running','succeeded','failed','cancelled'
  error jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  model text not null,
  created_at timestamptz not null default now()
)

messages (
  id uuid primary key,
  conversation_id uuid not null references conversations(id),
  role text not null,                    -- 'user','assistant','system','tool'
  content jsonb not null,                -- Responses-API content parts
  run_id uuid references runs(id),       -- null for user-authored messages
  created_at timestamptz not null default now()
)

-- Event bus (v1 schema includes this; v1 code does not read from it.
-- v1.1 postgres event bus reads/writes here.)
run_events (
  id bigserial primary key,
  run_id uuid not null references runs(id),
  sequence bigint not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id, sequence)
)
```

Indexes at least on: `conversations(user_id, updated_at desc)`, `messages(conversation_id, created_at)`, `runs(conversation_id, created_at desc)`, `runs(status) where status in ('queued','running')`, `run_events(run_id, sequence)`.

## 5. Authorization design

### v1 implementation

- A single module `rehketo.permissions.actions` defines the canonical action vocabulary (dotted lowercase names). The UI imports the same list through a generated TypeScript definition so both sides agree on action names.

  Initial action vocabulary (not exhaustive):
  ```
  chat.create_conversation
  chat.view_conversation
  chat.rename_conversation
  chat.delete_conversation
  chat.write            -- post a user message / start a run
  chat.cancel_run
  chat.upload_files     -- declared now; not enforced until file support lands
  admin.manage_users
  admin.view_audit
  ```

- A role-to-permission dict (`ROLE_PERMISSIONS`) maps the initial roles (`Admin`, `Moderator`, `User`) to sets of action strings.
- `check_permission(user_id, action, resource_type, resource_id=None)` resolves the user's roles, unions their permissions, and checks membership. Resource scoping is accepted on the signature but not yet evaluated in v1.
- `ResolvedPermissions` wraps this for FastAPI dependencies: handlers receive one object and call `permissions.can(action, resource_id)` throughout.

### Forward compatibility: OpenFGA is the target

v1 uses RBAC but treats `check_permission` as an interface, explicitly not an implementation. When the system needs resource-scoped checks (sharing conversations, workspace hierarchies, per-resource overrides), OpenFGA replaces the implementation. The migration path is pre-designed:

- **No handler bypasses the gate.** Every permission decision flows through `check_permission`. No handler reads roles directly.
- **Action vocabulary is already canonical.** Action names change one-for-one between v1 RBAC and OpenFGA relations.
- **Ownership facts are recorded at creation time** via `conversations.user_id`. At cutover, a one-time migration reads that column and writes `user:<id> owner conversation:<id>` tuples into OpenFGA.
- **Resource ids are always passed** even when v1 doesn't use them, so the call sites don't change at cutover.

At cutover we add OpenFGA and its database to docker-compose, upload the authorization model, run the backfill migration, and swap `check_permission`'s body to delegate to OpenFGA's `check` API (and `/me/capabilities` to use `batch-check`). Handlers, agent code, and the UI contract are untouched.

Sketch of the OpenFGA model for later (included here so the v1 action vocabulary aligns with it):

```
model
  schema 1.1

type user

type workspace
  relations
    define admin: [user]
    define member: [user] or admin

type conversation
  relations
    define workspace: [workspace]
    define owner: [user]
    define viewer: [user] or owner or member from workspace
    define can_upload: owner or admin from workspace
    define can_delete: owner or admin from workspace
```

## 6. Agent execution and runs

### 6.1 Run lifecycle

```
queued ──▶ running ──▶ succeeded
                 │
                 ├────▶ failed
                 ├────▶ cancelled
                 └────▶ abandoned   (v1 only: process restart while running)
```

On startup, rehketo-api runs a sweep that marks any `running` runs as `failed` with `error.code = "process_restart"`. The LangGraph checkpointer still holds state for those runs; v1.x will use that state to resume instead of failing, once agents execute in a dedicated worker process that supports restart-safe resumption.

### 6.2 RunEventBus abstraction

A single interface, swappable implementation:

```python
class RunEventBus(Protocol):
    async def publish(self, run_id: str, event: dict) -> None: ...
    async def subscribe(
        self,
        run_id: str,
        from_sequence: int | None = None,
    ) -> AsyncIterator[dict]: ...
```

- **v1: `InProcessEventBus`** — an asyncio-queue-per-run plus a short ring buffer so subscribers joining slightly after a publish don't miss events. Sequence numbers assigned from a per-run counter.
- **v1.1 fast-follow: `PostgresEventBus`** — `publish` inserts into `run_events` and issues `NOTIFY`. `subscribe` tails the table by `sequence`, wakes on `LISTEN`. Sequence comes from `run_events.sequence`. Durable, multi-process safe, survives restarts.

Agent code, the SSE handler, and the UI depend only on the interface. Cutover is a wiring change in one DI location; the `run_events` table ships in the v1 schema so no migration is needed at cutover.

### 6.3 Agent execution flow

```
POST /conversations/{id}/messages
  1. permissions.can("chat.write", conversation_id)   -- 403 if denied
  2. INSERT messages (role='user', content=...)
  3. INSERT runs (status='queued', model='claude-sonnet-4-6')
  4. asyncio.create_task(run_agent(run_id))
  5. return 202 { message_id, run_id }                 -- milliseconds

run_agent(run_id):
  1. UPDATE runs SET status='running', started_at=now()
  2. event_bus.publish(run_id, {"type": "run.status", "status": "running"})
  3. load conversation history from messages table
  4. build deepagents graph with:
       - ChatOpenAI(base_url=<bifrost>, use_responses_api=True,
                    model="claude-sonnet-4-6")
       - postgres checkpointer, thread_id=run_id
       - empty tool registry (v1)
  5. async for chunk in graph.astream(..., stream_mode="messages"):
         event = transform(chunk)
         await event_bus.publish(run_id, event)
  6. success:
       INSERT messages (role='assistant', content=final, run_id=...)
       UPDATE runs SET status='succeeded', finished_at=now()
       event_bus.publish(run_id, {"type": "run.status",
                                  "status": "succeeded"})
  7. error:
       UPDATE runs SET status='failed', error=..., finished_at=now()
       event_bus.publish(run_id, {"type": "run.status",
                                  "status": "failed", "error": ...})
  8. asyncio.CancelledError:
       UPDATE runs SET status='cancelled', finished_at=now()
       event_bus.publish(run_id, {"type": "run.status",
                                  "status": "cancelled"})
```

Every external call inside `run_agent` is awaited (httpx for Bifrost, asyncpg or psycopg3-async for postgres, LangGraph's async API). Dozens of concurrent runs and hundreds of other requests interleave cleanly on one event loop.

### 6.4 SSE event schema

Our schema, not a passthrough of upstream Responses events. The transform layer maps LangGraph's stream to a stable, versioned shape so the UI doesn't depend on upstream internals.

```json
// run status transitions
{"type": "run.status", "run_id": "...", "status": "running|succeeded|failed|cancelled", "sequence": 0}

// assistant message under construction — one delta per chunk
{"type": "message.delta", "run_id": "...", "message_id": "...", "delta": "partial text", "sequence": 1}

// a complete message has been persisted
{"type": "message.complete", "run_id": "...", "message": { /* full row */ }, "sequence": 2}

// tool events — shape defined, zero emitted in v1
{"type": "tool.call", "run_id": "...", "tool": "...", "arguments": {...}, "call_id": "...", "sequence": 3}
{"type": "tool.result", "run_id": "...", "call_id": "...", "result": {...}, "sequence": 4}

// terminal error
{"type": "error", "run_id": "...", "error": {"code": "...", "message": "..."}, "sequence": 99}
```

Each event carries a per-run monotonic `sequence`. SSE clients that disconnect can reconnect with `GET /runs/{run_id}/events?from_sequence=N` and resume without loss.

### 6.5 Cancellation (v1)

```
POST /runs/{run_id}/cancel
  - permissions.can("chat.cancel_run", conversation_id)
  - look up the process-local task handle keyed by run_id
  - task.cancel()
  - run_agent catches CancelledError, finalizes state, publishes event
```

v1 constraint: cancellation only works in the same process that started the run. This is acceptable for single-worker v1. After the postgres event-bus cutover, cancellation becomes a row update plus `NOTIFY`, and any process holding the run reacts.

## 7. API surface (v1)

All endpoints except `/auth/*` require a valid session cookie and run through `resolve_permissions`.

```
# Conversations
POST   /conversations                                  -> create; {id}
GET    /conversations                                  -> list (user's own)
GET    /conversations/{id}                             -> detail + messages
PATCH  /conversations/{id}                             -> rename / archive
DELETE /conversations/{id}                             -> soft-delete

# Messages + runs
POST   /conversations/{id}/messages                    -> create user message + kickoff run;
                                                           returns {message_id, run_id}
GET    /runs/{run_id}                                  -> run status
GET    /runs/{run_id}/events                           -> SSE stream
POST   /runs/{run_id}/cancel                           -> request cancellation

# Identity
GET    /me                                             -> current user summary
GET    /me/capabilities?resource_type=&resource_id=    -> allowed action names

# Auth (Pattern B)
GET    /auth/login                                     -> 302 to Entra
GET    /auth/callback                                  -> exchange code, set cookie, 302 to UI
POST   /auth/logout                                    -> revoke session, clear cookie
```

A post-run title-generation task (async, best-effort) sets `conversations.title` after the first successful run by prompting Bifrost to summarize the opening exchange.

## 8. Bifrost integration

- rehketo-api calls Bifrost via an OpenAI-compatible HTTP client configured for the Responses API. LangChain's `ChatOpenAI(base_url=<bifrost>, use_responses_api=True, model="claude-sonnet-4-6")` is the integration point; deepagents and LangGraph consume it.
- Bifrost's config lives in a file mounted into its container, version-controlled in the repository. The config declares the Anthropic provider, the default model, and any routing rules we want (none meaningful in v1; room for fallbacks later).
- Bifrost uses the `bifrost` postgres database for its own governance and logs.
- Provider swap is a Bifrost config change plus (possibly) a model-name change in rehketo-api. No other code changes.

## 9. Frontend (rehketo-ui)

- **Stack:** SvelteKit with `@sveltejs/adapter-static`. No SvelteKit server in production. Routing, layouts, and build ergonomics from SvelteKit; a static bundle as the output.
- **Auth:** browser has no token handling. A login button navigates to `/auth/login`, which the API handles end-to-end before redirecting back with the session cookie set.
- **State:** thin. Source-of-truth state lives server-side. The UI caches what it needs to render the current view (current conversation, message list, streaming run buffer) and subscribes to SSE for the active run.
- **Capabilities:** the UI calls `/me/capabilities` to hide/disable actions. Enforcement is always server-side; capabilities are render hints only.
- **v1 screens:** login landing, conversation list (sidebar), chat view (messages + composer + live run stream), basic settings (display name, logout).

## 10. Error handling

- **LLM transient error (network, Bifrost 5xx, provider rate limit):** one retry with short backoff inside the graph. If unrecoverable, `error.code = "llm_failure"` with the Bifrost error payload; run fails.
- **Checkpointer write failure:** fatal to the run. `error.code = "checkpointer_failure"`. The user message is already persisted; no assistant message is written.
- **Session expired mid-run:** the run continues (authorization was checked at start). The next UI action will 401 and trigger re-auth.
- **SSE subscriber disconnect mid-run:** the agent keeps running. The UI reconnects with `?from_sequence=` and picks up where it left off.
- **Process restart with runs in flight:** startup sweep marks orphaned `running` runs as `failed` with `error.code = "process_restart"`.
- **Cancellation:** treated as a normal terminal state, not an error.

All API errors return a stable JSON envelope: `{"error": {"code": "...", "message": "..."}}` with appropriate HTTP status. No provider error text ever leaks to the browser — error messages for UI consumption are curated.

## 11. Testing

- **Unit:** `check_permission` implementations, role-to-permission mapping, event bus publish/subscribe (contract tests written once so that both the v1 in-process bus and the v1.1 postgres bus must pass the same suite), message persistence, run state transitions, SSE event transform.
- **Integration:** a fake Bifrost server (`httpx` with `respx`, or a small local stub) feeding canned Responses-API streams. Real postgres via Testcontainers. Real checkpointer writes. No mocked DB.
- **E2E smoke:** `docker compose up` the full stack, drive rehketo-api with an httpx client, assert golden transcripts (POST user message → observe run events → assert final assistant message and run status).

## 12. v1 scope boundaries (explicit)

**In v1:**
- Single-provider identity (Entra), Pattern B sessions.
- Conversations, messages, runs; run lifecycle including cancellation.
- SSE streaming of run events with a stable schema and resume-by-sequence.
- deepagents + LangGraph with postgres checkpointer; empty tool registry.
- Bifrost routing to Claude Sonnet 4.6 via Responses API.
- Role-based authorization through the `check_permission` gate with resource-scoped signatures.
- Docker Compose stack: postgres (two DBs), bifrost, rehketo-api, rehketo-ui dev server.

**Not in v1 (architecture-ready, not built):**
- Tool registry populated with any tools.
- Connections (downstream API delegation).
- Multi-worker API / separate worker process for agents.
- Postgres event bus (in-process for v1).
- OpenFGA (RBAC in v1, gate interface is OpenFGA-ready).
- Additional identity providers.
- Agent long-term memory.

## 13. Fast-follow increments (sequencing after v1 ships)

1. **Postgres event bus cutover.** Swap `InProcessEventBus` for `PostgresEventBus`. Enables multi-worker deploy and lays the groundwork for a separate agent worker process.
2. **Separate agent worker process.** API process only creates `queued` runs and serves SSE. A worker process claims and drives them. Handlers and UI contract unchanged. Restart-safe resumption via checkpointer.
3. **First real tool.** Validate the tool-calling path end-to-end through Bifrost + Responses + deepagents with a well-scoped tool (web search is the likeliest first pick).
4. **Connections + first downstream-API-using capability.** Wire the consent flow and refresh mechanism end-to-end with one concrete use case (e.g., MS Graph mail read).
5. **OpenFGA migration.** Introduce the service, upload the model, backfill tuples, swap `check_permission`'s body.
6. **Elevation (bundled with the first dangerous action).** Whenever the first action with significant blast radius lands (admin ops, destructive user actions, permission grants), introduce the `session_elevated` cookie, the re-authentication endpoint, and the `requires_elevation` dependency alongside it. Not time-based; gated on the first action that warrants it.

## 14. Open decisions (tracked for the implementation plan)

- Choice of async postgres driver (asyncpg vs psycopg3 in async mode). LangGraph's postgres checkpointer supports psycopg; using the same driver for app data keeps the stack uniform. Tentatively: psycopg3.
- Encryption approach for `refresh_token_ct` / `access_token_cache_ct`: app-side envelope (fernet with a key from the runtime secret) vs `pgcrypto`. Default: app-side envelope for portability; revisit at the OpenFGA milestone.
- Exact MSAL library for the Entra flow in rehketo-api (`msal` vs `msal-extensions` vs a direct OIDC library). Default: `msal` for provider coverage and ergonomics.
- Title-generation model: same model as chat (Claude Sonnet 4.6) vs a cheaper model routed via Bifrost. Default: same model for v1 simplicity.

## 15. Risks and mitigations

- **Responses-API translation gaps across providers.** Bifrost translates Responses calls to each provider's native API; some Responses-specific features may not round-trip. Mitigation: v1 stays on the well-translated subset (prompt → stream → optional tool calls). We do not rely on provider-native Responses features (`previous_response_id`, `background: true`, built-in tools) because the architecture owns those concerns.
- **LangGraph checkpointer schema changes.** Upstream schema evolutions could require coordinated migrations. Mitigation: pin LangGraph version, isolate checkpointer tables in their own migration lineage, test upgrades before rolling.
- **In-process asyncio task loss on restart** (v1 only). Mitigation: startup sweep marks orphaned runs as failed with a clear code; fast-follow #2 removes the class of risk entirely.
- **Cookie/CSRF misconfiguration.** Mitigation: canonical auth module, integration tests that assert `SameSite`, `HttpOnly`, `Secure`, and double-submit token behavior end-to-end.
