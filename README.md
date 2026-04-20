# Rehketo API

Backend for the Rehketo chat application. FastAPI + async SQLAlchemy over psycopg3, deepagents + LangGraph for orchestration, Bifrost (MaximHQ) in front of Claude Sonnet 4.6 via the Responses API.

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` for the implementation plans this codebase has executed.

## What's in the box (v1)

- Entra OIDC auth — Pattern B (cookie session, backend-held refresh tokens). A `/auth/devonly/login` endpoint is gated behind `DEVONLY_LOGIN_ENABLED` for local dev and tests.
- Double-submit CSRF middleware on all unsafe methods.
- Canonical action vocabulary + RBAC gate (`check_permission`) behind a single seam that will swap to OpenFGA later.
- Conversations CRUD; `/me` and `/me/capabilities`.
- Runs as first-class entities, driven by deepagents + LangGraph with a postgres checkpointer.
- SSE streaming at `GET /runs/{id}/events` with `?from_sequence=N` resume.
- Cancellation; startup sweep for runs abandoned by the previous process; best-effort conversation-title generation.

## Prerequisites

- Docker Desktop (or equivalent — the stack runs on vanilla `docker compose`).
- [`uv`](https://docs.astral.sh/uv/) with Python 3.14 available.
- An Entra app registration with redirect URI `http://127.0.0.1:8000/auth/callback`. For the ship-check below you can skip real Entra login and use `/auth/devonly/login` instead — you still need the client id / tenant id / client secret in env so the app starts cleanly.
- An **Anthropic API key** for live chat turns, supplied to Bifrost through its admin UI (the test suite does not need one — tests mock Bifrost).

---

## Quick start — ship-check Plan 2 end-to-end

This takes you from a fresh checkout to streaming a real Claude Sonnet response through Bifrost.

### 1. Copy env templates

From `rehketo-api/`:

```bash
cp .env.example .env
cp deploy/.env.example deploy/.env
```

Fill in `rehketo-api/.env`:

- `SESSION_ENCRYPTION_KEY` — a Fernet key. Generate one:
  ```bash
  uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `CSRF_SIGNING_KEY` — any long random string (≥ 32 chars).
  ```bash
  uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET` — from your app registration. Values do not have to be correct for devonly login; they only gate app startup.
- `DEVONLY_LOGIN_ENABLED=true` — enables `/auth/devonly/login`.

Fill in `deploy/.env`:

- `ANTHROPIC_API_KEY` — your Anthropic key. Bifrost reads it via `${ANTHROPIC_API_KEY}` in `deploy/bifrost/config.yaml`.

### 2. Bring up postgres + Bifrost

From `rehketo-api/deploy/`:

```bash
docker compose up -d postgres bifrost
docker compose logs -f bifrost
```

The `postgres/init/00-create-databases.sh` script creates both `rehketo` (app) and `bifrost` (gateway state) databases on first boot. If you previously ran the stack with a different config, `docker compose down -v` first to wipe `pgdata`.

### 3. Configure Bifrost through its UI

Bifrost manages its own config at `/app/data/config.json` (persisted via the `bifrost_data` volume). Providers and model aliases are **not** baked into a mounted config file — configure them once through the Bifrost admin UI:

1. Open <http://localhost:8088> in a browser.
2. Add an **Anthropic** provider and paste your Anthropic API key.
3. Register a model alias named exactly **`claude-sonnet-4-6`** routed to Anthropic (that's the name `rehketo-api` sends; the `AGENT_MODEL` env var is the single seam if you ever want to rename it).
4. Ensure the OpenAI-compatible **Responses API** surface is enabled so LangChain's `ChatOpenAI(use_responses_api=True)` can speak to Bifrost unchanged.

This survives container restarts as long as the `bifrost_data` volume is kept.

### 4. Install deps + migrate

From `rehketo-api/`:

```bash
uv sync
uv run alembic upgrade head
```

This creates the 9 app tables plus the LangGraph checkpointer's 4 tables.

### 5. Seed a user and grant a role

The devonly login endpoint creates the user on first call and assigns the roles you pass in. No seeding script needed for the smoke test.

### 6. Run the API

```bash
uv run uvicorn rehketo.main:app --reload --host 127.0.0.1 --port 8000
```

Leave this running in its own terminal.

### 7. Smoke test a full chat turn

From a second terminal. Save cookies between requests with `curl -c cookies.txt -b cookies.txt`.

```bash
# 1. Log in (creates the user on first call).
curl -sS -c cookies.txt -b cookies.txt \
  -X POST http://127.0.0.1:8000/auth/devonly/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","display_name":"Me","roles":["User"]}'

# Pull the CSRF cookie out for the next requests.
CSRF=$(grep rehketo_csrf cookies.txt | awk '{print $NF}')

