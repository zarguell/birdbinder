<script lang="ts">
    import { aiSettings, auth, collection, profile } from '$lib/api';

    let settings = $state<Record<string, any>>({});
    let originals = $state<Record<string, string>>({});
    let loading = $state(true);
    let saving = $state(false);
    let message = $state<{ type: 'success' | 'error'; text: string } | null>(null);
    let authInfo = $state<{ ai_base_url: string; ai_enabled: boolean } | null>(null);

    // Region picker state
    let regions = $state<any[]>([]);
    let currentRegion = $state<string | null>(null);
    let regionLoading = $state(false);
    let regionMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

    async function loadSettings() {
        loading = true;
        try {
            const data = await aiSettings.get();
            settings = data;
            originals = {};
            for (const [key, meta] of Object.entries(data)) {
                originals[key] = (meta as any).value;
            }
        } catch (e: any) {
            message = { type: 'error', text: 'Failed to load settings' };
        } finally {
            loading = false;
        }
    }

    async function loadAuthSettings() {
        try {
            const info = await auth.settings();
            authInfo = info as any;
        } catch {
            // non-critical
        }
    }

    async function loadRegion() {
        try {
            const [regionList, prof] = await Promise.all([
                collection.regions(),
                profile.get()
            ]);
            regions = regionList;
            currentRegion = prof.region;
        } catch {
            // non-critical
        }
    }

    async function onRegionChange(e: Event) {
        const target = e.target as HTMLSelectElement;
        const value = target.value || null;
        regionLoading = true;
        regionMessage = null;
        try {
            await profile.update({ region: value });
            currentRegion = value;
            regionMessage = { type: 'success', text: 'Region updated!' };
        } catch (err: any) {
            regionMessage = { type: 'error', text: err.message || 'Failed to update region' };
        } finally {
            regionLoading = false;
        }
    }

    function isModified(key: string): boolean {
        return settings[key]?.value !== originals[key];
    }

    function hasChanges(): boolean {
        return Object.keys(settings).some(isModified);
    }

    async function save() {
        saving = true;
        message = null;
        try {
            const updates: Record<string, string> = {};
            for (const key of Object.keys(settings)) {
                if (isModified(key) && settings[key].value !== null) {
                    updates[key] = settings[key].value;
                }
            }
            if (Object.keys(updates).length === 0) {
                message = { type: 'error', text: 'No changes to save' };
                return;
            }
            await aiSettings.update(updates);
            // Reload to get fresh source badges
            for (const [key, value] of Object.entries(updates)) {
                originals[key] = value;
            }
            message = { type: 'success', text: 'Settings saved!' };
        } catch (e: any) {
            message = { type: 'error', text: e.message || 'Failed to save settings' };
        } finally {
            saving = false;
        }
    }

    $effect(() => {
        loadSettings();
        loadAuthSettings();
        loadRegion();
    });
</script>

