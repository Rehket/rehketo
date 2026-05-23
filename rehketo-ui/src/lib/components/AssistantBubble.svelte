<script lang="ts">
	import Badge from './Badge.svelte';
	import MarkdownView from './MarkdownView.svelte';
	import RunStatusDot from './RunStatusDot.svelte';
	import type { ErrorEnvelope, RunStatus } from '$lib/types';

	let {
		text,
		streaming = false,
		runStatus = null,
		runError = null
	}: {
		text: string;
		streaming?: boolean;
		runStatus?: RunStatus | null;
		runError?: ErrorEnvelope | null;
	} = $props();

	let isTerminalFail = $derived(runStatus === 'failed' || runStatus === 'cancelled');
	// Empty text + terminal → placeholder (spec §4.3 step 11).
	let placeholder = $derived.by(() => {
		if (!isTerminalFail) return null;
		if (text.trim().length > 0) return null;
		if (runStatus === 'failed') {
			const msg = runError?.message ?? '';
			return msg ? `No response — the run failed: ${msg}` : 'No response — the run failed';
		}
		return 'No response — the run was cancelled';
	});
	// When there IS partial text AND the run failed with an error, surface
	// the error message on its own wrap-capable line — the Badge itself
	// stays a fixed-size pill so long errors can't push it off-screen.
	let inlineError = $derived(
		runStatus === 'failed' && text.trim().length > 0 ? (runError?.message ?? null) : null
	);
</script>

<div class="flex justify-start">
	<div class="max-w-[85%] min-w-0 rounded-2xl rounded-bl-md bg-surface px-4 py-3 text-sm text-text">
		{#if placeholder}
			<p class="text-muted italic">{placeholder}</p>
		{:else if streaming}
			<!-- Streaming: render plain text with preserved whitespace. Markdown
			     parse runs on every token otherwise, which is O(n²) work and
			     dominates perceived latency. Terminal messages below render
			     through the full marked → hljs → DOMPurify pipeline. -->
			<p class="whitespace-pre-wrap">{text}</p>
		{:else}
			<MarkdownView {text} />
		{/if}

		{#if inlineError}
			<p class="mt-2 text-xs break-words text-danger">{inlineError}</p>
		{/if}

		<div class="mt-2 flex items-center gap-2">
			{#if streaming}
				<RunStatusDot />
			{/if}
			{#if runStatus === 'failed'}
				<Badge variant="failed" message={runError?.message} />
			{:else if runStatus === 'cancelled'}
				<Badge variant="cancelled" />
			{/if}
		</div>
	</div>
</div>
