<script lang="ts">
	import Sidebar from '$lib/components/Sidebar.svelte';

	let { children } = $props();
</script>

<div class="flex h-screen w-screen overflow-hidden">
	<Sidebar />
	<main class="flex flex-1 flex-col overflow-hidden">
		{@render children()}
	</main>
</div>
