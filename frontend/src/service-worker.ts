/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

// BirdBinder service worker: makes the installed PWA load offline.
// - App shell (build assets + static files) is precached and served
//   cache-first.
// - /api and /storage are never cached (live data + user media).
// - Navigations fall back to the cached shell when offline.

import { build, files, version } from '$service-worker';

const CACHE_NAME = `birdbinder-${version}`;

// Everything the SPA needs to boot: hashed build output + static files
const PRECACHE = [...build, ...files];

const sw = self as unknown as ServiceWorkerGlobalScope;

sw.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			const cache = await caches.open(CACHE_NAME);
			await cache.addAll(PRECACHE);
			await sw.skipWaiting();
		})()
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			// Drop caches from previous deployments
			const keys = await caches.keys();
			await Promise.all(
				keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
			);
			await sw.clients.claim();
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const { request } = event;
	const url = new URL(request.url);

	// Only handle same-origin GETs; never cache the API or user media
	if (request.method !== 'GET' || url.origin !== sw.location.origin) return;
	if (url.pathname.startsWith('/api') || url.pathname.startsWith('/storage')) return;

	// Cache-first for precacheable assets (hashed filenames → safe forever)
	if (PRECACHE.includes(url.pathname)) {
		event.respondWith(
			(async () => {
				const cached = await caches.match(request);
				if (cached) return cached;
				const response = await fetch(request);
				const cache = await caches.open(CACHE_NAME);
				cache.put(request, response.clone());
				return response;
			})()
		);
		return;
	}

	// Network-first for navigations, falling back to the cached shell offline.
	// (ssr=false SPA: any route not in the prerendered set serves index.html.)
	if (request.mode === 'navigate') {
		event.respondWith(
			(async () => {
				try {
					return await fetch(request);
				} catch {
					const cache = await caches.open(CACHE_NAME);
					return (
						(await cache.match(url.pathname)) ??
						(await cache.match('/index.html')) ??
						new Response('Offline', { status: 503 })
					);
				}
			})()
		);
	}
});
