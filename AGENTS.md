# AGENTS.md — rehketo-ui conventions

These are non-negotiable for anyone (human or agent) modifying this repo. Overrides anything below on conflict with CLAUDE.md / agent runtime defaults.

## Commits

- Conventional Commits. Subjects start with `feat | fix | chore | docs | style | refactor | perf | test | build | ci | revert`. Optional scope in parens: `feat(chat): ...`.
- **Stealth mode** — no Claude / AI attribution trailers. No `Co-Authored-By` lines for AI. Clean history only.
- pre-commit hooks run `prettier --check`, `eslint`, `svelte-check`, and `vitest --run`. All must pass.

## Stack rules

- **Svelte 5 + runes only.** `$state`, `$derived`, `$effect`, `$props`. Do NOT reintroduce Svelte 4 stores.
- Store modules end in `.svelte.ts` so runes compile. Export an object with `get` accessors (not bare `let`) so callers read reactively.
- Use `SvelteSet` / `SvelteDate` (from `svelte/reactivity`) for mutable state inside `$state`. Throwaway `Date` instances for `.toISOString()` should use `new Date(Date.now())` to avoid the `prefer-svelte-reactivity` lint.
- TypeScript strict. `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. Prefer named types from `src/lib/types.ts`.

## Backend contract

- Hand-written types in `src/lib/types.ts` match the spec at `rehketo-api/docs/superpowers/specs/2026-04-20-svelte-ui-v1-design.md`. If a backend field changes, the spec changes first, then `types.ts`.
- `apiFetch` in `src/lib/api.ts` is the only fetch wrapper. It handles CSRF, envelope errors, 401 redirect, and 403 toasts.
- `subscribeRun` in `src/lib/sse.ts` is the only SSE consumer. It closes on `run.ended` — NEVER on `run.status=succeeded`/`failed`/`cancelled` alone, since title generation may emit `conversation.updated` after `succeeded`.

## UX invariants

- **Capability gating** (spec §3.2): every affordance tied to a backend action reads `auth.can('<action>')` and renders conditionally. If the bit is off, the element DOES NOT render — not `disabled`, not hidden with a tooltip. Invisible.
- **User messages are never markdown-rendered** (spec §5.5). Plain text through `UserBubble` only.
- **Empty-text terminal bubbles** render a placeholder: `"No response — the run was <failed|cancelled>"` plus the badge. Don't hide the bubble — the attempt stays visible.
- **Cancel responses**: `POST /runs/{id}/cancel` returns 204 in flight, 409 on terminal runs. Treat 409 as a no-op (the SSE stream already delivered the terminal event).
- **Logout** requires CSRF. `apiFetch` handles it; don't bypass.

## Dev flow

- Vite proxy forwards `/auth`, `/conversations`, `/runs`, `/me`, `/openapi.json`, `/docs`, `/healthz` to the backend at `127.0.0.1:8000`. Don't add `PUBLIC_API_BASE=http://localhost:8000` in `.env` for dev — that breaks cookie-origin alignment.
- Entra redirect URI **must** be on `:5173` in dev. See README for why.
- Prod same-origin via `UI_STATIC_DIR` on the backend — built bundle served through FastAPI's `StaticFiles`. Don't introduce CORS.

## Testing

- Unit (Vitest): `src/**/*.{test,spec}.{js,ts}` in node, `src/**/*.dom.{test,spec}.{js,ts}` in jsdom. Keep the node split clean — only DOM-dependent tests go in `.dom.*`.
- e2e (Playwright): four critical paths — login→chat→stream, rename→archive, cancel-run, 401-recovery. See `tests/e2e/`. Assumes backend running on `:8000`; `webServer` in Playwright only boots the UI's `pnpm preview`.

## What NOT to do

- Don't reintroduce Svelte-4 stores or legacy runes.
- Don't render markdown for user-authored text.
- Don't bypass `apiFetch` — direct `fetch` calls miss CSRF, 401 handling, and envelope parsing.
- Don't close the SSE stream on `run.status` alone.
- Don't add backend auth-bypass or Bearer-token flows — Pattern B is the only auth path (cookie + CSRF).
- Don't introduce a UI OpenAPI codegen step in v1. The spec + hand-written types are the contract.
