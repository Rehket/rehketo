# Plan 2 — Runs + Agent + SSE

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing chat scaffolding actually chat. Extend rehketo-api with runs as first-class entities, a deepagents + LangGraph graph that streams from Claude Sonnet 4.6 through Bifrost, and an SSE endpoint the UI will subscribe to. End state: a user posts a message, a `run_id` comes back in milliseconds, and the UI (or an httpx client) consumes a server-sent-events stream of token deltas and persists messages for every turn. Still no tools registered (that's a Plan 2.x follow-up); still single-process; still no UI (Plan 3).

**Architecture (from the spec, summarized):** `POST /conversations/{id}/messages` creates the user `messages` row, creates a `runs` row in `queued`, spawns an `asyncio.Task` to drive the agent, returns `{message_id, run_id}`. The task transitions the run to `running`, builds a deepagents graph with a LangGraph postgres checkpointer, and calls `graph.astream(...)`. Chunks are transformed into our stable event schema (`run.status`, `message.delta`, `message.complete`, `tool.call`, `tool.result`, `error`) and published to an `InProcessEventBus` (v1; postgres LISTEN/NOTIFY impl is the fast-follow after Plan 2 ships). The SSE endpoint `GET /runs/{id}/events` subscribes and streams to the browser, with `?from_sequence=N` for reconnect. Cancellation via a process-local task registry. On app startup, a sweep marks any `running` row abandoned by the previous process as `failed`.

**Tech Stack:** deepagents + langgraph + langchain-openai (pointed at Bifrost via OpenAI-compatible URL, `use_responses_api=True`, model `claude-sonnet-4-6`), LangGraph's postgres checkpointer (its own tables in the `rehketo` database, managed by its own migrations), sse-starlette for SSE responses, respx for mocking Bifrost in tests. Everything async-all-the-way-down so the single-worker event loop interleaves dozens of concurrent runs + hundreds of other requests cleanly.

**Reference spec:** `docs/superpowers/specs/2026-04-19-chat-and-agent-v1-design.md` — §§ 2, 6, 7, 10, 11 are directly relevant. Read them before starting.

**Reference AGENTS.md:** `D:/Workspace/rehketo/rehketo-api/AGENTS.md`. Non-negotiable; overrides anything below on conflict.

---

## Prerequisites before executing this plan

1. **Bifrost can reach Anthropic.** You need an `ANTHROPIC_API_KEY` in the Bifrost container's env (via `deploy/.env`) and the Bifrost config must declare the provider. If `ANTHROPIC_API_KEY` isn't available to you, flag it before starting and we'll stub out the Bifrost config with a mock server. Integration tests in this plan do NOT require a real key (they use respx against Bifrost's URL).
2. **pre-commit hooks installed.** Run `pre-commit install` once in `rehketo-api/` if you haven't.
3. **Postgres container is up** (`docker compose -f deploy/docker-compose.yaml up -d postgres`). LangGraph's postgres checkpointer uses the same `rehketo` database.
4. **Plan 1 is on `main` (or on this branch).** Plan 2 assumes Plan 1's schema (runs, messages, run_events tables already exist; conversations + permissions + auth + session fixtures + etc.).

## File structure (net additions)

```
rehketo-api/
  rehketo/
    runs/
      __init__.py                    # NEW (empty)
      event_bus.py                   # NEW (Protocol + InProcessEventBus)
      registry.py                    # NEW (process-local task registry)
    agent/
      __init__.py                    # NEW (empty)
      llm.py                         # NEW (ChatOpenAI -> Bifrost factory)
      graph.py                       # NEW (deepagents graph + postgres checkpointer)
      events.py                      # NEW (LangGraph chunk -> our SSE schema)
      run.py                         # NEW (run_agent coroutine)
      sweep.py                       # NEW (startup sweep)
    api/
      messages.py                    # NEW (POST /conversations/{id}/messages)
      runs.py                        # NEW (GET /runs/{id}, SSE, cancel)
    main.py                          # MODIFY (include routers, install sweep + checkpointer setup)
  alembic/versions/
    0003_langgraph_checkpointer.py   # NEW — creates LangGraph's tables in our DB
  deploy/
    bifrost/config.yaml              # MODIFY — populate provider routing for Claude via Responses
    .env.example                     # MODIFY — add ANTHROPIC_API_KEY line
  tests/
    unit/
      test_event_bus_contract.py     # NEW — contract the postgres impl will also pass
      test_agent_events_transform.py # NEW — pure LangGraph-chunk → schema mapping
    integration/
      test_post_messages_kicks_run.py # NEW
      test_run_agent_end_to_end.py    # NEW — respx-mocked Bifrost
      test_sse_resume_by_sequence.py  # NEW
      test_run_cancel.py              # NEW
      test_startup_sweep.py           # NEW
      test_e2e_chat_smoke.py          # NEW — full login → message → stream → logout
```

## Key discipline carryovers from Plan 1

- **FastAPI `Annotated[T, Depends(...)]`**: import `T` at runtime (not TYPE_CHECKING). `# noqa: TC002` when ruff complains.
- **Parameter order**: Depends params before params with Python defaults.
- **`permissions.require(...)` on every data-touching endpoint**, with `resource_id` always passed.
- **Tests hit real postgres via testcontainers.** The existing `db_url` / `db` fixtures in `tests/conftest.py` still apply. Bifrost is mocked with `respx`.
- **No AI attribution in commits.** Conventional Commits.
- **Logger via `rehketo.core.logging.get_logger`.** No `print()`.

## Open callouts / decisions

- **LangGraph checkpointer driver**: LangGraph provides `langgraph-checkpoint-postgres` which ships with a psycopg3 sync backend and an async backend. Use the async backend to stay uniform with the rest of the stack. The checkpointer manages its own tables via its own `setup()` method — we still write migration `0003_langgraph_checkpointer.py` as a thin wrapper that invokes that setup so ops stays in Alembic-land.
- **Cancellation semantics**: best-effort. `task.cancel()` raises `CancelledError` inside `run_agent`, which finalizes the DB state and publishes a terminal event. Runs in-flight at LLM-call time may actually cancel immediately; runs mid-DB-write may finish the write then exit. Both are acceptable.
- **SSE framing**: use `sse-starlette`'s `EventSourceResponse` so the library handles keep-alives, headers, and proper chunked framing. Don't hand-roll.
- **Event `sequence` is per-run monotonic.** The in-process bus uses a counter; the future postgres bus will use a serial column. Both produce the same ordering per `run_id`.
- **Title generation**: tracked as task T18. Fires once per conversation, best-effort, async; if it fails (e.g., Bifrost unreachable) the run itself is unaffected.

