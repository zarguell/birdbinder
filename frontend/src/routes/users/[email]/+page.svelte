<script lang="ts">
		import { page } from '$app/stores';
		import { onMount } from 'svelte';
		import { users } from '$lib/api';

		let profile = $state<any>(null);
		let loading = $state(true);
		let error = $state('');

		let email = $state('');

		async function loadProfile() {
			if (!email) return;
			loading = true;
			error = '';
			try {
				profile = await users.getProfile(email);
			} catch (err) {
				error = err instanceof Error ? err.message : 'Failed to load profile';
			} finally {
				loading = false;
			}
		}

		onMount(() => {
			email = decodeURIComponent($page.params.email);
			// Re-run on client-side navigation
			const unsub = page.subscribe((p) => {
				const newEmail = decodeURIComponent(p.params.email);
				if (newEmail !== email) {
					email = newEmail;
					loadProfile();
				}
			});
			loadProfile();
			return unsub;
		});

	function formatDate(iso: string | null): string {
		if (!iso) return '';
		return new Date(iso).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
	}

	function formatRelativeTime(iso: string): string {
		const now = Date.now();
		const then = new Date(iso).getTime();
		const diff = now - then;
		const minutes = Math.floor(diff / 60000);
		const hours = Math.floor(diff / 3600000);
		const days = Math.floor(diff / 86400000);
		if (minutes < 1) return 'just now';
		if (minutes < 60) return `${minutes}m ago`;
		if (hours < 24) return `${hours}h ago`;
		if (days < 30) return `${days}d ago`;
		return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	function activityIcon(type: string): string {
		switch (type) {
			case 'sighting': return '📸';
			case 'card': return '🃏';
			case 'identification': return '🎯';
			case 'card_generation': return '🃏';
			case 'binder_add': return '📋';
			default: return '•';
		}
	}

	function activityDescription(activity: any): string {
		const t = activity.type || activity.activity_type;
		switch (t) {
			case 'sighting':
				return activity.description || 'Spotted a bird';
			case 'card':
				return activity.description || 'Unlocked a card';
			case 'identification':
				return `Identified ${activity.species_common || activity.species_code || 'a bird'}`;
			case 'card_generation':
				return `Generated card for ${activity.species_common || 'a species'}`;
			case 'binder_add':
				return `Added card to binder`;
			default:
				return activity.description || t?.replace('_', ' ') || 'Activity';
		}
	}

	function avatarUrl(): string | null {
		if (!profile?.avatar_path) return null;
		return `/storage/${profile.avatar_path}`;
	}

	function displayName(): string {
		return profile?.display_name || email.split('@')[0];
	}
</script>

<div class="space-y-6">
	<a href="/trades" class="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors">
		<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
		</svg>
		Back to trades
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
				onclick={loadProfile}
				class="mt-3 text-sm text-green-400 hover:text-green-300 underline underline-offset-2"
			>
				Try again
			</button>
		</div>
	{:else if profile}
		<div class="space-y-6">
			<div class="bg-gray-900 rounded-xl p-6 relative">
				<a
					href="/trades?to={encodeURIComponent(email)}"
					class="absolute top-6 right-6 bg-green-600 hover:bg-green-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
				>
					Propose Trade
				</a>

				<div class="flex items-center gap-5">
					{#if avatarUrl()}
						<img src={avatarUrl()} alt="Avatar" class="w-20 h-20 rounded-full object-cover border-2 border-gray-700" />
					{:else}
						<div class="w-20 h-20 rounded-full bg-gray-800 border-2 border-gray-700 flex items-center justify-center text-3xl">
							👤
						</div>
					{/if}
					<div>
						<h1 class="text-2xl font-bold">{displayName()}</h1>
						<p class="text-sm text-gray-400">{email}</p>
						{#if profile.region}
							<span class="inline-block mt-1.5 px-2.5 py-0.5 bg-gray-800 text-gray-300 text-xs font-medium rounded-full border border-gray-700">
								{profile.region}
							</span>
						{/if}
						{#if profile.created_at}
							<p class="text-xs text-gray-500 mt-1.5">Joined {formatDate(profile.created_at)}</p>
						{/if}
					</div>
				</div>
			</div>

			<div class="grid gap-4 sm:grid-cols-3">
				<div class="bg-gray-900 rounded-xl border border-gray-800 p-4">
					<p class="text-3xl font-bold text-white">{profile.stats?.total_cards ?? 0}</p>
					<p class="text-sm text-gray-500 mt-1">Cards Collected</p>
				</div>
				<div class="bg-gray-900 rounded-xl border border-gray-800 p-4">
					<p class="text-3xl font-bold text-white">{profile.stats?.unique_species ?? 0}</p>
					<p class="text-sm text-gray-500 mt-1">Unique Species</p>
				</div>
				<div class="bg-gray-900 rounded-xl border border-gray-800 p-4">
					<p class="text-3xl font-bold text-white">{profile.stats?.collection_percent ?? 0}%</p>
					<p class="text-sm text-gray-500 mt-1">Collection</p>
				</div>
			</div>

			<div class="space-y-3">
				<h2 class="text-lg font-semibold">Recent Activity</h2>
				{#if profile.recent_activity && profile.recent_activity.length > 0}
					<div class="space-y-2">
						{#each profile.recent_activity as activity}
							<div class="flex items-center gap-3 p-3 bg-gray-900 rounded-xl border border-gray-800">
								<span class="text-xl">{activityIcon(activity.type || activity.activity_type)}</span>
								<div class="flex-1 min-w-0">
									<p class="text-sm text-gray-200">{activityDescription(activity)}</p>
								</div>
								<span class="text-xs text-gray-500 shrink-0">{formatRelativeTime(activity.created_at)}</span>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-center py-8 text-gray-500">
						<p>No recent activity</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>