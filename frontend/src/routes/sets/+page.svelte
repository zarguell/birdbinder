<script lang="ts">
	import { sets, ApiError } from '$lib/api';
	import CompletionBar from '$lib/components/CompletionBar.svelte';

	let setsList = $state<any[]>([]);
	let progressMap = $state<Record<string, any>>({});
	let loading = $state(true);
	let error = $state('');
	let showForm = $state(false);
	let formName = $state('');
	let formDesc = $state('');
	let formRegion = $state('');
	let formTargets = $state('');
	let formLoading = $state(false);
	let formError = $state('');

	async function loadSets() {
		loading = true;
		error = '';
		try {
			const res = await sets.list({ limit: 50 });
			setsList = res.items ?? [];
			// Fetch progress for each set
			const map: Record<string, any> = {};
			await Promise.all(
				setsList.map(async (s: any) => {
					try {
						map[s.id] = await sets.progress(s.id);
					} catch {
						map[s.id] = null;
					}
				})
			);
			progressMap = map;
		} catch (e: any) {
			error = e.message || 'Failed to load sets';
		} finally {
			loading = false;
		}
	}

	async function handleCreate(e: Event) {
		e.preventDefault();
		formError = '';
		formLoading = true;
		try {
			const targets = formTargets
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean);
			await sets.create({
				name: formName,
				description: formDesc || undefined,
				region: formRegion || undefined,
				card_targets: targets.length > 0 ? targets : undefined
			});
			formName = '';
			formDesc = '';
			formRegion = '';
			formTargets = '';
			showForm = false;
			await loadSets();
		} catch (err: any) {
			formError = err.message || 'Failed to create set';
		} finally {
			formLoading = false;
		}
	}

	$effect(() => {
		loadSets();
	});
</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold text-gray-100">Sets</h1>
			<p class="mt-1 text-sm text-gray-500">Track your collection progress against birding sets</p>
		</div>
		<button
			type="button"
			class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500"
			onclick={() => (showForm = !showForm)}
		>
			{showForm ? 'Cancel' : '+ Create Set'}
		</button>
	</div>

	<!-- Create Form -->
	{#if showForm}
		<form
			onsubmit={handleCreate}
			class="space-y-4 rounded-xl border border-gray-800 bg-gray-900/60 p-5"
		>
			<h2 class="text-lg font-semibold text-gray-200">New Set</h2>

			{#if formError}
				<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-3 py-2 text-sm text-red-400">
					{formError}
				</div>
			{/if}

			<div>
				<label for="set-name" class="mb-1 block text-sm font-medium text-gray-400">Name *</label>
				<input
					id="set-name"
					type="text"
					required
					bind:value={formName}
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="e.g. Spring Warblers 2026"
				/>
			</div>

			<div>
				<label for="set-desc" class="mb-1 block text-sm font-medium text-gray-400">Description</label>
				<textarea
					id="set-desc"
					bind:value={formDesc}
					rows="2"
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="Optional description..."
				></textarea>
			</div>

			<div>
				<label for="set-region" class="mb-1 block text-sm font-medium text-gray-400">Region</label>
				<input
					id="set-region"
					type="text"
					bind:value={formRegion}
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="e.g. Northeast US"
				/>
			</div>

			<div>
				<label for="set-targets" class="mb-1 block text-sm font-medium text-gray-400">Card Targets</label>
				<input
					id="set-targets"
					type="text"
					bind:value={formTargets}
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="Comma-separated species codes: ybcu, bansw, nowar"
				/>
				<p class="mt-1 text-xs text-gray-600">Species codes to track, separated by commas</p>
			</div>

			<div class="flex justify-end gap-3">
				<button
					type="button"
					class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
					onclick={() => (showForm = false)}
				>
					Cancel
				</button>
				<button
					type="submit"
					disabled={formLoading}
					class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-50"
				>
					{formLoading ? 'Creating...' : 'Create'}
				</button>
			</div>
		</form>
	{/if}

	<!-- Loading -->
	{#if loading}
		<div class="flex items-center justify-center py-16">
			<div class="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-green-500"></div>
		</div>
	{:else if error}
		<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-4 py-3 text-center text-sm text-red-400">
			{error}
		</div>
	{:else if setsList.length === 0}
		<div class="rounded-xl border border-dashed border-gray-800 py-16 text-center">
			<div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-900">
				<svg class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
				</svg>
			</div>
			<p class="text-sm font-medium text-gray-400">No sets yet</p>
			<p class="mt-1 text-xs text-gray-600">Create your first birding set to start tracking progress</p>
		</div>
	{:else}
		<!-- Sets Grid -->
		<div class="grid gap-4 sm:grid-cols-2">
			{#each setsList as set (set.id)}
				<a
					href="/sets/{set.id}"
					class="group rounded-xl border border-gray-800 bg-gray-900/60 p-5 transition-all hover:border-gray-600 hover:bg-gray-900"
				>
					<div class="mb-3 flex items-start justify-between">
						<div class="min-w-0 flex-1">
							<h3 class="truncate text-lg font-semibold text-gray-100 group-hover:text-green-400 transition-colors">
								{set.name}
							</h3>
							{#if set.description}
								<p class="mt-0.5 truncate text-sm text-gray-500">{set.description}</p>
							{/if}
						</div>
						{#if set.region}
							<span class="ml-3 flex-shrink-0 rounded-full bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-400">
								{set.region}
							</span>
						{/if}
					</div>

					<div class="mb-3 text-xs text-gray-500">
						{set.card_targets?.length ?? 0} target{set.card_targets?.length !== 1 ? 's' : ''}
					</div>

					{#if progressMap[set.id]}
						<CompletionBar
							percent={progressMap[set.id].progress_percent ?? 0}
							collected={progressMap[set.id].collected ?? 0}
							total={progressMap[set.id].total_targets ?? 0}
						/>
					{:else}
						<div class="h-3 w-full rounded-full bg-gray-800 animate-pulse"></div>
					{/if}
				</a>
			{/each}
		</div>
	{/if}
</div>
