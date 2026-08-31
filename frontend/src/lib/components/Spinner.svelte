<script lang="ts">
	/** Shared loading spinner — replaces ~25 inlined SVG copies. */
	let { size = 'md', label = 'Loading' }: { size?: 'sm' | 'md' | 'lg'; label?: string } = $props();

	const sizeClass = {
		sm: 'h-4 w-4 border-2',
		md: 'h-8 w-8 border-2',
		lg: 'h-12 w-12 border-2'
	}[size];
</script>

<svg
	class={`animate-spin text-gray-600 border-brand ${sizeClass}`}
	viewBox="0 0 24 24"
	fill="none"
	role="status"
	aria-label={label}
>
	<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
	<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
</svg>
