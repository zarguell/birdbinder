# BirdBinder v3 — Collection Tracker, eBird Live Rarity, User Region

> **For Hermes:** Use subagent-driven-development skill (CI-gated variant) to implement this plan task-by-task.

**Goal:** Add species collection tracking, eBird live rarity enrichment, and user region configuration so users can track their discovered species against a regional checklist and see real rarity data.

**Architecture:** Three feature streams. Stream 1 (Region) is infrastructure that Streams 2 (Collection) and 3 (eBird) depend on. User model gets a `region` column. A new `regions.json` data file provides region metadata + species code lists derived from audio-birdle's US data. Collection endpoint cross-references user's cards against regional species list. eBird API fetches regional frequency data with TTL cache in AppSetting table.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (async), Pydantic V2, SvelteKit 2, Tailwind CSS 4. Tests: pytest with asyncio plugin, conftest fixtures.

**Key facts:**
- 11,145 global species in `backend/app/data/birds.json` (fields: species_code, common_name, scientific_name, family, family_code, taxon_order, order)
- 704 US species from audio-birdle — all codes already exist in birdbinder's birds.json
- audio-birdle regions: `us` (704 birds), `us-lower48` (subset)
- User model at `backend/app/models/user.py` — fields: id, email, display_name, avatar_path, created_at, updated_at
- AppSetting model at `backend/app/models/app_setting.py` — key-value store for UI-configurable settings
- Card model has `species_code`, `rarity_tier`, `user_identifier`
- Static rarity in `backend/app/services/rarity.py` — family-based heuristics with deterministic hash
- SpeciesCache model at `backend/app/models/species.py` — species_code, common_name, scientific_name, etc.
- Tests run from `backend/.venv` — command: `cd backend && source .venv/bin/activate && python -m pytest tests/ -v`
- `from __future__ import annotations` must be FIRST import in Python files
- Svelte 5 with rolldown (Vite 8) — NO `onmousedown|preventDefault` syntax, use inline `(e) => { e.preventDefault(); ... }`
- Alembic NOT set up — schema changes rely on SQLite tolerance for new columns
- No `profile` router in backend — profile API lives elsewhere. The `User` model maps to authenticated users.

---

## Stream 1: User Region Configuration

### Task 1.1: Add region field to User model + regions data file

**Objective:** Add `region` column to User model and create `regions.json` data file with US species code lists.

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/app/data/regions.json`
- Test: `backend/tests/test_collection.py` (new file for all collection tests)

**Step 1: Create regions.json data file**

Build a regions file with species code lists. Use audio-birdle data as the source for US species:

```bash
cd backend && source .venv/bin/activate && python3 -c "
import json

# Load birdbinder species for metadata
with open('app/data/birds.json') as f:
    bb_birds = {b['species_code']: b for b in json.load(f)}

# Load audio-birdle US birds
with open('/opt/data/home/repos/audio-birdle/public/data/birds.json') as f:
    ab_data = json.load(f)

us_birds = ab_data.get('us', [])
us_codes = [b['id'] for b in us_birds]

# Build enriched region entries
species_list = []
for code in us_codes:
    meta = bb_birds.get(code, {})
    species_list.append({
        'species_code': code,
        'common_name': meta.get('common_name', ''),
        'scientific_name': meta.get('scientific_name', ''),
        'family': meta.get('family', ''),
        'taxon_order': meta.get('taxon_order', 99999),
    })

regions = {
    'regions': [
        {
            'id': 'us',
            'name': 'United States',
            'country': 'US',
            'species_count': len(species_list),
            'species_codes': [s['species_code'] for s in sorted(species_list, key=lambda x: x['taxon_order'])],
        },
        {
            'id': 'us-lower48',
            'name': 'US Lower 48',
            'country': 'US',
            'species_count': len(species_list) - 10,  # approximate, we'll refine
            'species_codes': [],  # populated from eBird subregion data or filter of us
        },
    ]
}

with open('app/data/regions.json', 'w') as f:
    json.dump(regions, f, indent=2)

