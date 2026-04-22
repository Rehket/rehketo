import { error } from '@sveltejs/kit';

import { apiFetch } from '$lib/api';
import { ApiError, type ConversationDetail } from '$lib/types';
import type { PageLoad } from './$types';

export const ssr = false;
export const prerender = false;

export const load: PageLoad = async ({ params }) => {
	try {
		const detail = await apiFetch<ConversationDetail>(`/conversations/${params.id}`);
		return { conversation: detail };
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 404) throw error(404, 'Conversation not found');
			throw error(err.status || 500, err.message);
		}
		throw err;
	}
};
