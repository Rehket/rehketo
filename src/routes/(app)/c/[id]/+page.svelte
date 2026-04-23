<script lang="ts">
	import ChatView from '$lib/components/ChatView.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<!--
  {#key} forces a remount when navigating to a different conversation on
  the same route (/c/[id]). SvelteKit reuses the page component across
  same-route navigation, so $state initializers inside ChatView would
  otherwise cling to the previous conversation's messages/title — the
  "new chats don't clear" and "sidebar click doesn't update the pane"
  bug. Keying on conversation.id gives us fresh local state per chat
  without plumbing effect resets for every stateful field.
-->
{#key data.conversation.id}
	<ChatView conversation={data.conversation} />
{/key}
