<script lang="ts">
	let { species }: { species: string[] } = $props();
</script>

<div class="space-y-2">
	{#if species.length === 0}
		<div class="rounded-lg border border-green-800/40 bg-green-950/20 p-4 text-center">
			<p class="text-sm font-medium text-green-400">None missing! 🎉</p>
		</div>
	{:else}
		<p class="text-xs font-medium uppercase tracking-wider text-gray-500 mb-3">
			{species.length} missing
		</p>
		<ul class="space-y-1.5">
			{#each species as name}
				<li class="flex items-center gap-3 rounded-lg bg-gray-900/60 px-3 py-2">
					<span class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-gray-700 bg-gray-800">
						<svg class="h-3.5 w-3.5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
						</svg>
					</span>
					<span class="text-sm text-gray-300">{name}</span>
				</li>
			{/each}
		</ul>
	{/if}
</div>
