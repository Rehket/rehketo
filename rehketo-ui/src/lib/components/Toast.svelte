<script lang="ts">
	import { toasts } from '$lib/stores/toasts.svelte';
</script>

<div class="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2">
	{#each toasts.items as t (t.id)}
		<div
			class="pointer-events-auto max-w-sm min-w-64 rounded-md border px-3 py-2 text-sm shadow-lg {t.variant ===
			'error'
				? 'border-danger/40 bg-danger/10 text-danger'
				: 'border-border bg-surface text-text'}"
			role="status"
		>
			<div class="flex items-start justify-between gap-2">
				<span class="flex-1">{t.message}</span>
				<button
					type="button"
					onclick={() => toasts.dismiss(t.id)}
					class="text-muted hover:text-text"
					aria-label="Dismiss"
				>
					×
				</button>
			</div>
		</div>
	{/each}
</div>