## Environment additions

Append to `rehketo-api/.env.example`:
```
BIFROST_BASE_URL=http://localhost:8088/v1
BIFROST_API_KEY=dev-noop
AGENT_MODEL=claude-sonnet-4-6
```

Append to `deploy/.env.example`:
```
ANTHROPIC_API_KEY=
```

Append to `rehketo/config.py` Settings:
```python
bifrost_base_url: str = "http://localhost:8088/v1"
bifrost_api_key: SecretStr = SecretStr("dev-noop")
agent_model: str = "claude-sonnet-4-6"
```

---

## Task 1: Dependencies

**Files:**
- Modify: `rehketo-api/pyproject.toml`
- Modify: `rehketo-api/uv.lock`

Add runtime deps:
- `deepagents>=0.5.3` (back — we dropped it in Plan 1 T2)
- `langgraph>=0.2.0`
- `langgraph-checkpoint-postgres>=2.0.0`
- `langchain-openai>=0.2.0`
- `sse-starlette>=2.1.0`

- [ ] **Step 1: Edit pyproject.toml**

In `[project].dependencies`, add the five lines above alphabetically integrated with the existing list.

- [ ] **Step 2: Sync**

```
uv sync
```

Expect a longer resolution than Plan 1 — langchain's dep tree is wide.

- [ ] **Step 3: Verify import**

```
uv run python -c "import deepagents, langgraph, langchain_openai, sse_starlette; print('ok')"
```

Expected: `ok` (no import errors).

- [ ] **Step 4: Commit**

```
git add pyproject.toml uv.lock
git commit -m "chore(deps): add deepagents + langgraph + langchain-openai + sse-starlette for plan 2"
```

---

## Task 2: Config — agent settings

**Files:**
- Modify: `rehketo-api/rehketo/config.py`
- Modify: `rehketo-api/tests/conftest.py` (set the new env vars in `settings_env`)
- Modify: `rehketo-api/tests/unit/test_config.py` (add coverage for the new fields)
- Modify: `rehketo-api/.env.example`

- [ ] **Step 1: Add fields to Settings**

Append to `rehketo/config.py` inside `Settings`:

```python
bifrost_base_url: str = "http://localhost:8088/v1"
bifrost_api_key: SecretStr = SecretStr("dev-noop")
agent_model: str = "claude-sonnet-4-6"
```

- [ ] **Step 2: Update settings_env fixture**

In `tests/conftest.py` `settings_env`, add:
```python
monkeypatch.setenv("BIFROST_BASE_URL", "http://bifrost-mock/v1")
monkeypatch.setenv("BIFROST_API_KEY", "test-key")
monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4-6")
```

- [ ] **Step 3: Extend test_config.py**

Add a test that asserts the three fields load and have the expected values (`s.bifrost_base_url == "http://bifrost-mock/v1"`, `s.bifrost_api_key.get_secret_value() == "test-key"`, `s.agent_model == "claude-sonnet-4-6"`).

- [ ] **Step 4: Update .env.example**

Append the three lines listed in the "Environment additions" section above.

- [ ] **Step 5: Run tests and lints**

```
uv run pytest tests/unit/test_config.py -v
uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 6: Commit**

```
git add rehketo/config.py tests/conftest.py tests/unit/test_config.py .env.example
git commit -m "feat(config): add bifrost + agent model settings"
```

---

## Task 3: LangGraph postgres checkpointer migration

**Files:**
- Create: `rehketo-api/alembic/versions/0003_langgraph_checkpointer.py`

LangGraph ships `AsyncPostgresSaver.setup()` which idempotently creates its own tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`). Wrap that in an Alembic migration so ops and rollback live in one place.

- [ ] **Step 1: Write the migration**

```python
"""langgraph checkpointer tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20 ...
"""
from __future__ import annotations

import asyncio
from typing import Sequence

from alembic import op
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from rehketo.config import get_settings

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


async def _setup() -> None:
    settings = get_settings()
    # LangGraph's checkpointer wants the raw DSN without the +psycopg suffix.
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()


def upgrade() -> None:
    asyncio.run(_setup())


def downgrade() -> None:
    # Drop in reverse order; LangGraph doesn't expose a teardown.
    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
```

- [ ] **Step 2: Apply**

```
uv run alembic upgrade head
docker compose -f deploy/docker-compose.yaml exec -T postgres psql -U rehketo -d rehketo -c "\dt"
```

Expect the 9 v1 tables + 4 LangGraph tables + `alembic_version`.

- [ ] **Step 3: Round-trip**

```
uv run alembic downgrade 0002
uv run alembic upgrade head
```

Both succeed.

- [ ] **Step 4: Commit**

```
git add alembic/versions/0003_langgraph_checkpointer.py
git commit -m "feat(db): add langgraph checkpointer tables migration"
```

---

## Task 4: RunEventBus — interface + in-process impl

**Files:**
- Create: `rehketo-api/rehketo/runs/__init__.py` (empty)
- Create: `rehketo-api/rehketo/runs/event_bus.py`
- Create: `rehketo-api/tests/unit/test_event_bus_contract.py`

The interface is what the agent and the SSE endpoint depend on; the v1 implementation uses an `asyncio.Queue` per run_id plus a bounded ring buffer for late subscribers.

- [ ] **Step 1: Write the contract test**

`tests/unit/test_event_bus_contract.py`:

