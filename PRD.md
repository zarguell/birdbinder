# BirdBinder PRD

**Version:** 1.1  
**Status:** Finished draft  
**Product type:** Self-hosted, API-first PWA for bird sighting collection and card generation

## Overview

BirdBinder is a self-hosted, API-first progressive web app that turns real bird sightings into collectible digital cards. The core loop is simple: take or upload a photo, identify the bird with AI or manual entry, generate a card, and place it into a digital binder organized by species, pose variant, and curated sets.

The experience is intentionally calm and collecting-focused. It should feel closer to a personal field journal crossed with a card binder than a game with battles, leaderboards, or territorial mechanics.

## Product goals

BirdBinder exists to make bird sightings more playful, visual, and collectible without trying to replace scientific logging tools like eBird or identification tools like Merlin. It is a companion experience centered on personal sightings, card collection, and presentation.

Primary goals:

- Make bird sightings feel rewarding through card collection.  
- Use a binder metaphor that makes completion and duplicates fun.  
- Support both AI-assisted and manual bird entry.  
- Stay easy to self-host and easy to extend through an external API.  
- Use a PWA for a friendlier mobile experience.

Non-goals:

- No battling system.  
- No party mechanics.  
- No public leaderboard competition.  
- No enterprise-style permissions model.  
- No native iOS app requirement.

## Product principles

- **Photo \= acquisition.** You get cards by seeing birds and submitting photos, not by opening packs.  
- **Collection over competition.** The product is about discovery, completion, and sharing.  
- **API first.** The web app is just one client of the platform.  
- **Perimeter auth only.** The front door should be protected, but once inside, users are trusted.  
- **Consistent art direction.** The app should have one recognizable BirdBinder visual identity.  
- **Self-hosted by default.** The host should be able to run the entire stack locally or in a homelab.

## Users and use cases

The expected user is a trusted friend group, small community, or household running the app in a self-hosted environment. Everyone with access is considered trusted once authenticated.

Core use cases:

- Upload a bird photo from a phone.  
- Upload a higher-quality DSLR image from desktop.  
- Identify the bird using AI or manual override.  
- Turn the sighting into a collectible card.  
- Browse cards in a binder view.  
- Build and complete curated sets.  
- Hold duplicates and trade with friends.  
- Use the API directly for scripts, agents, and future automations.

## Positioning

BirdBinder should not present itself as a competitor to eBird or Merlin. It is a collectible companion layer built around personal sightings and visual collection.

## Auth and trust model

The threat model is intentionally simple: protect the app's entry point from the public internet. There is no requirement for fine-grained authorization, resource ownership enforcement, or role-based access control inside the app.

### Trust assumptions

- If a request comes through the allowed front door, it is trusted.  
- Users do not need resource-level authorization boundaries.  
- There are no admin-only management gates.  
- Any authenticated user can create sets and use all product features.

### Supported auth paths

#### 1\. Cloudflare Access for browser use

The primary browser path is Cloudflare Tunnel plus Cloudflare Access.

Behavior:

- Requests go through Cloudflare Tunnel.  
- Cloudflare Access enforces the allow policy.  
- The app reads the authenticated user header from the request.  
- Group-based access is enforced only at the Cloudflare front door.

This path is intended for normal interactive app use in the browser.

#### 2\. API key for direct service access

Because Cloudflare Access can be awkward for direct programmatic access, the app should also support a simple API key path when a client has direct network line-of-sight to the service.

Behavior:

- A client sends `Authorization: Bearer <api_key>`.  
- The backend validates the key against configured keys from environment variables.  
- If valid, the request is trusted the same way as a Cloudflare-authenticated request.

This path is intended for:

- local scripts  
- agents  
- homelab automations  
- direct LAN access  
- external experimentation against the REST API

#### 3\. Optional Cloudflare service tokens

Cloudflare service tokens may still be supported for automations routed through Cloudflare Access, but they are optional rather than the default approach.

### Explicitly out of scope

- No RBAC.  
- No owner-only resource enforcement.  
- No in-app permissions matrix.  
- No admin approval workflow.  
- No enterprise tenancy model.

## Core experience

The main loop is:

1. User opens the app.  
2. User uploads or captures a bird photo.  
3. The app stores the sighting.  
4. The app identifies the bird through AI or manual entry.  
5. The app classifies or assigns a pose variant.  
6. The app generates a card in the app's canonical art style.  
7. The card appears in the user's binder and counts toward any applicable sets.

