<script lang="ts">
	import { collection, ApiError } from '$lib/api';

	type Species = {
		species_code: string;
		common_name: string;
		scientific_name?: string;
		family: string;
		taxon_order: number;
		found?: boolean;
	};

	type FamilyGroup = {
		family: string;
		total: number;
		discovered: number;
		species: Species[];
	};

	type ProgressData = {
		region: string;
		total_species: number;
		discovered_count: number;
		progress_percent: number;
		discovered: Species[];
		missing: Species[];
		family_groups?: FamilyGroup[];
	};

	let loading = $state(true);
	let error = $state('');
	let data = $state<ProgressData | null>(null);
	let viewMode = $state<'family' | 'grid'>('family');
	let expandedFamily = $state<string | null>(null);
	let eBirdStatus = $state<'checking' | 'live' | 'static'>('checking');
	let toast = $state<{ message: string; type: 'success' | 'error' } | null>(null);
	let toastTimeout = $state<ReturnType<typeof setTimeout> | null>(null);
	let searchQuery = $state('');

	async function loadProgress() {
		loading = true;
		error = '';
		try {
			const progress = await collection.progress({ family_group: true });
			data = progress;
			// Build lookup of discovered species codes
			const discoveredCodes = new Set(progress.discovered.map((s: Species) => s.species_code));
			// Mark found on family groups and missing
			if (progress.family_groups) {
				for (const fg of progress.family_groups) {
					for (const sp of fg.species) {
						sp.found = discoveredCodes.has(sp.species_code);
					}
				}
			}
			for (const sp of progress.missing) {
				sp.found = false;
			}
		} catch (e: any) {
			error = e.message || 'Failed to load collection data';
		} finally {
			loading = false;
		}
	}

	async function checkEBirdStatus() {
		eBirdStatus = 'checking';
		try {
			const res = await fetch('/api/collection/refresh-ebird', { method: 'POST' });
			if (res.ok) {
				eBirdStatus = 'live';
				const result = await res.json();
				showToast(`eBird refreshed: ${result.species_count} species`, 'success');
			} else {
				eBirdStatus = 'static';
			}
		} catch {
			eBirdStatus = 'static';
		}
	}

	async function refreshEBird() {
		try {
			const res = await fetch('/api/collection/refresh-ebird', { method: 'POST' });
			if (res.ok) {
				const result = await res.json();
				eBirdStatus = 'live';
				showToast(`eBird refreshed: ${result.species_count} species`, 'success');
			} else {
				const body = await res.json().catch(() => ({ detail: 'Failed' }));
				eBirdStatus = 'static';
				showToast(body.detail || 'eBird refresh failed', 'error');
			}
		} catch {
			showToast('Network error', 'error');
		}
	}

	function showToast(message: string, type: 'success' | 'error') {
		if (toastTimeout) clearTimeout(toastTimeout);
		toast = { message, type };
		toastTimeout = setTimeout(() => {
			toast = null;
		}, 4000);
	}

	function toggleFamily(family: string, e: MouseEvent) {
		e.preventDefault();
		expandedFamily = expandedFamily === family ? null : family;
	}

	const regionLabel = $derived(() => {
		if (!data) return '';
		const labels: Record<string, string> = {
			us: 'United States',
			ca: 'Canada',
			eu: 'Europe',
			uk: 'United Kingdom',
			au: 'Australia',
			// fallback
		};
		return labels[data.region] || data.region.toUpperCase();
	});

	const filteredFamilyGroups = $derived(() => {
		if (!data?.family_groups) return [];
		if (!searchQuery.trim()) return data.family_groups;
		const q = searchQuery.toLowerCase().trim();
		return data.family_groups
			.map((fg) => ({
				...fg,
				species: fg.species.filter(
					(sp) =>
						sp.common_name.toLowerCase().includes(q) ||
						sp.scientific_name?.toLowerCase().includes(q) ||
						sp.family.toLowerCase().includes(q)
				)
			}))
			.filter((fg) => fg.species.length > 0);
	});

	const filteredAllSpecies = $derived(() => {
		if (!data) return [] as Species[];
		const all: Species[] = [
			...data.discovered.map((s) => ({ ...s, found: true })),
			...data.missing.map((s) => ({ ...s, found: false }))
		];
		if (!searchQuery.trim()) return all;
		const q = searchQuery.toLowerCase().trim();
		return all.filter(
			(sp) =>
				sp.common_name.toLowerCase().includes(q) ||
				sp.scientific_name?.toLowerCase().includes(q) ||
				sp.family.toLowerCase().includes(q)
		);
	});

	$effect(() => {
		loadProgress();
		checkEBirdStatus();
	});
