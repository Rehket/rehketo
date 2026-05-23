<script lang="ts">
	import { page } from '$app/state';
</script>

<section
	class="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-6 text-center text-text"
>
	<h1 class="text-2xl font-semibold">Something went wrong</h1>
	<p class="text-muted">
		{page.error?.message ?? 'Unexpected error'}
	</p>
	<button
		type="button"
		class="rounded-md bg-surface px-4 py-2 text-sm hover:bg-surface-hover"
		onclick={() => location.reload()}
	>
		Reload
	</button>
</section>