That loop is the heart of the product.

## Core features

## 1\. Sighting submission

Users can create sightings through:

- mobile camera capture  
- mobile photo library upload  
- desktop file upload  
- future API-based ingestion from external tools

Each sighting should store:

- original image  
- thumbnail  
- submission timestamp  
- optional EXIF timestamp  
- optional EXIF GPS  
- optional camera metadata  
- optional notes  
- optional manual species override  
- identification status

The app should support phone photos and DSLR uploads equally well.

### EXIF handling

The app should read EXIF metadata when present and store useful fields such as:

- timestamp  
- GPS coordinates  
- camera model

EXIF is informational in v1. It is not used as an authenticity gate.

## 2\. Bird identification

Bird identification is the hardest technical feature, so BirdBinder must support both AI-assisted and manual workflows.

### AI-assisted identification

The app sends the uploaded image to a configurable model provider and asks for:

- common name  
- scientific name  
- confidence score  
- likely family  
- brief distinguishing traits  
- pose/context classification from a fixed allowed list

The AI layer must support **OpenAI-compatible APIs with a configurable base URL**. This allows BirdBinder to work with OpenAI directly or with any provider that exposes an OpenAI-style interface.

Required configuration:

- model name  
- API key  
- base URL  
- configurable identification prompt

BirdBinder should ship with a **default prompt**, but the host must be able to override it through configuration.

### Manual identification

Users can override species identification manually. Manual entry is not a fallback edge case; it is a core supported path.

Manual workflows should include:

- species autocomplete  
- direct species search  
- confidence correction  
- pose correction  
- notes

## 3\. Card generation

A sighting becomes a card after identification.

### Card identity

A card is primarily defined by:

- species  
- pose/context variant  
- set membership  
- generated art  
- associated sighting metadata

Different poses of the same bird can produce different cards. For example:

- perched on branch  
- in flight  
- foraging on ground  
- in water  
- at feeder

This creates meaningful collectible variants without inventing fake species distinctions.

### Card layout

Front of card:

- stylized artwork derived from the user's sighting photo  
- species common name  
- scientific name  
- rarity badge  
- pose icon or label  
- set number / card number

Bottom metadata area:

- date seen  
- location  
- observer/user label  
- optional notes snippet

Back of card or detail view:

- raw sighting metadata  
- EXIF information if present  
- confidence score  
- identification method

## 4\. Binder experience

The binder is the primary browsing interface.

Capabilities:

- grid of owned cards  
- grouping by set  
- grouping by species or family  
- filters for rarity, pose, date, and duplicates  
- missing-card placeholders for incomplete sets  
- duplicate count indicators  
- card detail modal or detail page

The binder should feel visually satisfying first, utilitarian second.

## 5\. Sets

Sets are a major completion mechanic. They are curated collections of cards that users try to complete over time.

Set examples:

- Backyard Feeders  
- Spring Migration Mid-Atlantic  
- Chesapeake Shorebirds  
- Warblers 2026  
- Dawn Chorus  
- Winter Visitors

Rules:

- Any authenticated user can create sets.  
- No special role is required.  
- Sets can be permanent or seasonal.  
- Sets can define target cards by species and optionally pose variant.

### Set behavior

A set should include:

- name  
- description  
- region  
- season or date window  
- card list  
- completion percentage  
- release date  
- optional expiration date

## 6\. Trading

Trading is allowed between trusted users.

Rules:

- Users can hold duplicates.  
- Duplicates can be offered in trades.  
- Trades are direct exchanges between users.  
- No money handling is included.  
- No marketplace is required in v1.

Trading exists to support collection completion, not competition.

## 7\. Authenticity checks

Authenticity enforcement is **post-v1**.

For v1:

- read and store EXIF data when present  
- do not implement authenticity scoring or blocking  
- do not block uploads for missing EXIF  
- do not implement reverse-image checks yet

This keeps v1 focused on the core collection experience.

## Art direction

BirdBinder uses **one canonical art style** across the entire app for consistency. The product should not allow per-user or per-set art style switching in v1.

Rationale:

- stronger brand identity  
- more coherent binder aesthetic  
- easier prompting and generation consistency  
- lower implementation complexity

The art style must feel fresh and original to BirdBinder.

## API-first platform requirement

BirdBinder must be designed as a REST API first. The frontend is just one consumer of the API. Every core feature should be accessible through HTTP endpoints so external tools, scripts, and agents can automate workflows and build on top of the data.

