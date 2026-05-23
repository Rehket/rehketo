# Svelte UI v1 — design

Design doc for `rehketo-ui`, the thin-client SvelteKit front end that consumes the rehketo-api chat/agent harness.

Companion to:
- Backend design: `docs/superpowers/specs/2026-04-19-chat-and-agent-v1-design.md`
- ROADMAP: `ROADMAP.md` (Plan 3 — SvelteKit thin client)

---

## 1. Context & scope

### 1.1 Why

The backend (Plans 1 + 2) exposes a complete cookie-authenticated chat + agent API with SSE streaming. `rehketo-ui/` exists as an empty directory; nothing in the user story is reachable today without `curl` or Swagger. This spec is the thin client that closes that gap.

### 1.2 In scope (v1)

- Login landing page ("Sign in with Entra" button; surfaces `?auth_error=<code>`).
- Sidebar with conversation list, `New chat` button, and user menu (email + logout).
- Chat view per conversation: message list, markdown-rendered assistant replies, streaming run indicator, Cancel button, auto-resizing composer.
- Conversation rename (inline, PATCH) and soft-archive (DELETE → vanishes from sidebar).
- Capability-gated affordances sourced from `GET /me/capabilities`.

### 1.3 Out of scope (v1)

- Resume-on-reload for in-flight runs (SSE resume via `?from_sequence=N`). Backend supports it; UI doesn't use it.
- Client-side conversation search / filter.
- Admin UI, role management, audit views.
- Elevation flows for dangerous actions (explicitly deferred by backend ROADMAP).
- SSE auto-reconnect on transient disconnect.

---

## 2. Architecture & stack

### 2.1 Repo shape

Standalone SvelteKit project at `D:/Workspace/rehketo/rehketo-ui/`, its own git repo (peer to `rehketo-api`).

```
rehketo-ui/
  src/
    routes/
      +layout.svelte          # sidebar + user menu shell
      +layout.ts              # calls GET /me, hydrates auth state, 401 → /login
      +page.svelte            # "/" — empty chat shell, prompts to start or pick
      login/+page.svelte      # login landing
      c/[id]/+page.svelte     # chat view for one conversation
      c/[id]/+page.ts         # load() fetches conversation + messages
      +error.svelte           # unhandled error boundary
    lib/
      api.ts                  # fetch wrapper (CSRF, 401 handling, base URL)
      sse.ts                  # EventSource subscribe with typed events + state machine
      markdown.ts             # marked + highlight.js + DOMPurify pipeline
      stores/                 # runes-based state (auth, conversations)
      components/             # Sidebar, ConversationListItem, MessageBubble,
                              #  Composer, UserMenu, MarkdownView, RunStatusDot, …
    app.html, app.css
  tests/
    e2e/                      # Playwright
    unit/                     # Vitest
  svelte.config.js, vite.config.ts, tailwind.config.ts,
  tsconfig.json, package.json, playwright.config.ts
```

### 2.2 Stack pins

- **SvelteKit + Svelte 5** with runes.
- **`adapter-static`** — no SSR. `/login` is prerendered; `/c/[id]` is client-side rendered with `index.html` fallback.
- **TypeScript** throughout.
- **Tailwind 4** for styling.
- **melt-ui** for accessible headless primitives (menus, dialogs, tooltips).
- **marked** + **highlight.js** + **DOMPurify** for assistant markdown.
- **Native `EventSource`** for SSE.
- **pnpm** as package manager.

### 2.3 Dev topology

- `pnpm dev` runs SvelteKit on `localhost:5173`.
- `vite.config.ts` proxies `/auth`, `/conversations`, `/runs`, `/me`, `/openapi.json`, `/docs` to `http://127.0.0.1:8000`.
- Browser sees one origin (`localhost:5173`), cookies flow unchanged.
- FastAPI runs as today (`uv run rehketo-serve` or equivalent) on `127.0.0.1:8000`.

**Entra redirect URI must also live on the UI origin.** Set `ENTRA_REDIRECT_URI=http://localhost:5173/auth/callback` in the backend's `.env`. The Vite proxy forwards that path to the backend transparently, but the browser's origin stays `:5173` — so the session and CSRF cookies set on the callback response land for the UI to read. Pointing Entra at `:8000` directly scopes cookies to the backend port and breaks the whole flow. Two redirect URIs must exist in the Entra app registration: dev (`localhost:5173`) and prod (your deployed host).

