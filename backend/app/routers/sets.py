from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.db import get_db
from app.dependencies import get_current_user
from app.models.set import CardSet
from app.models.card import Card
from app.schemas.set_schemas import (
    CardSetCreate, CardSetUpdate, CardSetRead, CardSetList, SetProgress,
)

router = APIRouter()


@router.post("/sets", response_model=CardSetRead, status_code=status.HTTP_201_CREATED)
async def create_set(
    data: CardSetCreate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card_set = CardSet(
        creator_identifier=user,
        name=data.name,
        description=data.description,
        region=data.region,
        season=data.season,
        release_date=data.release_date,
        expiry_date=data.expiry_date,
        rules=data.rules,
        card_targets=data.card_targets or [],
    )
    db.add(card_set)
    await db.commit()
    await db.refresh(card_set)
    return card_set


@router.get("/sets", response_model=CardSetList)
async def list_sets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sets (global, not just user's)."""
    query = select(CardSet)
    count_query = select(func.count()).select_from(CardSet)
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.order_by(CardSet.created_at.desc()).offset(offset).limit(limit))
    sets = result.scalars().all()
    return CardSetList(items=sets, total=total, limit=limit, offset=offset)


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


@router.patch("/sets/{set_id}", response_model=CardSetRead)
async def update_set(
    set_id: str,
    data: CardSetUpdate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CardSet).where(CardSet.id == set_id, CardSet.creator_identifier == user))
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(card_set, field, value)
    await db.commit()
    await db.refresh(card_set)
    return card_set


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(
    set_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CardSet).where(CardSet.id == set_id, CardSet.creator_identifier == user))
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")
    await db.delete(card_set)
    await db.commit()


@router.get("/sets/{set_id}/progress", response_model=SetProgress)
async def get_set_progress(
    set_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's progress toward completing a set."""
    result = await db.execute(select(CardSet).where(CardSet.id == set_id))
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")

    targets = card_set.card_targets or []
    if not targets:
        return SetProgress(
            set_id=card_set.id,
            set_name=card_set.name,
            total_targets=0,
            collected=0,
            missing=[],
            progress_percent=100.0,
        )

    # Get user's cards by species_code
    result = await db.execute(
        select(Card.species_code).where(
            Card.user_identifier == user,
            Card.species_code.in_(targets),
        )
    )
    collected_codes = {r[0] for r in result.all()}
    missing = [t for t in targets if t not in collected_codes]

    return SetProgress(
        set_id=card_set.id,
        set_name=card_set.name,
        total_targets=len(targets),
        collected=len(collected_codes),
        missing=missing,
        progress_percent=round(len(collected_codes) / len(targets) * 100, 1) if targets else 100.0,
    )


@router.get("/sets/{set_id}/missing", response_model=list[str])
async def get_set_missing(
    set_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return the list of species codes not yet collected by the user for a set."""
    result = await db.execute(select(CardSet).where(CardSet.id == set_id))
    card_set = result.scalar_one_or_none()
    if not card_set:
        raise HTTPException(status_code=404, detail="Set not found")

    targets = card_set.card_targets or []
    if not targets:
        return []

    # Get user's collected species codes
    result = await db.execute(
        select(Card.species_code).where(
            Card.user_identifier == user,
            Card.species_code.in_(targets),
        )
    )
    collected_codes = {r[0] for r in result.all()}
    return [t for t in targets if t not in collected_codes]
