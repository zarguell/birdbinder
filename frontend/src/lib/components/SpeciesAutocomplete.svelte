<script lang="ts">
	import { species } from '$lib/api';

	let { onSelect }: { onSelect: (code: string, commonName: string) => void } = $props();

	let query = $state('');
	let results = $state<any[]>([]);
	let open = $state(false);
	let highlightIndex = $state(-1);
	let loading = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;

	function onInput(e: Event) {
		query = (e.target as HTMLInputElement).value;
		highlightIndex = -1;
		if (debounceTimer) clearTimeout(debounceTimer);
		if (query.trim().length < 2) {
			results = [];
			open = false;
			return;
		}
		debounceTimer = setTimeout(async () => {
			loading = true;
			try {
				const data = await species.search(query.trim());
				results = Array.isArray(data) ? data : data.items ?? data.results ?? [];
			} catch {
				results = [];
			} finally {
				loading = false;
				open = results.length > 0;
			}
		}, 300);
	}

	function selectItem(code: string, commonName: string) {
		onSelect(code, commonName);
		query = '';
		results = [];
		open = false;
		highlightIndex = -1;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			highlightIndex = Math.min(highlightIndex + 1, results.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			highlightIndex = Math.max(highlightIndex - 1, 0);
		} else if (e.key === 'Enter' && highlightIndex >= 0) {
			e.preventDefault();
			const item = results[highlightIndex];
			selectItem(item.code, item.common_name);
		} else if (e.key === 'Escape') {
			open = false;
		}
	}

	function handleFocus() {
		if (results.length > 0) open = true;
	}

	function handleBlur() {
		// Delay to allow click events on dropdown items to fire
		setTimeout(() => {
			open = false;
		}, 150);
	}
</script>

<div class="relative">
	<input
		type="text"
		placeholder="Search species..."
		value={query}
		oninput={onInput}
		onkeydown={handleKeydown}
		onfocus={handleFocus}
		onblur={handleBlur}
		class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-green-500 focus:ring-1 focus:ring-green-500/50"
	/>
	{#if loading}
		<div class="absolute left-2 top-1/2 -translate-y-1/2">
			<svg class="h-4 w-4 animate-spin text-gray-500" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{/if}
	{#if open}
		<ul class="absolute z-50 mt-1 w-full max-h-60 overflow-auto rounded-lg border border-gray-700 bg-gray-900 py-1 shadow-xl">
			{#each results as item, i}
				<li>
					<button
						type="button"
						onclick={() => selectItem(item.code, item.common_name)}
						class="w-full px-3 py-2 text-left text-sm transition-colors hover:bg-gray-800
							{i === highlightIndex ? 'bg-gray-800 text-green-400' : 'text-gray-300'}"
					>
						<span class="font-medium">{item.common_name}</span>
						<span class="ml-1.5 text-gray-500 italic">{item.scientific_name}</span>
						{#if item.family}
							<span class="ml-2 text-xs text-gray-600">{item.family}</span>
						{/if}
					</button>
				</li>
			{:else}
				<li class="px-3 py-2 text-sm text-gray-500">No species found</li>
			{/each}
		</ul>
	{/if}
</div>
