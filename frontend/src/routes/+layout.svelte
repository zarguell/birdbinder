<script>
	import '../app.css';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-950 text-gray-100">
	<nav class="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
		<div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
			<a href="/" class="text-lg font-bold text-green-400">🐦 BirdBinder</a>
			<div class="flex gap-4 text-sm">
				<a href="/upload" class="text-gray-400 hover:text-white transition-colors">Upload</a>
				<a href="/sightings" class="text-gray-400 hover:text-white transition-colors">Sightings</a>
				<a href="/binder" class="text-gray-400 hover:text-white transition-colors">Binder</a>
				<a href="/sets" class="text-gray-400 hover:text-white transition-colors">Sets</a>
				<a href="/trades" class="text-gray-400 hover:text-white transition-colors">Trades</a>
			</div>
		</div>
	</nav>
	<main class="max-w-5xl mx-auto px-4 py-6">
		{@render children()}
	</main>
</div>