**Dev startup order:** Postgres + Bifrost → backend → UI → open `http://localhost:5173/auth/login`. Docker compose only includes Postgres, Bifrost, and a prod-like `rehketo-api` service; local iteration uses `uv run rehketo-serve` on the host for hot reload.

### 2.4 Prod topology

- `pnpm build` → `rehketo-ui/build/` (static files).
- Backend config gains one env var: `UI_STATIC_DIR` (absolute path to the built bundle inside the process's filesystem). When set, `rehketo.main` registers a catch-all `GET /{full_path:path}` that serves real files from the bundle and falls back to `index.html` for unknown paths (SPA routing like `/c/<uuid>` survives a page load).
- API routers (`/auth`, `/conversations`, `/runs`, `/me`, `/openapi.json`, `/docs`, `/healthz`) are registered before the catch-all, so their paths win.
- One origin, one process, zero CORS, cookies same-origin, `UI_POST_LOGIN_URL=/` works in both dev and prod.
- Getting the build bundle into the container: either (a) multi-stage Dockerfile with a `pnpm build` stage that COPYs `build/` into the API image at a known path, or (b) CI builds separately and mounts the bundle volume. Either is compatible with the `UI_STATIC_DIR` contract.

### 2.5 Config

- `PUBLIC_API_BASE` build-time env var. Default `""` (empty = same origin). Override only if we ever split hosts.
- No other UI env vars in v1.

---

## 3. Routes & URL structure

| URL | File | Prerender | Role |
|---|---|---|---|
| `/login` | `routes/login/+page.svelte` | ✅ | Sign-in landing. "Sign in with Entra" anchors to `/auth/login`. Reads `?auth_error=<code>` + `?next=<path>` query params. |
| `/` | `routes/+page.svelte` | ❌ | Empty chat shell. Sidebar visible; main area shows "Start a new chat" CTA. |
| `/c/[id]` | `routes/c/[id]/+page.svelte` + `+page.ts` | ❌ | Chat view for one conversation. `load()` fetches `GET /conversations/{id}` + messages. Streams any in-flight run. |

`+layout.svelte` wraps `/` and `/c/[id]` with the sidebar + user menu. `/login` uses a bare layout.

### 3.1 Auth guard

`+layout.ts` (root) calls `GET /me` on first load. On 401, redirect to `/login?next=<currentPath>`. On 2xx, store `{user, capabilities}` in a rune-backed context readable by any descendant.

### 3.2 Capability gating

Every affordance that maps to a backend action checks `capabilities.has(action)` before rendering:

| UI element | Gating action |
|---|---|
| `New chat` button | `chat.create_conversation` |
| Send composer | `chat.write` |
| Rename menu item | `chat.rename_conversation` |
| Archive menu item | `chat.delete_conversation` |
| Cancel button | `chat.cancel_run` |

If the bit is off, the element doesn't render (not just disabled). UI never reconstructs the permission table locally.

---

## 4. Components

### 4.1 Chat shell (under `+layout.svelte`)

```
Sidebar.svelte
├── NewChatButton          → POST /conversations → goto(`/c/<id>`)
├── ConversationList       ← GET /conversations?include_archived=false
│   └── ConversationListItem
│       └── ConversationMenu (inline rename, archive)
└── UserMenu               (avatar + email; logout → POST /auth/logout → /login)
```

### 4.2 Chat view (`routes/c/[id]/+page.svelte`)

```
ChatHeader       (title; click to rename inline; "…" menu with archive)
MessageList      (auto-scroll to bottom on new message; no virtualization in v1)
  └── MessageBubble
      ├── UserBubble        (plain text, right-aligned)
      └── AssistantBubble
          ├── MarkdownView  (marked → DOMPurify → rendered HTML)
          └── RunStatusDot  (pulses while run is streaming)
Composer         (auto-resizing <textarea>, Enter=send, Shift+Enter=newline)
```

### 4.3 New-conversation flow

1. User clicks `New chat` → `POST /conversations` → receive `{id}` → prepend to sidebar store → `goto("/c/<id>")`.
2. Chat page mounts with empty message list, composer focused.
3. User submits first message → `POST /conversations/<id>/messages` → `{run_id}`.
4. UI optimistically appends user bubble and a streaming assistant bubble.
5. UI opens `EventSource` on `/runs/<run_id>/events`.
6. `message.delta` events append to the streaming bubble's text.
7. On success: `message.complete` arrives carrying a full `MessageOut` (id, conversation_id, role, content, run_id, created_at, run_status='succeeded', run_error=null). UI swaps the streaming bubble's backing object for the server-authoritative one so a reload matches live state.
8. `run.status=succeeded` arrives immediately after — UI clears the "running" indicator. Stream is NOT closed yet.
9. If the backend generated a conversation title (awaited server-side before the next event is emitted), a `conversation.updated` event (`{conversation_id, title}`) arrives next. UI patches the sidebar entry.
10. `run.ended` closes the stream.
11. On failure/cancel: no `message.complete` — the backend persists whatever partial text was accumulated as an assistant message and emits `run.status={failed|cancelled}` directly, then `run.ended`. UI converts the streaming bubble to a terminal bubble with the appropriate badge (red "Failed" with `error.code + message`, or amber "Cancelled"). On subsequent reload, `GET /conversations/{id}` returns the partial message with `run_status` and `run_error` populated, so the UI renders the same badge. **Empty-text edge case:** when a run fails/cancels before any `message.delta`, the persisted partial has `content.text === ""`. The UI renders a placeholder bubble with the badge — `"No response — the run was <failed|cancelled>"` plus the error affordance — so the attempt stays visible rather than leaving only the user message on screen.

---

## 5. Data flow

### 5.1 API client (`lib/api.ts`)

One `apiFetch(path, init)` wrapper. Responsibilities:

- `credentials: 'include'` so cookies flow.
- For unsafe methods (`POST | PUT | PATCH | DELETE`): read `rehketo_csrf` cookie (non-httpOnly) and set the `X-CSRF-Token` header.
- 2xx: parse JSON, return typed result.
- 401: clear auth rune, `goto('/login?next=<currentPath>')`. Skipped on `/login` itself.
- 403: surface a toast with the envelope's `message`; log a console warning (shouldn't happen if `/me/capabilities` gating is correct).
- 4xx (non-401/403): throw typed `ApiError({code, message})` parsed from the error envelope.
- 5xx / network error: throw `ApiError({code: 'network', message})` — callers render an inline banner with manual retry.
- Base URL: `PUBLIC_API_BASE || ""`.

