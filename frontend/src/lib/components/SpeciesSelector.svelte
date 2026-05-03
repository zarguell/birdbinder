<script lang="ts">
	import { species } from '$lib/api';

	interface SpeciesResult {
		species_code: string;
		common_name: string;
		scientific_name: string;
		family: string;
	}

	interface Props {
		placeholder?: string;
		filterFamily?: string;
		onselect?: (species: SpeciesResult) => void;
	}

	let { placeholder = 'Search species...', filterFamily = '', onselect }: Props = $props();

	let query = $state('');
	let results = $state<SpeciesResult[]>([]);
	let families = $state<{ name: string; code: string; species_count: number }[]>([]);
	let open = $state(false);
	let loading = $state(false);
	let familiesLoaded = $state(false);
	let selectedFamily = $state(filterFamily);
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let containerEl: HTMLDivElement | undefined = $state();

	// Load families list
	async function loadFamilies() {
		if (familiesLoaded) return;
		familiesLoaded = true;
		try {
			const data = await species.families();
			families = Array.isArray(data) ? data : data.items ?? [];
		} catch {
			families = [];
		}
	}

	// Group results by family
	const groupedResults = $derived(() => {
		const groups: Record<string, SpeciesResult[]> = {};
		for (const r of results) {
			const fam = r.family || 'Unknown';
			if (!groups[fam]) groups[fam] = [];
			groups[fam].push(r);
		}
		return Object.entries(groups)
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([family, items]) => ({ family, items }));
	});

	function onInput(e: Event) {
		query = (e.target as HTMLInputElement).value;
		if (debounceTimer) clearTimeout(debounceTimer);
		if (query.trim().length < 2) {
			results = [];
			open = false;
			return;
		}
		debounceTimer = setTimeout(async () => {
			loading = true;
			try {
				const params: { family?: string; limit?: number } = {};
				if (selectedFamily) params.family = selectedFamily;
				params.limit = 20;
				const data = await species.search(query.trim(), params);
				results = Array.isArray(data) ? data : data.items ?? data.results ?? [];
			} catch {
				results = [];
			} finally {
				loading = false;
				open = results.length > 0;
			}
		}, 300);
	}

	function selectSpecies(speciesItem: SpeciesResult) {
		onselect?.(speciesItem);
		query = '';
		results = [];
		open = false;
	}

	function handleFocus() {
		loadFamilies();
		if (results.length > 0) open = true;
	}

	function handleBlur() {
		// Delay to allow click events on dropdown items to fire
		setTimeout(() => {
			open = false;
		}, 150);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			open = false;
		}
	}

	function onFamilyChange(e: Event) {
		selectedFamily = (e.target as HTMLSelectElement).value;
		// Re-search if there's a query
		if (query.trim().length >= 2) {
			if (debounceTimer) clearTimeout(debounceTimer);
			debounceTimer = setTimeout(async () => {
				loading = true;
				try {
					const params: { family?: string; limit?: number } = {};
					if (selectedFamily) params.family = selectedFamily;
					params.limit = 20;
					const data = await species.search(query.trim(), params);
					results = Array.isArray(data) ? data : data.items ?? data.results ?? [];
				} catch {
					results = [];
				} finally {
					loading = false;
					open = results.length > 0;
				}
			}, 100);
		}
	}

	function handleContainerClick(e: MouseEvent) {
		loadFamilies();
	}
</script>

<div bind:this={containerEl} class="relative" onclick={handleContainerClick}>
	<!-- Family filter dropdown -->
	<div class="mb-2">
		<select
			value={selectedFamily}
			onchange={onFamilyChange}
			class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-200 outline-none transition-colors focus:border-green-500 focus:ring-1 focus:ring-green-500/50"
		>
			<option value="">All Families</option>
			{#each families as fam (fam.code || fam.name)}
				<option value={fam.code || fam.name}>{fam.name}{fam.species_count ? ` (${fam.species_count})` : ''}</option>
			{/each}
		</select>
	</div>

	<!-- Search input -->
	<div class="relative">
		<input
			type="text"
			placeholder={placeholder}
			value={query}
			oninput={onInput}
			onkeydown={handleKeydown}
			onfocus={handleFocus}
			onblur={handleBlur}
			class="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none transition-colors focus:border-green-500 focus:ring-1 focus:ring-green-500/50"
		/>
		{#if loading}
			<div class="absolute right-3 top-1/2 -translate-y-1/2">
				<svg class="h-4 w-4 animate-spin text-gray-500" viewBox="0 0 24 24" fill="none">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
			</div>
		{/if}
	</div>

	<!-- Results dropdown -->
	{#if open && groupedResults().length > 0}
		<div class="absolute z-50 mt-1 w-full max-h-72 overflow-auto rounded-lg border border-gray-700 bg-gray-800 shadow-xl">
			{#each groupedResults() as group (group.family)}
				<div class="sticky top-0 bg-gray-750 px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-700" style="background-color: #1e293b;">
					{group.family}
					<span class="ml-1 text-gray-500 normal-case">({group.items.length})</span>
				</div>
				{#each group.items as speciesItem (speciesItem.species_code)}
					<button
						type="button"
						class="w-full px-3 py-2 text-left hover:bg-gray-700 transition-colors border-b border-gray-800/50 last:border-b-0"
						onmousedown|preventDefault={() => selectSpecies(speciesItem)}
					>
						<span class="text-sm font-medium text-gray-200">{speciesItem.common_name}</span>
						<span class="ml-2 text-xs text-gray-500 italic">{speciesItem.scientific_name}</span>
					</button>
				{/each}
			{/each}
		</div>
	{/if}

	{#if open && loading && results.length === 0}
		<div class="absolute z-50 mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 p-4 shadow-xl">
			<div class="flex items-center justify-center">
				<svg class="h-5 w-5 animate-spin text-gray-500" viewBox="0 0 24 24" fill="none">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
				<span class="ml-2 text-sm text-gray-400">Searching…</span>
			</div>
		</div>
	{/if}
</div>