# 2. Create a conversation.
CONV_ID=$(curl -sS -c cookies.txt -b cookies.txt \
  -X POST http://127.0.0.1:8000/conversations \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -d '{}' | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "conversation: $CONV_ID"

# 3. Post a message — this kicks off the agent.
RUN_ID=$(curl -sS -c cookies.txt -b cookies.txt \
  -X POST "http://127.0.0.1:8000/conversations/$CONV_ID/messages" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"content":"Write a haiku about postgres."}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')
echo "run: $RUN_ID"

# 4. Stream the events. Ctrl-C after you see run.status=succeeded.
curl -N -b cookies.txt "http://127.0.0.1:8000/runs/$RUN_ID/events"

# 5. Fetch the conversation — should show user + assistant messages.
curl -sS -b cookies.txt "http://127.0.0.1:8000/conversations/$CONV_ID" | python -m json.tool
```

You should see a stream like:

```
event: run.status
data: {"type":"run.status","status":"running",...}

event: message.delta
data: {"type":"message.delta","delta":"A ","message_id":"...","sequence":1,...}

event: message.delta
data: {"type":"message.delta","delta":"quiet ","message_id":"...","sequence":2,...}

... more deltas ...

event: message.complete
data: {"type":"message.complete","message":{...}}

event: run.status
data: {"type":"run.status","status":"succeeded",...}
```

And the final `GET /conversations/{id}` response will contain both the user message and the assembled assistant message.

### 8. Verify conversation title (best-effort)

After the first successful run, a background task asks Bifrost for a 4-word title. Re-fetch the conversation a few seconds later — `title` should be populated.

---

## Development

```bash
uv run pytest                                          # full suite, ~15 s
uv run pytest tests/unit -v                            # unit only, sub-second
uv run pytest tests/integration/test_foo.py::test_bar  # single test

uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo
```

Pre-commit hooks gate the same checks. After the first clone:

```bash
uv run pre-commit install
```

Integration tests use `testcontainers[postgres]` to spin up a real `postgres:17` container per pytest invocation. The testcontainers URL is rewritten to use `127.0.0.1` instead of `localhost` to avoid Windows IPv6-fallback stalls; see `tests/conftest.py::_sa_url`.

## Project layout

See `AGENTS.md` for conventions (every contributor starts there). Short version:

```
rehketo/
  main.py                  # app factory + lifespan + routers
  config.py                # Settings via pydantic-settings
  core/logging.py          # sanitizing uvicorn-hierarchy logger
  db/                      # engine + SQLAlchemy models
  auth/                    # crypto, csrf, cookies, sessions, entra, dependencies
  permissions/             # actions vocabulary, roles, check_permission, deps
  api/                     # FastAPI routers (auth, conversations, messages, runs, me)
  runs/                    # RunEventBus + task registry
  agent/                   # llm, graph, events, run orchestrator, sweep, title
alembic/versions/          # 0001 auth, 0002 chat, 0003 langgraph checkpointer
tests/
  unit/                    # pure functions, no DB
  integration/             # real postgres, httpx ASGI client, respx for Bifrost
deploy/
  docker-compose.yaml      # postgres + bifrost
  postgres/init/           # multi-db init script
```

## Troubleshooting

**Bifrost fails to start** — check `docker compose logs bifrost`. If it complains about postgres DSN, confirm the `bifrost` database exists (`docker compose exec postgres psql -U rehketo -l`). If provider config appears missing, re-open <http://localhost:8088> and add Anthropic + the `claude-sonnet-4-6` model alias; Bifrost persists these to the `bifrost_data` volume.

**`POST /conversations/{id}/messages` returns 202 but no SSE events flow** — usually means Bifrost can't reach Anthropic. Check `docker compose logs bifrost` for 401s or network errors. Confirm `ANTHROPIC_API_KEY` is set in `deploy/.env` and that the Bifrost container env actually has it (`docker compose exec bifrost env | grep ANTHROPIC`).

**Windows: alembic hangs or tests take forever** — the `_sa_url` fix rewrites `localhost` → `127.0.0.1` for test connections. If you see similar latency in your own scripts, do the same on any connection URL you build.

**`alembic upgrade` errors on nested event loop** — migration 0003 runs the LangGraph checkpointer's async `setup()` inside a thread with its own event loop to dodge Windows's ProactorEventLoop. If you see `RuntimeError: asyncio.run() cannot be called from a running event loop`, you're likely on a codepath that bypassed that shim — file it.

**Entra callback rejects the redirect** — the redirect URI in the app registration must match `ENTRA_REDIRECT_URI` exactly. Default is `http://127.0.0.1:8000/auth/callback`.

**Pre-commit isn't running on commit** — `uv run pre-commit install` once in `rehketo-api/`. If you've already committed bypassing hooks, `uv run pre-commit run --all-files` will replay the checks.
