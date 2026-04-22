<script lang="ts">
	import { goto } from '$app/navigation';

	import { apiFetch } from '$lib/api';
	import { auth } from '$lib/stores/auth.svelte';
	import { conversations } from '$lib/stores/conversations.svelte';

	let {
		conversationId,
		title
	}: {
		conversationId: string;
		title: string | null;
	} = $props();

	let editing = $state(false);
	let draft = $state('');

	function startEdit(): void {
		if (!auth.can('chat.rename_conversation')) return;
		draft = title ?? '';
		editing = true;
	}

	async function submitEdit(): Promise<void> {
		const next = draft.trim();
		if (!next || next === title) {
			editing = false;
			return;
		}
		await apiFetch(`/conversations/${conversationId}`, {
			method: 'PATCH',
			body: JSON.stringify({ title: next })
		});
		conversations.patchTitle(conversationId, next);
		conversations.bumpUpdatedAt(conversationId);
		editing = false;
	}

	async function archive(): Promise<void> {
		await apiFetch(`/conversations/${conversationId}`, { method: 'DELETE' });
		conversations.remove(conversationId);
		await goto('/');
	}

	function onKeydown(e: KeyboardEvent): void {
		if (e.key === 'Enter') void submitEdit();
		else if (e.key === 'Escape') editing = false;
	}

	let displayTitle = $derived(title?.trim() || 'New chat');
</script>

<header
	class="flex items-center justify-between border-b border-border bg-bg/80 px-6 py-3 backdrop-blur-sm"
>
	{#if editing}
		<input
			type="text"
			bind:value={draft}
			onblur={submitEdit}
			onkeydown={onKeydown}
			class="w-full max-w-md rounded-md bg-surface px-3 py-1.5 text-sm text-text ring-1 ring-accent outline-none"
		/>
	{:else}
		<button
			type="button"
			onclick={startEdit}
			class="truncate text-left text-base font-semibold text-text transition-colors hover:text-accent"
		>
			{displayTitle}
		</button>
	{/if}

	{#if auth.can('chat.delete_conversation')}
		<button
			type="button"
			onclick={archive}
			class="rounded-md px-3 py-1 text-xs text-muted transition-colors hover:bg-surface hover:text-danger"
		>
			Archive
		</button>
	{/if}
</header>
