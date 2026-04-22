<script lang="ts">
	import { goto } from '$app/navigation';

	import { apiFetch } from '$lib/api';
	import { conversations } from '$lib/stores/conversations.svelte';
	import { ApiError, type ConversationSummary } from '$lib/types';

	let creating = $state(false);

	async function create(): Promise<void> {
		if (creating) return;
		creating = true;
		try {
			const { id } = await apiFetch<{ id: string }>('/conversations', {
				method: 'POST',
				body: JSON.stringify({})
			});
			const now = new Date(Date.now()).toISOString();
			const summary: ConversationSummary = {
				id,
				title: null,
				created_at: now,
				updated_at: now
			};
			conversations.prepend(summary);
			await goto(`/c/${id}`);
		} catch (err) {
			if (err instanceof ApiError) console.warn('new chat failed:', err.code, err.message);
			throw err;
		} finally {
			creating = false;
		}
	}
</script>

<button
	type="button"
	onclick={create}
	disabled={creating}
	class="flex w-full items-center justify-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-text transition-colors hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-60"
>
	<span class="text-base leading-none">+</span>
	<span>New chat</span>
</button>
