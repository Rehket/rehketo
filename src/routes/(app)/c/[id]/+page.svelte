<script lang="ts">
	import ChatHeader from '$lib/components/ChatHeader.svelte';
	import MessageList from '$lib/components/MessageList.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Local mutable state seeded from the server-side fetch. SvelteKit
	// re-instantiates the component on route param change, so seeding
	// from `data` once at construction time is correct — the
	// `state_referenced_locally` warning is a false positive here.
	// svelte-ignore state_referenced_locally
	let messages = $state(data.conversation.messages);
	// svelte-ignore state_referenced_locally
	let title = $state(data.conversation.title);
</script>

<div class="flex h-full flex-col">
	<ChatHeader conversationId={data.conversation.id} {title} />
	<MessageList {messages} />
	<!-- Composer + streaming wiring land in T11 + T12. -->
</div>
