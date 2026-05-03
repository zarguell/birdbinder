<script lang="ts">
	import { goto } from '$app/navigation';
	import { sightings } from '$lib/api';

	let items = $state<any[]>([]);
	let total = $state(0);
	let offset = $state(0);
	let loading = $state(false);
	let initialLoad = $state(true);
	let error = $state('');

	const PAGE_SIZE = 20;

	async function loadSightings() {
		loading = true;
		error = '';
		try {
			const data = await sightings.list({ limit: PAGE_SIZE, offset });
			items = data.items ?? [];
			total = data.total ?? items.length;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load sightings';
		} finally {
			loading = false;
			initialLoad = false;
		}
	}

	async function loadMore() {
		if (loading || offset + PAGE_SIZE >= total) return;
		loading = true;
		try {
			const nextOffset = offset + PAGE_SIZE;
			const data = await sightings.list({ limit: PAGE_SIZE, offset: nextOffset });
			items = [...items, ...(data.items ?? [])];
			total = data.total ?? total;
			offset = nextOffset;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load more sightings';
		} finally {
			loading = false;
		}
	}

	function formatDate(dateStr: string): string {
		try {
			return new Date(dateStr).toLocaleDateString('en-US', {
				month: 'short',
				day: 'numeric',
				year: 'numeric'
			});
		} catch {
			return dateStr;
		}
	}

	function statusBadge(status: string) {
		switch (status) {
			case 'identified':
				return 'bg-green-500/15 text-green-400 border-green-500/30';
			case 'pending':
				return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30';
			case 'failed':
				return 'bg-red-500/15 text-red-400 border-red-500/30';
			default:
				return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
		}
	}

	$effect(() => {
		loadSightings();
	});
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold">Sightings</h1>
			{#if total > 0}
				<p class="text-sm text-gray-500 mt-0.5">{total} sighting{total !== 1 ? 's' : ''}</p>
			{/if}
		</div>
		<a
			href="/upload"
			class="inline-flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500 transition-colors"
		>
			<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
			</svg>
			New
		</a>
	</div>

	{#if error}
		<div class="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
			<p class="text-sm text-red-300">{error}</p>
		</div>
	{/if}

	{#if initialLoad}
		<div class="flex items-center justify-center py-12">
			<svg class="h-8 w-8 animate-spin text-gray-600" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{:else if items.length === 0}
		<div class="text-center py-16 space-y-3">
			<svg class="w-16 h-16 text-gray-700 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
				<path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
				<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
			</svg>
			<p class="text-gray-400">No sightings yet. Upload one!</p>
			<a href="/upload" class="inline-flex items-center gap-1.5 text-sm text-green-400 hover:text-green-300 underline underline-offset-2">
				Upload a sighting →
			</a>
		</div>
	{:else}
		<div class="grid gap-3">
			{#each items as sighting}
				<a
					href="/sightings/{sighting.id}"
					class="flex items-center gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-3 transition-colors hover:border-gray-700 hover:bg-gray-900"
				>
					<!-- Thumbnail -->
					{#if sighting.image_url}
						<img
							src={sighting.image_url}
							alt={sighting.species_common ?? 'Unidentified'}
							class="h-16 w-16 rounded-lg object-cover bg-gray-800 shrink-0"
							loading="lazy"
						/>
					{:else}
						<div class="flex h-16 w-16 items-center justify-center rounded-lg bg-gray-800 shrink-0">
							<svg class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
							</svg>
						</div>
					{/if}

					<!-- Info -->
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<p class="font-medium truncate">
								{#if sighting.species_common}
									{sighting.species_common}
								{:else}
									<span class="text-gray-500 italic">Unidentified</span>
								{/if}
							</p>
							<span class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium {statusBadge(sighting.identification_status)}">
								{sighting.identification_status ?? 'pending'}
							</span>
						</div>
						<p class="text-sm text-gray-500 mt-0.5">
							{#if sighting.observed_at}
								{formatDate(sighting.observed_at)}
							{:else}
								{formatDate(sighting.created_at)}
							{/if}
						</p>
					</div>

					<!-- Arrow -->
					<svg class="w-5 h-5 text-gray-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
					</svg>
				</a>
			{/each}
		</div>

		<!-- Load More -->
		{#if offset + PAGE_SIZE < total}
			<div class="flex justify-center pt-2">
				<button
					onclick={loadMore}
					disabled={loading}
					class="rounded-lg border border-gray-700 bg-gray-900 px-6 py-2.5 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-gray-800 disabled:opacity-50"
				>
					{#if loading}
						<svg class="mr-2 inline h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
						</svg>
					{/if}
					Load more
				</button>
			</div>
		{/if}
	{/if}
</div>
