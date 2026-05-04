const API_BASE = '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const res = await fetch(`${API_BASE}${path}`, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		}
	});

	if (!res.ok) {
		const body = await res.json().catch(() => ({ detail: res.statusText }));
		throw new ApiError(res.status, body.detail || res.statusText);
	}

	if (res.status === 204) return undefined as T;
	return res.json();
}

export class ApiError extends Error {
	status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

// Sightings
export const sightings = {
	list: (params?: { limit?: number; offset?: number; status?: string }) => {
		const q = new URLSearchParams();
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		if (params?.status) q.set('status', params.status);
		return request<any>(`/sightings?${q}`);
	},
	get: (id: string) => request<any>(`/sightings/${id}`),
	getJob: (id: string) => request<{ job: any | null }>(`/sightings/${id}/job`),
	upload: (file: File, exif?: { datetime: string | null; lat: number | null; lon: number | null }) => {
		const form = new FormData();
		form.append('file', file);
		if (exif?.datetime) form.append('exif_datetime', exif.datetime);
		if (exif?.lat != null) form.append('exif_lat', String(exif.lat));
		if (exif?.lon != null) form.append('exif_lon', String(exif.lon));
		return fetch(`${API_BASE}/sightings`, { method: 'POST', body: form }).then(async (res) => {
			if (!res.ok) throw new ApiError(res.status, await res.text());
			return res.json();
		});
	},
	delete: (id: string) =>
		request<void>(`/sightings/${id}`, { method: 'DELETE' }),
	overrideSpecies: (id: string, speciesCode: string, speciesCommon: string) =>
		request<any>(`/sightings/${id}`, {
			method: 'PATCH',
			body: JSON.stringify({ species_code: speciesCode, species_common: speciesCommon })
		})
};

// Species
export const species = {
	search: (query: string, params?: { family?: string; limit?: number; offset?: number }) => {
		const q = new URLSearchParams({ q: query });
		if (params?.family) q.set('family', params.family);
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/species/search?${q}`);
	},
	families: () => request<any>(`/species/families`)
};

// Cards
export const cards = {
	list: (params?: { limit?: number; offset?: number }) => {
		const q = new URLSearchParams();
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/cards?${q}`);
	},
	get: (id: string) => request<any>(`/cards/${id}`),
	generate: (sightingId: string) =>
		request<any>(`/cards/generate/${sightingId}`, {
			method: 'POST',
		}),
	delete: (id: string) =>
		request<void>(`/cards/${id}`, { method: 'DELETE' })
};

// Binders
export const binders = {
	list: (params?: { limit?: number; offset?: number }) => {
		const q = new URLSearchParams();
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/binders?${q}`);
	},
	get: (id: string) => request<any>(`/binders/${id}`),
	create: (data: { name: string; description?: string }) =>
		request<any>('/binders', { method: 'POST', body: JSON.stringify(data) }),
	update: (id: string, data: { name?: string; description?: string }) =>
		request<any>(`/binders/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
	delete: (id: string) =>
		request<void>(`/binders/${id}`, { method: 'DELETE' }),
	addCard: (binderId: string, cardId: string) =>
		request<any>(`/binders/${binderId}/cards`, {
			method: 'POST',
			body: JSON.stringify({ card_id: cardId })
		}),
	removeCard: (binderId: string, cardId: string) =>
		request<void>(`/binders/${binderId}/cards/${cardId}`, { method: 'DELETE' })
};

// Sets
export const sets = {
	list: (params?: { limit?: number; offset?: number }) => {
		const q = new URLSearchParams();
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/sets?${q}`);
	},
	get: (id: string) => request<any>(`/sets/${id}`),
	create: (data: { name: string; description?: string; region?: string; card_targets?: string[] }) =>
		request<any>('/sets', { method: 'POST', body: JSON.stringify(data) }),
	update: (id: string, data: Record<string, unknown>) =>
		request<any>(`/sets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
	delete: (id: string) =>
		request<void>(`/sets/${id}`, { method: 'DELETE' }),
	progress: (id: string) => request<any>(`/sets/${id}/progress`)
};

// Trades
export const trades = {
	list: (params?: { status?: string; limit?: number; offset?: number }) => {
		const q = new URLSearchParams();
		if (params?.status) q.set('status', params.status);
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/trades?${q}`);
	},
	get: (id: string) => request<any>(`/trades/${id}`),
	create: (data: { offered_to: string; offered_card_ids: string[]; requested_card_ids: string[] }) =>
		request<any>('/trades', { method: 'POST', body: JSON.stringify(data) }),
	accept: (id: string) =>
		request<any>(`/trades/${id}/accept`, { method: 'POST' }),
	decline: (id: string) =>
		request<any>(`/trades/${id}/decline`, { method: 'POST' }),
	cancel: (id: string) =>
		request<any>(`/trades/${id}/cancel`, { method: 'POST' })
};

// Jobs
export const jobs = {
	get: (id: string) => request<any>(`/jobs/${id}`)
};

// Auth / debug
export const auth = {
	me: () => request<{ user_identifier: string; display_name: string | null; avatar_path: string | null; auth_source: string; has_cf_jwt_header: boolean; has_cf_cookie: boolean; has_cf_raw_header: boolean; has_bearer_header: boolean }>('/auth/me'),
	settings: () => request<Record<string, unknown>>('/auth/settings')
};

// Profile
export const profile = {
	get: () => request<{ email: string; display_name: string | null; avatar_path: string | null; created_at: string | null; region: string | null }>('/profile'),
	update: (data: { display_name?: string; region?: string | null }) => request<any>('/profile', { method: 'PATCH', body: JSON.stringify(data) }),
	uploadAvatar: (file: File) => {
		const form = new FormData();
		form.append('file', file);
		return fetch(`${API_BASE}/profile/avatar`, { method: 'POST', body: form }).then(async (res) => {
			if (!res.ok) throw new ApiError(res.status, await res.text());
			return res.json();
		});
	}
};

// Collection
export const collection = {
	regions: () => request<any[]>('/regions'),
	regionSpecies: (regionId: string) => request<any[]>(`/regions/${regionId}/species`),
	progress: (params?: { family_group?: boolean }) => {
		const q = new URLSearchParams();
		if (params?.family_group) q.set('family_group', 'true');
		return request<any>(`/collection/progress?${q}`);
	},
};

// Users
export const users = {
	list: () => request<any[]>('/users'),
	getProfile: (email: string) => request<any>(`/users/${encodeURIComponent(email)}`)
};

// AI Settings
export const aiSettings = {
	get: () => request<Record<string, any>>('/settings/ai'),
	update: (settings: Record<string, string>) =>
		request<any>('/settings/ai', { method: 'PATCH', body: JSON.stringify(settings) }),
};

// Feed (activity)
export const feed = {
	list: (params?: { limit?: number; offset?: number }) => {
		const q = new URLSearchParams();
		if (params?.limit) q.set('limit', String(params.limit));
		if (params?.offset) q.set('offset', String(params.offset));
		return request<any>(`/feed?${q}`);
	},
	like: (activityId: string) =>
		request<any>(`/feed/${activityId}/like`, { method: 'POST' }),
	unlike: (activityId: string) =>
		request<any>(`/feed/${activityId}/like`, { method: 'DELETE' }),
	comment: (activityId: string, content: string) =>
		request<any>(`/feed/${activityId}/comments`, {
			method: 'POST',
			body: JSON.stringify({ content }),
		}),
};
