<script lang="ts">
	import { goto } from '$app/navigation';
	import { sightings, ApiError } from '$lib/api';
	import exifr from 'exifr';

	let file: File | null = $state(null);
	let previewUrl: string = $state('');
	let loading = $state(false);
	let error = $state('');
	let sightingId: string | null = $state(null);

	// EXIF + location state
	let exifLat: number | null = $state(null);
	let exifLon: number | null = $state(null);
	let locationDisplayName: string = $state('');
	let showLocationPrompt: boolean = $state(false);
	let currentExif: { datetime: string | null; lat: number | null; lon: number | null } = {
		datetime: null,
		lat: null,
		lon: null
	};

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		const selected = target.files?.[0];
		if (selected) {
			setFile(selected);
		}
		target.value = '';
	}

	async function setFile(f: File) {
		file = f;
		error = '';
		sightingId = null;
		locationDisplayName = '';
		showLocationPrompt = false;
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		previewUrl = URL.createObjectURL(f);

		// Extract EXIF to check for GPS (parsed once, reused on upload)
		currentExif = await readExifFromFile(f);
		exifLat = currentExif.lat;
		exifLon = currentExif.lon;
		showLocationPrompt = exifLat === null && exifLon === null;
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function pad(n: number): string {
		return String(n).padStart(2, '0');
	}

	async function readExifFromFile(
		f: File
	): Promise<{ datetime: string | null; lat: number | null; lon: number | null }> {
		try {
			// exifr reads the GPS IFD and Exif IFD correctly (the old hand-rolled
			// parser only scanned IFD0, so geotagged photos usually came back empty)
			const parsed = await exifr.parse(f, { tiff: true, exif: true, gps: true });
			if (!parsed) return { datetime: null, lat: null, lon: null };

			const lat = typeof parsed.latitude === 'number' ? parsed.latitude : null;
			const lon = typeof parsed.longitude === 'number' ? parsed.longitude : null;

			let datetime: string | null = null;
			const dt: unknown =
				parsed.DateTimeOriginal ?? parsed.CreateDate ?? parsed.DateTime ?? parsed.DateTimeDigitized;
			if (dt instanceof Date && !isNaN(dt.getTime())) {
				// Backend expects "YYYY:MM:DD HH:MM:SS" — keep camera-local time
				datetime = `${dt.getFullYear()}:${pad(dt.getMonth() + 1)}:${pad(dt.getDate())} ${pad(
					dt.getHours()
				)}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
			}

			return { datetime, lat, lon };
		} catch {
			return { datetime: null, lat: null, lon: null };
		}
	}

	async function handleUpload() {
		if (!file || loading) return;

		loading = true;
		error = '';

		try {
			// Reuse the EXIF parsed in setFile — the file hasn't changed
			const result = await sightings.upload(file, currentExif, locationDisplayName || undefined);
			sightingId = result.id ?? result.sighting_id ?? null;
			if (sightingId) {
				goto(`/sightings/${sightingId}`);
			}
		} catch (err) {
			if (err instanceof ApiError) {
				error = `Upload failed (${err.status}): ${err.message}`;
			} else if (err instanceof Error) {
				error = err.message;
			} else {
				error = 'Upload failed. Please try again.';
			}
		} finally {
			loading = false;
		}
	}

	function handleRetry() {
		error = '';
	}
</script>

<svelte:head>
	<title>Upload Sighting · BirdBinder</title>
</svelte:head>

<div class="max-w-md mx-auto space-y-6">
	<h1 class="text-2xl font-bold">Upload Sighting</h1>
	<p class="text-gray-400 text-sm">Snap a photo or choose an image to identify a bird.</p>

	<!-- Camera + File Picker Buttons -->
	{#if !sightingId}
		<div class="grid grid-cols-2 gap-3">
			<label
				class="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-700 bg-gray-900/50 p-5 cursor-pointer transition-colors hover:border-green-500/60 hover:bg-gray-900 active:scale-[0.98]"
			>
				<svg class="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
					<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
				</svg>
				<span class="text-sm font-medium text-gray-300">Take Photo</span>
				<input
					type="file"
					accept="image/*"
					capture="environment"
					class="hidden"
					onchange={handleFileSelect}
					disabled={loading}
				/>
			</label>

			<label
				class="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-700 bg-gray-900/50 p-5 cursor-pointer transition-colors hover:border-green-500/60 hover:bg-gray-900 active:scale-[0.98]"
			>
				<svg class="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
				</svg>
				<span class="text-sm font-medium text-gray-300">Choose File</span>
				<input
					type="file"
					accept="image/*"
					class="hidden"
					onchange={handleFileSelect}
					disabled={loading}
				/>
			</label>
		</div>

		<!-- Image Preview -->
		{#if previewUrl}
			<div class="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
				<img
					src={previewUrl}
					alt="Preview"
					class="w-full max-h-80 object-contain bg-black/30"
				/>
				<div class="px-4 py-3 flex items-center justify-between border-t border-gray-800">
					<div class="min-w-0">
						<p class="text-sm font-medium truncate">{file?.name}</p>
						<p class="text-xs text-gray-500">{file ? formatSize(file.size) : ''}</p>
					</div>
					<button
						onclick={() => {
							file = null;
							previewUrl = '';
							showLocationPrompt = false;
							locationDisplayName = '';
						}}
						class="text-xs text-red-400 hover:text-red-300 font-medium px-3 py-1.5 rounded-lg hover:bg-red-400/10 transition-colors shrink-0"
					>
						Remove
					</button>
				</div>
			</div>

			<!-- Location Prompt (shown when no EXIF GPS) -->
			{#if showLocationPrompt}
				<div class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
					<div class="flex items-start gap-2">
						<svg class="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
							<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
						</svg>
						<div class="min-w-0">
							<p class="text-sm font-medium text-amber-300">No location found in photo</p>
							<p class="text-xs text-gray-400 mt-0.5">Adding a location helps the AI identify the bird more accurately (e.g. "Central Park, New York").</p>
						</div>
					</div>
					<input
						type="text"
						bind:value={locationDisplayName}
						placeholder="e.g. Prospect Park, Brooklyn, NY"
						class="w-full rounded-lg border border-gray-700 bg-gray-800/80 px-3 py-2.5 text-sm placeholder-gray-500 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/30"
					/>
					<div class="flex gap-2">
						<button
							onclick={() => { showLocationPrompt = false; }}
							class="flex-1 text-xs text-gray-400 hover:text-gray-300 font-medium py-2 rounded-lg hover:bg-gray-800 transition-colors"
						>
							Skip
						</button>
					</div>
				</div>
			{:else if exifLat !== null && exifLon !== null}
				<div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
					<svg class="w-4 h-4 text-green-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
						<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
						<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
					</svg>
					<span class="text-xs text-green-400">GPS location found in photo</span>
				</div>
			{/if}

			<!-- Upload Button -->
			<button
				onclick={handleUpload}
				disabled={!file || loading}
				class="w-full flex items-center justify-center gap-2 py-3.5 px-4 rounded-xl font-semibold text-sm transition-all
					{!file || loading
						? 'bg-gray-800 text-gray-500 cursor-not-allowed'
						: 'bg-green-600 hover:bg-green-500 active:scale-[0.98] text-white shadow-lg shadow-green-600/20'}"
			>
				{#if loading}
					<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
					</svg>
					<span>Uploading…</span>
				{:else}
					<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
					</svg>
					<span>Upload Photo</span>
				{/if}
			</button>
		{/if}

		<!-- Error Message -->
		{#if error}
			<div class="rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-2">
				<p class="text-sm text-red-300">{error}</p>
				<button
					onclick={handleRetry}
					class="text-xs text-red-400 hover:text-red-300 font-medium underline underline-offset-2"
				>
					Try again
				</button>
			</div>
		{/if}
	{/if}

	<!-- Success (shown briefly before redirect) -->
	{#if sightingId && !loading}
		<div class="rounded-xl border border-green-500/30 bg-green-500/10 p-5 text-center space-y-3">
			<svg class="w-12 h-12 text-green-400 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
				<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<p class="font-semibold text-green-300">Sighting uploaded!</p>
			<a
				href="/sightings/{sightingId}"
				class="inline-flex items-center gap-1.5 text-sm text-green-400 hover:text-green-300 underline underline-offset-2"
			>
				View sighting
				<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
				</svg>
			</a>
		</div>
	{/if}
</div>
