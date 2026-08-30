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

function qs(params?: Record<string, string | number | undefined | null>): string {
	if (!params) return '';
	const q = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v !== undefined && v !== null) q.set(k, String(v));
	}
	const s = q.toString();
	return s ? `?${s}` : '';
}

type PaginatedResponse<T> = { items: T[]; total: number; limit: number; offset: number };

function crud<T = any>(path: string) {
	return {
		list: (params?: Record<string, string | number | undefined>) =>
			request<PaginatedResponse<T>>(`/${path}${qs(params)}`),
		get: (id: string) => request<T>(`/${path}/${id}`),
		create: (data: Partial<T>) =>
			request<T>(`/${path}`, { method: 'POST', body: JSON.stringify(data) }),
		update: (id: string, data: Partial<T>) =>
			request<T>(`/${path}/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
		delete: (id: string) =>
			request<void>(`/${path}/${id}`, { method: 'DELETE' }),
	};
}

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
	upload: (file: File, exif?: { datetime: string | null; lat: number | null; lon: number | null }, locationDisplayName?: string) => {
		const form = new FormData();
		form.append('file', file);
		if (exif?.datetime) form.append('exif_datetime', exif.datetime);
		if (exif?.lat != null) form.append('exif_lat', String(exif.lat));
		if (exif?.lon != null) form.append('exif_lon', String(exif.lon));
		if (locationDisplayName) form.append('location_display_name', locationDisplayName);
		return fetch(`${API_BASE}/sightings`, { method: 'POST', body: form }).then(async (res) => {
			if (!res.ok) throw new ApiError(res.status, await res.text());
			return res.json();
		});
	},
	delete: (id: string) =>
		request<void>(`/sightings/${id}`, { method: 'DELETE' }),
	update: (id: string, data: Record<string, unknown>) =>
		request<any>(`/sightings/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
	overrideSpecies: (id: string, speciesCode: string, speciesCommon: string) =>
		request<any>(`/sightings/${id}`, {
			method: 'PATCH',
			body: JSON.stringify({ species_code: speciesCode, species_common: speciesCommon })
		}),
};

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

export const cards = {
	...crud<any>('cards'),
	generate: (sightingId: string) =>
		request<any>(`/cards/generate/${sightingId}`, { method: 'POST' }),
	regenerateArt: (cardId: string, promptHint?: string, styleOverride?: string) =>
		request<{ job_id: string; status: string }>(`/cards/${cardId}/regenerate-art`, {
			method: 'POST',
			body: JSON.stringify({
				prompt_hint: promptHint || undefined,
				style_override: styleOverride || undefined,
			}),
		})
};

export const binders = {
	...crud<any>('binders'),
	addCard: (binderId: string, cardId: string) =>
		request<any>(`/binders/${binderId}/cards`, {
			method: 'POST',
			body: JSON.stringify({ card_id: cardId })
		}),
	removeCard: (binderId: string, cardId: string) =>
		request<void>(`/binders/${binderId}/cards/${cardId}`, { method: 'DELETE' }),
};

export const sets = {
	...crud<any>('sets'),
	progress: (id: string) => request<any>(`/sets/${id}/progress`),
};

export const trades = {
	...crud<any>('trades'),
	accept: (id: string) => request<any>(`/trades/${id}/accept`, { method: 'POST' }),
	decline: (id: string) => request<any>(`/trades/${id}/decline`, { method: 'POST' }),
	cancel: (id: string) => request<any>(`/trades/${id}/cancel`, { method: 'POST' }),
};

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

// Version
export const getVersion = () =>
	request<{ commit: string }>('/version');

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
