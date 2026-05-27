import { defineConfig } from '@playwright/test';

// The Python e2e fixtures (rehketo-api/tests/e2e/) own the lifecycle of
// Postgres, the fake Bifrost, the api (uvicorn-in-thread), and serve the
// built SPA from the api's UI_STATIC_DIR mount. Playwright is invoked
// from pytest via subprocess; baseURL comes from REHKETO_BASE_URL.
// DO NOT add a `webServer` block here — pytest owns the server.

export default defineConfig({
	testDir: 'e2e',
	testMatch: '**/*.e2e.{ts,js}',
	// Default-deny: tests must set the right baseURL or fail loudly.
	use: {
		baseURL: process.env.REHKETO_BASE_URL,
		headless: true,
		// Capture artifacts on failure for debug from CI logs.
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure'
	},
	// Conservative timeout — fake Bifrost responds in <1s but UI load + nav
	// adds slack. CI is generally slower than local; bump if needed.
	timeout: 30_000,
	expect: { timeout: 10_000 },
	// One worker — the test suite shares one api instance, so parallel tests
	// would race on conversation/message state. Serialize for v1.
	workers: 1
});
