<script lang="ts">
	import { renderMarkdown } from '$lib/markdown';

	let { text }: { text: string } = $props();
	let html = $derived(renderMarkdown(text));
</script>

<div
	class="prose prose-sm max-w-none prose-invert prose-code:rounded prose-code:bg-surface prose-code:px-1 prose-code:py-0.5 prose-pre:bg-bg"
>
	<!-- html is produced by renderMarkdown() which runs DOMPurify.sanitize
	     as its final step. Trusted by construction; the eslint rule doesn't
	     know that. -->
	<!-- eslint-disable-next-line svelte/no-at-html-tags -->
	{@html html}
</div>
