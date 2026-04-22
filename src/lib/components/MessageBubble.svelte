<script lang="ts">
	import AssistantBubble from './AssistantBubble.svelte';
	import UserBubble from './UserBubble.svelte';
	import type { MessageOut } from '$lib/types';

	let { message }: { message: MessageOut } = $props();
</script>

{#if message.role === 'user'}
	<UserBubble text={message.content.text} />
{:else if message.role === 'assistant'}
	<AssistantBubble
		text={message.content.text}
		runStatus={message.run_status}
		runError={message.run_error}
	/>
{/if}
