# Simplification Cascades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate ~340 lines of duplicated code and standardize CRUD patterns across backend and frontend.

**Architecture:** Five independent cascades, each removing a family of duplication: (1) generic paginated list type, (2) shared DB engine for background workers, (3) CRUD utility functions, (4) route refactoring to use utilities, (5) frontend API factory.

**Tech Stack:** FastAPI, SQLAlchemy async + sync, Pydantic v2, Python 3.11+, Svelte 5, TypeScript.

---

### Task 1: Generic PaginatedList Type

**Removes:** 7 identical `*List` wrapper schemas (SightingList, CardList, BinderList, CardSetList, TradeList, SpeciesSearchResult + the implicit job response pattern).

**Insight:** Every paginated response has the same shape `{items: T[], total, limit, offset}`. A single generic type replaces all.

**Files:**
- Create: `backend/app/types.py`
- Modify: `backend/app/schemas/sighting.py:40-44`
- Modify: `backend/app/schemas/card.py:27-31`
- Modify: `backend/app/schemas/binder.py:37-41`
- Modify: `backend/app/schemas/set_schemas.py:44-48`
- Modify: `backend/app/schemas/trade.py:24-28`
- Modify: `backend/app/schemas/species.py:14-18`
- Modify: `backend/app/schemas/__init__.py` (update re-exports)
- Test: No test changes needed (same JSON shape, just different Python type)

- [ ] **Step 1: Create the generic type**

```python
# backend/app/types.py
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedList(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 2: Update each schema to use PaginatedList**

In `backend/app/schemas/card.py`, replace:
```python
class CardList(BaseModel):
    items: list[CardRead]
    total: int
    limit: int
    offset: int
```
with:
```python
from app.types import PaginatedList
CardList = PaginatedList[CardRead]
```

Do the same for:
- `sighting.py`: `SightingList = PaginatedList[SightingRead]`
- `binder.py`: `BinderList = PaginatedList[BinderRead]`
- `set_schemas.py`: `CardSetList = PaginatedList[CardSetRead]`
- `trade.py`: `TradeList = PaginatedList[TradeRead]`
- `species.py`: `SpeciesSearchResult = PaginatedList[SpeciesRead]`

Add `from app.types import PaginatedList` to each file.

- [ ] **Step 3: Remove old imports of concrete List types**

In each schemas file, remove the now-unnecessary explicit `class XxxList` definition.

In `backend/app/schemas/__init__.py`, add `from app.types import PaginatedList` (if there's a re-export pattern).

- [ ] **Step 4: Run tests to verify nothing broke**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: All tests pass. Paginated list endpoints return same JSON as before.

- [ ] **Step 5: Commit**

```bash
git add backend/app/types.py backend/app/schemas/
git commit -m "refactor: replace 7 identical list schemas with generic PaginatedList[T]"
```

---

### Task 2: Shared Sync Engine for Background Workers

**Removes:** Duplicate SQLAlchemy sync engine creation in two Huey task modules. Prevents future copy-paste when new background tasks are added.

**Insight:** Both `services/identifier.py` and `services/card_gen.py` independently create `_sync_engine` from the same URL transformation. There should be exactly one.

**Files:**
- Modify: `backend/app/db.py:10`
- Modify: `backend/app/services/identifier.py:14-16`
- Modify: `backend/app/services/card_gen.py:10-12`
- Test: No new tests needed (existing tests mock the sync engine indirectly via patching)

- [ ] **Step 1: Add sync engine to db.py**

In `backend/app/db.py`, append after `async_session`:
```python
_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(_sync_db_url)
```

Add the import at top:
```python
from sqlalchemy import create_engine
```

- [ ] **Step 2: Update identifier.py to use shared engine**

In `backend/app/services/identifier.py`, replace:
```python
_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
_sync_engine = create_engine(_sync_db_url)
```
with:
```python
from app.db import sync_engine as _sync_engine
```

- [ ] **Step 3: Update card_gen.py to use shared engine**

Same replacement in `backend/app/services/card_gen.py`:
```python
from app.db import sync_engine as _sync_engine
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/app/services/identifier.py backend/app/services/card_gen.py
git commit -m "refactor: consolidate duplicate sync engines into shared app.db.sync_engine"
```

---

### Task 3: CRUD Utility Functions

**Removes:** Repeated ownership-check + 404 pattern (15+ occurrences), paginated list boilerplate (6+ occurrences), and delete-with-ownership-check (4+ occurrences).

**Insight:** "Get by ID with ownership check + 404" is the same operation on every model. Paginated list is the same query + count pattern. These are functions, not copy-paste.

**Files:**
- Create: `backend/app/crud.py`
- Test: Create integration-style test for utility functions
- Modify: No route changes yet — utilities are consumed in Task 4

- [ ] **Step 1: Write utility tests**

Create `backend/tests/test_crud.py`:

```python
"""Tests for CRUD utility functions."""

