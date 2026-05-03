<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { sightings, cards, ApiError } from '$lib/api';
	import SpeciesAutocomplete from '$lib/components/SpeciesAutocomplete.svelte';

	let sighting = $state<any>(null);
	let loading = $state(true);
	let error = $state('');
	let identifying = $state(false);
	let generating = $state(false);
	let deleting = $state(false);
	let showDeleteConfirm = $state(false);
	let actionMessage = $state('');
	let actionMessageType: 'success' | 'error' = $state('success');
	let jobStatus = $state<any>(null);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	let id = $derived($page.params.id);

	function startPolling() {
		stopPolling();
		pollInterval = setInterval(async () => {
			try {
				const res = await sightings.getJob(id);
				jobStatus = res.job;
				if (jobStatus && (jobStatus.status === 'completed' || jobStatus.status === 'failed')) {
					stopPolling();
					await loadSighting();
					if (jobStatus.status === 'failed') {
						actionMessage = `Identification failed: ${jobStatus.error || 'Unknown error'}`;
						actionMessageType = 'error';
					} else if (jobStatus.status === 'completed') {
						actionMessage = '';
					}
				}
			} catch { /* ignore poll errors */ }
		}, 2000);
	}

	function stopPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	}

	async function loadSighting() {
		loading = true;
		error = '';
		sighting = null;
		try {
			sighting = await sightings.get(id);
			// Start polling if identification is in progress
			if (sighting.identification_status === 'pending' || sighting.identification_status === 'running') {
				startPolling();
			} else {
				stopPolling();
				jobStatus = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load sighting';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (id) loadSighting();
		return () => stopPolling();
	});

	function formatDate(dateStr: string): string {
		try {
			return new Date(dateStr).toLocaleDateString('en-US', {
				weekday: 'short',
				month: 'short',
				day: 'numeric',
				year: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return dateStr;
		}
	}

	function formatCoord(val: number | null | undefined, dir: string): string {
		if (val == null) return '—';
		const abs = Math.abs(val);
		const degrees = Math.floor(abs);
		const minutes = Math.floor((abs - degrees) * 60);
		return `${degrees}° ${minutes}' ${val >= 0 ? dir : 'S' === dir ? 'S' : 'W'}`;
	}

	async function handleIdentify() {
		identifying = true;
		actionMessage = '';
		jobStatus = null;
		try {
			await cards.generate(id);
			// Reload to pick up pending status, then start polling
			await loadSighting();
			startPolling();
		} catch (err) {
			actionMessage = err instanceof Error ? err.message : 'Identification failed';
			actionMessageType = 'error';
		} finally {
			identifying = false;
		}
	}

	async function handleGenerateCard() {
		generating = true;
		actionMessage = '';
		try {
			await cards.generate(id);
			actionMessage = 'Card generation started!';
			actionMessageType = 'success';
			setTimeout(() => loadSighting(), 3000);
		} catch (err) {
			actionMessage = err instanceof Error ? err.message : 'Card generation failed';
			actionMessageType = 'error';
		} finally {
			generating = false;
		}
	}

	async function handleDelete() {
		deleting = true;
		actionMessage = '';
		try {
			await sightings.delete(id);
			goto('/sightings');
		} catch (err) {
			actionMessage = err instanceof Error ? err.message : 'Failed to delete';
			actionMessageType = 'error';
			deleting = false;
			showDeleteConfirm = false;
		}
	}

	async function handleOverride(code: string, commonName: string) {
		actionMessage = '';
		try {
			sighting = await sightings.overrideSpecies(id, code, commonName);
			actionMessage = `Species updated to ${commonName}`;
			actionMessageType = 'success';
		} catch (err) {
			actionMessage = err instanceof Error ? err.message : 'Failed to override species';
			actionMessageType = 'error';
		}
	}
</script>

<div class="space-y-6">
	<!-- Back link -->
	<a href="/sightings" class="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors">
		<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
		</svg>
		Back to sightings
	</a>

	{#if loading}
		<div class="flex items-center justify-center py-16">
			<svg class="h-8 w-8 animate-spin text-gray-600" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{:else if error}
		<div class="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center">
			<p class="text-red-300 font-medium">{error}</p>
			<button
				onclick={loadSighting}
				class="mt-3 text-sm text-green-400 hover:text-green-300 underline underline-offset-2"
			>
				Try again
			</button>
		</div>
	{:else if sighting}
		<!-- Image + Info Grid -->
		<div class="grid gap-6 lg:grid-cols-5">
			<!-- Image -->
			<div class="lg:col-span-3">
				{#if sighting.image_url}
					<img
						src={sighting.image_url}
						alt={sighting.species_common ?? 'Sighting'}
						class="w-full rounded-xl border border-gray-800 bg-gray-900 object-contain max-h-[60vh]"
					/>
				{:else}
					<div class="flex aspect-video w-full items-center justify-center rounded-xl border border-gray-800 bg-gray-900">
						<svg class="h-12 w-12 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
							<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
						</svg>
					</div>
				{/if}
			</div>

			<!-- Info Panel -->
			<div class="lg:col-span-2 space-y-5">
				<!-- Species & Status -->
				<div>
					<h1 class="text-2xl font-bold">
						{#if sighting.species_common}
							{sighting.species_common}
						{:else}
							<span class="text-gray-500 italic">Unidentified</span>
						{/if}
					</h1>
					{#if sighting.species_code}
						<p class="text-sm text-gray-500 mt-0.5">{sighting.species_code}</p>
					{/if}
					<div class="mt-2">
						<span class="inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium
							{sighting.identification_status === 'identified'
								? 'bg-green-500/15 text-green-400 border-green-500/30'
								: sighting.identification_status === 'failed'
									? 'bg-red-500/15 text-red-400 border-red-500/30'
									: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'}">
							{#if sighting.identification_status === 'pending' || sighting.identification_status === 'running'}
								<svg class="inline -mt-0.5 mr-1 h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
								{sighting.identification_status === 'running' ? 'Identifying…' : 'Queued'}
							{:else}
								{sighting.identification_status ?? 'pending'}
							{/if}
						</span>
						{#if sighting.id_method}
							<span class="ml-2 text-xs text-gray-500">
								via {sighting.id_method}
							</span>
						{/if}
						{#if sighting.id_confidence != null}
							<span class="ml-2 text-xs text-gray-500">
								{sighting.id_confidence}% confidence
							</span>
						{/if}
					</div>
				</div>

				<!-- EXIF / Location Data -->
				<div class="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Details</h2>
					<dl class="space-y-2 text-sm">
						<div class="flex justify-between">
							<dt class="text-gray-500">Date</dt>
							<dd class="text-gray-200 text-right">
								{sighting.observed_at ? formatDate(sighting.observed_at) : formatDate(sighting.created_at)}
							</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-500">Latitude</dt>
							<dd class="text-gray-200 font-mono text-right">
								{sighting.latitude != null ? sighting.latitude.toFixed(5) : '—'}
							</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-500">Longitude</dt>
							<dd class="text-gray-200 font-mono text-right">
								{sighting.longitude != null ? sighting.longitude.toFixed(5) : '—'}
							</dd>
						</div>
					</dl>
				</div>

				<!-- Action Buttons -->
				<div class="space-y-2.5">
					{#if sighting.identification_status === 'pending'}
						<button
							onclick={handleIdentify}
							disabled={identifying}
							class="w-full flex items-center justify-center gap-2 rounded-lg bg-green-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-500 disabled:opacity-50"
						>
							{#if identifying}
								<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
							{/if}
							Identify Bird
						</button>
					{/if}

					{#if sighting.identification_status === 'failed'}
						<button
							onclick={handleIdentify}
							disabled={identifying}
							class="w-full flex items-center justify-center gap-2 rounded-lg bg-yellow-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-yellow-500 disabled:opacity-50"
						>
							{#if identifying}
								<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
							{/if}
							Try Again
						</button>
					{/if}

					{#if sighting.identification_status === 'identified' && (!sighting.cards || sighting.cards.length === 0)}
						<button
							onclick={handleGenerateCard}
							disabled={generating}
							class="w-full flex items-center justify-center gap-2 rounded-lg bg-green-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-500 disabled:opacity-50"
						>
							{#if generating}
								<svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
							{/if}
							Generate Card
						</button>
					{/if}
				</div>

				<!-- Manual Override -->
				<div class="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Manual Override</h2>
					<SpeciesAutocomplete onSelect={handleOverride} />
					<p class="text-xs text-gray-600">Type to search and override the species identification.</p>
				</div>

				<!-- Delete -->
				<div class="pt-2 border-t border-gray-800">
					{#if !showDeleteConfirm}
						<button
							onclick={() => showDeleteConfirm = true}
							class="text-sm text-red-400 hover:text-red-300 font-medium transition-colors"
						>
							Delete sighting
						</button>
					{:else}
						<div class="space-y-2">
							<p class="text-sm text-red-300">Are you sure? This cannot be undone.</p>
							<div class="flex gap-2">
								<button
									onclick={handleDelete}
									disabled={deleting}
									class="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 disabled:opacity-50"
								>
									{#if deleting}
										<svg class="mr-1 inline h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
											<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
											<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
										</svg>
									{/if}
									Delete
								</button>
								<button
									onclick={() => showDeleteConfirm = false}
									class="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 transition-colors hover:border-gray-600"
								>
									Cancel
								</button>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>

		<!-- Action Message -->
		{#if actionMessage}
			<div class="rounded-xl border p-4 {actionMessageType === 'error'
				? 'border-red-500/30 bg-red-500/10'
				: 'border-green-500/30 bg-green-500/10'}">
				<p class="text-sm {actionMessageType === 'error' ? 'text-red-300' : 'text-green-300'}">{actionMessage}</p>
			</div>
		{/if}

		<!-- Cards Section -->
		{#if sighting.cards && sighting.cards.length > 0}
			<div class="space-y-3">
				<h2 class="text-lg font-semibold">Cards</h2>
				<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
					{#each sighting.cards as card}
						<a
							href="/cards/{card.id}"
							class="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden transition-colors hover:border-gray-700 hover:bg-gray-900"
						>
							{#if card.art_url}
								<img
									src={card.art_url}
									alt={card.species_common ?? 'Card'}
									class="w-full aspect-[2.5/3.5] object-cover bg-gray-800"
									loading="lazy"
								/>
							{:else}
								<div class="flex aspect-[2.5/3.5] w-full items-center justify-center bg-gray-800">
									<svg class="h-8 w-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
									</svg>
								</div>
							{/if}
							<div class="p-3 flex items-center justify-between">
								<div class="min-w-0">
									<p class="text-sm font-medium truncate">{card.species_common ?? 'Card'}</p>
									{#if card.rarity}
										<span class="text-xs font-medium
											{card.rarity === 'common' ? 'text-gray-400' :
											 card.rarity === 'uncommon' ? 'text-green-400' :
											 card.rarity === 'rare' ? 'text-blue-400' :
											 card.rarity === 'epic' ? 'text-purple-400' :
											 'text-yellow-400'}">
											{card.rarity}
										</span>
									{/if}
								</div>
								<svg class="w-4 h-4 text-gray-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
								</svg>
							</div>
						</a>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
