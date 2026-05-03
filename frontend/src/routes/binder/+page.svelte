<script lang="ts">
	import { cards, binders } from '$lib/api';
	import CardGrid from '$lib/components/CardGrid.svelte';
	import CardModal from '$lib/components/CardModal.svelte';

	let allCards = $state<any[]>([]);
	let binderList = $state<any[]>([]);
	let activeBinderId = $state('all');

	let loading = $state(true);
	let error = $state('');

	// New binder form
	let showNewBinder = $state(false);
	let newBinderName = $state('');
	let newBinderDesc = $state('');
	let creatingBinder = $state(false);

	// Filters & sort
	let searchQuery = $state('');
	let rarityFilter = $state('');
	let sortBy = $state<'newest' | 'oldest' | 'rarity' | 'name'>('newest');

	// Modal
	let selectedCard = $state<any>(null);

	const RARITY_ORDER: Record<string, number> = {
		common: 0,
		uncommon: 1,
		rare: 2,
		epic: 3,
		legendary: 4
	};

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [cardData, binderData] = await Promise.all([
				cards.list({ limit: 200 }),
				binders.list({ limit: 50 })
			]);
			allCards = cardData.items ?? [];
			binderList = binderData.items ?? [];
			if (binderList.length === 0) {
				activeBinderId = 'all';
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	}

	async function createBinder() {
		if (!newBinderName.trim()) return;
		creatingBinder = true;
		try {
			const binder = await binders.create({ name: newBinderName.trim(), description: newBinderDesc.trim() || undefined });
			binderList = [...binderList, binder];
			activeBinderId = binder.id;
			newBinderName = '';
			newBinderDesc = '';
			showNewBinder = false;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to create binder';
		} finally {
			creatingBinder = false;
		}
	}

	async function deleteBinder(id: string) {
		try {
			await binders.delete(id);
			binderList = binderList.filter((b) => b.id !== id);
			if (activeBinderId === id) activeBinderId = 'all';
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to delete binder';
		}
	}

	const activeBinder = $derived(
		activeBinderId === 'all' ? null : binderList.find((b) => b.id === activeBinderId)
	);

	const binderCardIds = $derived(() => {
		if (!activeBinder) return new Set<string>();
		return new Set(activeBinder.cards?.map((bc: any) => bc.card_id) ?? []);
	});

	const filteredCards = $derived(() => {
		let result = allCards;

		// Filter by binder
		if (activeBinder) {
			const ids = binderCardIds();
			result = result.filter((c) => ids.has(c.id));
		}

		// Search filter
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase().trim();
			result = result.filter(
				(c) =>
					c.species_common?.toLowerCase().includes(q) ||
					c.species_code?.toLowerCase().includes(q) ||
					c.family?.toLowerCase().includes(q)
			);
		}

		// Rarity filter
		if (rarityFilter) {
			result = result.filter((c) => c.rarity_tier?.toLowerCase() === rarityFilter);
		}

		// Sort
		result = [...result];
		switch (sortBy) {
			case 'newest':
				result.sort((a, b) => new Date(b.generated_at ?? 0).getTime() - new Date(a.generated_at ?? 0).getTime());
				break;
			case 'oldest':
				result.sort((a, b) => new Date(a.generated_at ?? 0).getTime() - new Date(b.generated_at ?? 0).getTime());
				break;
			case 'rarity':
				result.sort(
					(a, b) =>
						(RARITY_ORDER[b.rarity_tier?.toLowerCase()] ?? 0) -
						(RARITY_ORDER[a.rarity_tier?.toLowerCase()] ?? 0)
				);
				break;
			case 'name':
				result.sort((a, b) => (a.species_common ?? '').localeCompare(b.species_common ?? ''));
				break;
		}

		return result;
	});

	function handleCardSelect(card: any) {
		selectedCard = card;
	}

	function closeModal() {
		selectedCard = null;
		// Refresh data in case card was added to binder
		loadData();
	}

	$effect(() => {
		loadData();
	});