```python
from __future__ import annotations

import asyncio

import pytest

from rehketo.runs.event_bus import InProcessEventBus, RunEventBus


async def _collect(bus: RunEventBus, run_id: str, n: int, *, from_sequence: int | None = None) -> list[dict]:
    events: list[dict] = []
    async for e in bus.subscribe(run_id, from_sequence=from_sequence):
        events.append(e)
        if len(events) >= n:
            break
    return events


async def test_publish_and_subscribe_roundtrip() -> None:
    bus = InProcessEventBus()

    async def publisher() -> None:
        for i in range(3):
            await bus.publish("r1", {"type": "tick", "i": i})

    task = asyncio.create_task(publisher())
    events = await _collect(bus, "r1", 3)
    await task
    assert [e["i"] for e in events] == [0, 1, 2]
    assert all("sequence" in e for e in events)


async def test_late_subscriber_reads_from_ring_buffer() -> None:
    bus = InProcessEventBus(buffer_size=16)
    for i in range(5):
        await bus.publish("r1", {"type": "tick", "i": i})
    # Subscribe AFTER publish — the ring buffer replays.
    events = await _collect(bus, "r1", 5)
    assert [e["i"] for e in events] == [0, 1, 2, 3, 4]


async def test_subscribe_from_sequence_resumes() -> None:
    bus = InProcessEventBus(buffer_size=16)
    for i in range(5):
        await bus.publish("r1", {"type": "tick", "i": i})
    events = await _collect(bus, "r1", 2, from_sequence=3)  # skip first 3 (seq 0,1,2)
    assert [e["i"] for e in events] == [3, 4]


async def test_isolation_between_run_ids() -> None:
    bus = InProcessEventBus()
    await bus.publish("r1", {"type": "tick"})
    await bus.publish("r2", {"type": "tock"})
    r1 = await _collect(bus, "r1", 1)
    r2 = await _collect(bus, "r2", 1)
    assert r1[0]["type"] == "tick"
    assert r2[0]["type"] == "tock"
```

- [ ] **Step 2: Run — expect FAIL (module missing)**

```
uv run pytest tests/unit/test_event_bus_contract.py -v
```

- [ ] **Step 3: Implement**

Create `rehketo/runs/__init__.py` (empty).

Create `rehketo/runs/event_bus.py`:

```python
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Protocol


class RunEventBus(Protocol):
    async def publish(self, run_id: str, event: dict[str, object]) -> None: ...
    def subscribe(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
    ) -> AsyncIterator[dict[str, object]]: ...


class InProcessEventBus:
    """asyncio.Queue-per-run bus with a bounded ring buffer for late subscribers.

    Single-process only. The postgres LISTEN/NOTIFY implementation (fast-follow)
    will be a drop-in replacement satisfying the same contract.
    """

    def __init__(self, *, buffer_size: int = 1024) -> None:
        self._buffer_size = buffer_size
        self._seq: dict[str, int] = defaultdict(int)
        self._history: dict[str, deque[dict[str, object]]] = defaultdict(
            lambda: deque(maxlen=self._buffer_size)
        )
        self._queues: dict[str, list[asyncio.Queue[dict[str, object]]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, run_id: str, event: dict[str, object]) -> None:
        async with self._lock:
            seq = self._seq[run_id]
            self._seq[run_id] = seq + 1
            enriched = {**event, "sequence": seq, "run_id": run_id}
            self._history[run_id].append(enriched)
            for q in list(self._queues[run_id]):
                q.put_nowait(enriched)

    async def subscribe(
        self,
        run_id: str,
        *,
        from_sequence: int | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        q: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        async with self._lock:
            # Replay buffered history from from_sequence onward
            if self._history.get(run_id):
                for e in self._history[run_id]:
                    if from_sequence is None or e["sequence"] >= from_sequence:
                        q.put_nowait(e)
            self._queues[run_id].append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            async with self._lock:
                if q in self._queues[run_id]:
                    self._queues[run_id].remove(q)
```

- [ ] **Step 4: Run — expect PASS**

```
uv run pytest tests/unit/test_event_bus_contract.py -v
```

- [ ] **Step 5: Gates**

```
uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 6: Commit**

```
git add rehketo/runs/__init__.py rehketo/runs/event_bus.py tests/unit/test_event_bus_contract.py
git commit -m "feat(runs): add RunEventBus interface + in-process implementation"
```

---

## Task 5: Run task registry (for cancellation)

**Files:**
- Create: `rehketo-api/rehketo/runs/registry.py`

Process-local dict of `run_id → asyncio.Task`. Thread-safe for our single-worker scenario (the event loop is single-threaded).

- [ ] **Step 1: Implement directly**

```python
from __future__ import annotations

import asyncio
from uuid import UUID


class RunTaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def register(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self._tasks[run_id] = task
        task.add_done_callback(lambda _t, rid=run_id: self._tasks.pop(rid, None))

    def cancel(self, run_id: UUID) -> bool:
        task = self._tasks.get(run_id)
        if task is None:
            return False
        return task.cancel()

    def has(self, run_id: UUID) -> bool:
        return run_id in self._tasks


_registry_singleton: RunTaskRegistry | None = None


def get_registry() -> RunTaskRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = RunTaskRegistry()
    return _registry_singleton


def reset_registry_for_tests() -> None:
    global _registry_singleton
    _registry_singleton = None
```

- [ ] **Step 2: Gates**

```
uv run ruff check rehketo
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 3: Commit**

```
git add rehketo/runs/registry.py
git commit -m "feat(runs): add in-process task registry for cancellation"
```

---

## Task 6: LLM client (ChatOpenAI → Bifrost, Responses API)

**Files:**
- Create: `rehketo-api/rehketo/agent/__init__.py` (empty)
- Create: `rehketo-api/rehketo/agent/llm.py`

- [ ] **Step 1: Implement**

```python
from __future__ import annotations

from langchain_openai import ChatOpenAI

from rehketo.config import get_settings


def build_chat_model() -> ChatOpenAI:
    """Factory for the LangChain chat model pointed at Bifrost.

    Bifrost exposes an OpenAI-compatible interface; we use the Responses API
    shape so `use_responses_api=True`. The provider routing (Anthropic Claude
    Sonnet 4.6) happens inside Bifrost based on the model name.
    """
    s = get_settings()
    return ChatOpenAI(
        base_url=s.bifrost_base_url,
        api_key=s.bifrost_api_key.get_secret_value(),
        model=s.agent_model,
        use_responses_api=True,
        streaming=True,
    )
```

- [ ] **Step 2: Gates**

```
uv run ruff check rehketo
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 3: Commit**

```
git add rehketo/agent/__init__.py rehketo/agent/llm.py
git commit -m "feat(agent): add ChatOpenAI factory pointed at Bifrost"
```

---

## Task 7: Agent graph (deepagents + checkpointer)

**Files:**
- Create: `rehketo-api/rehketo/agent/graph.py`

- [ ] **Step 1: Implement**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from deepagents import create_deep_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from rehketo.agent.llm import build_chat_model
from rehketo.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


async def _checkpointer_dsn() -> str:
    raw = get_settings().database_url
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


async def build_agent(run_id: str) -> AsyncIterator[object]:
    """Yields a deepagents graph bound to a postgres checkpointer scoped to
    thread_id=run_id. Tools list is empty for v1 — infrastructure only."""
    dsn = await _checkpointer_dsn()
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        agent = create_deep_agent(
            tools=[],
            instructions="You are a helpful assistant.",
            model=build_chat_model(),
        )
        agent.checkpointer = saver
        yield agent
```

**Note:** `create_deep_agent`'s exact API may differ between versions. If the version we installed exposes `checkpointer=` as a kwarg, pass it directly rather than setting the attribute. Check `uv run python -c "import deepagents; help(deepagents.create_deep_agent)"` if unsure.

- [ ] **Step 2: Gates**

```
uv run ruff check rehketo
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 3: Commit**

```
git add rehketo/agent/graph.py
git commit -m "feat(agent): add deepagents graph with postgres checkpointer"
```

---

## Task 8: Event transformer (LangGraph chunk → our SSE schema)

**Files:**
- Create: `rehketo-api/rehketo/agent/events.py`
- Create: `rehketo-api/tests/unit/test_agent_events_transform.py`

The transformer is pure — given a LangGraph stream chunk, it returns zero or more events in our schema. This lets us unit-test it without the agent or network.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from rehketo.agent.events import transform_chunk


def test_message_delta_chunk_emits_message_delta() -> None:
    # LangGraph's "messages" stream mode yields tuples of (AIMessageChunk, metadata).
    # Shape varies; adapt the transformer and test together.
    class _AIChunk:
        content = "hello "
        id = "msg-1"
    events = list(transform_chunk((_AIChunk(), {"langgraph_node": "agent"})))
    assert len(events) == 1
    assert events[0]["type"] == "message.delta"
    assert events[0]["message_id"] == "msg-1"
    assert events[0]["delta"] == "hello "


def test_empty_chunk_emits_nothing() -> None:
    class _AIChunk:
        content = ""
        id = "msg-1"
    assert list(transform_chunk((_AIChunk(), {}))) == []
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def transform_chunk(chunk: tuple[Any, dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Convert a LangGraph `stream_mode='messages'` chunk into zero or more
    events in our stable schema. Yields nothing for empty / metadata-only chunks."""
    msg, _metadata = chunk
    delta = getattr(msg, "content", None)
    if not delta:
        return
    yield {
        "type": "message.delta",
        "message_id": getattr(msg, "id", None),
        "delta": delta,
    }
```

Note: real LangGraph chunks may be richer (tool_calls, etc.). v1 only emits `message.delta`. `tool.call` / `tool.result` / `message.complete` / `run.status` are produced by `run_agent` directly, not by `transform_chunk`. Keep this module focused.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Gates**

- [ ] **Step 6: Commit**

```
git add rehketo/agent/events.py tests/unit/test_agent_events_transform.py
git commit -m "feat(agent): add LangGraph chunk to SSE schema transformer"
```

---

## Task 9: `run_agent` coroutine

**Files:**
- Create: `rehketo-api/rehketo/agent/run.py`

Orchestrates: status transitions, history load, graph execution, event publication, message persistence, error handling, cancellation.

- [ ] **Step 1: Implement**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select, update

from rehketo.agent.events import transform_chunk
from rehketo.agent.graph import build_agent
from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Message, Run
from rehketo.runs.event_bus import RunEventBus

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


async def _load_history(db, conversation_id: UUID) -> list[object]:
    msgs = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    ).scalars().all()
    result: list[object] = [SystemMessage(content="You are a helpful assistant.")]
    for m in msgs:
        content = m.content if isinstance(m.content, str) else str(m.content.get("text", ""))
        if m.role == "user":
            result.append(HumanMessage(content=content))
        elif m.role == "assistant":
            result.append(AIMessage(content=content))
    return result


