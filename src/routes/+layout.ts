import { goto } from '$app/navigation';

import { apiFetch, registerAuthExpiredHook } from '$lib/api';
import { auth } from '$lib/stores/auth.svelte';
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
// app triggers the same recovery path.
let authHookInstalled = false;
function installAuthHook(url: URL): void {
	if (authHookInstalled) return;
	authHookInstalled = true;
	registerAuthExpiredHook(() => {
		auth.clear();
		void goto(loginHrefFor(url), { replaceState: true });
	});
}

export const load: LayoutLoad = async ({ url, route }) => {
	installAuthHook(url);

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
			void goto(loginHrefFor(url), { replaceState: true });
			return { authenticated: false };
		}
		throw err;
	}
};
