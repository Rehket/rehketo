<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';

	let {
		isStreaming = false,
		onSend
	}: {
		isStreaming?: boolean;
		onSend: (text: string) => void;
	} = $props();

	let text = $state('');
	let textarea: HTMLTextAreaElement | undefined = $state();

	let canWrite = $derived(auth.can('chat.write'));
	let disabled = $derived(!canWrite || isStreaming);

	function autoResize(): void {
		if (!textarea) return;
		textarea.style.height = 'auto';
		textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
	}

	function submit(): void {
		const value = text.trim();
		if (!value || disabled) return;
		onSend(value);
		text = '';
		if (textarea) {
			textarea.style.height = 'auto';
			textarea.focus();
		}
	}

	function onKeydown(e: KeyboardEvent): void {
		if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
			e.preventDefault();
			submit();
		}
	}

	$effect(() => {
		// Re-size on value mutation from elsewhere (e.g. cleared after submit).
		void text;
		autoResize();
	});
</script>

{#if canWrite}
	<div class="border-t border-border bg-bg/80 px-6 py-3 backdrop-blur-sm">
		<div class="mx-auto flex max-w-3xl items-end gap-2">
			<textarea
				bind:this={textarea}
				bind:value={text}
				oninput={autoResize}
				onkeydown={onKeydown}
				{disabled}
				rows="1"
				placeholder={isStreaming ? 'Waiting for reply…' : 'Message Rehketo…'}
				class="flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-muted focus:ring-1 focus:ring-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
			></textarea>
			<button
				type="button"
				onclick={submit}
				disabled={disabled || text.trim().length === 0}
				class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
			>
				Send
			</button>
		</div>
	</div>
{/if}
