<script lang="ts">
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>{page.status} · BirdBinder</title>
</svelte:head>

<div class="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
	<p class="text-6xl font-bold text-gray-800">{page.status}</p>
	<h1 class="text-xl font-semibold text-gray-200">
		{page.status === 404 ? 'Page not found' : 'Something went wrong'}
	</h1>
	<p class="max-w-md text-sm text-gray-500">
		{page.error?.message ?? 'An unexpected error occurred.'}
	</p>
	<div class="mt-2 flex gap-3">
		<a
			href="/"
			class="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500"
		>
			Go home
		</a>
		<a
			href="/binder"
			class="rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800"
		>
			My binder
		</a>
	</div>
</div>
