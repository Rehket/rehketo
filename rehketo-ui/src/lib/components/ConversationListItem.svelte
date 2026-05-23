<script lang="ts">
	import { page } from '$app/state';

	import ConversationMenu from './ConversationMenu.svelte';
	import type { ConversationSummary } from '$lib/types';

	let { conversation }: { conversation: ConversationSummary } = $props();

	let isActive = $derived(page.url.pathname === `/c/${conversation.id}`);
	let displayTitle = $derived(conversation.title?.trim() || 'New chat');
</script>

<a
	href={`/c/${conversation.id}`}
	class="group flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm transition-colors {isActive
		? 'bg-surface-hover text-text'
		: 'text-muted hover:bg-surface hover:text-text'}"
>
	<span class="truncate">{displayTitle}</span>
	<ConversationMenu {conversation} />
</a>
