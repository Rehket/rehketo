<script lang="ts">
	type Variant = 'failed' | 'cancelled';
	let { variant, message }: { variant: Variant; message?: string | undefined } = $props();

	let palette = $derived(
		variant === 'failed'
			? 'border-danger/40 bg-danger/10 text-danger'
			: 'border-warning/40 bg-warning/10 text-warning'
	);
	let label = $derived(variant === 'failed' ? 'Failed' : 'Cancelled');
</script>

<span
	class={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${palette}`}
	title={message}
>
	{label}
	{#if message}
		<span class="truncate text-[10px] opacity-80" title={message}>— {message}</span>
	{/if}
</span>