async def run_agent(run_id: UUID, bus: RunEventBus) -> None:
    """Drive the agent for `run_id`. Called as an asyncio.Task."""
    async with sessionmaker()() as db:
        run = (await db.execute(select(Run).where(Run.id == run_id))).scalar_one()
        conversation_id = run.conversation_id

        await db.execute(
            update(Run).where(Run.id == run_id).values(
                status="running", started_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await bus.publish(str(run_id), {"type": "run.status", "status": "running"})

        history = await _load_history(db, conversation_id)

    assembled_text = ""
    assembled_message_id: str | None = None

    try:
        async for agent in build_agent(str(run_id)):
            async for chunk in agent.astream(
                {"messages": history},
                config={"configurable": {"thread_id": str(run_id)}},
                stream_mode="messages",
            ):
                for event in transform_chunk(chunk):
                    await bus.publish(str(run_id), event)
                    if event["type"] == "message.delta":
                        assembled_text += event["delta"]
                        assembled_message_id = event.get("message_id") or assembled_message_id

        # Persist the assistant message and close the run
        async with sessionmaker()() as db:
            assistant_id = uuid4()
            db.add(Message(
                id=assistant_id,
                conversation_id=conversation_id,
                role="assistant",
                content={"text": assembled_text},
                run_id=run_id,
            ))
            await db.execute(
                update(Run).where(Run.id == run_id).values(
                    status="succeeded", finished_at=datetime.now(UTC),
                )
            )
            await db.commit()

        await bus.publish(str(run_id), {
            "type": "message.complete",
            "message": {
                "id": str(assistant_id),
                "role": "assistant",
                "content": {"text": assembled_text},
                "run_id": str(run_id),
            },
        })
        await bus.publish(str(run_id), {"type": "run.status", "status": "succeeded"})

    except Exception as exc:  # noqa: BLE001
        logger.exception("run_agent failed run_id=%s", str(run_id))
        async with sessionmaker()() as db:
            await db.execute(
                update(Run).where(Run.id == run_id).values(
                    status="failed",
                    error={"code": "llm_failure", "message": str(exc)},
                    finished_at=datetime.now(UTC),
                )
            )
            await db.commit()
        await bus.publish(str(run_id), {
            "type": "run.status", "status": "failed",
            "error": {"code": "llm_failure", "message": str(exc)},
        })

    # CancelledError handling — must propagate after finalization
    # (handled outside this try/except via task.cancel() semantics)
```

**Notes for the implementer:**
- `transform_chunk` may not be where `message.delta` enforcement happens once LangGraph's internal shape stabilizes; be prepared to adjust.
- `except Exception` is broad; bandit/ruff may flag `BLE001` — the `# noqa: BLE001` comment is justified because we explicitly want to catch-all-to-finalize. Do NOT suppress `CancelledError` (it isn't a subclass of Exception in 3.8+, so it propagates as desired).
- If `CancelledError` is raised during `astream`, the `except` block does not catch it; the task's completion callback will see it and mark the run cancelled. Add a separate `except asyncio.CancelledError:` block at the end of the try that mirrors the failed path but with status='cancelled' — see Task 12 for the cancellation test.

- [ ] **Step 2: Add cancellation handler**

After the `except Exception` block, add:

```python
    except asyncio.CancelledError:
        async with sessionmaker()() as db:
            await db.execute(
                update(Run).where(Run.id == run_id).values(
                    status="cancelled", finished_at=datetime.now(UTC),
                )
            )
            await db.commit()
        await bus.publish(str(run_id), {"type": "run.status", "status": "cancelled"})
        raise
```

Import `asyncio` at the top.

- [ ] **Step 3: Gates**

```
uv run ruff check rehketo
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 4: Commit**

```
git add rehketo/agent/run.py
git commit -m "feat(agent): add run_agent orchestrator with status + events"
```

---

## Task 10: Startup sweep for abandoned runs

**Files:**
- Create: `rehketo-api/rehketo/agent/sweep.py`
- Modify: `rehketo-api/rehketo/main.py` (call sweep inside the lifespan)

- [ ] **Step 1: Implement**

```python
# rehketo/agent/sweep.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update

from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Run

logger = get_logger(__name__)


async def sweep_abandoned_runs() -> None:
    """On startup, mark any runs stuck in `running` or `queued` as failed.

    Anything in those states at startup was abandoned by the previous
    process; the checkpointer may still have state but v1 does not resume.
    """
    async with sessionmaker()() as db:
        result = await db.execute(
            update(Run)
            .where(Run.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error={"code": "process_restart", "message": "run abandoned by process restart"},
                finished_at=datetime.now(UTC),
            )
            .returning(Run.id)
        )
        ids = [row[0] for row in result.all()]
        await db.commit()
        if ids:
            logger.info("swept %d abandoned runs on startup", len(ids))
```

- [ ] **Step 2: Wire into the lifespan**

In `rehketo/main.py`, inside `_lifespan`, after `app.state.settings = settings` and before `yield`:

```python
from rehketo.agent.sweep import sweep_abandoned_runs
await sweep_abandoned_runs()
```

- [ ] **Step 3: Gates**

- [ ] **Step 4: Commit**

```
git add rehketo/agent/sweep.py rehketo/main.py
git commit -m "feat(agent): sweep abandoned runs at startup"
```

---

## Task 11: POST /conversations/{id}/messages

**Files:**
- Create: `rehketo-api/rehketo/api/messages.py`
- Modify: `rehketo-api/rehketo/main.py` (include router; create a singleton `RunEventBus`)
- Create: `rehketo-api/tests/integration/test_post_messages_kicks_run.py`

- [ ] **Step 1: Expose the event bus + registry via app state**

Modify `main.py`'s `create_app`:

```python
from rehketo.runs.event_bus import InProcessEventBus
from rehketo.runs.registry import get_registry

# inside create_app, before include_routers:
app.state.event_bus = InProcessEventBus()
app.state.task_registry = get_registry()
```

- [ ] **Step 2: Write the endpoint**

```python
# rehketo/api/messages.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)

from rehketo.agent.run import run_agent
from rehketo.config import get_settings
from rehketo.db import get_session
from rehketo.db.models import Conversation, Message, Run
from rehketo.permissions.dependencies import ResolvedPermissions, resolve_permissions

router = APIRouter(prefix="/conversations", tags=["messages"])


class MessageCreate(BaseModel):
    content: str


class MessageKickoffOut(BaseModel):
    message_id: UUID
    run_id: UUID


@router.post(
    "/{conversation_id}/messages",
    status_code=202,
    response_model=MessageKickoffOut,
)
async def post_message(
    conversation_id: UUID,
    payload: MessageCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> MessageKickoffOut:
    perms.require(
        "chat.write",
        resource_type="conversation",
        resource_id=conversation_id,
    )
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == perms.user_id,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    settings = get_settings()
    message_id = uuid4()
    run_id = uuid4()

    db.add(Message(
        id=message_id,
        conversation_id=conv.id,
        role="user",
        content={"text": payload.content},
    ))
    db.add(Run(
        id=run_id,
        conversation_id=conv.id,
        user_id=perms.user_id,
        status="queued",
        model=settings.agent_model,
    ))
    await db.commit()

    bus = request.app.state.event_bus
    registry = request.app.state.task_registry
    task = asyncio.create_task(run_agent(run_id, bus))
    registry.register(run_id, task)

    return MessageKickoffOut(message_id=message_id, run_id=run_id)
```

- [ ] **Step 3: Wire router**

In `main.py`:
```python
from rehketo.api import messages as messages_api
app.include_router(messages_api.router)
```

- [ ] **Step 4: Write the integration test**

```python
# tests/integration/test_post_messages_kicks_run.py
from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, Message, Run, User, UserRole
from rehketo.main import create_app


@respx.mock
async def test_posting_a_message_creates_row_and_kicks_off_run(
    settings_env, db_url, db,
) -> None:
    # Mock Bifrost so the agent request resolves immediately with an empty stream
    respx.post("http://bifrost-mock/v1/responses").mock(
        return_value=Response(200, json={"output": [{"content": [{"text": "hi"}]}]})
    )

    u = User(id=uuid4(), display_name="A", email="a@x")
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add_all([u, UserRole(user_id=u.id, role="User"), conv])
    await db.commit()
    sid = await create_session(db, user_id=u.id, identity_provider="entra",
                               refresh_token="rt", ttl_minutes=60)
    csrf = issue_csrf_token(str(sid))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/conversations/{conv.id}/messages",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"content": "hello"},
        )
    assert r.status_code == 202
    body = r.json()
    assert UUID(body["message_id"])
    assert UUID(body["run_id"])

    # Give the background task a moment to transition the run
    await asyncio.sleep(0.2)

    # User message was persisted
    msgs = (await db.execute(
        select(Message).where(Message.conversation_id == conv.id)
    )).scalars().all()
    assert any(m.role == "user" and m.content.get("text") == "hello" for m in msgs)

    # Run row exists
    runs = (await db.execute(
        select(Run).where(Run.conversation_id == conv.id)
    )).scalars().all()
    assert len(runs) == 1
    assert runs[0].status in ("queued", "running", "succeeded", "failed")
```

- [ ] **Step 5: Run tests + gates + commit**

```
uv run pytest tests/integration/test_post_messages_kicks_run.py -v
uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo -q

git add rehketo/api/messages.py rehketo/main.py tests/integration/test_post_messages_kicks_run.py
git commit -m "feat(api): POST /conversations/{id}/messages kicks off run"
```

---

## Task 12: GET /runs/{id} + SSE events + cancel

**Files:**
- Create: `rehketo-api/rehketo/api/runs.py`
- Modify: `rehketo-api/rehketo/main.py` (include router; extend CSRF exempt prefixes if needed)
- Modify: `rehketo-api/rehketo/permissions/actions.py` (already includes `chat.cancel_run`; verify)

- [ ] **Step 1: Implement routes**

```python
# rehketo/api/runs.py
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,  # noqa: TC002  # FastAPI needs runtime type for Depends()
)
from sse_starlette.sse import EventSourceResponse

from rehketo.db import get_session
from rehketo.db.models import Run
from rehketo.permissions.dependencies import ResolvedPermissions, resolve_permissions

router = APIRouter(prefix="/runs", tags=["runs"])


class RunOut(BaseModel):
    id: UUID
    conversation_id: UUID
    status: str
    model: str


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> RunOut:
    perms.require(
        "chat.view_conversation",
        resource_type="run",
        resource_id=run_id,
    )
    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.user_id == perms.user_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunOut(
        id=run.id,
        conversation_id=run.conversation_id,
        status=run.status,
        model=run.model,
    )


@router.get("/{run_id}/events")
async def run_events(
    run_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
    from_sequence: int | None = None,
) -> EventSourceResponse:
    perms.require(
        "chat.view_conversation",
        resource_type="run",
        resource_id=run_id,
    )
    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.user_id == perms.user_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    bus = request.app.state.event_bus

    async def _stream():
        async for event in bus.subscribe(str(run_id), from_sequence=from_sequence):
            yield {
                "event": event["type"],
                "data": event,
            }
            # Terminal states close the stream
            if event.get("type") == "run.status" and event.get("status") in (
                "succeeded", "failed", "cancelled",
            ):
                return

    return EventSourceResponse(_stream())


@router.post("/{run_id}/cancel", status_code=204)
async def cancel_run(
    run_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    perms: Annotated[ResolvedPermissions, Depends(resolve_permissions)],
) -> None:
    perms.require(
        "chat.cancel_run",
        resource_type="run",
        resource_id=run_id,
    )
    run = (
        await db.execute(
            select(Run).where(Run.id == run_id, Run.user_id == perms.user_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    registry = request.app.state.task_registry
    registry.cancel(run_id)
    return None
```

- [ ] **Step 2: Wire router**

```python
from rehketo.api import runs as runs_api
app.include_router(runs_api.router)
```

- [ ] **Step 3: Gates**

```
uv run ruff check rehketo tests
uv run mypy rehketo
uv run bandit -r rehketo -q
```

- [ ] **Step 4: Commit**

```
git add rehketo/api/runs.py rehketo/main.py
git commit -m "feat(api): GET /runs/{id}, SSE events, cancel"
```

---

## Task 13: Integration test — full run end-to-end with respx-mocked Bifrost

**Files:**
- Create: `rehketo-api/tests/integration/test_run_agent_end_to_end.py`

This is the big one. It mocks Bifrost's Responses endpoint to stream a simple response, POSTs a message, subscribes to SSE, and asserts the observed event sequence.

- [ ] **Step 1: Write the test**

```python
from __future__ import annotations

import json
from uuid import uuid4

import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, Message, Run, User, UserRole
from rehketo.main import create_app


def _sse_stream_for_hello() -> bytes:
    """Fake a minimal Responses-API SSE stream that produces 'hello'."""
    lines = [
        'data: {"type":"response.output_text.delta","delta":"hel"}\n\n',
        'data: {"type":"response.output_text.delta","delta":"lo"}\n\n',
        'data: {"type":"response.completed"}\n\n',
        'data: [DONE]\n\n',
    ]
    return "".join(lines).encode()


@respx.mock
async def test_run_produces_streamed_assistant_message(settings_env, db_url, db) -> None:
    respx.post("http://bifrost-mock/v1/responses").mock(
        return_value=Response(200, content=_sse_stream_for_hello(),
                              headers={"content-type": "text/event-stream"})
    )

    u = User(id=uuid4(), display_name="A", email="a@x")
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add_all([u, UserRole(user_id=u.id, role="User"), conv])
    await db.commit()
    sid = await create_session(db, user_id=u.id, identity_provider="entra",
                               refresh_token="rt", ttl_minutes=60)
    csrf = issue_csrf_token(str(sid))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/conversations/{conv.id}/messages",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"content": "say hello"},
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]

        # Consume the SSE stream
        events: list[dict] = []
        async with c.stream(
            "GET", f"/runs/{run_id}/events",
            cookies={SESSION_COOKIE: str(sid)},
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    types = [e["type"] for e in events]
    assert "run.status" in types  # running + terminal
    assert types.count("run.status") >= 2
    terminal = [e for e in events if e["type"] == "run.status"][-1]
    assert terminal["status"] == "succeeded"

    # Assistant message persisted
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    fresh = create_async_engine(db_url, future=True)
    maker = async_sessionmaker(fresh, expire_on_commit=False)
    async with maker() as s:
        assistant = (await s.execute(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.role == "assistant",
            )
        )).scalar_one_or_none()
    await fresh.dispose()
    assert assistant is not None
    assert "hello" in assistant.content.get("text", "").lower()
```

**Expect this test to need iteration.** The exact Bifrost → LangChain Responses-API frame shape may not match the hand-rolled SSE above. If the test fails at the LangChain parsing layer, adjust the fake SSE payload to match what LangChain's OpenAI Responses client expects. As a last resort, replace the respx mock with a stub at the ChatOpenAI layer: monkey-patch `build_chat_model` in the test to return a FakeListChatModel that streams `"hello"`. This is acceptable if Bifrost-level fidelity isn't achievable via respx quickly.

- [ ] **Step 2: Run, iterate, commit**

```
uv run pytest tests/integration/test_run_agent_end_to_end.py -v
```

Expect to iterate. When green:

```
git add tests/integration/test_run_agent_end_to_end.py
git commit -m "test: agent end-to-end with mocked Bifrost stream"
```

---

## Task 14: Integration test — cancellation

**Files:**
- Create: `rehketo-api/tests/integration/test_run_cancel.py`

- [ ] **Step 1: Test**

Use a fake chat model that blocks forever inside `.astream()` (monkey-patch `build_chat_model`). POST a message, wait for the run to be `running`, POST /runs/{id}/cancel, assert the run ends up `cancelled` and the SSE stream emits a terminal `run.status:cancelled`.

Sketch:

```python
from __future__ import annotations

import asyncio
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.auth.csrf import issue_csrf_token
from rehketo.auth.sessions import create_session
from rehketo.db.models import Conversation, User, UserRole
from rehketo.main import create_app


async def test_cancel_transitions_run_to_cancelled(
    settings_env, db_url, db, monkeypatch,
) -> None:
    # Replace the chat model builder with a never-completing async iterator
    class _NeverStreamsChat:
        async def astream(self, *args, **kwargs):
            await asyncio.sleep(30)
            if False:
                yield  # pragma: no cover

    from rehketo.agent import llm as llm_mod
    monkeypatch.setattr(llm_mod, "build_chat_model", lambda: _NeverStreamsChat())

    u = User(id=uuid4(), display_name="A", email="a@x")
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add_all([u, UserRole(user_id=u.id, role="User"), conv])
    await db.commit()
    sid = await create_session(db, user_id=u.id, identity_provider="entra",
                               refresh_token="rt", ttl_minutes=60)
    csrf = issue_csrf_token(str(sid))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            f"/conversations/{conv.id}/messages",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
            json={"content": "hang please"},
        )
        run_id = r.json()["run_id"]

        # Let the run reach "running"
        await asyncio.sleep(0.3)

        r = await c.post(
            f"/runs/{run_id}/cancel",
            cookies={SESSION_COOKIE: str(sid), CSRF_COOKIE: csrf},
            headers={CSRF_HEADER: csrf},
        )
        assert r.status_code == 204

        # Give the task a moment to handle CancelledError
        await asyncio.sleep(0.3)

        r = await c.get(f"/runs/{run_id}", cookies={SESSION_COOKIE: str(sid)})
    assert r.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run, fix, commit**

```
git add tests/integration/test_run_cancel.py
git commit -m "test: run cancellation flow"
```

---

## Task 15: Integration test — startup sweep

**Files:**
- Create: `rehketo-api/tests/integration/test_startup_sweep.py`

- [ ] **Step 1: Test**

Insert a `Run` with `status='running'` directly into the DB; call `sweep_abandoned_runs()` (or spin up the app and trigger the lifespan); assert the run is now `failed` with `error.code == 'process_restart'`.

```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from rehketo.agent.sweep import sweep_abandoned_runs
from rehketo.db.models import Conversation, Run, User
from rehketo.main import create_app


async def test_sweep_marks_running_runs_as_failed(
    settings_env, db_url, db,
) -> None:
    u = User(id=uuid4(), display_name="A", email="a@x")
    conv = Conversation(id=uuid4(), user_id=u.id, title="t")
    db.add_all([u, conv])
    await db.commit()
    db.add(Run(
        id=uuid4(), conversation_id=conv.id, user_id=u.id,
        status="running", model="claude-sonnet-4-6",
        started_at=datetime.now(UTC),
    ))
    await db.commit()

    await sweep_abandoned_runs()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    fresh = create_async_engine(db_url, future=True)
    maker = async_sessionmaker(fresh, expire_on_commit=False)
    async with maker() as s:
        run = (await s.execute(select(Run))).scalar_one()
    await fresh.dispose()
    assert run.status == "failed"
    assert run.error["code"] == "process_restart"
```

- [ ] **Step 2: Commit**

```
git add tests/integration/test_startup_sweep.py
git commit -m "test: startup sweep marks abandoned runs failed"
```

---

## Task 16: Integration test — SSE resume by sequence

**Files:**
- Create: `rehketo-api/tests/integration/test_sse_resume_by_sequence.py`

- [ ] **Step 1: Test**

Start a run, consume the first 3 events, disconnect, reconnect with `?from_sequence=3`, assert the remaining events arrive in order without dup.

Use the same fake-streamer pattern as T13 or T14. Focus on the reconnect behavior.

- [ ] **Step 2: Commit**

```
git add tests/integration/test_sse_resume_by_sequence.py
git commit -m "test: SSE resume by sequence"
```

---

## Task 17: CSRF middleware — exempt SSE GETs aren't exempt (confirm)

**Files:**
- No code change expected; this is a verification task.

- [ ] **Step 1: Confirm that GET endpoints (including `/runs/{id}/events`) bypass CSRF middleware**

The middleware already gates on `request.method in UNSAFE_METHODS`. GET is safe. Confirm by reviewing `csrf_middleware.py`, then add a short integration test asserting an SSE subscribe succeeds without a CSRF token.

```python
async def test_sse_subscribe_does_not_require_csrf(
    settings_env, db_url, db,
) -> None:
    # seed user + session (no csrf token issued/supplied)
    ...
    async with AsyncClient(...) as c:
        async with c.stream(
            "GET", f"/runs/{run_id}/events",
            cookies={SESSION_COOKIE: str(sid)},  # no CSRF cookie/header
        ) as resp:
            assert resp.status_code == 200
```

Place in `tests/integration/test_sse_resume_by_sequence.py` or its own file. If its own file, add to the commit below.

- [ ] **Step 2: Commit (if any new test added)**

```
git add tests/integration/test_sse_csrf_exempt.py
git commit -m "test: confirm SSE GETs bypass CSRF middleware"
```

---

## Task 18: Conversation title generation (best-effort)

**Files:**
- Create: `rehketo-api/rehketo/agent/title.py`
- Modify: `rehketo-api/rehketo/agent/run.py` (call title generator after first successful run)

- [ ] **Step 1: Implement**

```python
# rehketo/agent/title.py
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update

from rehketo.agent.llm import build_chat_model
from rehketo.core.logging import get_logger
from rehketo.db import sessionmaker
from rehketo.db.models import Conversation, Message

logger = get_logger(__name__)


async def generate_title_if_needed(conversation_id: UUID) -> None:
    """Best-effort async title generation. Failures are logged and swallowed."""
    try:
        async with sessionmaker()() as db:
            conv = (
                await db.execute(select(Conversation).where(Conversation.id == conversation_id))
            ).scalar_one()
            if conv.title:
                return
            msgs = (
                await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                    .limit(4)
                )
            ).scalars().all()
        if not msgs:
            return

        prompt = "Summarize this exchange in 4 words or less, plain text only:\n\n"
        for m in msgs:
            text = m.content.get("text", "") if isinstance(m.content, dict) else str(m.content)
            prompt += f"{m.role}: {text}\n"

        model = build_chat_model()
        resp = await model.ainvoke(prompt)
        title = (getattr(resp, "content", "") or "").strip().strip('"').strip(".")[:80]
        if not title:
            return

        async with sessionmaker()() as db:
            await db.execute(
                update(Conversation).where(Conversation.id == conversation_id).values(title=title)
            )
            await db.commit()
    except Exception:
        logger.exception("title generation failed for conversation %s", conversation_id)
```

In `run.py`, after the successful-finalization block, add:
```python
import asyncio
from rehketo.agent.title import generate_title_if_needed
asyncio.create_task(generate_title_if_needed(conversation_id))
```

- [ ] **Step 2: Gates + commit**

```
git add rehketo/agent/title.py rehketo/agent/run.py
git commit -m "feat(agent): best-effort conversation title generation after first run"
```

---

## Task 19: Update E2E smoke for full chat turn

**Files:**
- Modify: `rehketo-api/tests/integration/test_e2e_chat_smoke.py` (create new, alongside Plan 1's `test_e2e_smoke.py`)

- [ ] **Step 1: Write**

```python
from __future__ import annotations

import json

import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select

from rehketo.auth.cookies import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from rehketo.db.models import Message
from rehketo.main import create_app


def _fake_sse() -> bytes:
    return (
        'data: {"type":"response.output_text.delta","delta":"hi"}\n\n'
        'data: {"type":"response.completed"}\n\n'
        'data: [DONE]\n\n'
    ).encode()


@respx.mock
async def test_full_chat_turn(settings_env, db_url, db) -> None:
    respx.post("http://bifrost-mock/v1/responses").mock(
        return_value=Response(200, content=_fake_sse(),
                              headers={"content-type": "text/event-stream"})
    )

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/auth/devonly/login",
                         json={"email": "al@example.com", "roles": ["User"]})
        assert r.status_code == 200
        sid = next(x for x in r.cookies.jar if x.name == SESSION_COOKIE).value
        csrf = next(x for x in r.cookies.jar if x.name == CSRF_COOKIE).value
        auth = dict(cookies={SESSION_COOKIE: sid, CSRF_COOKIE: csrf},
                    headers={CSRF_HEADER: csrf})

        r = await c.post("/conversations", json={}, **auth)
        conv_id = r.json()["id"]

        r = await c.post(
            f"/conversations/{conv_id}/messages",
            json={"content": "hi there"},
            **auth,
        )
        run_id = r.json()["run_id"]

        events: list[dict] = []
        async with c.stream("GET", f"/runs/{run_id}/events",
                            cookies={SESSION_COOKIE: sid}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        assert any(e["type"] == "run.status" and e.get("status") == "succeeded"
                   for e in events)

        # Detail shows both messages
        r = await c.get(f"/conversations/{conv_id}", cookies={SESSION_COOKIE: sid})
        msgs = r.json()["messages"]
        roles = [m["role"] for m in msgs]
        assert "user" in roles and "assistant" in roles
```

- [ ] **Step 2: Commit**

```
git add tests/integration/test_e2e_chat_smoke.py
git commit -m "test: e2e smoke for full chat turn with streamed agent response"
```

---

## Self-review (inline — Plan 2)

**Spec coverage:**
- §6.1 run lifecycle — Tasks 9, 10, 12 cover all states and the startup sweep.
- §6.2 RunEventBus interface + v1 InProcessEventBus — Task 4 defines, Tasks 11/12/13 consume.
- §6.3 agent execution flow — Task 9.
- §6.4 SSE event schema — Task 8 (delta transform) + Task 9 (status/complete/error) + Task 12 (streaming).
- §6.5 cancellation — Tasks 5, 12, 14.
- §7 new API endpoints — Tasks 11 (POST messages), 12 (GET run + SSE + cancel).
- §10 error handling — covered inside run.py's try/except; error envelope from Plan 1 still applies.
- §11 testing — Tasks 13–19.

**Explicit deferrals (not gaps):**
- Tool registry population — still empty.
- Postgres event bus — fast-follow after Plan 2.
- Separate worker process — next after the postgres bus.
- Connection-using features (MS Graph) — later.
- UI — Plan 3.

**Placeholder scan:** none. Every step has concrete code or commands.

**Ambiguity items flagged:**
- The exact `stream_mode` on `graph.astream` and the shape LangGraph returns may need minor adjustment (Task 8 / Task 13). The transformer is unit-tested with a synthetic chunk shape; if LangGraph's real shape differs, update together.
- The mocked Bifrost SSE in tests may need to be adjusted to match what LangChain's Responses-API client accepts. Fallback: monkey-patch `build_chat_model` to return a `FakeListChatModel`.

---

## Execution handoff

**Plan complete and saved to `rehketo-api/docs/superpowers/plans/2026-04-20-plan-2-runs-agent-sse.md`.**

Two execution options (same as Plan 1):

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task or cluster, review between, same cadence as Plan 1. Suggested clusters:
- Cluster 1: T1–T3 (deps + config + checkpointer migration)
- Cluster 2: T4–T5 (event bus + registry)
- Cluster 3: T6–T9 (LLM + graph + events + run orchestrator)
- Cluster 4: T10–T12 (sweep + API endpoints)
- Cluster 5: T13–T17 (integration tests)
- Cluster 6: T18–T19 (title gen + full E2E)

**2. Inline Execution** — same-session batch with checkpoints.

Which approach?
