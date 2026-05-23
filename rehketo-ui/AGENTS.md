# Rehketo UI — AGENTS.md

These are non-negotiable for anyone (human or agent) modifying `rehketo-ui`. They override agent runtime defaults on conflict. The repo-wide North Star and charter live in the root `AGENTS.md`.

## What it is

The rehketo-ui frontend: a SvelteKit (`adapter-static`) thin client. Cookies carry auth; `/me/capabilities` drives UI affordances; `EventSource` consumes run SSE. One half of the rehketo monorepo — the root `AGENTS.md` holds the North Star.

## How to validate work

From `rehketo-ui/`. Quote real output (charter rule 5).

```bash
pnpm run lint                 # prettier --check + eslint (incl. no-raw-fetch, no-user-markdown)
pnpm run check                # svelte-check
pnpm run test:unit -- --run   # vitest
```

These run in pre-commit (`.pre-commit-config.yaml`, scoped to `rehketo-ui/`) and in CI. The UI invariants below are enforced as ESLint rules — see `eslint.config.js`.

## Where things live

- `src/lib/api.ts` — `apiFetch`, the **only** fetch wrapper (CSRF, 401/403, envelope).
- `src/lib/sse.ts` — `subscribeRun`, the **only** SSE consumer.
- `src/lib/types.ts` — hand-written backend contract types.
- `src/lib/components/` — Svelte components. `src/routes/` — pages.

## Conventions in force

### Commits

- Conventional Commits. Subjects start with `feat | fix | chore | docs | style | refactor | perf | test | build | ci | revert`. Optional scope in parens: `feat(chat): ...`.
- **Stealth mode** — no Claude / AI attribution trailers. No `Co-Authored-By` lines for AI. Clean history only. (enforced: `check-no-ai-attribution`)

### Stack rules

- **Svelte 5 + runes only.** `$state`, `$derived`, `$effect`, `$props`. Do NOT reintroduce Svelte 4 stores.
- Store modules end in `.svelte.ts` so runes compile. Export an object with `get` accessors (not bare `let`) so callers read reactively.
- Use `SvelteSet` / `SvelteDate` (from `svelte/reactivity`) for mutable state inside `$state`. Throwaway `Date` instances for `.toISOString()` should use `new Date(Date.now())` to avoid the `prefer-svelte-reactivity` lint.
- TypeScript strict. `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. Prefer named types from `src/lib/types.ts`.

### Backend contract

- Hand-written types in `src/lib/types.ts` match the spec at `rehketo-api/docs/superpowers/specs/2026-04-20-svelte-ui-v1-design.md`. If a backend field changes, the spec changes first, then `types.ts`. (The OpenAPI snapshot guard `check_contract.py` surfaces backend drift.)
- `apiFetch` in `src/lib/api.ts` is the only fetch wrapper. It handles CSRF, envelope errors, 401 redirect, and 403 toasts. (enforced: eslint `no-raw-fetch`)
- `subscribeRun` in `src/lib/sse.ts` is the only SSE consumer. It closes on `run.ended` — NEVER on `run.status=succeeded`/`failed`/`cancelled` alone, since title generation may emit `conversation.updated` after `succeeded`. (covered by `sse.spec.ts`)

### UX invariants

- **Capability gating** (spec §3.2): every affordance tied to a backend action reads `auth.can('<action>')` and renders conditionally. If the bit is off, the element DOES NOT render — not `disabled`, not hidden with a tooltip. Invisible.
- **User messages are never markdown-rendered** (spec §5.5). Plain text through `UserBubble` only. (enforced: eslint `no-user-markdown`)
- **Empty-text terminal bubbles** render a placeholder: `"No response — the run was <failed|cancelled>"` plus the badge. Don't hide the bubble — the attempt stays visible.
- **Cancel responses**: `POST /runs/{id}/cancel` returns 204 in flight, 409 on terminal runs. Treat 409 as a no-op (the SSE stream already delivered the terminal event).
- **Logout** requires CSRF. `apiFetch` handles it; don't bypass.

### Dev flow

- Vite proxy forwards `/auth`, `/conversations`, `/runs`, `/me`, `/openapi.json`, `/docs`, `/healthz` to the backend at `127.0.0.1:8000`. Don't add `PUBLIC_API_BASE=http://localhost:8000` in `.env` for dev — that breaks cookie-origin alignment.
- Entra redirect URI **must** be on `:5173` in dev. See README for why.
- Prod same-origin via `UI_STATIC_DIR` on the backend — built bundle served through FastAPI's `StaticFiles`. Don't introduce CORS.

### Testing

- Unit (Vitest): `src/**/*.{test,spec}.{js,ts}` in node, `src/**/*.dom.{test,spec}.{js,ts}` in jsdom. Keep the node split clean — only DOM-dependent tests go in `.dom.*`.
- e2e (Playwright): four critical paths — login→chat→stream, rename→archive, cancel-run, 401-recovery. See `tests/e2e/`. Assumes backend running on `:8000`; `webServer` in Playwright only boots the UI's `pnpm preview`.

## Don'ts

- Don't reintroduce Svelte-4 stores or legacy runes.
- Don't render markdown for user-authored text. (enforced: eslint `no-user-markdown`)
- Don't bypass `apiFetch` — direct `fetch` calls miss CSRF, 401 handling, and envelope parsing. (enforced: eslint `no-raw-fetch`)
- Don't close the SSE stream on `run.status` alone. (covered by `sse.spec.ts`)
- Don't add backend auth-bypass or Bearer-token flows — Pattern B is the only auth path (cookie + CSRF).
- Don't introduce a UI OpenAPI codegen step in v1. The spec + hand-written types are the contract.