print(f'US species: {len(species_list)}')
"
```

Note: For us-lower48, exclude Alaska/Hawaii species. A simple approach: hardcode known AK/HI-only codes or derive from audio-birdle's `excludedSubregions` logic. For v1, `us` (all 704) is the primary region. `us-lower48` can be a subset.

**Step 2: Add region column to User model**

In `backend/app/models/user.py`, add:
```python
region: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

**Step 3: Write failing test**

```python
# backend/tests/test_collection.py
import pytest
from app.models.user import User

async def test_user_region_field(db_session):
    """User model should accept a region value."""
    user = User(email="test@example.com", region="us")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.region == "us"
```

**Step 4: Run test to verify pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py::test_user_region_field -v`
Expected: PASS (SQLite allows new columns)

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add region field to User model and regions data file"
```

### Task 1.2: Region service — load regions, list available regions

**Objective:** Service layer to load region data from JSON and expose available regions.

**Files:**
- Create: `backend/app/services/region_service.py`
- Test: `backend/tests/test_collection.py`

**Step 1: Write failing test**

```python
async def test_get_available_regions():
    """Should return list of regions with species counts."""
    from app.services.region_service import get_available_regions
    regions = get_available_regions()
    assert len(regions) >= 1
    us = next((r for r in regions if r['id'] == 'us'), None)
    assert us is not None
    assert us['species_count'] > 0
    assert len(us['species_codes']) == us['species_count']


async def test_get_region_species():
    """Should return species list for a specific region."""
    from app.services.region_service import get_region_species
    species = get_region_species("us")
    assert len(species) == 704
    assert species[0]['species_code']  # first entry has a code
    # Should be sorted by taxon_order
    orders = [s['taxon_order'] for s in species]
    assert orders == sorted(orders)


async def test_get_region_species_invalid():
    """Should raise for unknown region."""
    from app.services.region_service import get_region_species
    with pytest.raises(ValueError):
        get_region_species("antarctica")
```

**Step 2: Implement region_service.py**

```python
# backend/app/services/region_service.py
from __future__ import annotations

import json
from pathlib import Path

_data_path = Path(__file__).parent.parent / "data" / "regions.json"
_cache: dict | None = None


def _load_data() -> dict:
    global _cache
    if _cache is None:
        with open(_data_path) as f:
            _cache = json.load(f)
    return _cache


def get_available_regions() -> list[dict]:
    data = _load_data()
    return data["regions"]


def get_region_species(region_id: str) -> list[dict]:
    data = _load_data()
    region = next((r for r in data["regions"] if r["id"] == region_id), None)
    if not region:
        raise ValueError(f"Unknown region: {region_id}")
    codes = region["species_codes"]
    # Load bird metadata
    birds_path = Path(__file__).parent.parent / "data" / "birds.json"
    with open(birds_path) as f:
        all_birds = {b["species_code"]: b for b in json.load(f)}
    species_list = []
    for code in codes:
        meta = all_birds.get(code, {})
        species_list.append({
            "species_code": code,
            "common_name": meta.get("common_name", code),
            "scientific_name": meta.get("scientific_name", ""),
            "family": meta.get("family", ""),
            "taxon_order": meta.get("taxon_order", 99999),
        })
    return sorted(species_list, key=lambda x: x["taxon_order"])


def get_region_codes(region_id: str) -> set[str]:
    """Return set of species codes for a region."""
    data = _load_data()
    region = next((r for r in data["regions"] if r["id"] == region_id), None)
    if not region:
        raise ValueError(f"Unknown region: {region_id}")
    return set(region["species_codes"])
```

**Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add region service with species list loading"
```

### Task 1.3: Region API endpoints + profile region setting

**Objective:** Add region list endpoint and allow users to set their region via profile/settings.

**Files:**
- Create: `backend/app/routers/collection.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_collection.py`
- Modify: `frontend/src/lib/api.ts` (add collection + profile region API)
- Modify: `frontend/src/routes/settings/+page.svelte` (add region picker)

**Step 1: Write failing test**

```python
async def test_list_regions(auth_client):
    resp = await auth_client.get("/api/regions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    us = next((r for r in data if r["id"] == "us"), None)
    assert us is not None
    assert us["species_count"] == 704


async def test_set_user_region(auth_client, db_session):
    resp = await auth_client.patch("/api/profile", json={"region": "us"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "us"


async def test_set_user_region_invalid(auth_client):
    resp = await auth_client.patch("/api/profile", json={"region": "mars"})
    assert resp.status_code == 422
```

**Step 2: Create collection router**

```python
# backend/app/routers/collection.py
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.services.region_service import get_available_regions, get_region_species

router = APIRouter()


@router.get("/regions")
async def list_regions(user: str = Depends(get_current_user)):
    """List available regions with species counts."""
    return get_available_regions()


@router.get("/regions/{region_id}/species")
async def list_region_species(
    region_id: str,
    user: str = Depends(get_current_user),
):
    """List all species in a region."""
    return get_region_species(region_id)
```

**Step 3: Register in main.py**

Add to main.py:
```python
from app.routers.collection import router as collection_router
app.include_router(collection_router.router, prefix="/api", tags=["collection"])
```

**Step 4: Add region to profile PATCH**

Find the existing profile PATCH endpoint. It likely accepts `display_name`. Add `region` to the accepted fields. Check `backend/app/routers/auth.py` or wherever profile endpoints live.

**Step 5: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: add region list API and profile region setting"
```

### Task 1.4: Frontend region picker in settings

**Objective:** Add region dropdown to settings page so users can pick their region.

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/routes/settings/+page.svelte`

**Step 1: Add API methods to api.ts**

```typescript
// Collection
export const collection = {
    regions: () => request<any[]>('/regions'),
    regionSpecies: (regionId: string) => request<any[]>(`/regions/${regionId}/species`),
};

// Update profile to include region
// In the existing profile.update, add region to the data type
```

Also update `profile.update` call type to include `region?: string`.

**Step 2: Add region picker to settings page**

In `settings/+page.svelte`, add a section:
- Dropdown populated from `collection.regions()` API
- On change, call `profile.update({ region: selectedRegion })`
- Show current region with a badge

**Step 3: Verify manually**

Open settings → select "United States" → save → verify profile returns `region: "us"`.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add region picker to settings page"
```

---

## Stream 2: Collection Tracker

### Task 2.1: Collection progress backend endpoint

**Objective:** API endpoint that returns user's collection progress: total species in region, discovered species, missing species, grouped by family.

**Files:**
- Modify: `backend/app/routers/collection.py`
- Test: `backend/tests/test_collection.py`

**Step 1: Write failing tests**

```python
async def test_collection_progress(auth_client, db_session):
    """GET /api/collection/progress should return collection stats."""
    resp = await auth_client.get("/api/collection/progress")
    assert resp.status_code == 200
    data = resp.json()
    # Should have basic structure even without cards
    assert "total_species" in data
    assert "discovered_count" in data
    assert "discovered" in data
    assert "missing" in data


async def test_collection_progress_with_cards(auth_client, db_session, sample_card):
    """Should count user's cards as discovered."""
    resp = await auth_client.get("/api/collection/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["discovered_count"] >= 1
    # The card's species should be in discovered list
    species_codes = [s["species_code"] for s in data["discovered"]]
    assert sample_card.species_code in species_codes


async def test_collection_progress_family_groups(auth_client):
    """Should group species by family."""
    resp = await auth_client.get("/api/collection/progress?family_group=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "family_groups" in data
    assert len(data["family_groups"]) > 0
    fg = data["family_groups"][0]
    assert "family" in fg
    assert "total" in fg
    assert "discovered" in fg
```

**Step 2: Implement collection progress endpoint**

```python
@router.get("/collection/progress")
async def get_collection_progress(
    family_group: bool = Query(default=False),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get user's region from User table
    from app.models.user import User
    result = await db.execute(select(User).where(User.email == user))
    user_obj = result.scalar_one_or_none()

    # Default to "us" if no region set
    region_id = "us"
    if user_obj and user_obj.region:
        region_id = user_obj.region

    region_codes = get_region_codes(region_id)

    # Get user's distinct species codes from cards
    result = await db.execute(
        select(Card.species_code).where(
            Card.user_identifier == user,
            Card.species_code.in_(region_codes) if region_codes else True,
        ).distinct()
    )
    discovered_codes = {row[0] for row in result.all()}

    # Build discovered species list with metadata
    all_species = get_region_species(region_id)
    species_map = {s["species_code"]: s for s in all_species}

    discovered = [species_map[code] for code in discovered_codes if code in species_map]
    discovered.sort(key=lambda x: x["taxon_order"])

    missing_codes = region_codes - discovered_codes
    missing = [species_map[code] for code in missing_codes if code in species_map]
    missing.sort(key=lambda x: x["taxon_order"])

    response = {
        "region": region_id,
        "total_species": len(region_codes),
        "discovered_count": len(discovered),
        "progress_percent": round(len(discovered) / len(region_codes) * 100, 1) if region_codes else 0,
        "discovered": discovered,
        "missing": missing,
    }

    if family_group:
        # Group all species (discovered + missing) by family
        family_map: dict[str, dict] = {}
        for species in all_species:
            fam = species.get("family", "Unknown")
            if fam not in family_map:
                family_map[fam] = {"family": fam, "total": 0, "discovered": 0, "species": []}
            family_map[fam]["total"] += 1
            is_found = species["species_code"] in discovered_codes
            if is_found:
                family_map[fam]["discovered"] += 1
            family_map[fam]["species"].append({**species, "found": is_found})

        response["family_groups"] = sorted(family_map.values(), key=lambda x: -x["discovered"])

    return response
```

**Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add collection progress endpoint with family grouping"
```

### Task 2.2: Collection grid frontend page

**Objective:** Create `/collection` page showing species grid with discovered/mystery cards, family grouping, progress bar, and stats.

**Files:**
- Create: `frontend/src/routes/collection/+page.svelte`
- Modify: `frontend/src/lib/api.ts` (add collection API)

**Step 1: Add collection API methods**

```typescript
// In api.ts, add to collection object:
progress: (params?: { family_group?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.family_group) q.set('family_group', 'true');
    return request<any>(`/collection/progress?${q}`);
},
```

**Step 2: Create collection page**

Build `/collection/+page.svelte` with:

1. **Header section:**
   - Progress bar (X / 704 species)
   - Percentage badge
   - Region label

2. **Family group view** (default):
   - Cards for each family showing: family name, X/Y discovered, mini progress bar
   - Expand to see species grid within family

3. **Flat grid view** (toggle):
   - All species in region as small cards
   - Discovered species: show bird name, common name, card art thumbnail if available
   - Mystery species: show "❓" with question mark icon, family hint

4. **Stats sidebar/section:**
   - Rarity breakdown: how many common/uncommon/rare/epic/legendary discovered
   - Biggest family completion % leaders

5. **Styling:**
   - Use existing Tailwind patterns from binder page
   - Card grid responsive (2 cols mobile, 3-4 cols tablet, 6 cols desktop)
   - Mystery cards slightly faded/dimmed

**Step 3: Verify manually**

Open /collection → see grid with progress → expand a family → see discovered vs mystery species.

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add collection tracker page with species grid"
```

### Task 2.3: Collection navigation integration

**Objective:** Add collection link to main navigation.

**Files:**
- Modify: `frontend/src/routes/+layout.svelte` (add nav link)

**Step 1: Add nav link**

In the main navigation (check layout.svelte for existing nav pattern), add a "Collection" link pointing to `/collection`. Use a field guide or grid icon.

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add collection link to navigation"
```

---

## Stream 3: eBird Live Rarity

### Task 3.1: eBird API service with TTL cache

**Objective:** Service that fetches regional frequency data from eBird API and caches it with a configurable TTL.

**Files:**
- Create: `backend/app/services/ebird_service.py`
- Test: `backend/tests/test_collection.py`

**Step 1: Write failing tests**

```python
async def test_ebird_api_key_from_settings(db_session):
    """Should read eBird API key from AppSetting or env."""
    from app.services.ebird_service import get_ebird_api_key
    # Without key set, should return None
    key = get_ebird_api_key(db_session)
    assert key is None  # No key configured in test


async def test_ebird_frequency_cache_ttl():
    """Cached data should respect TTL."""
    from app.services.ebird_service import FrequencyCache
    cache = FrequencyCache(ttl_seconds=60)
    cache.set("US", "norewe", 0.05)
    assert cache.get("US", "norewe") == 0.05


async def test_ebird_frequency_cache_expiry():
    """Expired entries should return None."""
    import time
    from app.services.ebird_service import FrequencyCache
    cache = FrequencyCache(ttl_seconds=0)  # instant expiry
    cache.set("US", "norewe", 0.05)
    assert cache.get("US", "norewe") is None


async def test_get_rarity_tier_live():
    """Should return a tier when eBird data is available."""
    from app.services.ebird_service import get_ebird_rarity_tier
    tier = get_ebird_rarity_tier("US", "norcar", frequency=0.85)
    assert tier in ["common", "uncommon", "rare", "epic", "legendary"]
    # Very high frequency should be common
    tier_rare = get_ebird_rarity_tier("US", "somebird", frequency=0.001)
    assert tier_rare in ["rare", "epic", "legendary"]
```

**Step 2: Implement ebird_service.py**

```python
# backend/app/services/ebird_service.py
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

TIERS = ["common", "uncommon", "rare", "epic", "legendary"]

# eBird frequency thresholds for rarity tiers
FREQUENCY_THRESHOLDS = {
    "common": 0.10,      # seen in >10% of checklists
    "uncommon": 0.03,    # 3-10% of checklists
    "rare": 0.005,       # 0.5-3% of checklists
    "epic": 0.001,       # 0.1-0.5% of checklists
    "legendary": 0.0,    # <0.1% of checklists
}


class FrequencyCache:
    """In-memory cache for eBird frequency data with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self._data: dict[str, dict[str, float]] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl_seconds

    def set(self, region: str, species_code: str, frequency: float) -> None:
        if region not in self._data:
            self._data[region] = {}
        self._data[region][species_code] = frequency
        self._timestamps[region] = time.time()

    def get(self, region: str, species_code: str) -> float | None:
        region_data = self._data.get(region, {})
        if species_code not in region_data:
            return None
        ts = self._timestamps.get(region, 0)
        if time.time() - ts > self._ttl:
            return None
        return region_data[species_code]

    def get_all(self, region: str) -> dict[str, float] | None:
        if region not in self._data:
            return None
        ts = self._timestamps.get(region, 0)
        if time.time() - ts > self._ttl:
            return None
        return self._data[region]

    def clear(self, region: str | None = None) -> None:
        if region:
            self._data.pop(region, None)
            self._timestamps.pop(region, None)
        else:
            self._data.clear()
            self._timestamps.clear()


# Global cache instance (lives in process memory)
_cache = FrequencyCache(ttl_seconds=3600)  # 1 hour TTL


def get_ebird_api_key(db=None) -> str | None:
    """Get eBird API key from DB settings or env var."""
    import os
    # Check env first
    key = os.environ.get("EBIRD_API_KEY")
    if key:
        return key
    # Check DB (if session provided)
    if db is not None:
        from app.services.settings_service import get_effective_setting
        key = get_effective_setting(db, "ebird_api_key")
        if key:
            return key
    return None


def get_ebird_rarity_tier(
    region: str,
    species_code: str,
    frequency: float | None = None,
) -> str:
    """Convert eBird frequency to rarity tier."""
    if frequency is None:
        return "common"  # No data = assume common

    if frequency >= FREQUENCY_THRESHOLDS["common"]:
        return "common"
    elif frequency >= FREQUENCY_THRESHOLDS["uncommon"]:
        return "uncommon"
    elif frequency >= FREQUENCY_THRESHOLDS["rare"]:
        return "rare"
    elif frequency >= FREQUENCY_THRESHOLDS["epic"]:
        return "epic"
    else:
        return "legendary"


async def fetch_region_frequencies(
    region: str,
    api_key: str,
) -> dict[str, float]:
    """Fetch frequency data for all species in a region from eBird API.

    Uses the eBird Regional Frequency endpoint:
    https://api.ebird.org/v2/product/regional-stats/{region}
    """
    url = f"https://api.ebird.org/v2/product/regional-stats/{region}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url,
            headers={"X-eBirdApiToken": api_key},
            params={"month": datetime.now(timezone.utc).month},
        )
        resp.raise_for_status()
        data = resp.json()

    frequencies: dict[str, float] = {}
    for entry in data:
        # eBird regional stats returns species with frequency info
        if "howMany" in entry and "speciesCode" in entry:
            # Frequency is in the "howMany" or "frequency" field depending on endpoint
            freq = entry.get("frequency", entry.get("howMany", 0))
            if isinstance(freq, (int, float)):
                frequencies[entry["speciesCode"]] = float(freq) / 100.0  # normalize to 0-1

    logger.info("Fetched eBird frequencies for %s: %d species", region, len(frequencies))
    return frequencies


async def get_live_frequency(
    region: str,
    species_code: str,
    db=None,
) -> float | None:
    """Get frequency for a species, using cache or fetching from eBird."""
    # Check cache first
    cached = _cache.get(region, species_code)
    if cached is not None:
        return cached

    # Need to fetch from eBird
    api_key = get_ebird_api_key(db)
    if not api_key:
        return None

    try:
        all_freqs = await fetch_region_frequencies(region, api_key)
        # Cache all frequencies for this region
        for code, freq in all_freqs.items():
            _cache.set(region, code, freq)
        return all_freqs.get(species_code)
    except Exception:
        logger.warning("Failed to fetch eBird frequencies for %s", region, exc_info=True)
        return None
```

**Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add eBird API service with frequency cache"
```

### Task 3.2: Integrate eBird rarity into card generation + rarity endpoint

**Objective:** When generating cards, check eBird live frequency data to override static rarity tier. Add an API endpoint to manually refresh eBird data.

**Files:**
- Modify: `backend/app/services/rarity.py` (add live rarity lookup)
- Modify: `backend/app/services/card_gen.py` (use live rarity when available)
- Modify: `backend/app/routers/collection.py` (add refresh endpoint)
- Test: `backend/tests/test_collection.py`

**Step 1: Write failing test**

```python
async def test_rarity_with_ebird_data():
    """Should prefer eBird frequency over static rarity when available."""
    from app.services.rarity import get_rarity_tier
    from app.services.ebird_service import _cache
    # Northern Cardinal — static says "common" (passerine)
    # With eBird showing very low frequency, should change
    _cache.set("US", "norcar", 0.001)
    tier = get_rarity_tier("norcar", region="US")
    assert tier != "common"  # Should be rare/epic/legendary


async def test_rarity_falls_back_to_static():
    """Should use static rarity when no eBird data available."""
    from app.services.rarity import get_rarity_tier
    from app.services.ebird_service import _cache
    _cache.clear()  # Clear cache
    tier = get_rarity_tier("norcar")
    assert tier == "common"  # Passerine = common
```

**Step 2: Update rarity.py get_rarity_tier signature**

Add optional `region` parameter. If region is provided and eBird cache has data, use live rarity:

```python
def get_rarity_tier(
    species_code: str | None,
    family: str | None = None,
    region: str | None = None,
) -> str:
    # Check eBird live data first
    if region and species_code:
        try:
            from app.services.ebird_service import _cache
            freq = _cache.get(region, species_code)
            if freq is not None:
                return get_ebird_rarity_tier(region, species_code, frequency=freq)
        except Exception:
            pass

    # Fall back to static family-based rarity (existing logic)
    # ... rest of existing function ...
```

**Step 3: Update card_gen.py**

When creating a card, pass the user's region to `get_rarity_tier()`:

```python
# In card_gen.py, where rarity is assigned:
from app.services.region_service import get_region_codes  # or get user's region
user_region = "us"  # get from user object
rarity = get_rarity_tier(species_code, family=family, region=user_region)
```

**Step 4: Add eBird refresh endpoint**

```python
# In collection router
@router.post("/collection/refresh-ebird")
async def refresh_ebird_data(
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a refresh of eBird frequency data for user's region."""
    from app.services.ebird_service import get_ebird_api_key, fetch_region_frequencies, _cache
    api_key = get_ebird_api_key(db)
    if not api_key:
        raise HTTPException(status_code=400, detail="eBird API key not configured")
    
    # Get user's region
    from app.models.user import User
    result = await db.execute(select(User).where(User.email == user))
    user_obj = result.scalar_one_or_none()
    region = user_obj.region if user_obj else "us"
    
    try:
        frequencies = await fetch_region_frequencies(region, api_key)
        for code, freq in frequencies.items():
            _cache.set(region, code, freq)
        return {"status": "refreshed", "region": region, "species_count": len(frequencies)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"eBird API error: {str(e)}")
```

**Step 5: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_collection.py -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: integrate eBird live rarity into card generation"
```

### Task 3.3: eBird API key settings UI + collection page eBird badge

**Objective:** Add eBird API key field to settings page and show data source badge on collection page.

**Files:**
- Modify: `backend/app/schemas/set_schemas.py` — N/A, use AppSetting whitelist
- Modify: `backend/app/services/settings_service.py` (add `ebird_api_key` to whitelist)
- Modify: `frontend/src/routes/settings/+page.svelte` (add eBird key field)
- Modify: `frontend/src/routes/collection/+page.svelte` (add eBird badge + refresh button)

**Step 1: Add ebird_api_key to settings whitelist**

In `backend/app/services/settings_service.py`, add `"ebird_api_key"` to the `ALLOWED_KEYS` set.

**Step 2: Add eBird section to settings page**

Below AI settings, add:
- eBird API Key input (password field, masked)
- Test Connection button (calls `/collection/refresh-ebird`, shows result)
- Note: "Optional. Enables live rarity data from eBird instead of static estimates."

**Step 3: Add eBird badge to collection page**

On the collection progress page:
- Show "Static Rarity" or "Live eBird" badge depending on whether API key is configured
- "Refresh Data" button (calls `/collection/refresh-ebird`)
- Last refresh timestamp

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add eBird API key settings and live rarity badge"
```

---

## Summary

| Stream | Tasks | Dependencies |
|--------|-------|-------------|
| 1. Region | 1.1-1.4 | None |
| 2. Collection | 2.1-2.3 | Stream 1 |
| 3. eBird | 3.1-3.3 | Stream 1 (uses region) |

**Parallelization:**
- Tasks 1.1 and 1.2 are sequential (1.2 depends on regions.json from 1.1)
- Task 1.3 backend can run after 1.2, Task 1.4 frontend can run after 1.3 backend
- Tasks 2.1 and 2.2 can run together once 1.3 backend is done
- Tasks 3.1, 3.2, 3.3 are sequential

**Recommended execution order:**
1.1 → 1.2 → 1.3 (backend) → [1.4 (frontend) + 2.1 (backend) + 3.1 (backend)] in parallel → 2.2 (frontend) → 3.2 → 3.3

**New files created:**
- `backend/app/data/regions.json`
- `backend/app/services/region_service.py`
- `backend/app/services/ebird_service.py`
- `backend/app/routers/collection.py`
- `backend/tests/test_collection.py`
- `frontend/src/routes/collection/+page.svelte`

**Modified files:**
- `backend/app/models/user.py` (add region column)
- `backend/app/main.py` (register collection router)
- `backend/app/services/rarity.py` (add region param for live lookup)
- `backend/app/services/card_gen.py` (pass region to rarity)
- `backend/app/services/settings_service.py` (add ebird_api_key to whitelist)
- `frontend/src/lib/api.ts` (add collection + region API methods)
- `frontend/src/routes/settings/+page.svelte` (region picker + eBird key)
- `frontend/src/routes/+layout.svelte` (nav link)