### Why API first matters

- external agents can automate image processing  
- image management can happen outside the app  
- future fine-tuning datasets can be assembled through the API  
- scripts can bulk import or export sightings  
- alternate clients can be built later without refactoring the backend  
- future agent systems can consume the OpenAPI schema directly

### Example external uses

- Watch a DSLR export folder and upload images automatically.  
- Pull manually corrected records for future model tuning.  
- Run image cleanup or crop pipelines outside the main app.  
- Generate cards in batches.  
- Export a binder or a set for external analysis.

## API requirements

### Base principles

- RESTful JSON API  
- stable object IDs  
- pagination on list endpoints  
- filterable resources  
- async jobs for long-running operations  
- OpenAPI spec exposed automatically  
- usable both through Cloudflare and directly on LAN

### Authentication for API

Accepted methods:

- Cloudflare-authenticated request headers  
- optional Cloudflare service token headers  
- bearer API key for direct access

### Example endpoint families

#### Sightings

- `POST /api/sightings`  
- `GET /api/sightings`  
- `GET /api/sightings/{id}`  
- `DELETE /api/sightings/{id}`

#### Cards

- `POST /api/cards/generate/{sighting_id}`  
- `GET /api/cards`  
- `GET /api/cards/{id}`  
- `PATCH /api/cards/{id}`  
- `DELETE /api/cards/{id}`

#### Jobs

- `GET /api/jobs/{job_id}`

#### Binder

- `GET /api/binder`

#### Sets

- `GET /api/sets`  
- `POST /api/sets`  
- `GET /api/sets/{id}`  
- `PATCH /api/sets/{id}`  
- `GET /api/sets/{id}/missing`

#### Trades

- `POST /api/trades`  
- `GET /api/trades`  
- `POST /api/trades/{id}/accept`  
- `POST /api/trades/{id}/decline`

#### Species

- `GET /api/species/search`  
- `GET /api/species/{code}`

### Async job model

Bird identification and card generation may take time, so they should run as async jobs.

Pattern:

- client creates a generation request  
- server returns a `job_id`  
- client polls job status endpoint  
- result contains created card ID or failure reason

## Data model

## Sighting

Suggested fields:

- `id`  
- `user_identifier`  
- `photo_original_url`  
- `photo_thumbnail_url`  
- `submitted_at`  
- `exif_datetime`  
- `exif_lat`  
- `exif_lon`  
- `exif_camera_model`  
- `location_display_name`  
- `notes`  
- `manual_species_override`  
- `status`

## Card

Suggested fields:

- `id`  
- `sighting_id`  
- `user_identifier`  
- `species_common`  
- `species_scientific`  
- `species_code`  
- `family`  
- `pose_variant`  
- `rarity_tier`  
- `set_ids`  
- `card_number`  
- `card_art_url`  
- `id_method`  
- `id_confidence`  
- `duplicate_count`  
- `tradeable`  
- `generated_at`

## Set

Suggested fields:

- `id`  
- `creator_identifier`  
- `name`  
- `description`  
- `region`  
- `season`  
- `release_date`  
- `expiry_date`  
- `rules`  
- `card_targets`

## Trade

Suggested fields:

- `id`  
- `offered_by`  
- `offered_to`  
- `offered_card_ids`  
- `requested_card_ids`  
- `status`  
- `created_at`  
- `resolved_at`

## Pose taxonomy

The app should use a fixed pose/context vocabulary so variants stay consistent.

Initial allowed values:

- `perched_branch`  
- `in_flight`  
- `ground_foraging`  
- `water_swimming`  
- `water_wading`  
- `nest`  
- `feeder`  
- `other`

The AI model must choose from this list, and users can manually correct it.

## Rarity model

BirdBinder should ship with static rarity and taxonomy data bundled with the app by default.

Default behavior:

- include static bird frequency/taxonomy data with the app  
- use bundled data for rarity calculations out of the box

Optional behavior:

- if the host configures an eBird API key, the app may enrich or update data with live integration

## PWA requirements

BirdBinder is a PWA for convenience and installability, not for deep offline-first behavior.

Requirements:

- installable manifest  
- mobile-friendly layout  
- standalone display mode  
- app icon support  
- responsive upload and binder screens

Explicitly not required:

- offline binder browsing  
- offline queued submission  
- heavy service worker caching strategy

The purpose of the PWA is to make the web app feel more app-like on phones, especially iPhone, without requiring App Store distribution.

## Frontend recommendation

