<script lang="ts">
    import { feed } from '$lib/api';

    let activities = $state<any[]>([]);
    let total = $state(0);
    let loading = $state(true);
    let error = $state('');
    let commentInputs = $state<Record<string, string>>({});
    let submittingComment = $state<Record<string, boolean>>({});

    async function loadFeed() {
        loading = true;
        error = '';
        try {
            const data = await feed.list({ limit: 50 });
            activities = data.items || [];
            total = data.total;
        } catch (e: any) {
            error = e.message || 'Failed to load feed';
        } finally {
            loading = false;
        }
    }

    async function toggleLike(activity: any) {
        if (activity.current_user_liked) {
            activity.like_count--;
            activity.current_user_liked = false;
            try { await feed.unlike(activity.id); } catch { activity.like_count++; activity.current_user_liked = true; }
        } else {
            activity.like_count++;
            activity.current_user_liked = true;
            try { await feed.like(activity.id); } catch { activity.like_count--; activity.current_user_liked = false; }
        }
    }

    async function submitComment(activityId: string) {
        const content = commentInputs[activityId]?.trim();
        if (!content) return;
        submittingComment[activityId] = true;
        try {
            const comment = await feed.comment(activityId, content);
            const activity = activities.find((a: any) => a.id === activityId);
            if (activity) {
                activity.comments = [...(activity.comments || []), comment];
                activity.comment_count = (activity.comment_count || 0) + 1;
            }
            commentInputs[activityId] = '';
        } catch (e: any) {
            console.error('Failed to submit comment:', e);
        } finally {
            submittingComment[activityId] = false;
        }
    }

    function timeAgo(dateStr: string): string {
        const now = Date.now();
        const then = new Date(dateStr).getTime();
        const diff = Math.floor((now - then) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    }

    function userDisplayName(activity: any): string {
        return activity.display_name || activity.user_identifier;
    }

    function userInitials(activity: any): string {
        const name = userDisplayName(activity);
        if (name.includes('@')) return name.split('@')[0].slice(0, 2).toUpperCase();
        return name.slice(0, 2).toUpperCase();
    }

    function commentUserDisplayName(comment: any): string {
        return comment.display_name || comment.user_identifier;
    }

    function commentUserInitials(comment: any): string {
        const name = commentUserDisplayName(comment);
        if (name.includes('@')) return name.split('@')[0].slice(0, 2).toUpperCase();
        return name.slice(0, 2).toUpperCase();
    }

    const activityIcons: Record<string, string> = {
        sighting: '📸',
        card: '🃏',
        set_completion: '🏆',
    };

    const activityLabels: Record<string, string> = {
        sighting: 'Sighting',
        card: 'Card',
        set_completion: 'Set',
    };

    $effect(() => { loadFeed(); });
</script>

<svelte:head>
    <title>Feed — BirdBinder</title>
</svelte:head>

<div class="mx-auto max-w-2xl px-4 py-6">
    <h1 class="mb-6 text-2xl font-bold text-gray-100">Activity Feed</h1>
    {#if loading}
        <div class="space-y-4">
            {#each Array(3) as _}
                <div class="animate-pulse rounded-xl bg-gray-800 p-4">
                    <div class="h-4 w-1/3 rounded bg-gray-700"></div>
                    <div class="mt-3 h-3 w-2/3 rounded bg-gray-700"></div>
                </div>
            {/each}
        </div>
    {:else if error}
        <div class="rounded-xl border border-red-800/50 bg-red-900/20 p-4 text-red-400">{error}</div>
    {:else if activities.length === 0}
        <div class="rounded-xl border border-gray-800 bg-gray-900 p-8 text-center">
            <p class="text-4xl">🐦</p>
            <p class="mt-2 text-gray-400">No activity yet. Go spot some birds!</p>
        </div>
    {:else}
        <div class="space-y-4">
            {#each activities as activity}
                <div class="rounded-xl border border-gray-800 bg-gray-900 p-4">
                    <div class="flex items-start justify-between">
                        <div class="flex items-center gap-3">
                            <a
                                href="/users/{activity.user_identifier}"
                                class="flex h-10 w-10 items-center justify-center rounded-full bg-green-900/30 text-green-400 text-sm font-bold transition-colors hover:bg-green-900/50"
                                title="{activity.user_identifier}"
                            >
                                {userInitials(activity)}
                            </a>
                            <div>
                                <a
                                    href="/users/{activity.user_identifier}"
                                    class="text-sm font-medium text-gray-200 hover:text-green-400 transition-colors"
                                >
                                    {userDisplayName(activity)}
                                </a>
                                <p class="text-xs text-gray-500">{timeAgo(activity.created_at)}</p>
                            </div>
                        </div>
                        <span class="rounded-full border border-gray-700 px-2 py-0.5 text-xs text-gray-400">
                            {activityIcons[activity.activity_type] || '📝'} {activityLabels[activity.activity_type] || activity.activity_type}
                        </span>
                    </div>
                    <p class="mt-3 text-gray-300">{activity.description}</p>

                    <!-- Actions -->
                    <div class="mt-3 flex items-center gap-4 border-t border-gray-800 pt-3">
                        <button
                            type="button"
                            onclick={() => toggleLike(activity)}
                            class="flex items-center gap-1.5 text-sm transition-colors {activity.current_user_liked ? 'text-red-400' : 'text-gray-500 hover:text-red-400'}"
                        >
                            <svg class="h-4 w-4" viewBox="0 0 24 24" fill={activity.current_user_liked ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="2">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
                            </svg>
                            {activity.like_count}
                        </button>
                        <button
                            type="button"
                            class="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300"
                        >
                            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                            </svg>
                            {activity.comment_count}
                        </button>
                    </div>

                    <!-- Comments -->
                    {#if activity.comments?.length > 0}
                        <div class="mt-3 space-y-2 pl-2 border-l-2 border-gray-800">
                            {#each activity.comments as comment}
                                <div class="text-sm flex items-start gap-2">
                                    <a
                                        href="/users/{comment.user_identifier}"
                                        class="font-medium text-gray-300 hover:text-green-400 transition-colors shrink-0"
                                        title="{comment.user_identifier}"
                                    >
                                        {commentUserDisplayName(comment)}
                                    </a>
                                    <span class="text-gray-400">{comment.content}</span>
                                </div>
                            {/each}
                        </div>
                    {/if}

                    <!-- Comment Input -->
                    <div class="mt-3 flex gap-2">
                        <input
                            type="text"
                            bind:value={commentInputs[activity.id]}
                            placeholder="Add a comment..."
                            class="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-green-500 focus:outline-none"
                            onkeydown={(e) => e.key === 'Enter' && submitComment(activity.id)}
                        />
                        <button
                            type="button"
                            onclick={() => submitComment(activity.id)}
                            disabled={submittingComment[activity.id] || !commentInputs[activity.id]?.trim()}
                            class="rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-40"
                        >
                            Post
                        </button>
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>
