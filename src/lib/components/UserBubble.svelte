<script lang="ts">
	// User messages are NEVER markdown-rendered (spec §5.5).
	let { text }: { text: string } = $props();
</script>

<div class="flex justify-end">
	<div
		class="max-w-[80%] rounded-2xl rounded-br-md bg-accent/90 px-4 py-2 text-sm whitespace-pre-wrap text-white"
	>
		{text}
	</div>
</div>