</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold">Binder</h1>
			<p class="text-sm text-gray-500 mt-0.5">{allCards.length} card{allCards.length !== 1 ? 's' : ''} total</p>
		</div>
	</div>

	{#if error}
		<div class="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
			<p class="text-sm text-red-300">{error}</p>
		</div>
	{/if}

	<!-- Binder Tabs + New Binder -->
	<div class="space-y-3">
		<div class="flex flex-wrap items-center gap-2">
			<button
				type="button"
				onclick={() => (activeBinderId = 'all')}
				class="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors {activeBinderId === 'all'
					? 'bg-green-600 text-white'
					: 'border border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-200'}"
			>
				All Cards
			</button>

			{#each binderList as binder (binder.id)}
				<div class="group relative flex items-center">
					<button
						type="button"
						onclick={() => (activeBinderId = binder.id)}
						class="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors {activeBinderId === binder.id
							? 'bg-green-600 text-white'
							: 'border border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-200'}"
					>
						{binder.name}
						<span class="ml-1 text-xs opacity-70">({binder.card_count ?? 0})</span>
					</button>
					<button
						type="button"
						onclick={() => deleteBinder(binder.id)}
						class="ml-1 flex h-5 w-5 items-center justify-center rounded text-gray-600 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
						aria-label="Delete binder"
					>
						<svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			{/each}

			<button
				type="button"
				onclick={() => (showNewBinder = !showNewBinder)}
				class="rounded-lg border border-dashed border-gray-700 px-3 py-1.5 text-sm text-gray-500 transition-colors hover:border-green-500/50 hover:text-green-400"
			>
				+ New Binder
			</button>
		</div>

		<!-- New Binder Form -->
		{#if showNewBinder}
			<div class="flex flex-wrap items-end gap-2 rounded-xl border border-gray-800 bg-gray-900/50 p-4">
				<div class="flex-1 min-w-[160px]">
					<label for="new-binder-name" class="block text-xs font-medium text-gray-500 mb-1">Name</label>
					<input
						id="new-binder-name"
						type="text"
						bind:value={newBinderName}
						placeholder="My Collection"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50"
					/>
				</div>
				<div class="flex-1 min-w-[160px]">
					<label for="new-binder-desc" class="block text-xs font-medium text-gray-500 mb-1">Description (optional)</label>
					<input
						id="new-binder-desc"
						type="text"
						bind:value={newBinderDesc}
						placeholder="e.g. Shore birds"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50"
					/>
				</div>
				<button
					type="button"
					onclick={createBinder}
					disabled={!newBinderName.trim() || creatingBinder}
					class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed"
				>
					{#if creatingBinder}
						<svg class="inline h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
						</svg>
					{:else}
						Create
					{/if}
				</button>
				<button
					type="button"
					onclick={() => { showNewBinder = false; newBinderName = ''; newBinderDesc = ''; }}
					class="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
				>
					Cancel
				</button>
			</div>
		{/if}
	</div>

	<!-- Filter & Sort Controls -->
	{#if !loading && allCards.length > 0}
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

			<!-- Rarity Filter -->
			<select
				bind:value={rarityFilter}
				class="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50"
			>
				<option value="">All Rarities</option>
				<option value="common">Common</option>
				<option value="uncommon">Uncommon</option>
				<option value="rare">Rare</option>
				<option value="epic">Epic</option>
				<option value="legendary">Legendary</option>
			</select>

			<!-- Sort -->
			<select
				bind:value={sortBy}
				class="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50"
			>
				<option value="newest">Newest First</option>
				<option value="oldest">Oldest First</option>
				<option value="rarity">By Rarity</option>
				<option value="name">By Name</option>
			</select>
		</div>
	{/if}

	<!-- Content -->
	{#if loading}
		<div class="flex items-center justify-center py-16">
			<svg class="h-8 w-8 animate-spin text-gray-600" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	{:else if allCards.length === 0}
		<div class="text-center py-16 space-y-3">
			<svg class="w-16 h-16 text-gray-700 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
				<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
			</svg>
			<p class="text-gray-400">No cards yet. Generate cards from your sightings!</p>
			<a href="/sightings" class="inline-flex items-center gap-1.5 text-sm text-green-400 hover:text-green-300 underline underline-offset-2">
				View sightings →
			</a>
		</div>
	{:else if filteredCards().length === 0}
		<div class="text-center py-16 space-y-3">
			<p class="text-gray-400">No cards match your filters.</p>
			<button
				type="button"
				onclick={() => { searchQuery = ''; rarityFilter = ''; }}
				class="text-sm text-green-400 hover:text-green-300 underline underline-offset-2"
			>
				Clear filters
			</button>
		</div>
	{:else}
		<p class="text-xs text-gray-500">{filteredCards().length} card{filteredCards().length !== 1 ? 's' : ''} shown</p>
		<CardGrid cards={filteredCards()} onselect={handleCardSelect} />
	{/if}
</div>

<!-- Card Detail Modal -->
{#if selectedCard}
	<CardModal card={selectedCard} onClose={closeModal} />
{/if}
