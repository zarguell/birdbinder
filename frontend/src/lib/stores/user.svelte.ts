import { auth } from '$lib/api';

export interface UserInfo {
	user_identifier: string;
	display_name: string | null;
	avatar_path: string | null;
	auth_source: string;
}

/**
 * App-wide authenticated user state. The layout loads it once; pages that
 * change the profile call `setUser` so the nav updates immediately instead
 * of going stale until the next reload.
 */
export const userStore = $state<{ user: UserInfo | null; loaded: boolean }>({
	user: null,
	loaded: false
});

export async function loadUser(force = false): Promise<UserInfo | null> {
	if (userStore.loaded && !force) return userStore.user;
	try {
		userStore.user = await auth.me();
	} catch {
		userStore.user = null;
	}
	userStore.loaded = true;
	return userStore.user;
}

export function setUser(u: UserInfo | null) {
	userStore.user = u;
	userStore.loaded = true;
}
