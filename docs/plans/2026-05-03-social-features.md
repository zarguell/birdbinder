# BirdBinder — Social & Card Detail Features

## Priority Order

### Bug: Card detail page 404 (P0)
The sighting detail page links to `/cards/{id}` but no route exists.
**Fix:** Create `frontend/src/routes/cards/[id]/+page.svelte` — fetch card via `GET /api/cards/{id}`, display full card with art, rarity badge, species info, generated date, sighting link.

### Story 1: User directory + trade recipient dropdown (P1)
Trade creation has a bare text input for `offered_to` — users have to guess email addresses.
**Backend:** `GET /api/users` — list all users (id, email, display_name, avatar_path, created_at).
**Frontend:** Replace text input with searchable dropdown in trade form. Show display_name or email, with avatar thumbnail.

### Story 2: Public user profile page (P1)
**Backend:** `GET /api/users/{email}` — user profile with collection stats (total cards, unique species, region, join date, activity feed preview).
**Frontend:** `frontend/src/routes/users/[email]/+page.svelte` — public profile view with:
  - Avatar, display name, join date, region
  - Collection stats (cards collected, unique species, collection %)
  - Recent activity (their feed items)
  - "Propose Trade" button → pre-fills trade form with this user

### Story 3: Initiate trade from user profile (P2)
The "Propose Trade" button on the user profile page navigates to `/trades?to=email`, pre-selecting the recipient. The trade form detects the query param and locks the recipient field.

## Tasks

1. **Card detail page** — `frontend/src/routes/cards/[id]/+page.svelte`
   - Fetch card data, display full card image large, rarity tier badge, species info
   - Link back to sighting
   - Show generated_at date, card notes

2. **Users list endpoint** — `backend/app/routers/auth.py` or new `backend/app/routers/users.py`
   - `GET /api/users` → list of all users (public fields only)
   - Register router in `main.py`

3. **User profile endpoint** — `backend/app/routers/users.py`
   - `GET /api/users/{email}` → full public profile + collection stats
   - Collection stats: card count, unique species count, collection % for their region

4. **Trade recipient dropdown** — update `frontend/src/routes/trades/+page.svelte`
   - Fetch users on mount, render searchable dropdown instead of text input
   - Show avatar + display name + email

5. **User profile page** — `frontend/src/routes/users/[email]/+page.svelte`
   - Public profile with stats, activity feed, trade button

6. **Pre-fill trade from profile** — trade page reads `?to=` query param