<svelte:head>
    <title>AI Settings — BirdBinder</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-4 py-6">
    <h1 class="mb-6 text-2xl font-bold text-gray-100">AI Settings</h1>

    {#if loading}
        <div class="space-y-4">
            {#each Array(4) as _}
                <div class="animate-pulse rounded-xl bg-gray-800 p-4">
                    <div class="h-4 w-1/4 rounded bg-gray-700"></div>
                    <div class="mt-2 h-8 w-full rounded bg-gray-700"></div>
                </div>
            {/each}
        </div>
    {:else}
        <!-- Message toast -->
        {#if message}
            <div class="mb-4 rounded-lg border px-4 py-2 text-sm {message.type === 'success' ? 'border-green-800/50 bg-green-900/30 text-green-400' : 'border-red-800/50 bg-red-900/30 text-red-400'}">
                {message.text}
                <button
                    type="button"
                    onclick={() => (message = null)}
                    class="ml-2 opacity-60 hover:opacity-100"
                >✕</button>
            </div>
        {/if}

        <div class="space-y-4">
            {#each Object.entries(settings) as [key, meta]}
                <div class="rounded-xl border border-gray-800 bg-gray-900 p-4">
                    <div class="mb-1 flex items-center justify-between">
                        <label for="setting-{key}" class="text-sm font-semibold text-gray-200"
                            >{meta.label}</label
                        >
                        <span
                            class="rounded-full px-2 py-0.5 text-xs {meta.source === 'database'
                                ? 'bg-green-900/30 text-green-400'
                                : 'bg-gray-800 text-gray-500'}"
                        >
                            {meta.source}
                        </span>
                    </div>
                    <p class="mb-2 text-xs text-gray-500">{meta.description}</p>
                    {#if meta.type === 'text'}
                        <textarea
                            id="setting-{key}"
                            bind:value={meta.value}
                            rows="4"
                            class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm text-gray-200 placeholder-gray-600 focus:border-green-500 focus:outline-none"
                        ></textarea>
                        <p class="mt-1 text-right text-xs text-gray-600">{meta.value?.length || 0} chars</p>
                    {:else}
                        <input
                            type="text"
                            id="setting-{key}"
                            bind:value={meta.value}
                            class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-green-500 focus:outline-none"
                        />
                    {/if}
                </div>
            {/each}
        </div>

        <!-- Save -->
        <div class="mt-6 flex justify-end">
            <button
                type="button"
                onclick={save}
                disabled={saving || !hasChanges()}
                class="rounded-lg bg-green-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
                {#if saving}Saving...{:else}Save Changes{/if}
            </button>
        </div>

        <!-- Read-only info -->
        <div class="mt-8 border-t border-gray-800 pt-6">
            <h2 class="mb-1 text-sm font-semibold uppercase tracking-wider text-gray-400">
                Protected Settings
            </h2>
            <p class="text-xs text-gray-600">
                These cannot be changed from the UI (set via environment variables).
            </p>
            <div class="mt-3 space-y-2 text-sm">
                <div class="flex justify-between text-gray-500">
                    <span>API Base URL</span>
                    <span class="text-gray-400">
                        {#if authInfo?.ai_base_url && authInfo.ai_base_url !== '(default: OpenAI)'}
                            Configured
                        {:else}
                            Default (OpenAI)
                        {/if}
                    </span>
                </div>
                <div class="flex justify-between text-gray-500">
                    <span>API Key</span>
                    <span class="font-mono text-gray-400">••••••••</span>
                </div>
                <div class="flex justify-between text-gray-500">
                    <span>AI Enabled</span>
                    <span class={authInfo?.ai_enabled ? 'text-green-400' : 'text-red-400'}>
                        {authInfo?.ai_enabled ? 'Yes' : 'No'}
                    </span>
                </div>
            </div>
        </div>

        <!-- Region picker -->
        <div class="mt-8 border-t border-gray-800 pt-6">
            <h2 class="mb-1 text-lg font-bold text-gray-100">Region</h2>
            <p class="mb-4 text-xs text-gray-500">Select your birding region to customize species data and collection progress.</p>

            {#if regionMessage}
                <div class="mb-4 rounded-lg border px-4 py-2 text-sm {regionMessage.type === 'success' ? 'border-green-800/50 bg-green-900/30 text-green-400' : 'border-red-800/50 bg-red-900/30 text-red-400'}">
                    {regionMessage.text}
                    <button
                        type="button"
                        onclick={() => (regionMessage = null)}
                        class="ml-2 opacity-60 hover:opacity-100"
                    >✕</button>
                </div>
            {/if}

            <div class="rounded-xl border border-gray-800 bg-gray-900 p-4">
                <div class="mb-1 flex items-center justify-between">
                    <label for="region-select" class="text-sm font-semibold text-gray-200">Birding Region</label>
                    {#if currentRegion}
                        <span class="rounded-full bg-green-900/30 px-2 py-0.5 text-xs text-green-400">
                            ✓ Active
                        </span>
                    {/if}
                </div>
                <select
                    id="region-select"
                    onchange={onRegionChange}
                    disabled={regionLoading}
                    class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-green-500 focus:outline-none disabled:opacity-50"
                >
                    <option value="" selected={!currentRegion}>
                        Select your region...
                    </option>
                    {#each regions as r}
                        <option value={r.code} selected={currentRegion === r.code}>
                            {r.name}
                        </option>
                    {/each}
                </select>
                {#if regionLoading}
                    <p class="mt-2 text-xs text-gray-500">Saving...</p>
                {/if}
            </div>
        </div>
    {/if}
</div>
