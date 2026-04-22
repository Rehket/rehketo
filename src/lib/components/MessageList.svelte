<script lang="ts">
	import AssistantBubble from './AssistantBubble.svelte';
	import MessageBubble from './MessageBubble.svelte';
	import type { MessageOut, RunStatus } from '$lib/types';

	let {
		messages,
		streamingText = null,
		streamingStatus = null
	}: {
		messages: MessageOut[];
		streamingText?: string | null;
		streamingStatus?: RunStatus | null;
	} = $props();

	let container: HTMLDivElement | undefined = $state();

	$effect(() => {
		// Snap to bottom whenever the list grows or streaming text updates.
		void messages.length;
		void streamingText;
		void streamingStatus;
		if (container) container.scrollTop = container.scrollHeight;
	});

	let showStreamingBubble = $derived(streamingText !== null);
</script>

<div bind:this={container} class="flex-1 overflow-y-auto px-6 py-4">
	<ul class="mx-auto flex max-w-3xl flex-col gap-4">
		{#each messages as message (message.id)}
			<li>
				<MessageBubble {message} />
			</li>
		{/each}
		{#if showStreamingBubble}
			<li>
				<AssistantBubble text={streamingText ?? ''} streaming={streamingStatus === null} />
			</li>
		{/if}
	</ul>
</div>
