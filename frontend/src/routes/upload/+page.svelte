<script lang="ts">
	import { goto } from '$app/navigation';
	import { sightings, ApiError } from '$lib/api';

	let file: File | null = $state(null);
	let previewUrl: string = $state('');
	let loading = $state(false);
	let error = $state('');
	let sightingId: string | null = $state(null);

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		const selected = target.files?.[0];
		if (selected) {
			setFile(selected);
		}
		target.value = '';
	}

	function setFile(f: File) {
		file = f;
		error = '';
		sightingId = null;
		if (previewUrl) URL.revokeObjectURL(previewUrl);
		previewUrl = URL.createObjectURL(f);
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function readExifFromFile(file: File): Promise<{ datetime: string | null; lat: number | null; lon: number | null }> {
		return new Promise((resolve) => {
			const reader = new FileReader();
			reader.onload = function (e) {
				const buffer = e.target?.result as ArrayBuffer;
				if (!buffer) {
					resolve({ datetime: null, lat: null, lon: null });
					return;
				}
				const view = new DataView(buffer);
				let datetime: string | null = null;
				let lat: number | null = null;
				let lon: number | null = null;

				if (view.byteLength < 2 || view.getUint16(0) !== 0xffd8) {
					resolve({ datetime, lat, lon });
					return;
				}

				let offset = 2;
				while (offset < view.byteLength - 1) {
					const marker = view.getUint16(offset);
					if (marker === 0xffd9 || marker === 0xffd7) {
						break;
					}
					if ((marker & 0xff00) !== 0xff00) {
						break;
					}
					const length = view.getUint16(offset + 2);
					const segment = view.getUint16(offset + 4);

					if (segment === 0xe1) {
						const exifOffset = offset + 4;
						if (view.byteLength < exifOffset + 6) break;
						const exifHeader = new TextDecoder().decode(
							new Uint8Array(buffer, exifOffset, 4)
						);
						if (exifHeader === "Exif") {
							const tiffOffset = exifOffset + 6;
							const byteOrder = view.getUint16(tiffOffset);
							const littleEndian = byteOrder === 0x4949;
							const ifdOffset = view.getUint32(tiffOffset + 4, littleEndian);
							const ifdStart = tiffOffset + ifdOffset;

							let numEntries = view.getUint16(ifdStart, littleEndian);
							for (let i = 0; i < numEntries; i++) {
								const entryOffset = ifdStart + 2 + i * 12;
								const tag = view.getUint16(entryOffset, littleEndian);
								const type = view.getUint16(entryOffset + 2, littleEndian);
								const numValues = view.getUint32(entryOffset + 4, littleEndian);

								if (tag === 0x9003 || tag === 0x0132) {
									const valueOffset = tiffOffset + view.getUint32(entryOffset + 8, littleEndian);
									const strLen = type === 2 ? numValues : 2;
									if (valueOffset + strLen <= view.byteLength) {
										const timeStr = new TextDecoder().decode(
											new Uint8Array(buffer, valueOffset, Math.min(19, strLen))
										);
										const match = timeStr.match(/(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
										if (match) {
											datetime = `${match[1]}:${match[2]}:${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
										}
									}
								}

				if (tag === 0x0002 || tag === 0x0004) {
						const valueOffset = tiffOffset + view.getUint32(entryOffset + 8, littleEndian);
						if (valueOffset + 24 <= view.byteLength) {
							const toDecimal = (off: number): number => {
								const deg = view.getUint32(off, littleEndian);
								const min = view.getUint32(off + 4, littleEndian);
								const sec = view.getUint32(off + 8, littleEndian) / view.getUint32(off + 12, littleEndian);
								return deg + min / 60 + sec / 3600;
							};
							const gpsLat = toDecimal(valueOffset);
							const gpsLon = toDecimal(valueOffset + 12);
							const latRef = String.fromCharCode(view.getUint8(valueOffset + 20));
							const lonRef = String.fromCharCode(view.getUint8(valueOffset + 22));
							lat = latRef === 'S' ? -gpsLat : gpsLat;
							lon = lonRef === 'W' ? -gpsLon : gpsLon;
						}
					}
							}
						}
						break;
					}
					offset += 2 + 2 + length;
				}

				resolve({ datetime, lat, lon });
			};
			reader.readAsArrayBuffer(file);
		});
	}

	async function handleUpload() {
		if (!file || loading) return;

		loading = true;
		error = '';

		try {
			// Try to extract EXIF before upload (belt-and-suspenders with backend extraction)
			const exif = await readExifFromFile(file);
			const result = await sightings.upload(file, exif);
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
						}}
						class="text-xs text-red-400 hover:text-red-300 font-medium px-3 py-1.5 rounded-lg hover:bg-red-400/10 transition-colors shrink-0"
					>
						Remove
					</button>
				</div>
			</div>

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