import uuid
import pytest
from sqlalchemy import select
from app.models.sighting import Sighting
from app.models.card import Card


async def test_get_owned_or_404_returns_object(db_session, sighting):
    from app.crud import get_owned_or_404
    obj = await get_owned_or_404(db_session, Sighting, sighting.id, sighting.user_identifier)
    assert obj.id == sighting.id
    assert obj.notes == "Test sighting"


async def test_get_owned_or_404_raises_on_wrong_user(db_session, sighting):
    from app.crud import get_owned_or_404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_owned_or_404(db_session, Sighting, sighting.id, "other-user")
    assert exc.value.status_code == 404


async def test_get_owned_or_404_raises_on_missing_id(db_session):
    from app.crud import get_owned_or_404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_owned_or_404(db_session, Sighting, str(uuid.uuid4()), "any-user")
    assert exc.value.status_code == 404


async def test_paginated_owned_list_empty(db_session):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    items, total = await paginated_owned_list(
        db_session, Sighting, "no-sightings-user", limit=20, offset=0
    )
    assert items == []
    assert total == 0


async def test_paginated_owned_list_with_data(db_session, sighting):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    items, total = await paginated_owned_list(
        db_session, Sighting, sighting.user_identifier, limit=20, offset=0
    )
    assert len(items) == 1
    assert total == 1
    assert items[0].id == sighting.id


async def test_paginated_owned_list_respects_limit(db_session, sighting):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    # Add second sighting
    import copy
    s2 = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=sighting.user_identifier,
        photo_path=None,
        thumbnail_path=None,
        submitted_at=sighting.submitted_at,
        notes="Second sighting",
        status="pending",
    )
    db_session.add(s2)
    await db_session.commit()

    items, total = await paginated_owned_list(
        db_session, Sighting, sighting.user_identifier, limit=1, offset=0
    )
    assert len(items) == 1
    assert total == 2


async def test_delete_owned_removes_object(db_session, sighting):
    from app.crud import delete_owned
    from sqlalchemy import select
    await delete_owned(db_session, Sighting, sighting.id, sighting.user_identifier)
    # Verify gone
    result = await db_session.execute(
        select(Sighting).where(Sighting.id == sighting.id)
    )
    assert result.scalar_one_or_none() is None
```

- [ ] **Step 2: Verify tests fail (no module yet)**

```bash
cd backend && python -m pytest tests/test_crud.py -v --tb=short
```
Expected: ImportError for `app.crud`.

- [ ] **Step 3: Write CRUD utility module**

Create `backend/app/crud.py`:

```python
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


