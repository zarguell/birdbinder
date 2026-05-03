# PRD Compliance: BirdBinder v1

## Source
- PRD location: `PRD.md` (project root)
- PRD version: 1.1

## Acceptance Criteria (verifiable)

### Auth & Access
1. [ ] App decodes `CF_Authorization` JWT header, extracts email as user_identifier
2. [ ] App accepts Bearer API key authentication via `Authorization: Bearer ***`
3. [ ] API keys are validated against comma-separated list from `API_KEYS` env var
4. [ ] Both auth paths grant equivalent trust (no RBAC or resource-level auth)

### Sighting Submission
5. [ ] `POST /api/sightings` accepts image upload (multipart form)
6. [ ] Sighting stores: original image, thumbnail, submitted_at, EXIF datetime/GPS/camera, notes, manual_species_override, status, user_identifier
7. [ ] Thumbnail is generated from uploaded image
8. [ ] EXIF metadata is extracted and stored when present (datetime, lat/lon, camera model)
9. [ ] Missing EXIF does not block upload
10. [ ] Sighting has a status field tracking identification progress

### Bird Identification (AI)
11. [ ] AI identification calls OpenAI-compatible API with configurable base URL (`AI_BASE_URL`), model (`AI_MODEL`), and key (`AI_API_KEY`)
12. [ ] AI response returns: common_name, scientific_name, family, confidence, distinguishing_traits, pose_variant
13. [ ] AI pose_variant must come from fixed taxonomy: perched_branch, in_flight, ground_foraging, water_swimming, water_wading, nest, feeder, other
14. [ ] Default identification prompt ships with app, overridable via `BIRDBINDER_ID_PROMPT` env var
15. [ ] Identification runs as async job — returns job_id, client polls status

### Bird Identification (Manual)
16. [ ] Users can manually set species, confidence, pose_variant, and notes on a sighting
17. [ ] Species autocomplete/search endpoint exists (`GET /api/species/search`)
18. [ ] Manual entry is a fully supported path (not just a fallback)

### Card Generation
19. [ ] `POST /api/cards/generate/{sighting_id}` creates a card from an identified sighting
20. [ ] Card generation runs as async job (returns job_id)
21. [ ] Card stores: sighting_id, species_common, species_scientific, species_code, family, pose_variant, rarity_tier, set_ids, card_number, card_art_url, id_method, id_confidence, generated_at
22. [ ] Card art generated via AI image generation using OpenAI-compatible API (with configurable base URL)
23. [ ] Fallback: if no `AI_API_KEY` configured, card uses original sighting photo instead of AI art
24. [ ] Card front displays: artwork, species common name, scientific name, rarity badge, pose label, set/card number, date seen, location, observer
25. [ ] Card back/detail shows: raw sighting metadata, EXIF info, confidence score, identification method

### Rarity
26. [ ] Static bird frequency/taxonomy data bundled from eBird taxonomy (same source as audio-birdle)
27. [ ] Rarity tiers derived from bundled taxonomy data
28. [ ] Optional: eBird API key (`EBIRD_API_KEY`) enriches data (not required for v1)

### Binder
29. [ ] `GET /api/binder` returns owned cards in grid-ready format
30. [ ] Binder supports grouping by set, species, and family
31. [ ] Binder supports filtering by rarity, pose, date, and duplicates
32. [ ] Incomplete sets show missing-card placeholders
33. [ ] Duplicate count indicators shown in binder
34. [ ] Card detail modal/page accessible from binder

### Sets
35. [ ] Any authenticated user can create a set (`POST /api/sets`)
36. [ ] Set fields: name, description, region, season, release_date, expiry_date, rules, card_targets
37. [ ] Cards auto-match to sets based on species and pose criteria
38. [ ] Completion percentage calculated and returned
39. [ ] `GET /api/sets/{id}/missing` returns cards needed to complete a set

### Trading
40. [ ] `POST /api/trades` creates a trade offer (offered_card_ids, requested_card_ids)
41. [ ] `GET /api/trades` lists trades
42. [ ] `POST /api/trades/{id}/accept` and `/decline` endpoints exist
43. [ ] Duplicate cards are tradeable
44. [ ] No money handling, no marketplace in v1

### REST API
45. [ ] All core features accessible via RESTful JSON endpoints
46. [ ] Stable object IDs (UUID)
47. [ ] Pagination on list endpoints
48. [ ] Filterable resources
49. [ ] OpenAPI spec auto-generated and accessible
50. [ ] API usable through Cloudflare tunnel AND direct LAN access

### PWA
51. [ ] Installable web app manifest
52. [ ] Standalone display mode
53. [ ] App icon support
54. [ ] Mobile-friendly responsive layout
55. [ ] Responsive upload and binder screens

### Configuration
56. [ ] All config via environment variables: APP_URL, API_KEYS, CF_ACCESS_ENABLED, CF_TEAM_DOMAIN, AI_BASE_URL, AI_MODEL, AI_API_KEY, BIRDBINDER_ID_PROMPT, CARD_STYLE_NAME, DATABASE_URL, STORAGE_PATH, EBIRD_API_KEY

### Tech Stack
57. [ ] Backend: FastAPI
58. [ ] Frontend: SvelteKit
59. [ ] Database: SQLite
60. [ ] Object storage: local disk (S3-compatible optional)
61. [ ] Async jobs: huey (SQLite-backed, lightweight)

## Out of Scope (explicit exclusions)
- Native iOS/Android apps
- Deep offline support (offline browsing, queued submissions, heavy service worker caching)
- RBAC, admin dashboard, permissions matrix
- Public social network features
- Authenticity enforcement, reverse-image validation, EXIF-as-authenticity-gate
- Automatic DSLR desktop utility (API-only path)
- Monetization
- Advanced market/auction mechanics
- Battle system, leaderboards, stats-driven gameplay
- Per-user or per-set art style switching (one global style only)
- Enterprise tenancy model

## Technical Decisions (Resolved)
- **Card art**: AI image generation via OpenAI-compatible API. Fallback to original photo if no AI_API_KEY.
- **Background worker**: huey (SQLite-backed, lightweight, survives restarts, no Redis needed)
- **Bird taxonomy data**: eBird taxonomy JSON/CSV (same dataset from audio-birdle: `ebird-taxonomy.json`)
- **User identity**: Decode `CF_Authorization` JWT, extract email as user_identifier
- **SvelteKit** for frontend (PRD preferred, confirmed)
- **FastAPI** for backend
- **SQLite** for database (simple, self-hosted)
- **Alembic** for DB migrations
- **Local disk** for object storage under `STORAGE_PATH`
- **UUIDs** for stable object IDs
- **Pillow** for image processing (thumbnails, EXIF extraction)
- **No user accounts table** — user_identifier derived from auth header
