import { redirect } from '@sveltejs/kit';

import { goto } from '$app/navigation';

import { apiFetch, registerAuthExpiredHook, registerForbiddenHook } from '$lib/api';
import { auth } from '$lib/stores/auth.svelte';
import { toasts } from '$lib/stores/toasts.svelte';
import { ApiError, type CapabilitiesOut, type MeOut } from '$lib/types';
import type { LayoutLoad } from './$types';

// adapter-static has no server runtime, so load runs in the browser.
export const ssr = false;
export const prerender = false;

function loginHrefFor(url: URL): string {
	const currentPath = url.pathname + url.search;
	const next = encodeURIComponent(currentPath || '/');
	return `/login?next=${next}`;
}

// Register the 401 hook once. apiFetch fires this on unauthorized responses
// (except when skipAuthRedirect is set) so any fetch from anywhere in the
// app triggers the same recovery path. The URL argument is captured at
// install time — for post-load 401s we want "wherever the user is NOW",
// not where they were on the initial load.
let authHookInstalled = false;
function installAuthHook(): void {
	if (authHookInstalled) return;
	authHookInstalled = true;
	registerAuthExpiredHook(() => {
		const here = new URL(window.location.href);
		// Already on /login (e.g. the layout already redirected us and a
		// sibling load is 401ing on its own): don't re-redirect, or we
		// double-encode the `next` param — "/login?next=/login?next=/c/x".
		if (here.pathname === '/login' || here.pathname.startsWith('/login/')) return;
		auth.clear();
		// post-load 401 (e.g. session expired while browsing): use goto,
		// which is the documented client-side nav primitive. Read the URL
		// at call time so `next` captures the current page.
		void goto(loginHrefFor(here), { replaceState: true });
	});
	registerForbiddenHook((err) => {
		toasts.push({ variant: 'error', message: err.message });
	});
}

export const load: LayoutLoad = async ({ url, route }) => {
	installAuthHook();

	// The login page handles its own state. Skipping /me here keeps a
	// signed-out user from bouncing to an error.
	if (route.id?.startsWith('/login')) {
		return { authenticated: false };
	}

	try {
		const [me, caps] = await Promise.all([
			apiFetch<MeOut>('/me', { skipAuthRedirect: true }),
			apiFetch<CapabilitiesOut>('/me/capabilities', { skipAuthRedirect: true })
		]);
		auth.hydrate(me, caps);
		return { authenticated: true };
	} catch (err) {
		if (err instanceof ApiError && err.status === 401) {
			// `throw redirect()` is the documented way to redirect from
			// `load`. The previous `void goto(…)` approach was fire-and-
			// forget: the load would resolve with `authenticated: false`,
			// children would render briefly, and children's own fetches
			// would queue *another* goto — racing in some browsers (Firefox
			// has been seen to end up on the protected page with blank
			// data).
			throw redirect(302, loginHrefFor(url));
		}
		throw err;
	}
};
