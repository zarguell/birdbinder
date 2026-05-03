<script lang="ts">
	import '../app.css';
	import { auth, profile } from '$lib/api';
	import { onMount } from 'svelte';

	let { children } = $props();
	let userInfo: { user_identifier: string; display_name: string | null; avatar_path: string | null; auth_source: string } | null = $state(null);
	let showSettings = $state(false);
	let appSettings: Record<string, unknown> | null = $state(null);
	let settingsError = $state('');

	onMount(async () => {
		try {
			userInfo = await auth.me();
		} catch {
			userInfo = null;
		}
	});

	async function loadSettings() {
		showSettings = !showSettings;
		if (showSettings && !appSettings) {
			try {
				appSettings = await auth.settings();
				settingsError = '';
			} catch (e: any) {
				settingsError = e.message || 'Failed to load settings';
			}
		}
	}

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
				<button onclick={loadSettings} class="text-gray-400 hover:text-white transition-colors" title="Settings">⚙️</button>
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

	{#if showSettings}
		<div class="max-w-5xl mx-auto px-4 pt-4">
			<div class="bg-gray-900 border border-gray-700 rounded-lg p-5 mb-2">
				<h2 class="text-sm font-semibold text-gray-300 mb-3 flex items-center justify-between">
					⚙️ App Configuration
					<button onclick={() => showSettings = false} class="text-gray-500 hover:text-white text-lg leading-none">&times;</button>
				</h2>
				{#if settingsError}
					<p class="text-red-400 text-sm">{settingsError}</p>
				{:else if appSettings}
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
						{#each Object.entries(appSettings) as [key, value]}
							<div class="flex justify-between gap-4">
								<span class="text-gray-500 font-mono text-xs">{key}</span>
								<span class="text-gray-200 text-right">{String(value)}</span>
							</div>
						{/each}
					</div>
					{#if userInfo}
						<div class="mt-3 pt-3 border-t border-gray-700">
							<div class="flex justify-between gap-4 text-sm">
								<span class="text-gray-500 font-mono text-xs">user_identifier</span>
								<span class="text-green-400 font-mono text-right">{userInfo.user_identifier}</span>
							</div>
							<div class="flex justify-between gap-4 text-sm mt-1">
								<span class="text-gray-500 font-mono text-xs">display_name</span>
								<span class="text-gray-200 text-right">{userInfo.display_name || '(not set)'}</span>
							</div>
							<div class="flex justify-between gap-4 text-sm mt-1">
								<span class="text-gray-500 font-mono text-xs">auth_source</span>
								<span class="text-gray-200 text-right">{userInfo.auth_source}</span>
							</div>
						</div>
					{/if}
				{:else}
					<p class="text-gray-500 text-sm">Loading...</p>
				{/if}
			</div>
		</div>
	{/if}

	<main class="max-w-5xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
