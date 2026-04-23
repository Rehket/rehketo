# 2026-04-22 — UI bugfix session follow-ups

Shipped today, tracked here for tomorrow. Spec of record:
`rehketo-api/docs/superpowers/specs/2026-04-20-svelte-ui-v1-design.md`.

## Fixed today

| # | Bug | Fix |
|---|---|---|
| 1 | SSE events never reached the UI — backend emits `event: <type>` frames, client only listened for generic `message` events | `sse.ts` registers one listener per event type (`message.delta`, `message.complete`, `run.status`, `conversation.updated`, `run.ended`). Mock in `sse.spec.ts` now dispatches by type to match browser semantics. |
| 2 | "Disconnected — reload to resume" flashed on every run | `sse.ts` `error` handler now suppresses `onError` when the stream has already reached a terminal status; `close()` is once-only so `onEnded` cannot fire twice. |
| 3 | New chat and sidebar navigation showed stale messages from the previous conversation | Chat pane extracted to `lib/components/ChatView.svelte`. `(app)/c/[id]/+page.svelte` wraps it with `{#key data.conversation.id}` so `$state` re-initializes per conversation (SvelteKit otherwise reuses same-route components). |
| 4 | Error `<Badge>` with long messages extended off-screen | `Badge.svelte` is now a fixed pill (`shrink-0 whitespace-nowrap`, tooltip only). The full error message renders as a separate `break-words` line inside `AssistantBubble`. |
| 5 | Markdown pipeline re-ran on every streaming token (O(n²)) | `MessageList` computes `isActivelyStreaming` from status; `AssistantBubble` renders plain `whitespace-pre-wrap` text during streaming, `<MarkdownView>` only after the run terminates. |
| 6 | Post-Entra callback always landed on `ui_post_login_url` regardless of where the user was headed | Backend `/auth/login?next=<path>` stores a short-lived `rehketo_oauth_next` cookie (path `/auth/`, httpOnly, SameSite=lax). `/auth/callback` reads it and redirects to `ui_origin + next`. `_is_safe_next` rejects anything that isn't a single-slash relative path. New tests in `tests/integration/test_auth_next_preservation.py`. |
| 7 | Layout load used fire-and-forget `goto('/login?next=…')` which raced with child-page loads and produced `?next=/login?next=/c/…` double-encoded URLs | `+layout.ts` uses `throw redirect(302, …)`. `(app)/c/[id]/+page.ts` passes `skipAuthRedirect` and throws its own `redirect`. The auth-expired hook short-circuits when `window.location.pathname` is already `/login` so late 401s don't re-enter the login route. |

> Firefox "didn't prompt sign-in" → Entra SSO used an existing session. Not a bug.

## Next up

### P1 — finish verifying the streaming path

`DEVONLY_LOGIN_ENABLED` is currently `false` in `.env`, so chrome-devtools
MCP couldn't drive a full chat turn. Flip to `true`, restart backend, then:

1. Send a short message, watch the Network tab `eventstream` entry — confirm
   every frame's event name (not just `message`).
2. Hit send again with Anthropic mid-outage, confirm the "Disconnected" banner
   does NOT appear and the failed bubble renders with its inline error.
3. New-chat from a populated conversation — confirm the pane clears.
4. Sidebar-click between two conversations — confirm no stale messages and
   no perceptible "reload" flash.

Flip `DEVONLY_LOGIN_ENABLED` back to `false` after.

### P2 — the e2e gap that let these bugs through

`rehketo-ui/playwright.config.ts` and `AGENTS.md` both reference a
`tests/e2e/` directory that does not exist. Every bug shipped today is the
class a real-browser e2e would have caught on the first run. Minimum viable
suite (one test per path in spec §3.2):

- login → send → assert a delta actually rendered → assert no banner
- run failure (mock Anthropic 529) → assert Failed badge + inline error, no banner
- cancel in flight → assert Cancelled badge
- 401 mid-session → assert `/login?next=<current>`, no double-encode

Wire into `pnpm test` once devonly login has a Playwright auth-state helper.

### P3 — `ConversationListItem` invalid markup

`<a href="/c/…"><ConversationMenu>…<button>…</button></ConversationMenu></a>`
nests buttons inside an anchor. Today the `⋯` button relies on
`e.stopPropagation()`; keyboard Enter on that button will also activate the
anchor. Refactor: the list item becomes a `<button>` that calls
`goto()`, with the action menu as a sibling positioned via `relative`.
Preserve the capability gating already in place.

### P4 — `ENTRA_REDIRECT_URI` scope

Observed `redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fcallback` in
the `/auth/login` 302 today. Per README the dev redirect URI should be
`http://localhost:5173/auth/callback` so the session cookies set by the
callback land on the UI origin. If callbacks have been working, the cookie
domain trick is carrying us, but it's worth tightening the env value and
deleting any dual Entra redirect URIs.

## Tooling wins worth keeping

- `chrome-devtools` MCP (connected tonight) made the `next=` and redirect-race
  bugs visible in seconds via the Network tab. Keep it in the dev loop for
  any UI work touching navigation, cookies, or streams.
- The `sse.spec.ts` mock now dispatches by `event:` type. Future SSE protocol
  additions that forget a listener will fail this test — the bug class from
  today can't silently come back.
