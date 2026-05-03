<script lang="ts">
	import { trades, cards, ApiError } from '$lib/api';

	let allTrades = $state<any[]>([]);
	let tradeableCards = $state<any[]>([]);
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state<'incoming' | 'outgoing' | 'all'>('incoming');
	let statusFilter = $state('');
	let showCreateForm = $state(false);

	// Create trade form
	let formRecipient = $state('');
	let formOfferedIds = $state<string[]>([]);
	let formRequestedCodes = $state('');
	let formLoading = $state(false);
	let formError = $state('');
	let formSuccess = $state('');

	const statusColors: Record<string, string> = {
		pending: 'bg-yellow-900/40 text-yellow-300 border-yellow-700/50',
		accepted: 'bg-green-900/40 text-green-300 border-green-700/50',
		declined: 'bg-red-900/40 text-red-300 border-red-700/50',
		cancelled: 'bg-gray-800 text-gray-400 border-gray-700'
	};

	async function loadTrades() {
		loading = true;
		error = '';
		try {
			const res = await trades.list({ limit: 50 });
			allTrades = res.items ?? [];
		} catch (e: any) {
			error = e.message || 'Failed to load trades';
		} finally {
			loading = false;
		}
	}

	async function loadTradeableCards() {
		try {
			const res = await cards.list({ limit: 100 });
			tradeableCards = (res.items ?? []).filter((c: any) => c.tradeable && c.duplicate_count > 0);
		} catch {
			// Non-critical
		}
	}

	function filteredTrades() {
		let list = allTrades;
		if (activeTab === 'incoming') {
			list = list.filter((t) => t.status === 'pending');
		} else if (activeTab === 'outgoing') {
			list = list.filter((t) => t.offered_by === 'self' || t.status === 'pending');
		}
		if (statusFilter) {
			list = list.filter((t) => t.status === statusFilter);
		}
		return list;
	}

	function formatDate(dateStr: string) {
		return new Date(dateStr).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	async function handleAccept(id: string) {
		try {
			await trades.accept(id);
			await loadTrades();
		} catch (e: any) {
			alert(e.message || 'Failed to accept trade');
		}
	}

	async function handleDecline(id: string) {
		if (!confirm('Decline this trade?')) return;
		try {
			await trades.decline(id);
			await loadTrades();
		} catch (e: any) {
			alert(e.message || 'Failed to decline trade');
		}
	}

	async function handleCancel(id: string) {
		if (!confirm('Cancel this trade?')) return;
		try {
			await trades.cancel(id);
			await loadTrades();
		} catch (e: any) {
			alert(e.message || 'Failed to cancel trade');
		}
	}

	function toggleOffered(cardId: string) {
		formOfferedIds = formOfferedIds.includes(cardId)
			? formOfferedIds.filter((id) => id !== cardId)
			: [...formOfferedIds, cardId];
	}

	async function handleCreateTrade(e: Event) {
		e.preventDefault();
		formError = '';
		formSuccess = '';
		if (!formRecipient.trim()) {
			formError = 'Recipient is required';
			return;
		}
		if (formOfferedIds.length === 0) {
			formError = 'Select at least one card to offer';
			return;
		}
		const requestedIds = formRequestedCodes
			.split(',')
			.map((t) => t.trim())
			.filter(Boolean);
		if (requestedIds.length === 0) {
			formError = 'Enter at least one card to request';
			return;
		}

		formLoading = true;
		try {
			await trades.create({
				offered_to: formRecipient.trim(),
				offered_card_ids: formOfferedIds,
				requested_card_ids: requestedIds
			});
			formSuccess = 'Trade created successfully!';
			formRecipient = '';
			formOfferedIds = [];
			formRequestedCodes = '';
			showCreateForm = false;
			await loadTrades();
		} catch (err: any) {
			formError = err.message || 'Failed to create trade';
		} finally {
			formLoading = false;
		}
	}

	$effect(() => {
		loadTrades();
		loadTradeableCards();
	});
</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold text-gray-100">Trades</h1>
			<p class="mt-1 text-sm text-gray-500">Trade duplicate cards with other birders</p>
		</div>
		<button
			type="button"
			class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500"
			onclick={() => {
				showCreateForm = !showCreateForm;
				formError = '';
				formSuccess = '';
			}}
		>
			{showCreateForm ? 'Cancel' : '+ Create Trade'}
		</button>
	</div>

	<!-- Create Trade Form -->
	{#if showCreateForm}
		<form
			onsubmit={handleCreateTrade}
			class="space-y-4 rounded-xl border border-gray-800 bg-gray-900/60 p-5"
		>
			<h2 class="text-lg font-semibold text-gray-200">New Trade</h2>

			{#if formError}
				<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-3 py-2 text-sm text-red-400">
					{formError}
				</div>
			{/if}
			{#if formSuccess}
				<div class="rounded-lg border border-green-800/40 bg-green-950/20 px-3 py-2 text-sm text-green-400">
					{formSuccess}
				</div>
			{/if}

			<div>
				<label for="trade-recipient" class="mb-1 block text-sm font-medium text-gray-400">Recipient *</label>
				<input
					id="trade-recipient"
					type="text"
					required
					bind:value={formRecipient}
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="User identifier or username"
				/>
			</div>

			<div>
				<label class="mb-1 block text-sm font-medium text-gray-400">Cards to Offer *</label>
				{#if tradeableCards.length > 0}
					<div class="max-h-48 space-y-1.5 overflow-y-auto rounded-lg border border-gray-700 bg-gray-800/50 p-3">
						{#each tradeableCards as card (card.id)}
							<label class="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-gray-700/50">
								<input
									type="checkbox"
									checked={formOfferedIds.includes(card.id)}
									onchange={() => toggleOffered(card.id)}
									class="h-4 w-4 rounded border-gray-600 bg-gray-800 text-green-500 focus:ring-green-500"
								/>
								<div class="min-w-0 flex-1">
									<span class="text-sm text-gray-200">{card.species_common ?? card.species_code}</span>
									{#if card.species_code}
										<span class="ml-1.5 text-xs text-gray-500 italic">{card.species_code}</span>
									{/if}
								</div>
								<span class="text-xs text-gray-500">×{card.duplicate_count}</span>
							</label>
						{/each}
					</div>
					<p class="mt-1 text-xs text-gray-600">
						{formOfferedIds.length} selected
					</p>
				{:else}
					<p class="text-sm text-gray-500">No tradeable duplicate cards found</p>
				{/if}
			</div>

			<div>
				<label for="trade-requested" class="mb-1 block text-sm font-medium text-gray-400">Cards to Request *</label>
				<input
					id="trade-requested"
					type="text"
					bind:value={formRequestedCodes}
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
					placeholder="Comma-separated species codes: ybcu, bansw"
				/>
				<p class="mt-1 text-xs text-gray-600">Species codes you want in return</p>
			</div>

			<div class="flex justify-end gap-3">
				<button
					type="button"
					class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
					onclick={() => (showCreateForm = false)}
				>
					Cancel
				</button>
				<button
					type="submit"
					disabled={formLoading}
					class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-50"
				>
					{formLoading ? 'Creating...' : 'Propose Trade'}
				</button>
			</div>
		</form>
	{/if}

	<!-- Tabs -->
	<div class="flex items-center gap-1 rounded-lg bg-gray-900 p-1">
		{#each [
			{ key: 'incoming' as const, label: 'Incoming' },
			{ key: 'outgoing' as const, label: 'Outgoing' },
			{ key: 'all' as const, label: 'All' }
		] as tab}
			<button
				type="button"
				class="rounded-md px-4 py-2 text-sm font-medium transition-colors {activeTab === tab.key
					? 'bg-gray-800 text-gray-100 shadow-sm'
					: 'text-gray-500 hover:text-gray-300'}"
				onclick={() => (activeTab = tab.key)}
			>
				{tab.label}
			</button>
		{/each}

		<!-- Status filter -->
		<select
			bind:value={statusFilter}
			class="ml-auto rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-300 focus:border-green-500 focus:outline-none"
		>
			<option value="">All statuses</option>
			<option value="pending">Pending</option>
			<option value="accepted">Accepted</option>
			<option value="declined">Declined</option>
			<option value="cancelled">Cancelled</option>
		</select>
	</div>

	<!-- Loading -->
	{#if loading}
		<div class="flex items-center justify-center py-16">
			<div class="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-green-500"></div>
		</div>
	{:else if error}
		<div class="rounded-lg border border-red-800/40 bg-red-950/20 px-4 py-3 text-center text-sm text-red-400">
			{error}
		</div>
	{:else}
		{@const displayed = filteredTrades()}
		{#if displayed.length === 0}
			<div class="rounded-xl border border-dashed border-gray-800 py-16 text-center">
				<div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-900">
					<svg class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
					</svg>
				</div>
				<p class="text-sm font-medium text-gray-400">No trades found</p>
				<p class="mt-1 text-xs text-gray-600">
					{activeTab === 'incoming' ? 'No pending incoming trades' : activeTab === 'outgoing' ? 'No outgoing trades' : 'No trades match your filters'}
				</p>
			</div>
		{:else}
			<!-- Trades List -->
			<div class="space-y-3">
				{#each displayed as trade (trade.id)}
					<div class="rounded-xl border border-gray-800 bg-gray-900/60 p-4 transition-colors hover:border-gray-700">
						<div class="mb-3 flex items-center justify-between">
							<div class="flex items-center gap-3">
								<span class="rounded-full border px-2.5 py-0.5 text-xs font-semibold {statusColors[trade.status] ?? 'bg-gray-800 text-gray-400 border-gray-700'}">
									{trade.status}
								</span>
								<span class="text-xs text-gray-500">{formatDate(trade.created_at)}</span>
							</div>
							<span class="text-xs text-gray-500">
								{#if trade.offered_by}
									From: {trade.offered_by}
								{/if}
								{#if trade.offered_to}
									{trade.offered_by ? ' → ' : ''}To: {trade.offered_to}
								{/if}
							</span>
						</div>

						<div class="grid gap-3 sm:grid-cols-2">
							<!-- Offered Cards -->
							<div>
								<p class="mb-1.5 text-xs font-medium uppercase tracking-wider text-gray-500">Offered</p>
								<div class="flex flex-wrap gap-1.5">
									{#each (trade.offered_card_ids ?? []) as cardId}
										<span class="rounded-full bg-blue-900/30 border border-blue-700/40 px-2.5 py-1 text-xs text-blue-300">
											{cardId}
										</span>
									{/each}
									{#if (trade.offered_card_ids ?? []).length === 0}
										<span class="text-xs text-gray-600">None</span>
									{/if}
								</div>
							</div>

							<!-- Requested Cards -->
							<div>
								<p class="mb-1.5 text-xs font-medium uppercase tracking-wider text-gray-500">Requested</p>
								<div class="flex flex-wrap gap-1.5">
									{#each (trade.requested_card_ids ?? []) as cardId}
										<span class="rounded-full bg-purple-900/30 border border-purple-700/40 px-2.5 py-1 text-xs text-purple-300">
											{cardId}
										</span>
									{/each}
									{#if (trade.requested_card_ids ?? []).length === 0}
										<span class="text-xs text-gray-600">None</span>
									{/if}
								</div>
							</div>
						</div>

						<!-- Action Buttons -->
						{#if trade.status === 'pending'}
							<div class="mt-3 flex items-center gap-2 border-t border-gray-800 pt-3">
								{#if activeTab === 'incoming' || !trade.offered_by}
									<button
										type="button"
										onclick={() => handleAccept(trade.id)}
										class="rounded-lg bg-green-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-green-500"
									>
										Accept
									</button>
									<button
										type="button"
										onclick={() => handleDecline(trade.id)}
										class="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-1.5 text-sm font-medium text-red-400 transition-colors hover:bg-red-950/60"
									>
										Decline
									</button>
								{:else}
									<button
										type="button"
										onclick={() => handleCancel(trade.id)}
										class="rounded-lg border border-gray-700 px-4 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
									>
										Cancel
									</button>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>
