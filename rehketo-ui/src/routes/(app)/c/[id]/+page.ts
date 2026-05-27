import { error, redirect } from '@sveltejs/kit';

import { apiFetch } from '$lib/api';
import { ApiError, type ConversationDetail } from '$lib/types';
import type { PageLoad } from './$types';

export const ssr = false;
export const prerender = false;

export const load: PageLoad = async ({ params, url }) => {
	try {
		// skipAuthRedirect: the layout load runs in parallel and handles 401
		// via its own throw redirect(). If this load also fires the
		// auth-expired hook, two gotos race and the `next=` param ends up
		// double-encoded — "/login?next=/login?next=/c/x".
		const detail = await apiFetch<ConversationDetail>(`/conversations/${params.id}`, {
			skipAuthRedirect: true
		});
		return { conversation: detail };
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 401) {
				const next = encodeURIComponent(url.pathname + url.search);
				throw redirect(302, `/login?next=${next}`);
			}
			if (err.status === 404) throw error(404, 'Conversation not found');
			throw error(err.status || 500, err.message);
		}
		throw err;
	}
};
