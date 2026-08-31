<script lang="ts">
	/** Shared empty state: icon, title, hint, optional action. */
	import type { Snippet } from 'svelte';

	let {
		icon,
		title,
		hint,
		children
	}: { icon?: string; title: string; hint?: string; children?: Snippet } = $props();
</script>

<div class="py-16 text-center space-y-3">
	{#if icon}
		<p class="text-4xl">{icon}</p>
	{/if}
	<p class="font-medium text-gray-400">{title}</p>
	{#if hint}
		<p class="mt-1 text-xs text-gray-600">{hint}</p>
	{/if}
	{@render children?.()}
</div>
