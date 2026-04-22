# rehketo-ui

SvelteKit thin client for the [rehketo-api](../rehketo-api/) chat/agent backend. Static-adapter build, Workbench aesthetic, Svelte 5 runes, Tailwind 4.

Design spec: [`../rehketo-api/docs/superpowers/specs/2026-04-20-svelte-ui-v1-design.md`](../rehketo-api/docs/superpowers/specs/2026-04-20-svelte-ui-v1-design.md). Contributor conventions: [`AGENTS.md`](AGENTS.md).

## Prerequisites

- **Node 22 LTS** and **pnpm ≥ 10** on the host.
- **rehketo-api running on `:8000`**: `docker compose -f ../rehketo-api/deploy/docker-compose.yaml up -d postgres bifrost` + `uv run rehketo-serve` (see [rehketo-api's README](../rehketo-api/README.md)).
- **Entra app registration** with `http://localhost:5173/auth/callback` as a redirect URI (dev). See rehketo-api's README for why the dev redirect lives on the UI origin rather than the backend's.

## Dev workflow

```sh
pnpm install
pnpm dev
```

UI runs on `http://localhost:5173`. Vite proxies `/auth`, `/conversations`, `/runs`, `/me`, `/openapi.json`, `/docs`, `/healthz` to the backend at `127.0.0.1:8000`. The browser sees one origin, cookies flow, CSRF works.

**Dev startup order:** Postgres + Bifrost → backend (`uv run rehketo-serve`) → UI (`pnpm dev`) → open `http://localhost:5173/auth/login`. If you're not using Entra, `/auth/devonly/login` (when `DEVONLY_LOGIN_ENABLED=true` on the backend) issues a session cookie without leaving the stack.

## Production smoke (same-origin via backend)

```sh
pnpm build
# rehketo-ui/build/ now has index.html + immutable assets.
UI_STATIC_DIR="$PWD/build" uv run --project ../rehketo-api rehketo-serve
```

Open `http://127.0.0.1:8000/` — backend serves the SvelteKit bundle; API routes still win at their prefixes (`/auth/*`, `/conversations/*`, `/runs/*`, `/me`, `/docs`, `/openapi.json`, `/healthz`); unknown paths fall back to `index.html` so client-side routes like `/c/<uuid>` survive a reload.

## Tests

```sh
pnpm test:unit -- --run     # Vitest — api / sse / markdown
pnpm test:e2e               # Playwright — critical paths (requires a running backend)
pnpm check                  # svelte-check + tsc
pnpm lint                   # prettier + eslint
```

Vitest runs in two projects:

- `server` (node): `src/**/*.{test,spec}.{js,ts}` — pure logic (no DOM).
- `dom` (jsdom): `src/**/*.dom.{test,spec}.{js,ts}` — anything needing `window` (e.g., DOMPurify).

## Scripts

| Script           | What it does                                   |
| ---------------- | ---------------------------------------------- |
| `pnpm dev`       | Vite dev server on :5173 with backend proxy.   |
| `pnpm build`     | Static SvelteKit build into `build/`.          |
| `pnpm preview`   | Serve the built bundle locally (no API proxy). |
| `pnpm check`     | `svelte-check --tsconfig`.                     |
| `pnpm lint`      | Prettier + ESLint.                             |
| `pnpm format`    | Write Prettier fixes.                          |
| `pnpm test:unit` | Vitest.                                        |
| `pnpm test:e2e`  | Playwright.                                    |

## Conventions

- Conventional Commits. Types: `feat | fix | chore | docs | style | refactor | perf | test | build | ci | revert`.
- Svelte 5 runes only — no Svelte-4 stores.
- Hand-written types for the backend contract in `src/lib/types.ts`. No OpenAPI codegen in v1.
- Capability-gated rendering (`auth.can('chat.write')`, etc.): gated affordances DO NOT RENDER when the bit is off — never disabled, never tooltip'd.
- User messages are **never** markdown-rendered (spec §5.5).
- SSE stream closes on `run.ended`, not on `run.status`.

Full conventions in [AGENTS.md](AGENTS.md).
