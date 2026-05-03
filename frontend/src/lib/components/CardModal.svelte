<script lang="ts">
	import { cards, binders } from '$lib/api';

	let { card, onClose }: { card: any; onClose: () => void } = $props();

	let binderList = $state<any[]>([]);
	let selectedBinderId = $state('');
	let adding = $state(false);
	let addError = $state('');
	let addSuccess = $state('');
	let flipped = $state(false);

	const rarityConfig: Record<string, { bg: string; text: string; label: string }> = {
		common: { bg: 'bg-gray-600', text: 'text-gray-200', label: 'Common' },
		uncommon: { bg: 'bg-green-700', text: 'text-green-100', label: 'Uncommon' },
		rare: { bg: 'bg-blue-700', text: 'text-blue-100', label: 'Rare' },
		epic: { bg: 'bg-purple-700', text: 'text-purple-100', label: 'Epic' },
		legendary: { bg: 'bg-amber-600', text: 'text-amber-100', label: 'Legendary' }
	};

	function getRarity(tier: string) {
		return rarityConfig[tier?.toLowerCase()] ?? rarityConfig.common;
	}

	const rarity = $derived(getRarity(card?.rarity_tier));

	function formatDate(dateStr: string): string {
		try {
			return new Date(dateStr).toLocaleDateString('en-US', {
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

	async function loadBinders() {
		try {
			const data = await binders.list({ limit: 50 });
			binderList = data.items ?? [];
			// Check if card is already in any binder
			const inBinder = binderList.find((b: any) =>
				b.cards?.some((bc: any) => bc.card_id === card?.id)
			);
			if (inBinder) {
				selectedBinderId = '__already__';
			}
		} catch {
			binderList = [];
		}
	}

	async function addToBinder() {
		if (!selectedBinderId || selectedBinderId === '__already__') return;
		adding = true;
		addError = '';
		addSuccess = '';
		try {
			await binders.addCard(selectedBinderId, card.id);
			addSuccess = 'Card added to binder!';
			selectedBinderId = '__already__';
		} catch (err) {
			addError = err instanceof Error ? err.message : 'Failed to add card';
		} finally {
			adding = false;
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) onClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (card) {
			loadBinders();
			addError = '';
			addSuccess = '';
			selectedBinderId = '';
			flipped = false;
			// Focus trap
			document.addEventListener('keydown', handleKeydown);
		}
		return () => {
			document.removeEventListener('keydown', handleKeydown);
		};
	});
</script>

{#if card}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
		onclick={handleBackdropClick}
		role="dialog"
		aria-modal="true"
		aria-label="Card details"
	>
		<div class="relative w-full max-w-lg overflow-hidden rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl transition-all duration-300">
			<!-- Close Button -->
			<button
				type="button"
				onclick={onClose}
				class="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-black/50 text-gray-400 transition-colors hover:bg-black/70 hover:text-gray-200"
			>
				<svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>

			{#if !flipped}
				<!-- FRONT VIEW -->
				<div class="flex flex-col sm:flex-row">
					<!-- Card Art -->
					<div class="relative aspect-[3/4] w-full shrink-0 overflow-hidden bg-gray-800 sm:w-48 sm:aspect-auto sm:min-h-64">
						{#if card.card_art_url}
							<img
								src={card.card_art_url}
								alt={card.species_common ?? 'Card'}
								class="h-full w-full object-cover"
							/>
						{:else}
							<div class="flex h-full w-full items-center justify-center bg-gradient-to-br from-gray-800 via-gray-750 to-gray-900">
								<svg class="h-16 w-16 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
									<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
								</svg>
							</div>
						{/if}
					</div>

					<!-- Card Details -->
					<div class="flex-1 space-y-4 p-5">
						<div>
							<h2 class="text-xl font-bold text-gray-100">{card.species_common ?? 'Unknown Species'}</h2>
							{#if card.species_code}
								<p class="text-sm text-gray-500 italic mt-0.5">{card.species_code}</p>
							{/if}
						</div>

						<div class="flex flex-wrap items-center gap-2">
							<span class="rounded-full px-2.5 py-1 text-xs font-semibold {rarity.bg} {rarity.text}">
								{rarity.label}
							</span>
							{#if card.pose_variant}
								<span class="rounded-full border border-gray-700 px-2.5 py-1 text-xs text-gray-300">
									{card.pose_variant}
								</span>
							{/if}
						</div>

						<dl class="space-y-2 text-sm">
							{#if card.family}
								<div class="flex justify-between">
									<dt class="text-gray-500">Family</dt>
									<dd class="text-gray-200">{card.family}</dd>
								</div>
							{/if}
							{#if card.id_method}
								<div class="flex justify-between">
									<dt class="text-gray-500">ID Method</dt>
									<dd class="text-gray-200">{card.id_method}</dd>
								</div>
							{/if}
							{#if card.id_confidence != null}
								<div class="flex justify-between">
									<dt class="text-gray-500">Confidence</dt>
									<dd class="text-gray-200">{Math.round(card.id_confidence * 100)}%</dd>
								</div>
							{/if}
							{#if card.duplicate_count > 1}
								<div class="flex justify-between">
									<dt class="text-gray-500">Duplicates</dt>
									<dd class="text-gray-200">{card.duplicate_count}</dd>
								</div>
							{/if}
							{#if card.generated_at}
								<div class="flex justify-between">
									<dt class="text-gray-500">Generated</dt>
									<dd class="text-gray-200">{formatDate(card.generated_at)}</dd>
								</div>
							{/if}
							{#if card.set_ids?.length}
								<div class="flex justify-between">
									<dt class="text-gray-500">Sets</dt>
									<dd class="text-gray-200">{card.set_ids.length} set{card.set_ids.length !== 1 ? 's' : ''}</dd>
								</div>
							{/if}
							{#if card.tradeable}
								<div class="flex justify-between">
									<dt class="text-gray-500">Tradeable</dt>
									<dd class="text-green-400">Yes</dd>
								</div>
							{/if}
						</dl>

						<!-- Add to Binder -->
						{#if binderList.length > 0}
							<div class="border-t border-gray-800 pt-4 space-y-2">
								<label for="binder-select" class="block text-xs font-medium text-gray-500 uppercase tracking-wider">Add to Binder</label>
								<div class="flex gap-2">
									<select
										id="binder-select"
										bind:value={selectedBinderId}
										disabled={selectedBinderId === '__already__' || adding}
										class="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50 disabled:opacity-50"
									>
										{#if selectedBinderId === '__already__'}
											<option value="__already__">Already in binder</option>
										{:else}
											<option value="" disabled>Select binder...</option>
										{/if}
										{#each binderList as binder}
											<option value={binder.id}>{binder.name} ({binder.card_count ?? 0})</option>
										{/each}
									</select>
									<button
										onclick={addToBinder}
										disabled={!selectedBinderId || selectedBinderId === '__already__' || adding}
										class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed"
									>
										{#if adding}
											<svg class="inline h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
												<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
												<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
											</svg>
										{:else}
											Add
										{/if}
									</button>
								</div>
								{#if addError}
									<p class="text-xs text-red-400">{addError}</p>
								{/if}
								{#if addSuccess}
									<p class="text-xs text-green-400">{addSuccess}</p>
								{/if}
							</div>
						{/if}
					</div>
				</div>
			{:else}
				<!-- CARD BACK VIEW -->
				<div class="p-6 space-y-5">
					<div class="text-center border-b border-gray-700 pb-4">
						<p class="text-xs font-medium text-gray-500 uppercase tracking-widest mb-1">Card Back</p>
						<h2 class="text-lg font-bold text-gray-100">{card.species_common ?? 'Unknown Species'}</h2>
						{#if card.species_scientific}
							<p class="text-sm text-gray-400 italic">{card.species_scientific}</p>
						{/if}
					</div>

					<dl class="space-y-3 text-sm">
						{#if card.generated_at}
							<div class="flex justify-between">
								<dt class="text-gray-500">Submitted</dt>
								<dd class="text-gray-200">{formatDate(card.generated_at)}</dd>
							</div>
						{/if}

						{#if card.sighting?.location_display_name || card.sighting?.exif_lat}
							<div class="flex justify-between">
								<dt class="text-gray-500">Location</dt>
								<dd class="text-gray-200">
									{card.sighting?.location_display_name || `${card.sighting?.exif_lat?.toFixed(4)}, ${card.sighting?.exif_lon?.toFixed(4)}`}
								</dd>
							</div>
						{/if}

						{#if card.user_identifier}
							<div class="flex justify-between">
								<dt class="text-gray-500">Observer</dt>
								<dd class="text-gray-200">{card.user_identifier}</dd>
							</div>
						{/if}

						{#if card.id_confidence != null}
							<div class="flex justify-between">
								<dt class="text-gray-500">Confidence</dt>
								<dd class="text-gray-200">
									<span class="inline-flex items-center gap-1">
										<span class="inline-block h-2 w-2 rounded-full {card.id_confidence >= 0.8 ? 'bg-green-500' : card.id_confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'}"></span>
										{Math.round(card.id_confidence * 100)}%
									</span>
								</dd>
							</div>
						{/if}

						{#if card.id_method}
							<div class="flex justify-between">
								<dt class="text-gray-500">ID Method</dt>
								<dd class="text-gray-200">{card.id_method}</dd>
							</div>
						{/if}

						{#if card.sighting?.exif_camera_model}
							<div class="flex justify-between">
								<dt class="text-gray-500">Camera</dt>
								<dd class="text-gray-200">{card.sighting.exif_camera_model}</dd>
							</div>
						{/if}

						{#if card.pose_variant}
							<div class="flex justify-between">
								<dt class="text-gray-500">Pose Variant</dt>
								<dd class="text-gray-200">{card.pose_variant}</dd>
							</div>
						{/if}

						{#if card.rarity_tier}
							<div class="flex justify-between">
								<dt class="text-gray-500">Rarity</dt>
								<dd class="text-gray-200">
									<span class="rounded-full px-2 py-0.5 text-xs font-semibold {rarity.bg} {rarity.text}">
										{rarity.label}
									</span>
								</dd>
							</div>
						{/if}

						{#if card.sighting?.exif_datetime}
							<div class="flex justify-between">
								<dt class="text-gray-500">Photo Taken</dt>
								<dd class="text-gray-200">{formatDate(card.sighting.exif_datetime)}</dd>
							</div>
						{/if}
					</dl>
				</div>
			{/if}

			<!-- Flip Card Button (bottom-right) -->
			<button
				type="button"
				onclick={() => flipped = !flipped}
				class="absolute bottom-3 right-3 z-10 flex h-9 items-center gap-1.5 rounded-full bg-black/60 px-3 text-xs font-medium text-gray-300 backdrop-blur-sm transition-colors hover:bg-black/80 hover:text-gray-100"
			>
				<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
				</svg>
				{flipped ? 'Show Front' : 'Flip Card'}
			</button>
		</div>
	</div>
{/if}
