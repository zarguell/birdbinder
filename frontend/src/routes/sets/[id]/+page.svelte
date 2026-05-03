<script lang="ts">
	import { page } from '$app/stores';
	import { sets, ApiError } from '$lib/api';
	import CompletionBar from '$lib/components/CompletionBar.svelte';
	import MissingCards from '$lib/components/MissingCards.svelte';

	let setData = $state<any>(null);
	let progress = $state<any>(null);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);
	let deleteError = $state('');

	const set_id = $derived($page.params.id);

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [s, p] = await Promise.all([
				sets.get(set_id),
				sets.progress(set_id)
			]);
			setData = s;
			progress = p;
		} catch (e: any) {
			error = e.message || 'Failed to load set';
		} finally {
			loading = false;
		}
	}

	async function handleDelete() {
		if (!confirm('Are you sure you want to delete this set?')) return;
		deleting = true;
		deleteError = '';
		try {
			await sets.delete(set_id);
			window.location.href = '/sets';
		} catch (e: any) {
			deleteError = e.message || 'Failed to delete set';
		} finally {
			deleting = false;
		}
	}

	$effect(() => {
		const id = $page.params.id;
		if (id) loadData();
	});
</script>

<div class="space-y-6">
	<!-- Back -->
	<a href="/sets" class="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors">
		<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
		</svg>
		Back to Sets
	</a>

	{#if loading}
		<div class="flex items-center justify-center py-16">
			<div class="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-green-500"></div>
		</div>
	{:else if error}
		<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-4 py-3 text-center text-sm text-red-400">
			{error}
		</div>
	{:else if setData}
		<!-- Set Header -->
		<div class="flex items-start justify-between gap-4">
			<div>
				<h1 class="text-2xl font-bold text-gray-100">{setData.name}</h1>
				{#if setData.description}
					<p class="mt-1 text-sm text-gray-400">{setData.description}</p>
				{/if}
				<div class="mt-2 flex flex-wrap items-center gap-3 text-xs text-gray-500">
					{#if setData.region}
						<span class="rounded-full bg-gray-800 px-2.5 py-0.5 font-medium text-gray-400">
							📍 {setData.region}
						</span>
					{/if}
					{#if setData.season}
						<span class="rounded-full bg-gray-800 px-2.5 py-0.5 font-medium text-gray-400">
							🗓 {setData.season}
						</span>
					{/if}
					{#if setData.release_date}
						<span>Released: {new Date(setData.release_date).toLocaleDateString()}</span>
					{/if}
				</div>
			</div>
			<button
				type="button"
				disabled={deleting}
				onclick={handleDelete}
				class="flex-shrink-0 rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-950/60 hover:border-red-700 disabled:opacity-50"
			>
				{deleting ? 'Deleting...' : 'Delete Set'}
			</button>
		</div>

		{#if deleteError}
			<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-3 py-2 text-sm text-red-400">
				{deleteError}
			</div>
		{/if}

		<!-- Progress Section -->
		{#if progress}
			<div class="rounded-xl border border-gray-800 bg-gray-900/60 p-5">
				<h2 class="mb-4 text-lg font-semibold text-gray-200">Collection Progress</h2>
				<CompletionBar
					percent={progress.progress_percent ?? 0}
					collected={progress.collected ?? 0}
					total={progress.total_targets ?? 0}
				/>
			</div>

			<!-- Two-column layout -->
			<div class="grid gap-6 lg:grid-cols-2">
				<!-- Collected / Card Targets -->
				<div class="rounded-xl border border-gray-800 bg-gray-900/60 p-5">
					<h2 class="mb-4 text-lg font-semibold text-gray-200">
						Card Targets
						<span class="ml-2 text-sm font-normal text-gray-500">
							({setData.card_targets?.length ?? 0} total)
						</span>
					</h2>
					{#if setData.card_targets && setData.card_targets.length > 0}
						<div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
							{#each setData.card_targets as target}
								{@const isCollected = progress.missing && !progress.missing.includes(target)}
								<div class="flex items-center gap-2 rounded-lg bg-gray-800/50 px-3 py-2">
									{#if isCollected}
										<span class="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-green-600/20">
											<svg class="h-3 w-3 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
												<path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
											</svg>
										</span>
										<span class="text-sm text-green-300">{target}</span>
									{:else}
										<span class="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-gray-700 bg-gray-800">
										</span>
										<span class="text-sm text-gray-500">{target}</span>
									{/if}
								</div>
							{/each}
						</div>
					{:else}
						<p class="text-sm text-gray-500">No card targets defined</p>
					{/if}
				</div>

				<!-- Missing Cards -->
				<div class="rounded-xl border border-gray-800 bg-gray-900/60 p-5">
					<h2 class="mb-4 text-lg font-semibold text-gray-200">Missing Cards</h2>
					<MissingCards species={progress.missing ?? []} />
				</div>
			</div>
		{/if}
	{/if}
</div>
