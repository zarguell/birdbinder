# BirdBinder v3 — M4: API Ecosystem

## Tasks

### 4.1 Update README.md
- Add v2 features (activity feed, AI settings, location override, species selector)
- Add v3 features (regions, collection tracker, eBird rarity)
- Fix incorrect details (remove Alembic mention, update test count, add EBIRD_API_KEY)
- Update project structure to reflect actual files

### 4.2 Create API_GUIDE.md — Agent-friendly API reference
- Quick-start for API access (API key setup, base URL)
- Auth header examples
- All endpoint families with curl examples:
  - Sightings (create, list, get, delete, patch)
  - Cards (generate, list, get, update, delete)
  - Jobs (poll status)
  - Binders (list, add/remove cards)
  - Sets (CRUD, missing cards)
  - Trades (create, list, accept, decline)
  - Collection (progress, refresh eBird)
  - Regions (list, species)
  - Species (search, families)
  - Settings (get, patch AI config)
  - Feed (list, like, comment)
  - Auth (profile, update region)
- Error format documentation
- Pagination/filtering notes

### 4.3 Create example scripts in docs/examples/
- `upload_and_generate.sh` — bash script: upload sighting → poll job → get card
- `collection_export.py` — Python script: fetch collection progress → export CSV
- `batch_import.py` — Python script: bulk create sightings from a folder of images

## Notes
- No new backend/frontend code — pure documentation
- README is the public face, API_GUIDE is for developers/agents
- Example scripts should be self-contained and runnable with minimal setup
