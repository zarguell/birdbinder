# UI/UX & Architecture Review + Improvement Plan (2026-08-30)

Full review of backend (FastAPI/SQLAlchemy/Huey) and frontend (SvelteKit 5/Tailwind v4) after merging the week-of-2026-08-24 release. Findings are ranked by severity; each item cites file:line. Suggested execution order is phased at the bottom.

---

## P0 — Ship-blocking bugs & security

### Security
1. **Unauthenticated `/api/auth/debug` leaks credentials** — `backend/app/routers/auth.py:36-109` returns all request headers (including the real `Authorization: Bearer <api-key>` and the CF JWT), decoded claims, and auth config. Delete the endpoint or gate it to local-only/dev mode.
2. **CF JWT accepted without signature verification by default** — `backend/app/auth.py:145-157`, `backend/app/dependencies.py:27-37`. With `CF_VERIFY_JWT=false` (the default) anyone who can reach port 8000 can mint a JWT with any `email` claim and impersonate any user. Worse, even `CF_VERIFY_JWT=true` **silently falls back to unverified decode** when cert fetch fails or kid is unknown (`auth.py:133-142`). Make verification mandatory; fail closed.
3. **`/storage` static mount serves all user photos & card art with no auth** — `backend/app/main.py:63-65`. Photos are UUID-guessable and URLs leak via the API. Route media through an authenticated endpoint or signed URLs.
4. **SPA fallback path escape** — `backend/app/main.py:75-82` joins URL `path` directly; add an explicit `resolve()` + prefix containment check.
5. **Prompt-injection / cost abuse** — user-controlled `prompt_hint` is interpolated verbatim into image prompts (`backend/app/routers/cards.py:87-91`, `backend/app/services/ai.py:240,261`), and `/cards/{id}/regenerate-art` has no rate limit or quota while each call bills an image generation. Sanitize the hint and add a per-user daily regen quota.

### Broken features
6. **`GET /api/sightings/{id}/job` is a guaranteed 500** — `NameError: select/Job` (missing imports) at `backend/app/routers/sightings.py:262-263`. This is the identification-progress polling endpoint the frontend depends on. Fix imports, add ownership check, add a test.
7. **Trades "Incoming"/"Outgoing" tabs are functionally broken** — direction is ignored in filtering, so your own outgoing pending trades appear under *Incoming* with Accept/Decline buttons attached (you can accept your own trade). `frontend/src/routes/trades/+page.svelte:90-101`, buttons at :488-502.
8. **EXIF parser reads the wrong IFD** — `frontend/src/routes/upload/+page.svelte:79-141` reads GPS/DateTimeOriginal from IFD0 only; GPS lives in the GPS IFD (0x8825) and date in the Exif IFD (0x8769), so geotagged photos usually report "No location found" and observed-date falls back to upload time — degrading the app's primary flow. Replace the hand-rolled parser with a maintained library (e.g. `exifr`) or fix the IFD traversal.
9. **eBird live rarity is a stub** — `fetch_region_frequencies` returns `{}` (`backend/app/services/ebird_service.py:136-157`); `POST /collection/refresh-ebird` can never succeed, yet the Collection page fires it on **every visit** (`frontend/src/routes/collection/+page.svelte:158-161`). Implement the real call (or remove the feature + UI trigger), and read the key from settings instead of `os.environ` (`collection.py:134`).
10. **Favicon 404 on every page** — `frontend/src/app.html:9` links `/favicon.png` which doesn't exist; the SVG favicon at `src/lib/assets/favicon.svg` is never used.

---

## P1 — Reliability & data integrity (backend)

