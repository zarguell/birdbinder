<script lang="ts">
	import { page } from '$app/stores';
	import { cards } from '$lib/api';

	let card = $state<any>(null);
	let loading = $state(true);
	let error = $state('');

	let id = $derived($page.params.id);

	async function loadCard() {
		loading = true;
		error = '';
		card = null;
		try {
			card = await cards.get(id);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load card';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (id) loadCard();
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

	function rarityColor(rarity: string | undefined): string {
		switch (rarity) {
			case 'common': return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
			case 'uncommon': return 'bg-green-500/15 text-green-400 border-green-500/30';
			case 'rare': return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
			case 'epic': return 'bg-purple-500/15 text-purple-400 border-purple-500/30';
			case 'legendary': return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
			default: return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
		}
	}
</script>

<div class="space-y-6">
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
			{#if error.includes('404') || error.includes('Not found')}
				<p class="mt-2 text-sm text-gray-400">Card not found.</p>
			{:else}
				<button
					onclick={loadCard}
					class="mt-3 text-sm text-green-400 hover:text-green-300 underline underline-offset-2"
				>
					Try again
				</button>
			{/if}
		</div>
	{:else if card}
		<a
			href={card.sighting_id ? `/sightings/${card.sighting_id}` : '/sightings'}
			class="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors"
		>
			<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
			</svg>
			{card.sighting_id ? 'Back to sighting' : 'Back to sightings'}
		</a>

		<div class="grid gap-6 lg:grid-cols-2">
			<div>
				{#if card.card_art_url}
					<img
						src={card.card_art_url}
						alt={card.species_common ?? 'Card'}
						class="w-full rounded-xl border border-gray-800 bg-gray-900 object-contain"
					/>
				{:else}
					<div class="flex aspect-[2.5/3.5] w-full items-center justify-center rounded-xl border border-gray-800 bg-gray-900">
						<svg class="h-12 w-12 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
							<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
						</svg>
					</div>
				{/if}
			</div>

			<div class="space-y-5">
				<div>
					<h1 class="text-3xl font-bold">{card.species_common ?? 'Card'}</h1>
					{#if card.species_scientific}
						<p class="text-lg text-gray-400 italic mt-1">{card.species_scientific}</p>
					{/if}
					{#if card.species_code}
						<p class="text-sm text-gray-500 mt-1">{card.species_code}</p>
					{/if}
					{#if card.rarity_tier}
						<div class="mt-3">
							<span class="inline-block rounded-full border px-3 py-1 text-sm font-medium {rarityColor(card.rarity_tier)}">
								{card.rarity_tier}
							</span>
						</div>
					{/if}
				</div>

				{#if card.notes}
					<div class="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-2">
						<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Notes</h2>
						<p class="text-sm text-gray-300 whitespace-pre-wrap">{card.notes}</p>
					</div>
				{/if}

				<div class="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-2">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">Details</h2>
					<dl class="space-y-2 text-sm">
						{#if card.generated_at}
							<div class="flex justify-between">
								<dt class="text-gray-500">Generated</dt>
								<dd class="text-gray-200">{formatDate(card.generated_at)}</dd>
							</div>
						{/if}
						{#if card.sighting_id}
							<div class="flex justify-between">
								<dt class="text-gray-500">Sighting</dt>
								<dd class="text-gray-200">
									<a href="/sightings/{card.sighting_id}" class="text-green-400 hover:text-green-300 transition-colors">
										{card.sighting_id}
									</a>
								</dd>
							</div>
						{/if}
					</dl>
				</div>

				<p class="text-xs text-gray-600">ID: {card.id}</p>
			</div>
		</div>
	{/if}
</div>