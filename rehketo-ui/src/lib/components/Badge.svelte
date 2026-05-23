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

<!--
  Pill only. The full error message (when present) is hovered via `title`,
  and rendered in a wrap-capable line by the caller — so long backend
  errors don't stretch the badge off-screen.
-->
<span
	class={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap ${palette}`}
	title={message ?? undefined}
>
	{label}
</span>