11. **Huey tasks: no retries, no idempotency, no stale-job reconciliation** — plain `@huey.task()` (`backend/app/services/identifier.py:184`, `card_gen.py:137,244`): a transient OpenAI 429 permanently fails the job; consumer redelivery can insert **duplicate Cards** (`card_gen.py:104`); jobs stuck in `running` after a crash are never swept; DB commit precedes enqueue (`card_gen.py:164-168`) so enqueue failure strands a `pending` row forever. Add `retries`/backoff, idempotency guards, a startup sweeper, and enqueue-before-commit or outbox pattern.
12. **Trade execution is not transactional or race-safe** — `scalar_one()` per JSON-listed card id 500s if a card was deleted (`backend/app/services/trading.py:43-62`); concurrent accepts can double-execute because status check and update aren't atomic. Re-validate at accept time inside one transaction; add FKs or a membership table instead of JSON arrays.
13. **Ownership gaps on job endpoints** — `GET /api/jobs/{id}` returns any user's job including raw AI response (`backend/app/routers/jobs.py:18`); `GET /sightings/{id}/job` doesn't check sighting ownership. Add `user_identifier` to `Job` and enforce it.
14. **Blocking work in async handlers** — synchronous upload write (`backend/app/storage.py:18`) and Pillow EXIF/HEIF/thumbnail processing stall the event loop (`backend/app/routers/sightings.py:68-106`). Move to a threadpool (`run_in_executor`) or into the Huey task.
15. **No cost/timeout controls on OpenAI calls** — no retries, no rate-limit handling, full AI responses logged at INFO (`backend/app/services/ai.py:102,109`). Add retries with backoff, demote logging to DEBUG with redaction, cap tokens, and honor the regen quota from item 5.
16. **SQLite concurrency & process supervision** — async engine + sync engine + 2 Huey workers write one DB file with no WAL mode; `huey_consumer` runs as an unsupervised background child of the entrypoint shell (`entrypoint.sh:24-33`), so it can die while the healthcheck stays green. Enable WAL + busy_timeout, and either supervise huey (supervisor loop in entrypoint or split containers).
17. **Schema drift by design** — `ensure_schema.py` auto-`ALTER`s missing columns at boot alongside Alembic (`backend/app/ensure_schema.py:42-60`), creating two sources of truth. Remove it and make Alembic authoritative (tests currently bypass migrations entirely via `create_all`).

## P1 — UX correctness & mobile (frontend)

18. **Mobile navigation overflows with no hamburger** — 8 links in a non-wrapping row (`frontend/src/routes/+layout.svelte:31-57`); half the app is unreachable on a 375px phone. Add a hamburger/bottom tab bar; while there, add `aria-current` and active-link styling.
19. **Binder delete is invisible on touch** — `opacity-0 group-hover:opacity-100` with **no confirmation** (`frontend/src/routes/binder/+page.svelte:195-204`). Make it always visible on touch and use the standard confirm dialog.
20. **Trades UI is unusable for its purpose** — offered/requested cards render as raw UUID chips (`trades/+page.svelte:458-481`); creating a trade requires typing raw species codes with no validation or autocomplete (:346-356). Reuse `SpeciesSelector` + card pickers; show species names.
21. **Silent failures** — card-delete errors only `console.error` (`CardModal.svelte:99`), feed comment errors swallow the user's typed text (`feed/+page.svelte:50`), identify-poll errors ignored (`sightings/[id]:50`), card generation uses a blind 3s `setTimeout` instead of polling the job (`sightings/[id]:133`). Surface errors; poll job status.
22. **Silent 100-card cap** — `cards.list({ limit: 100 })` in binder and trades (`binder/+page.svelte:40`, `trades/+page.svelte:83`); larger collections silently vanish. Paginate with "Load more" and show counts.
23. **Leaked polling intervals & redundant server work** — regen polls never cleaned up on navigation (`sightings/[id]:219`, `cards/[id]:47-62`); Collection POSTs `refresh-ebird` on every visit. Centralize polling in a composable with teardown; trigger eBird refresh only via explicit button.
24. **No error page & no titles** — no `+error.svelte` anywhere; 12 of 14 routes missing `<title>`; no login/logout page (unauthenticated users see "⚠ no auth" in the nav). Add error page, per-route titles, and a proper auth state.

## P2 — Architecture & code health

