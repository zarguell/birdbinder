<script lang="ts">
	import { profile } from '$lib/api';
	import { onMount } from 'svelte';

	let email = $state('');
	let displayName = $state('');
	let avatarPath = $state<string | null>(null);
	let createdAt = $state<string | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);
	let uploadingAvatar = $state(false);

	onMount(async () => {
		try {
			const data = await profile.get();
			email = data.email;
			displayName = data.display_name || '';
			avatarPath = data.avatar_path;
			createdAt = data.created_at;
		} catch (e: any) {
			message = { type: 'error', text: 'Failed to load profile' };
		} finally {
			loading = false;
		}
	});

	async function saveDisplayName() {
		saving = true;
		message = null;
		try {
			const data = await profile.update({ display_name: displayName || undefined });
			displayName = data.display_name || '';
			message = { type: 'success', text: 'Profile updated!' };
			// Update nav bar by refreshing auth/me
			await fetch('/api/auth/me', { credentials: 'include' }).catch(() => {});
		} catch (e: any) {
			message = { type: 'error', text: e.message || 'Failed to save' };
		} finally {
			saving = false;
		}
	}

	async function handleAvatarUpload(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		if (file.size > 2 * 1024 * 1024) {
			message = { type: 'error', text: 'Image must be under 2MB' };
			return;
		}

		uploadingAvatar = true;
		message = null;
		try {
			const data = await profile.uploadAvatar(file);
			avatarPath = data.avatar_path;
			message = { type: 'success', text: 'Avatar updated!' };
			// Refresh nav bar
			await fetch('/api/auth/me', { credentials: 'include' }).catch(() => {});
		} catch (e: any) {
			message = { type: 'error', text: e.message || 'Failed to upload avatar' };
		} finally {
			uploadingAvatar = false;
			input.value = '';
		}
	}

	function formatDate(iso: string | null) {
		if (!iso) return '';
		return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
	}

	function avatarUrl() {
		if (!avatarPath) return null;
		return `/storage/${avatarPath}`;
	}
</script>

<div class="max-w-lg mx-auto">
	<h1 class="text-2xl font-bold mb-6">Profile</h1>

	{#if loading}
		<p class="text-gray-400">Loading...</p>
	{:else}
		<!-- Avatar section -->
		<div class="bg-gray-900 rounded-lg p-6 mb-4">
			<div class="flex items-center gap-5">
				<div class="relative group">
					{#if avatarUrl()}
						<img src={avatarUrl()} alt="Avatar" class="w-20 h-20 rounded-full object-cover border-2 border-gray-700" />
					{:else}
						<div class="w-20 h-20 rounded-full bg-gray-800 border-2 border-gray-700 flex items-center justify-center text-3xl">
							👤
						</div>
					{/if}
					<label for="avatar-input" class="absolute inset-0 rounded-full bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
						{#if uploadingAvatar}
							<span class="text-xs text-white animate-pulse">...</span>
						{:else}
							<span class="text-xs text-white">📷</span>
						{/if}
					</label>
					<input id="avatar-input" type="file" accept="image/jpeg,image/png,image/webp" onchange={handleAvatarUpload} class="hidden" disabled={uploadingAvatar} />
				</div>
				<div>
					<p class="text-lg font-semibold">{displayName || email.split('@')[0]}</p>
					<p class="text-sm text-gray-400">{email}</p>
					{#if createdAt}
						<p class="text-xs text-gray-500 mt-1">Joined {formatDate(createdAt)}</p>
					{/if}
				</div>
			</div>
		</div>

		<!-- Display name -->
		<div class="bg-gray-900 rounded-lg p-6 mb-4">
			<label for="display-name" class="block text-sm font-medium text-gray-300 mb-2">Display Name</label>
			<input
				id="display-name"
				type="text"
				bind:value={displayName}
				placeholder={email.split('@')[0]}
				maxlength="100"
				class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
			/>
			<p class="text-xs text-gray-500 mt-1.5">Leave blank to use your email username. Used in trades and public features.</p>
			<button
				onclick={saveDisplayName}
				disabled={saving}
				class="mt-3 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>
				{saving ? 'Saving...' : 'Save'}
			</button>
		</div>

		<!-- Message -->
		{#if message}
			<div class="rounded-lg p-3 text-sm {message.type === 'success' ? 'bg-green-900/30 text-green-400 border border-green-800' : 'bg-red-900/30 text-red-400 border border-red-800'}">
				{message.text}
			</div>
		{/if}
	{/if}
</div>
