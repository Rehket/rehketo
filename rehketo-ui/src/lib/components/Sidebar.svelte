<script lang="ts">
	import { onMount } from 'svelte';

	import ConversationListItem from './ConversationListItem.svelte';
	import NewChatButton from './NewChatButton.svelte';
	import UserMenu from './UserMenu.svelte';
	import { auth } from '$lib/stores/auth.svelte';
	import { conversations } from '$lib/stores/conversations.svelte';

	onMount(() => {
		if (!conversations.loaded) void conversations.load();
	});
</script>

<aside class="flex h-full w-64 shrink-0 flex-col border-r border-border bg-surface/40 px-3 py-4">
	<div class="mb-4">
		<h2 class="px-2 text-sm font-semibold tracking-wide text-muted uppercase">Rehketo</h2>
	</div>

	{#if auth.can('chat.create_conversation')}
		<NewChatButton />
	{/if}

	<nav class="mt-4 flex-1 overflow-y-auto">
		<ul class="flex flex-col gap-0.5">
			{#each conversations.items as c (c.id)}
				<li>
					<ConversationListItem conversation={c} />
				</li>
			{/each}
		</ul>
		{#if conversations.loaded && conversations.items.length === 0}
			<p class="mt-4 px-2 text-xs text-muted">No conversations yet.</p>
		{/if}
	</nav>

	<div class="mt-4 border-t border-border pt-3">
		<UserMenu />
	</div>
</aside>
