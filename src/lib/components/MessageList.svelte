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
	// "Streaming" means deltas are still flowing — i.e. the run hasn't
	// reached a terminal status yet. Guards the O(n²) markdown render
	// during streaming (we show plain text instead) and the pulsing dot.
	let isActivelyStreaming = $derived(
		streamingStatus === null || streamingStatus === 'queued' || streamingStatus === 'running'
	);
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
				<AssistantBubble text={streamingText ?? ''} streaming={isActivelyStreaming} />
			</li>
		{/if}
	</ul>
</div>
