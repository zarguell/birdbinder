<script lang="ts">
	let { percent, collected, total }: { percent: number; collected: number; total: number } = $props();

	const colorClass = $derived(() => {
		if (percent < 25) return 'bg-red-500';
		if (percent < 50) return 'bg-yellow-500';
		if (percent < 75) return 'bg-blue-500';
		return 'bg-green-500';
	});

	const barColor = $derived(colorClass());
</script>

<div class="w-full">
	<!-- Bar track -->
	<div class="h-3 w-full overflow-hidden rounded-full bg-gray-800">
		<div
			class="h-full rounded-full transition-all duration-500 ease-out {barColor}"
			style="width: {Math.min(100, Math.max(0, percent))}%"
		></div>
	</div>
	<!-- Label -->
	<p class="mt-1.5 text-xs text-gray-400">
		{collected} / {total} collected
		<span class="font-medium text-gray-300">({percent}%)</span>
	</p>
</div>
