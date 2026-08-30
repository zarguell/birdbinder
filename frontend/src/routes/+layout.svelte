<script lang="ts">
	import '../app.css';
	import { auth } from '$lib/api';
	import { onMount } from 'svelte';

	let { children } = $props();
	let userInfo: { user_identifier: string; display_name: string | null; avatar_path: string | null; auth_source: string } | null = $state(null);

	onMount(async () => {
		try {
			userInfo = await auth.me();
		} catch {
			userInfo = null;
		}
	});

	function displayName(id: string, customName: string | null) {
		if (customName) return customName;
		if (id === 'local-user') return 'Local User';
		if (id.startsWith('api-key:')) return 'API User';
		return id.split('@')[0];
	}

	function avatarUrl(path: string | null) {
		if (!path) return null;
		return `/storage/${path}`;
	}
</script>

<div class="min-h-screen bg-gray-950 text-gray-100">
	<nav class="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
		<div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
			<a href="/" class="text-lg font-bold text-green-400">🐦 BirdBinder</a>
			<div class="flex items-center gap-4 text-sm">
				<a href="/upload" class="text-gray-400 hover:text-white transition-colors">Upload</a>
				<a href="/sightings" class="text-gray-400 hover:text-white transition-colors">Sightings</a>
				<a href="/feed" class="text-gray-400 hover:text-white transition-colors">Feed</a>
				<a href="/binder" class="text-gray-400 hover:text-white transition-colors">Binder</a>
				<a href="/sets" class="text-gray-400 hover:text-white transition-colors">Sets</a>
				<a href="/collection" class="text-gray-400 hover:text-white transition-colors">Collection</a>
				<a href="/trades" class="text-gray-400 hover:text-white transition-colors">Trades</a>
				<a href="/settings" class="text-gray-400 hover:text-white transition-colors" title="Settings">⚙️</a>
				{#if userInfo}
					<a href="/profile" class="flex items-center gap-2 text-gray-300 hover:text-white transition-colors border-l border-gray-700 pl-3">
						{#if avatarUrl(userInfo.avatar_path)}
							<img src={avatarUrl(userInfo.avatar_path)} alt="" class="w-6 h-6 rounded-full object-cover" />
						{:else}
							<span class="text-base">👤</span>
						{/if}
						<span class="text-xs">{displayName(userInfo.user_identifier, userInfo.display_name)}</span>
					</a>
				{:else}
					<span class="text-xs text-red-400 border-l border-gray-700 pl-3">⚠ no auth</span>
				{/if}
			</div>
		</div>
	</nav>

	<main class="max-w-5xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