25. **Duplicated task plumbing** — `identifier.py:18-180` and `card_gen.py:18-241` are near-clones (job state machine, settings lookups, activity publish, error tails). Extract a generic task wrapper; share one DB engine instead of the separate sync engine (`db.py:14-15`).
26. **Over-eager loading & N+1** — `Sighting.cards` + `jobs` selectin-load everywhere (`models/sighting.py:47-52`); `list_binders` runs one COUNT per binder in a loop (`routers/binders.py:46-49`); no composite index on `(user_identifier, created_at)` for every paginated list. Tune loading and add indexes.
27. **JSON-column denormalization** — `Card.set_ids`, `Trade` card lists as JSON arrays with no FK integrity; `Binder.cover_card_id` has no FK (`models/binder.py:23`); species fields triple-copied (sighting → card → prompts). Introduce membership/trade-item tables.
28. **Dead code** — `SpeciesCache` table unused (species read from 2.7MB `birds.json` per request with a linear scan, loaded/cached independently in 4 modules: `services/species.py:18-34`, `region_service.py`, `rarity.py`, `identifier.py`). Consolidate into one cached loader or move taxonomy into the DB.
29. **Frontend untyped end-to-end** — `crud<any>` in `src/lib/api.ts`; generate types from the OpenAPI schema and type the API client.
30. **Duplicated primitives** — 7 copies of `formatDate`, 4 copies of `holo-shimmer` CSS (3 variants), 3 rarity-color definitions, ~25 inlined spinner SVGs, ~30 copies of the primary button classes, 2 overlapping species components (`SpeciesSelector` vs `SpeciesAutocomplete`, and the mouse-only one is used in the prominent override flow). Extract shared utils/components; move holo-shimmer to `app.css`.
31. **Inconsistent idioms** — 4 confirmation patterns (native `confirm()`/`alert()`, inline confirm, 3s two-click, none); 3 fetch idioms (api client vs raw `fetch` vs `$app/stores` legacy in 5 files); `$effect` used as one-time mount hook in ~8 pages; deprecated `<svelte:component>` in `CardGrid.svelte:12`; `$derived(() => {...})` function-holding idiom in several components. Standardize on runes + api client + one ConfirmDialog component.
32. **PWA is installable but online-only** — manifest exists, no service worker, no offline behavior, no install prompt; cold offline start is a blank page. Add a service worker (e.g. SvelteKit's `service-worker` module) with app-shell caching and offline fallback.
33. **Design system** — hardcoded dark-only grays, `green`/`emerald` mixed in the same components, no theme tokens in `app.css` (one line), no `focus-visible:` counterparts to `hover:` states, sparse a11y (unlabeled selects, icon buttons without `aria-label`, status by color/emoji only). Define a token layer (`@theme`) and a small component kit (Button, Badge, Spinner, EmptyState, ErrorState).
34. **Misc** — `python-jose` unmaintained (use `pyjwt`); `openai` dep unused; base image `python:3.14-slim` vs `requires-python >=3.11` vs README 3.13; `chmod 777` on data dirs (`Dockerfile:47`); dead `@sveltejs/adapter-auto` dep; profile save's no-op `fetch('/api/auth/me')` (`profile/+page.svelte:36,61`) while nav state stays stale (needs a shared user store).

---

## Suggested execution phases

**Phase 0 — Hotfixes (days):** items 1, 2, 3, 4, 6, 7, 10. Pure bug/security fixes, low risk, immediate.
**Phase 1 — Core flow correctness (1–2 weeks):** items 8, 9, 11, 12, 13, 14, 18, 19, 20, 21, 22. These fix the primary upload→identify→card→binder→trade loops on both ends.
**Phase 2 — Reliability & polish (2–3 weeks):** items 5, 15, 16, 17, 23, 24, 26, 27, 29.
**Phase 3 — Maintainability & PWA (ongoing):** items 25, 28, 30, 31, 32, 33, 34. Note `docs/plans/simplification-cascades.md` already covers part of item 25 and the pagination consolidation — coordinate with it.

Each fix should land with a test where the backend is involved (item 6's 500 would have been caught by one endpoint test; item 7 by one UI-flow test).