**Recommended frontend stack: SvelteKit.**

Rationale:

- good fit for a smaller, UI-heavy app  
- simpler component and state model  
- strong PWA path  
- easier to keep lightweight than a more boilerplate-heavy React stack

React remains a viable alternative, but SvelteKit is the preferred choice for v1.

## Technical architecture

Recommended stack:

- **Frontend:** SvelteKit PWA  
- **Backend:** FastAPI  
- **Database:** SQLite  
- **Object storage:** local disk or S3-compatible storage such as MinIO  
- **Async jobs:** lightweight background worker model  
- **Reverse proxy / exposure:** Cloudflare Tunnel  
- **Front-door auth:** Cloudflare Access  
- **Direct API auth:** Bearer API key  
- **Optional AI providers:** OpenAI-compatible API with configurable base URL

## Configuration

Suggested environment variables:

- `APP_URL`  
- `API_KEYS`  
- `CF_ACCESS_ENABLED`  
- `CF_TEAM_DOMAIN`  
- `AI_BASE_URL`  
- `AI_MODEL`  
- `AI_API_KEY`  
- `BIRDBINDER_ID_PROMPT`  
- `CARD_STYLE_NAME`  
- `DATABASE_URL`  
- `STORAGE_PATH`  
- `EBIRD_API_KEY` optional

Notes:

- `API_KEYS` can be a simple comma-separated list for v1.  
- `AI_BASE_URL` allows OpenAI-compatible providers.  
- `BIRDBINDER_ID_PROMPT` overrides the default identification prompt.  
- `CARD_STYLE_NAME` defines the single global BirdBinder style.  
- `EBIRD_API_KEY` is optional and only enhances the bundled static dataset behavior.

## Default identification prompt

BirdBinder should ship with a default prompt for bird identification. The host can override it in configuration.

Example default prompt behavior:

- identify the most likely bird species in the image  
- return common name, scientific name, family, confidence, and distinguishing traits  
- choose exactly one pose variant from the allowed taxonomy  
- prefer concise structured output  
- avoid hallucinating certainty when the image is ambiguous

The exact wording is an implementation detail, but configurable prompting is a product requirement.

## v1 scope

The first release should include:

- Cloudflare-protected frontend access  
- optional direct API key access  
- photo upload  
- EXIF extraction and storage  
- AI identification with manual override  
- pose assignment  
- card generation  
- binder view  
- set creation by any user  
- set completion tracking  
- duplicate support  
- basic trading flow  
- OpenAPI-documented REST API

## Out of scope for v1

- native mobile apps  
- deep offline support  
- RBAC and admin dashboard  
- public social network features  
- authenticity enforcement  
- reverse-image validation  
- automatic DSLR desktop utility  
- monetization  
- advanced market or auction mechanics  
- battle system or stats-driven gameplay

## Success criteria

BirdBinder v1 is successful if:

- trusted users can install and use it easily from phones and desktop  
- a user can go from photo upload to card creation with low friction  
- the binder feels satisfying and collectible  
- manual override makes imperfect AI acceptable  
- sets create replayability and collection goals  
- the REST API is good enough that future automation feels natural  
- the app is easy to self-host without enterprise complexity

## Milestones

### Milestone 1: Core loop

- auth  
- upload  
- sighting record  
- EXIF extraction  
- AI/manual ID  
- basic card creation  
- binder display

### Milestone 2: Sets

- create sets  
- assign cards to sets  
- completion progress  
- missing card slots

### Milestone 3: Trading and polish

- duplicate support  
- trade flow  
- improved card detail view  
- stronger art consistency

### Milestone 4: API ecosystem

- documentation cleanup  
- agent-friendly workflows  
- example integrations  
- optional live eBird enrichment

## Final decisions

| Topic | Decision |
| :---- | :---- |
| In-app authorization | None beyond trusted authenticated access |
| Frontend stack | SvelteKit preferred |
| AI provider model | OpenAI-compatible API with configurable base URL |
| Prompting | Configurable BirdBinder prompt with default prompt shipped |
| Art style ownership | One global BirdBinder style |
| Set creation | Any authenticated user can create sets |
| Database | SQLite |
| eBird data | Ship static data, optional live API integration |
| Offline support | Not required |
| DSLR workflow | Only enable via public API, no dedicated utility now |
| Direct automation auth | Support API keys in addition to Cloudflare mechanisms |
| Authenticity checks | Post-v1; only EXIF reading in v1 |

