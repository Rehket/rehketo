import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { apiFetch, registerAuthExpiredHook } from './api';
import { ApiError } from './types';

// api.ts reads document.cookie for the CSRF token. Tests run in the node
// project (no DOM), so stub document globally per test.
function stubCookie(value: string | null): void {
	if (value === null) {
		vi.stubGlobal('document', undefined);
	} else {
		vi.stubGlobal('document', { cookie: value });
	}
}

function jsonResponse(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

const CSRF_COOKIE = 'rehketo_csrf=csrf-token-abc';

describe('apiFetch', () => {
	beforeEach(() => {
		registerAuthExpiredHook(() => undefined);
		stubCookie(CSRF_COOKIE);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		vi.restoreAllMocks();
	});

	test('GET parses JSON and does NOT send X-CSRF-Token', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
		vi.stubGlobal('fetch', fetchMock);

		const body = await apiFetch<{ ok: boolean }>('/me');

		expect(body).toEqual({ ok: true });
		const [, init] = fetchMock.mock.calls[0] ?? [];
		const headers = new Headers(init.headers);
		expect(headers.has('X-CSRF-Token')).toBe(false);
		expect(init.credentials).toBe('include');
	});

	test('POST injects X-CSRF-Token read from rehketo_csrf cookie', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { id: 'x' }));
		vi.stubGlobal('fetch', fetchMock);

		await apiFetch('/conversations', { method: 'POST', body: JSON.stringify({}) });

		const [, init] = fetchMock.mock.calls[0] ?? [];
		const headers = new Headers(init.headers);
		expect(headers.get('X-CSRF-Token')).toBe('csrf-token-abc');
		expect(headers.get('Content-Type')).toBe('application/json');
	});

	test('unsafe method without CSRF cookie throws csrf_missing without calling fetch', async () => {
		const fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);
		stubCookie('');

		await expect(apiFetch('/conversations', { method: 'POST' })).rejects.toMatchObject({
			name: 'ApiError',
			code: 'csrf_missing'
		});
		expect(fetchMock).not.toHaveBeenCalled();
	});

	test('204 returns undefined without parsing a body', async () => {
		const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
		vi.stubGlobal('fetch', fetchMock);

		const result = await apiFetch<void>('/auth/logout', { method: 'POST' });

		expect(result).toBeUndefined();
	});

	test('401 fires onAuthExpired hook and throws ApiError with status 401', async () => {
		const hook = vi.fn();
		registerAuthExpiredHook(hook);
		const fetchMock = vi
			.fn()
			.mockResolvedValue(jsonResponse(401, { error: { code: 'unauthorized', message: 'no' } }));
		vi.stubGlobal('fetch', fetchMock);

		await expect(apiFetch('/me')).rejects.toMatchObject({
			code: 'unauthorized',
			status: 401
		});
		expect(hook).toHaveBeenCalledTimes(1);
	});

	test('401 with skipAuthRedirect does NOT fire the hook', async () => {
		const hook = vi.fn();
		registerAuthExpiredHook(hook);
		const fetchMock = vi
			.fn()
			.mockResolvedValue(jsonResponse(401, { error: { code: 'unauthorized', message: 'no' } }));
		vi.stubGlobal('fetch', fetchMock);

		await expect(apiFetch('/me', { skipAuthRedirect: true })).rejects.toBeInstanceOf(ApiError);
		expect(hook).not.toHaveBeenCalled();
	});

	test('403 parses the error envelope code + message', async () => {
		const fetchMock = vi
			.fn()
			.mockResolvedValue(
				jsonResponse(403, { error: { code: 'forbidden', message: 'no permission' } })
			);
		vi.stubGlobal('fetch', fetchMock);

		await expect(apiFetch('/conversations/123', { method: 'DELETE' })).rejects.toMatchObject({
			code: 'forbidden',
			message: 'no permission',
			status: 403
		});
	});

	test('500 with non-JSON body falls back to http_500 code', async () => {
		const fetchMock = vi.fn().mockResolvedValue(new Response('<html>oops</html>', { status: 500 }));
		vi.stubGlobal('fetch', fetchMock);

		await expect(apiFetch('/me')).rejects.toMatchObject({
			code: 'http_500',
			status: 500
		});
	});

	test('network failure surfaces as ApiError code=network', async () => {
		const fetchMock = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		vi.stubGlobal('fetch', fetchMock);

		await expect(apiFetch('/me')).rejects.toMatchObject({
			code: 'network'
		});
	});
});
