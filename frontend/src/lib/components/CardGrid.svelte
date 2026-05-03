<script lang="ts">
	import CardComponent from './CardComponent.svelte';

	let { cards, onselect }: { cards: any[]; onselect?: (card: any) => void } = $props();
</script>

{#if cards.length === 0}
	<div class="py-8 text-center text-gray-500 text-sm">No cards to display.</div>
{:else}
	<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4">
		{#each cards as card (card.id)}
			<svelte:component
				this={CardComponent}
				{card}
				{onselect}
			/>
		{/each}
	</div>
{/if}
