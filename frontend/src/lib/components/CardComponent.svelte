<script lang="ts">
	let { card, onselect }: { card: any; onselect?: (card: any) => void } = $props();

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

	const rarity = $derived(getRarity(card.rarity_tier));
</script>

<button
	type="button"
	class="group relative flex flex-col overflow-hidden rounded-xl border border-gray-800 bg-gray-900/80 transition-all duration-200 hover:scale-[1.03] hover:border-gray-600 hover:shadow-lg hover:shadow-black/30 focus:outline-none focus:ring-2 focus:ring-green-500/50"
	onclick={() => onselect?.(card)}
>
	<!-- Card Art -->
	<div class="relative aspect-[3/4] w-full overflow-hidden bg-gray-800">
		{#if card.card_art_url}
			<img
				src={card.card_art_url}
				alt={card.species_common ?? 'Card'}
				class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
				loading="lazy"
			/>
		{:else}
			<div class="flex h-full w-full items-center justify-center bg-gradient-to-br from-gray-800 via-gray-750 to-gray-900">
				<svg class="h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
					<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
				</svg>
			</div>
		{/if}

		<!-- Rarity Badge (top-left) -->
		<span class="absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-semibold {rarity.bg} {rarity.text}">
			{rarity.label}
		</span>

		<!-- Pose Label (top-right) -->
		{#if card.pose_variant}
			<span class="absolute right-2 top-2 rounded-full bg-black/60 px-2 py-0.5 text-xs text-gray-300 backdrop-blur-sm">
				{card.pose_variant}
			</span>
		{/if}

		<!-- Duplicate Count (bottom-right) -->
		{#if card.duplicate_count > 1}
			<span class="absolute bottom-2 right-2 flex h-6 w-6 items-center justify-center rounded-full bg-green-600 text-xs font-bold text-white shadow-lg">
				×{card.duplicate_count}
			</span>
		{/if}
	</div>

	<!-- Card Info -->
	<div class="flex flex-col gap-0.5 p-2.5">
		<p class="truncate text-sm font-medium text-gray-100">
			{card.species_common ?? 'Unknown'}
		</p>
		{#if card.species_code}
			<p class="truncate text-xs text-gray-500 italic">{card.species_code}</p>
		{/if}
	</div>
</button>