</script>

<div class="space-y-6">
	<!-- Header -->
	<div>
		<div class="flex items-center justify-between flex-wrap gap-3">
			<div>
				<h1 class="text-2xl font-bold">Collection</h1>
				{#if data}
					<p class="text-sm text-gray-500 mt-0.5">{regionLabel()} · {data.total_species} species</p>
				{/if}
			</div>
			<div class="flex items-center gap-3">
				<!-- eBird badge -->
				{#if eBirdStatus === 'checking'}
					<span class="inline-flex items-center gap-1.5 rounded-full bg-gray-800 border border-gray-700 px-3 py-1 text-xs text-gray-400">
						<svg class="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
						</svg>
						Checking eBird…
					</span>
				{:else if eBirdStatus === 'live'}
					<span class="inline-flex items-center gap-1.5 rounded-full bg-emerald-900/40 border border-emerald-700/50 px-3 py-1 text-xs text-emerald-300">
						<span class="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
						Live eBird
					</span>
				{:else}
					<span class="inline-flex items-center gap-1.5 rounded-full bg-gray-800 border border-gray-700 px-3 py-1 text-xs text-gray-500">
						<span class="h-1.5 w-1.5 rounded-full bg-gray-600"></span>
						Static Rarity
					</span>
				{/if}
				<button
					type="button"
					onclick={refreshEBird}
					class="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
				>
					↻ Refresh
				</button>
			</div>
		</div>

		<!-- Progress bar -->
		{#if data}
			<div class="mt-4 space-y-2">
				<div class="flex items-center gap-3">
					<div class="flex-1 h-3 rounded-full bg-gray-800 overflow-hidden">
						<div
							class="h-full rounded-full bg-gradient-to-r from-green-600 to-emerald-400 transition-all duration-500"
							style="width: {Math.min(data.progress_percent, 100)}%"
						></div>
					</div>
					<span class="text-sm font-semibold text-emerald-400 shrink-0">{data.discovered_count}/{data.total_species}</span>
					<span class="rounded-full bg-emerald-900/40 border border-emerald-700/50 px-2 py-0.5 text-xs font-medium text-emerald-300 shrink-0">
						{data.progress_percent}%
					</span>
				</div>
			</div>
		{/if}
	</div>

	<!-- Toast -->
	{#if toast}
		<div class="rounded-xl border p-3 text-sm transition-all {toast.type === 'success'
				? 'border-emerald-700/50 bg-emerald-900/30 text-emerald-300'
				: 'border-red-700/50 bg-red-900/30 text-red-300'}">
			{toast.message}
		</div>
	{/if}

	{#if error}
		<div class="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
			<p class="text-sm text-red-300">{error}</p>
		</div>
	{/if}

	<!-- Controls -->
	{#if !loading && data}
		<div class="flex flex-wrap items-center gap-3">
			<!-- Search -->
			<div class="relative flex-1 min-w-[200px] max-w-xs">
				<svg class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
				</svg>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search species..."
					class="w-full rounded-lg border border-gray-700 bg-gray-800 py-2 pl-9 pr-3 text-sm text-gray-200 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50"
				/>
			</div>

			<!-- View toggle -->
			<div class="flex rounded-lg border border-gray-700 overflow-hidden">
				<button
					type="button"
					onclick={() => (viewMode = 'family')}
					class="px-3 py-1.5 text-sm font-medium transition-colors {viewMode === 'family'
						? 'bg-green-600 text-white'
						: 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
				>
					Family View
				</button>
				<button
					type="button"
					onclick={() => (viewMode = 'grid')}
					class="px-3 py-1.5 text-sm font-medium transition-colors {viewMode === 'grid'
						? 'bg-green-600 text-white'
						: 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
				>
					Grid View
				</button>
			</div>
		</div>
	{/if}

	<!-- Loading -->
	{#if loading}
		<div class="flex items-center justify-center py-16">
			<svg class="h-8 w-8 animate-spin text-gray-600" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>

	<!-- Family View -->
	{:else if data && viewMode === 'family'}
		<div class="space-y-3">
			{#if filteredFamilyGroups().length === 0}
				<p class="text-gray-500 text-sm text-center py-8">No families match your search.</p>
			{:else}
				{#each filteredFamilyGroups() as fg (fg.family)}
					{@const pct = fg.total > 0 ? Math.round((fg.discovered / fg.total) * 100) : 0}
					{@const isOpen = expandedFamily === fg.family}
					<div class="rounded-xl border border-gray-800 bg-gray-900 overflow-hidden transition-all">
						<button
							type="button"
							onclick={(e: MouseEvent) => toggleFamily(fg.family, e)}
							class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-800/50 transition-colors"
						>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-3">
									<span class="text-sm font-semibold text-gray-200 truncate">{fg.family}</span>
									<span class="text-xs text-gray-500 shrink-0">{fg.discovered}/{fg.total} discovered</span>
								</div>
								<div class="mt-1.5 flex items-center gap-2">
									<div class="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden max-w-[200px]">
										<div
											class="h-full rounded-full bg-gradient-to-r from-green-600 to-emerald-400 transition-all duration-300"
											style="width: {pct}%"
										></div>
									</div>
									<span class="text-xs text-gray-500">{pct}%</span>
								</div>
							</div>
							<svg class="h-4 w-4 text-gray-500 shrink-0 transition-transform {isOpen ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
								<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
							</svg>
						</button>

						{#if isOpen}
							<div class="border-t border-gray-800 px-4 py-3">
								<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
									{#each fg.species as sp (sp.species_code)}
										<div
											class="rounded-lg border p-2 transition-colors {sp.found
												? 'border-green-800/40 bg-green-900/20'
												: 'border-gray-800 bg-gray-900/50 opacity-60'}"
											title="{sp.common_name} — {sp.scientific_name || ''}"
										>
											<div class="flex items-start gap-1.5">
												<span class="text-sm leading-none mt-0.5 shrink-0">{sp.found ? '✅' : '❓'}</span>
												<div class="min-w-0">
													<p class="text-xs font-medium text-gray-200 truncate">{sp.common_name}</p>
													{#if !sp.found}
														<p class="text-[10px] text-gray-600 truncate italic mt-0.5">undiscovered</p>
													{/if}
												</div>
											</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>

	<!-- Grid View -->
	{:else if data && viewMode === 'grid'}
		{#if filteredAllSpecies().length === 0}
			<p class="text-gray-500 text-sm text-center py-8">No species match your search.</p>
		{:else}
			<p class="text-xs text-gray-500">{filteredAllSpecies().length} species shown</p>
			<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-2">
				{#each filteredAllSpecies() as sp (sp.species_code)}
					<div
						class="rounded-lg border p-2.5 transition-colors {sp.found
							? 'border-green-800/40 bg-green-900/20 hover:bg-green-900/30'
							: 'border-gray-800 bg-gray-900/50 opacity-50 hover:opacity-70'}"
						title="{sp.common_name} — {sp.family}"
					>
						{#if sp.found}
							<div class="flex items-start gap-1.5">
								<span class="text-sm leading-none mt-0.5 shrink-0">✅</span>
								<div class="min-w-0">
									<p class="text-xs font-medium text-gray-100 truncate">{sp.common_name}</p>
									<p class="text-[10px] text-gray-500 truncate mt-0.5">{sp.family}</p>
								</div>
							</div>
						{:else}
							<div class="flex flex-col items-center gap-1 text-center">
								<span class="text-2xl">❓</span>
								<p class="text-[10px] text-gray-600 truncate italic">{sp.family}</p>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>
