// Sidebar conversation list state. Single-user scope per v1; another
// session's changes aren't reflected until reload. No polling.

import { apiFetch } from '$lib/api';
import type { ConversationList, ConversationSummary } from '$lib/types';

let items = $state<ConversationSummary[]>([]);
let loaded = $state(false);

export const conversations = {
	get items(): ConversationSummary[] {
		return items;
	},
	get loaded(): boolean {
		return loaded;
	},
	async load(): Promise<void> {
		const body = await apiFetch<ConversationList>('/conversations?include_archived=false');
		items = body.items;
		loaded = true;
	},
	prepend(c: ConversationSummary): void {
		items = [c, ...items];
	},
	patchTitle(id: string, title: string): void {
		items = items.map((c) => (c.id === id ? { ...c, title } : c));
	},
	bumpUpdatedAt(id: string): void {
		// Throwaway ISO string — no reactivity on this Date instance.
		// eslint-disable-next-line svelte/prefer-svelte-reactivity
		const now = new Date(Date.now()).toISOString();
		items = items.map((c) => (c.id === id ? { ...c, updated_at: now } : c));
		items.sort((a, b) => (a.updated_at > b.updated_at ? -1 : 1));
	},
	remove(id: string): void {
		items = items.filter((c) => c.id !== id);
	},
	clear(): void {
		items = [];
		loaded = false;
	}
};
