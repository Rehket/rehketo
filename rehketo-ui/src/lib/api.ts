// Typed fetch wrapper for the rehketo-api backend.
//
// Responsibilities (matches spec §5.1):
// - credentials: 'include' so session cookies flow.
// - X-CSRF-Token header on unsafe methods, read from the non-httpOnly
//   rehketo_csrf cookie at call time. No cookie → throw before the fetch.
// - 2xx → parsed JSON (or undefined for 204).
// - 401 → clear auth state via onAuthExpired hook, then throw ApiError.
// - 403 / other 4xx → ApiError parsed from the server's error envelope.
// - 5xx / network error → ApiError({code: 'network', ...}).
//
// Routing (401 → /login?next=…) is NOT in this module. The layout hooks
// onAuthExpired to `goto()` so api.ts stays decoupled from SvelteKit's
// navigation.

import { ApiError, type ErrorEnvelope } from './types';

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

type ApiFetchInit = RequestInit & {
	skipAuthRedirect?: boolean;
};

let onAuthExpiredHook: (() => void) | null = null;
let onForbiddenHook: ((err: ApiError) => void) | null = null;

/** Register the callback invoked on 401 (typically clears auth state and
 *  navigates to /login). Called once from the root layout. */
export function registerAuthExpiredHook(fn: () => void): void {
	onAuthExpiredHook = fn;
}

/** Register the callback invoked on 403 (typically pushes a toast).
 *  Capability-gated UI should make 403s rare, but they can happen when
 *  the server's capability view has drifted. */
export function registerForbiddenHook(fn: (err: ApiError) => void): void {
	onForbiddenHook = fn;
}

function getCookie(name: string): string | null {
	if (typeof document === 'undefined') return null;
	const match = document.cookie.match(
		new RegExp('(?:^|; )' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '=([^;]*)')
	);
	return match ? decodeURIComponent(match[1] ?? '') : null;
}

function resolveUrl(path: string): string {
	const base = import.meta.env.PUBLIC_API_BASE ?? '';
	if (path.startsWith('http://') || path.startsWith('https://')) return path;
	if (!path.startsWith('/')) return `${base}/${path}`;
	return `${base}${path}`;
}

async function parseErrorEnvelope(res: Response): Promise<ErrorEnvelope> {
	try {
		const body = (await res.json()) as { error?: ErrorEnvelope };
		if (body.error && typeof body.error.code === 'string') return body.error;
	} catch {
		// fall through — response not JSON
	}
	return { code: `http_${res.status}`, message: res.statusText || 'request failed' };
}

export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
	const method = (init.method ?? 'GET').toUpperCase();
	const headers = new Headers(init.headers);

	if (UNSAFE_METHODS.has(method)) {
		const csrf = getCookie('rehketo_csrf');
		if (!csrf) {
			// Surface as a client-side issue so the user gets a clearer signal
			// than the server's generic 403.
			throw new ApiError({
				code: 'csrf_missing',
				message: 'CSRF cookie unavailable — log in again.'
			});
		}
		headers.set('X-CSRF-Token', csrf);
	}

	if (init.body !== undefined && !headers.has('Content-Type')) {
		headers.set('Content-Type', 'application/json');
	}

	let res: Response;
	try {
		res = await fetch(resolveUrl(path), {
			...init,
			method,
			headers,
			credentials: 'include'
		});
	} catch (err) {
		throw new ApiError({
			code: 'network',
			message: err instanceof Error ? err.message : 'network request failed'
		});
	}

	if (res.status === 401) {
		if (!init.skipAuthRedirect) onAuthExpiredHook?.();
		const env = await parseErrorEnvelope(res);
		throw new ApiError({ code: env.code, message: env.message, status: 401 });
	}

	if (res.status === 204) return undefined as T;

	if (res.ok) {
		return (await res.json()) as T;
	}

	const env = await parseErrorEnvelope(res);
	const err = new ApiError({ code: env.code, message: env.message, status: res.status });
	if (res.status === 403) {
		onForbiddenHook?.(err);
		console.warn('403 on', resolveUrl(path), '—', env.code, env.message);
	}
	throw err;
}