async def get_owned_or_404(
    db: AsyncSession,
    model,
    id: str,
    user: str,
    detail: str = "Not found",
    user_field: str = "user_identifier",
):
    """Get a user-owned object by ID, raising 404 if missing or not owned."""
    result = await db.execute(
        select(model).where(
            getattr(model, "id") == id,
            getattr(model, user_field) == user,
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


async def paginated_owned_list(
    db: AsyncSession,
    model,
    user: str,
    limit: int,
    offset: int,
    *filters,
    order_field: str | None = None,
    user_field: str = "user_identifier",
):
    """Paginated list of user-owned objects with optional filters."""
    base_where = getattr(model, user_field) == user
    query = select(model).where(base_where)
    count_query = select(func.count()).select_from(model).where(base_where)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar() or 0

    order_col = getattr(model, order_field) if order_field else getattr(model, "created_at")
    result = await db.execute(
        query.order_by(order_col.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()
    return items, total


async def delete_owned(
    db: AsyncSession,
    model,
    id: str,
    user: str,
    detail: str = "Not found",
    user_field: str = "user_identifier",
):
    """Delete a user-owned object by ID. Raises 404 if missing."""
    obj = await get_owned_or_404(db, model, id, user, detail=detail, user_field=user_field)
    await db.delete(obj)
    await db.commit()
```

- [ ] **Step 4: Verify tests pass**

```bash
cd backend && python -m pytest tests/test_crud.py -v --tb=short
```
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/crud.py backend/tests/test_crud.py
git commit -m "refactor: add CRUD utility functions (get_owned, paginated_list, delete_owned)"
```

---

### Task 4: Refactor Routes to Use CRUD Utilities

**Removes:** ~80 lines of boilerplate from routers. Every `select(Model).where(Model.id == id, Model.user_identifier == user)` + 404 check is replaced with a one-liner.

**Files:**
- Modify: `backend/app/routers/cards.py`
- Modify: `backend/app/routers/sightings.py`
- Modify: `backend/app/routers/binders.py`
- Modify: `backend/app/routers/sets.py`
- Modify: `backend/app/routers/trades.py`
- Modify: `backend/app/routers/species.py`
- Modify: `backend/app/routers/jobs.py`

**Key constraint:** Behavior-preserving refactor. Every endpoint must return the same status codes and response shapes.

- [ ] **Step 1: Refactor cards.py**

```python
from app.crud import get_owned_or_404, paginated_owned_list, delete_owned
from app.db import get_db
from app.dependencies import get_current_user
from app.models.card import Card
from app.models.sighting import Sighting
from app.schemas.card import CardList, CardRead

@router.post("/cards/generate/{sighting_id}", status_code=status.HTTP_202_ACCEPTED)
async def generate_card(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.card_gen import start_card_generation
    sighting = await get_owned_or_404(db, Sighting, sighting_id, user, detail="Sighting not found")
    if sighting.status != "identified":
        raise HTTPException(status_code=400, detail="Sighting must be identified before generating card")
    try:
        job_id = await start_card_generation(sighting_id, db)
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cards", response_model=CardList)
async def list_cards(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    rarity: str | None = Query(default=None),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if rarity:
        filters.append(Card.rarity_tier == rarity)
    items, total = await paginated_owned_list(db, Card, user, limit, offset, *filters, order_field="generated_at")
    return CardList(items=items, total=total, limit=limit, offset=offset)


@router.get("/cards/{card_id}", response_model=CardRead)
async def get_card(
    card_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_owned_or_404(db, Card, card_id, user, detail="Card not found")


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_owned(db, Card, card_id, user, detail="Card not found")
```

- [ ] **Step 2: Verify cards tests pass**

```bash
cd backend && python -m pytest tests/test_cards.py -v --tb=short
```
Expected: All pass.

- [ ] **Step 3: Refactor sightings.py**

Replace the `get_sighting` endpoint:
```python
@router.get("/sightings/{sighting_id}", response_model=SightingRead)
async def get_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_owned_or_404(db, Sighting, sighting_id, user, detail="Sighting not found")
```

Replace `delete_sighting`:
```python
@router.delete("/sightings/{sighting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_owned(db, Sighting, sighting_id, user, detail="Sighting not found")
```

Replace `list_sightings`:
```python
@router.get("/sightings", response_model=SightingList)
async def list_sightings(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if status_filter:
        filters.append(Sighting.status == status_filter)
    items, total = await paginated_owned_list(db, Sighting, user, limit, offset, *filters, order_field="submitted_at")
    return SightingList(items=items, total=total, limit=limit, offset=offset)
```

Replace `identify_sighting` (ownership check only):
```python
@router.post("/sightings/{sighting_id}/identify")
async def identify_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.identifier import start_identification
    sighting = await get_owned_or_404(db, Sighting, sighting_id, user, detail="Sighting not found")
    try:
        job_id = await start_identification(sighting_id, db)
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

The `update_sighting` and `create_sighting` endpoints stay as-is (they have custom logic).

- [ ] **Step 4: Verify sightings tests pass**

```bash
cd backend && python -m pytest tests/test_sightings.py -v --tb=short
```
Expected: All pass.

- [ ] **Step 5: Refactor binders.py**

Replace `get_binder` (simplify the 404 + ownership):
```python
@router.get("/binders/{binder_id}", response_model=BinderRead)
async def get_binder(
    binder_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binder = await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")
    card_count_q = select(func.count()).select_from(BinderCard).where(BinderCard.binder_id == binder_id)
    cc = (await db.execute(card_count_q)).scalar() or 0
    return BinderRead.model_validate(binder, from_attributes=True).model_copy(update={"card_count": cc})
```

Replace `list_binders`:
```python
@router.get("/binders", response_model=BinderList)
async def list_binders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await paginated_owned_list(db, Binder, user, limit, offset, order_field="updated_at")
    enriched = []
    for b in items:
        card_count_q = select(func.count()).select_from(BinderCard).where(BinderCard.binder_id == b.id)
        cc = (await db.execute(card_count_q)).scalar() or 0
        enriched.append(
            BinderRead.model_validate(b, from_attributes=True).model_copy(update={"card_count": cc})
        )
    return BinderList(items=enriched, total=total, limit=limit, offset=offset)
```

Replace `delete_binder`:
```python
@router.delete("/binders/{binder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binder(
    binder_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_owned(db, Binder, binder_id, user, detail="Binder not found")
```

Replace ownership check in `list_binder_cards`, `add_card_to_binder`, `remove_card_from_binder`, and `update_binder`:
- `list_binder_cards`: `await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")`
- `add_card_to_binder`: same
- `remove_card_from_binder`: same
- `update_binder`: same

- [ ] **Step 6: Verify binder tests pass**

```bash
cd backend && python -m pytest tests/test_binders.py -v --tb=short
```
Expected: All pass.

- [ ] **Step 7: Refactor sets.py**

Replace `get_set`, `delete_set`:
```python
@router.get("/sets/{set_id}", response_model=CardSetRead)
async def get_set(
    set_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CardSet).where(CardSet.id == set_id))
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")
    return card_set
```
(Sets are global — no user ownership filter, so `get_owned_or_404` doesn't apply. Keep as-is but note this is the exception.)

Replace `list_sets` with `paginated_owned_list` if it uses user filtering, or keep as-is if truly global. Looking at the original code, sets are global (no user filter), so keep list_sets as-is.

Replace `delete_set` (uses creator_identifier instead of user_identifier — this is a different ownership model):
```python
@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(
    set_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CardSet).where(CardSet.id == set_id, CardSet.creator_identifier == user)
    )
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")
    await db.delete(card_set)
    await db.commit()
```
(Sets use `creator_identifier` not `user_identifier` — keep as-is since the field name differs. The utility functions accept `user_field` parameter so they could be used, but it's a judgement call.)

- [ ] **Step 8: Verify sets tests pass**

```bash
cd backend && python -m pytest tests/test_sets.py -v --tb=short
```
Expected: All pass.

- [ ] **Step 9: Refactor remaining routers**

Apply the same `get_owned_or_404` pattern to:
- `trades.py` `get_trade` (note: trades use `offered_by`/`offered_to`, not straight ownership — keep custom logic)
- `jobs.py` `get_job_status` (no user ownership — keep as-is)

- [ ] **Step 10: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 11: Commit**

```bash
git add backend/app/routers/
git commit -m "refactor: replace repetitive CRUD boilerplate with utility functions"
```

---

### Task 5: Frontend API Client Factory

**Removes:** ~90 lines of repetitive CRUD wrappers in `api.ts`. Every resource has the same `list(params)`, `get(id)`, `create(data)`, `delete(id)` pattern.

**Insight:** CRUD over `/resource/{id}` is a one-expression factory call, not 10-line blocks.

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add query string helper and CRUD factory**

Replace the imports/additions section of `api.ts`:

```typescript
import { z } from 'zod';  // Only if adding types; skip for now

const API_BASE = '/api';

function qs(params?: Record<string, string | number | undefined | null>): string {
    if (!params) return '';
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) q.set(k, String(v));
    }
    const s = q.toString();
    return s ? `?${s}` : '';
}

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

type PaginatedResponse<T> = { items: T[]; total: number; limit: number; offset: number };

function crud<T = any>(path: string, options?: { listName?: string }) {
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
```

- [ ] **Step 2: Replace all resource blocks with factory calls**

Replace the entire resource section of `api.ts`:

```typescript
export const cards = crud<any>('cards');
export const binders = crud<any>('binders');
export const sets = crud<any>('sets');
export const trades = crud<any>('trades');

export const sightings = {
    ...crud<any>('sightings'),
    upload: (file: File) => {
        const form = new FormData();
        form.append('file', file);
        return fetch(`${API_BASE}/sightings`, { method: 'POST', body: form }).then(async (res) => {
            if (!res.ok) throw new ApiError(res.status, await res.text());
            return res.json();
        });
    },
    overrideSpecies: (id: string, speciesCode: string, speciesCommon: string) =>
        request<any>(`/sightings/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ species_code: speciesCode, species_common: speciesCommon })
        })
};

export const species = {
    search: (query: string) => request<any>(`/species/search?q=${encodeURIComponent(query)}`)
};

export const jobs = {
    get: (id: string) => request<any>(`/jobs/${id}`)
};
```

The `crud()` factory covers `list()`, `get()`, `create()`, `update()`, `delete()` for cards, binders, sets, and trades. Sightings keeps its custom `upload` and `overrideSpecies` endpoints on top of the factory. Species and jobs stay custom (they don't fit the CRUD pattern).

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds. No type errors (everything is `<any>`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "refactor: replace repetitive CRUD blocks with generic factory in api.ts"
```

---

### Task 6: Fix `rarity_tier` Scope Bug in card_gen.py (Bonus)

**Bug:** In `_run_card_generation()`, the `species_info` dict used for AI art generation references `rarity_tier` before it's been updated with the real rarity lookup. The AI art prompt always receives `"common"` even for rare/epic/legendary birds.

**Files:**
- Modify: `backend/app/services/card_gen.py`

- [ ] **Step 1: Move rarity lookup before species_info construction**

In `backend/app/services/card_gen.py`, within `_run_card_generation()`, move the rarity lookup block before the AI card art section:

```python
# Get rarity tier (must be before species_info for AI art)
rarity_tier = "common"
try:
    from app.services.rarity import get_rarity_tier
    rarity_tier = get_rarity_tier(sighting.species_code)
except ImportError:
    pass

# Determine card art URL
card_art_url = None
if settings.ai_api_key:
    try:
        import asyncio
        from app.services.ai import generate_card_art

        species_info = {
            "common_name": sighting.species_common or "Unknown",
            "scientific_name": sighting.species_scientific or "Unknown",
            "pose_variant": sighting.pose_variant or "perching",
            "rarity_tier": rarity_tier,  # now correctly set
        }
        art_path = asyncio.get_event_loop().run_until_complete(
            generate_card_art(
                image_path=sighting.photo_path or "",
                species_info=species_info,
            )
        )
        if art_path:
            card_art_url = f"/api/storage/{art_path}"
    except Exception:
        card_art_url = None

# Fallback
if not card_art_url and sighting.photo_path:
    card_art_url = f"/api/storage/{sighting.photo_path}"

# Remove the duplicate rarity lookup that was here before
```

- [ ] **Step 2: Run tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/card_gen.py
git commit -m "fix: move rarity lookup before species_info so AI art prompt gets correct rarity_tier"
```

---

### Full Verification

- [ ] **Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Run frontend build**

```bash
cd frontend && npm run build
```

- [ ] **Final summary commit (if any dangling changes)**

```bash
git status
```
