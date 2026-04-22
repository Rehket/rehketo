<script lang="ts">
	// (app) group layout — the authenticated chat shell.
	// Sidebar, user menu, and toast mount land here in T8 + T14 + T16.
	let { children } = $props();
</script>

<div class="flex h-screen w-screen overflow-hidden">
	<!-- T8 mounts Sidebar here -->
	<main class="flex flex-1 flex-col overflow-hidden">
		{@render children()}
	</main>
</div>
