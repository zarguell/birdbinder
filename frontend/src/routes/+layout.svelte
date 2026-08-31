<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { userStore, loadUser } from '$lib/stores/user.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();
	let mobileMenuOpen = $state(false);
	const userInfo = $derived(userStore.user);

	const navLinks = [
		{ href: '/upload', label: 'Upload' },
		{ href: '/sightings', label: 'Sightings' },
		{ href: '/feed', label: 'Feed' },
		{ href: '/binder', label: 'Binder' },
		{ href: '/sets', label: 'Sets' },
		{ href: '/collection', label: 'Collection' },
		{ href: '/trades', label: 'Trades' },
		{ href: '/settings', label: 'Settings' }
	];

	// Close the mobile menu whenever navigation happens
	$effect(() => {
		page.url.pathname;
		mobileMenuOpen = false;
	});

	onMount(() => {
		loadUser();
	});

	function isActive(href: string) {
		const path = page.url.pathname;
		return href === '/' ? path === '/' : path === href || path.startsWith(href + '/');
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

			<!-- Desktop nav -->
			<div class="hidden md:flex items-center gap-4 text-sm">
				{#each navLinks as link (link.href)}
					<a
						href={link.href}
						aria-current={isActive(link.href) ? 'page' : undefined}
						class="transition-colors {isActive(link.href)
							? 'text-green-400 font-medium'
							: 'text-gray-400 hover:text-white'}"
					>{link.label}</a
					>
				{/each}
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
					<span class="text-xs text-gray-500 border-l border-gray-700 pl-3">Not signed in</span>
				{/if}
			</div>

			<!-- Mobile: profile + hamburger -->
			<div class="md:hidden flex items-center gap-2">
				{#if userInfo}
					<a href="/profile" aria-label="Profile" class="text-gray-300">
						{#if avatarUrl(userInfo.avatar_path)}
							<img src={avatarUrl(userInfo.avatar_path)} alt="" class="w-7 h-7 rounded-full object-cover" />
						{:else}
							<span class="text-lg">👤</span>
						{/if}
					</a>
				{/if}
				<button
					type="button"
					class="p-2 text-gray-300 rounded-md focus-visible:outline focus-visible:outline-green-500"
					aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
					aria-expanded={mobileMenuOpen}
					onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
				>
					{#if mobileMenuOpen}
						<svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					{:else}
						<svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
						</svg>
					{/if}
				</button>
			</div>
		</div>

		<!-- Mobile menu panel -->
		{#if mobileMenuOpen}
			<div class="md:hidden border-t border-gray-800 bg-gray-950 px-4 pb-4 pt-2">
				<div class="flex flex-col">
					{#each navLinks as link (link.href)}
						<a
							href={link.href}
							aria-current={isActive(link.href) ? 'page' : undefined}
							class="rounded-md px-3 py-2.5 text-sm transition-colors {isActive(link.href)
								? 'bg-gray-900 text-green-400 font-medium'
								: 'text-gray-300 hover:bg-gray-900 hover:text-white'}"
						>{link.label}</a
						>
					{/each}
				</div>
			</div>
		{/if}
	</nav>

	<main class="max-w-5xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