### 5.2 Auth state

Rune-backed store:

```ts
let authState = $state<{user: User; capabilities: Set<Action>} | null>(null);
```

Hydrated by `+layout.ts` on first load. The backend's `GET /me/capabilities` returns `{actions: string[]}` — the hydration helper deserializes to `new Set(body.actions)` so lookups are O(1). The reverse is never needed (UI doesn't POST capabilities anywhere).

Logout: `POST /auth/logout` with the `X-CSRF-Token` header (required — `/auth/logout` is CSRF-enforced so cross-site logout can't silently succeed) → clear rune → `goto('/login')`.

### 5.3 Conversation list state

Single rune store `conversations = $state<ConversationSummary[]>([])`. Populated by `GET /conversations` on shell mount. Mutations update both server and store:

- Create → prepend.
- Rename → patch in place.
- Archive → remove.

No polling. Single-user scope per v1; another session's changes aren't reflected until reload.

### 5.4 SSE streaming (`lib/sse.ts`)

Typed discriminated union for events:

```ts
type RunEvent =
  | { type: 'message.delta'; delta: string; message_id: string;
      sequence: number; run_id: string }
  | { type: 'message.complete'; message: MessageOut;
      sequence: number; run_id: string }
  | { type: 'conversation.updated'; conversation_id: string; title: string;
      sequence: number; run_id: string }
  | { type: 'run.status'; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
      error?: { code: string; message: string };
      sequence: number; run_id: string }
  | { type: 'run.ended'; sequence: number; run_id: string };

type MessageOut = {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: { text: string };
  run_id: string | null;
  created_at: string;
  run_status: 'succeeded' | 'failed' | 'cancelled' | null;
  run_error: { code: string; message: string } | null;
};
```

Per-run state machine: `idle → queued → streaming → terminal → closed`. Driven by event arrivals.

Protocol order on success:

```
message.delta*  →  message.complete  →  run.status=succeeded
                                        ↓
                                        (backend awaits title generation)
                                        ↓
                   [conversation.updated]  (only if a title was generated)
                                        ↓
                                     run.ended   ← SSE handler closes HERE
```

Protocol order on failure / cancel (no `message.complete`):

```
message.delta*  →  run.status={failed|cancelled}  →  run.ended
```

- Open EventSource on `/runs/<id>/events`.
- `message.delta`: append `delta` to streaming bubble's text rune.
- `message.complete` (success path only): replace streaming bubble backing object with `message` (server-authoritative IDs/timestamps). Run state → awaiting terminal.
- `run.status=succeeded`: UI clears the "running" indicator and marks the bubble as settled. Does NOT close the stream — `conversation.updated` may still arrive.
- `conversation.updated`: patch the sidebar store's title for that conversation. Only arrives on success paths after `run.status=succeeded`.
- `run.status=failed`: UI converts the streaming bubble to a failed bubble carrying `error.code + message`. No preceding `message.complete` — the streaming bubble IS the terminal artifact. The backend has persisted this partial as an assistant message linked to the failed run, so a subsequent `GET /conversations/{id}` will return it with `run_status='failed'`.
- `run.status=cancelled`: same shape as failed. Convert streaming bubble to a cancelled bubble (no error). Partial text is persisted the same way.
- `run.ended`: SSE handler closes the stream. The ONLY event that closes the stream — `run.status` alone is a state signal, not a terminator.
- `error` event (native EventSource): close stream, show "Disconnected — reload to retry" banner.
- Unsubscribe on route change / component unmount.
- No auto-reconnect in v1.

**Why `run.ended` is separate from `run.status`.** Title generation takes an LLM round-trip (seconds). If the stream closed on `run.status=succeeded`, the subsequent `conversation.updated` would be dropped and the sidebar title would lag until the next full page reload. Emitting `succeeded` eagerly + closing on an explicit `run.ended` lets the UI clear its "running" indicator immediately while still picking up the title update in the same stream.

**Terminal-without-complete contract.** The UI must NOT assume every `run.status=succeeded` event is preceded by a `message.complete` — it IS on the success path, but `failed` and `cancelled` paths skip `message.complete` entirely. The streaming bubble is the terminal artifact in those cases, until a reload hydrates the persisted version from `GET /conversations/{id}`.

### 5.5 Markdown rendering (`lib/markdown.ts`)

Pipeline: `marked.parse(text)` → `DOMPurify.sanitize(html, {ALLOWED_TAGS: [...]})` → `innerHTML`.

- Fence highlighting via `highlight.js` with language allowlist: `ts, js, py, bash, json, yaml, sql, md`. Unknown languages render as plain `<pre><code>`.
- All hyperlinks get `rel="noopener noreferrer"` and `target="_blank"` (DOMPurify `ADD_ATTR` hook).
- **User messages are not markdown-rendered** — plain text only, to prevent user input being interpreted as structure.

### 5.6 CSRF edge case

On first page load after login, the CSRF cookie is already set (backend delivered it on the callback response). The fetch wrapper reads `document.cookie` at call time — no race. If the cookie is missing when an unsafe fetch is attempted, the wrapper throws `ApiError({code: 'csrf_missing'})` before the request leaves the browser, so the error surfaces as a client-side issue rather than a server 403.

---

## 6. Error handling

| Surface | Behavior |
|---|---|
| 401 on any fetch | Wrapper clears auth rune, `goto('/login?next=<path>')`. Skipped on `/login`. |
| 403 on any fetch | Toast with envelope `message`; console warning. |
| 500 / 502 / network | Inline banner on the affected view with manual retry button. No auto-retry. |
| SSE `error` event | Stream closes; chat header banner: "Disconnected — reload to resume". |
| SSE `run.status=failed` | Assistant bubble gets a red "Failed" affordance with `error.code + message`. No preceding `message.complete` — the streaming bubble IS the terminal bubble. On reload, the backend surfaces the partial message with `run_status='failed'` and `run_error` populated. User can compose again. If `content.text` is empty (failure before first delta), render a placeholder bubble `"No response — the run failed: <error.message>"` so the attempt stays visible. |
| Cancel in-flight | Cancel button next to the streaming indicator → `POST /runs/<id>/cancel` (returns 204 while in flight, 409 on a run that already terminated — treat 409 as "nothing to cancel"). Bubble settles to partial text, labeled "Cancelled". Partial text is persisted server-side (same shape as failed); reload shows it with `run_status='cancelled'` and an amber badge. Empty-text edge case: render `"No response — the run was cancelled"`. |
| OAuth callback failure | Login page reads `?auth_error=<code>` and maps to a friendly message via the vocabulary below. Unknown codes fall back to a generic "Sign-in failed — please try again." |
| Unhandled boundary | `+error.svelte` catches load-time failures; shows a reload-friendly shell. |

**OAuth `auth_error` vocabulary.** Backend forwards the `error` field from Entra's token endpoint response verbatim, falling back to `token_exchange_failed` if the body isn't parseable JSON. The login page maps these to user-facing strings:

| `auth_error=` | User-facing message |
|---|---|
| `invalid_grant` | "Sign-in expired. Please try again." |
| `invalid_client` | "Backend is misconfigured (client credentials rejected). Contact the admin." |
| `invalid_request` | "Sign-in request was malformed. Please try again." |
| `unauthorized_client` | "This app isn't authorized to sign in. Contact the admin." |
| `unsupported_grant_type` | "Backend is misconfigured. Contact the admin." |
| `consent_required` | "Additional consent is needed. Contact the admin to approve the app for your account." |
| `interaction_required` | "Please sign in again." |
| `token_exchange_failed` (backend fallback) | "We couldn't complete sign-in. Please try again." |
| *anything else* | "Sign-in failed — please try again." + log the raw code to console for debugging |

---

## 7. Testing

### 7.1 Playwright (`tests/e2e/`) — critical paths

1. **Login → chat → stream → reply visible.** Uses `/auth/devonly/login` for the auth step (same approach as the backend E2E smoke). Asserts an assistant message appears and contains text.
2. **Conversation rename → archive.** Create, rename inline, archive, assert sidebar removal.
3. **Cancel in-flight run.** POST message → observe streaming → click Cancel → assert status transitions to `cancelled`.
4. **401 recovery.** Revoke the session cookie mid-session (hit `POST /auth/logout` out-of-band), click anywhere that fetches, assert redirect to `/login?next=<path>`.

`playwright.config.ts` uses `webServer` to launch `pnpm preview` against a built bundle. Backend is started by the test runner against a disposable testcontainers Postgres, mirroring backend test fixtures. CI runs both.

### 7.2 Vitest (`tests/unit/`) — pure logic

- **`markdown.ts`:** assistant text with `<script>`, event handlers, and `javascript:` URLs is stripped (DOMPurify regression guard).
- **`sse.ts`:** feed synthetic events through the parser; assert state machine transitions and that assembled text equals the concatenation of deltas.
- **`api.ts`:** CSRF header injection on unsafe methods; 401 triggers the auth-cleared hook; error envelope parsing.

### 7.3 No component-level tests in v1

Playwright covers the render-plus-interaction dimension. Component snapshot tests are churn without commensurate value at this scope.

---

## 8. Deferred / follow-on work

Not in scope for v1 but called out so the plan doesn't anticipate them:

- **SSE resume-on-reload.** Backend supports it via `?from_sequence=N`; UI adds the reconnect state machine when it becomes a real pain point.
- **Admin UI.** Gated behind `admin.*` capabilities. Lands when roles need to be managed and connections revoked.
- **Elevation flows.** Second cookie `session_elevated`, orthogonal to `check_permission`, triggered by first dangerous action per backend ROADMAP.
- **Connection consent UI** for downstream OAuth (MS Graph, Google, etc.) once backend Plan "Connections" lands.
- **Dark/light mode toggle.** Workbench aesthetic is dark by default; a toggle is a small follow-up.
- **Context compression for long conversations.** `_load_history` in `rehketo/agent/run.py` currently feeds the full message history to the LLM on every turn. This is a known ceiling — a fast-follow after v1 kicks the tires. The solution is a real context-compression design (summarization, rolling window with checkpoints, tokenizer-budgeted packing, or a hybrid), not a mechanical last-N cap.

---

## 9. Open questions

- **CSRF `path` on the CSRF cookie.** Backend sets `path="/"`. Not a question, just reminding the plan to verify during integration that the UI dev proxy doesn't strip it.
- **Multi-stage Dockerfile or separate UI build + volume mount?** Both are compatible with the `UI_STATIC_DIR` contract (§2.4). Pick one in the implementation plan based on how CI is already structured.
