from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.crud import get_owned_or_404, paginated_owned_list, delete_owned
from app.db import get_db
from app.dependencies import get_current_user
from app.models.binder import Binder, BinderCard
from app.models.card import Card
from app.schemas.binder import (
    BinderCreate, BinderUpdate, BinderRead, BinderList,
    BinderCardRead, AddCardToBinder,
)
from app.schemas.card import CardRead

router = APIRouter()


@router.post("/binders", response_model=BinderRead, status_code=status.HTTP_201_CREATED)
async def create_binder(
    data: BinderCreate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binder = Binder(
        user_identifier=user,
        name=data.name,
        description=data.description,
        cover_card_id=data.cover_card_id,
    )
    db.add(binder)
    await db.commit()
    await db.refresh(binder)
    return binder


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
        cc = (await db.execute(select(func.count()).select_from(BinderCard).where(BinderCard.binder_id == b.id))).scalar() or 0
        enriched.append(BinderRead.model_validate(b, from_attributes=True).model_copy(update={"card_count": cc}))
    return BinderList(items=enriched, total=total, limit=limit, offset=offset)


@router.get("/binders/{binder_id}", response_model=BinderRead)
async def get_binder(
    binder_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binder = await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")
    cc = (await db.execute(select(func.count()).select_from(BinderCard).where(BinderCard.binder_id == binder_id))).scalar() or 0
    return BinderRead.model_validate(binder, from_attributes=True).model_copy(update={"card_count": cc})


@router.get("/binders/{binder_id}/cards", response_model=list[CardRead])
async def list_binder_cards(
    binder_id: str,
    rarity: str | None = Query(default=None, description="Filter by rarity tier"),
    pose_variant: str | None = Query(default=None, description="Filter by pose variant"),
    date_from: datetime | None = Query(default=None, description="Filter cards generated after this date"),
    date_to: datetime | None = Query(default=None, description="Filter cards generated before this date"),
    duplicates_only: bool = Query(default=False, description="Only show cards with duplicate_count > 1"),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CardRead]:
    """List cards in a binder with optional filtering."""
    await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")

    # Build query: cards that are in this binder
    query = (
        select(Card)
        .join(BinderCard, BinderCard.card_id == Card.id)
        .where(BinderCard.binder_id == binder_id)
    )

    if rarity is not None:
        query = query.where(Card.rarity_tier == rarity.lower())
    if pose_variant is not None:
        query = query.where(Card.pose_variant == pose_variant.lower())
    if date_from is not None:
        query = query.where(Card.generated_at >= date_from)
    if date_to is not None:
        query = query.where(Card.generated_at <= date_to)
    if duplicates_only:
        query = query.where(Card.duplicate_count > 1)

    query = query.order_by(BinderCard.position)
    result = await db.execute(query)
    cards = result.scalars().all()
    return cards


@router.patch("/binders/{binder_id}", response_model=BinderRead)
async def update_binder(
    binder_id: str,
    data: BinderUpdate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binder = await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")
    if data.name is not None:
        binder.name = data.name
    if data.description is not None:
        binder.description = data.description
    if data.cover_card_id is not None:
        binder.cover_card_id = data.cover_card_id
    await db.commit()
    await db.refresh(binder)
    card_count_q = select(func.count()).select_from(BinderCard).where(
        BinderCard.binder_id == binder_id
    )
    cc = (await db.execute(card_count_q)).scalar() or 0
    return BinderRead.model_validate(binder, from_attributes=True).model_copy(
        update={"card_count": cc}
    )


@router.delete("/binders/{binder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binder(
    binder_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_owned(db, Binder, binder_id, user, detail="Binder not found")


@router.post(
    "/binders/{binder_id}/cards", response_model=BinderCardRead, status_code=status.HTTP_201_CREATED
)
async def add_card_to_binder(
    binder_id: str,
    data: AddCardToBinder,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify binder ownership
    await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")
    # Verify card ownership
    result = await db.execute(
        select(Card).where(Card.id == data.card_id, Card.user_identifier == user)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    # Check for duplicate
    existing = await db.execute(
        select(BinderCard).where(
            BinderCard.binder_id == binder_id, BinderCard.card_id == data.card_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Card already in binder")
    # Get next position
    if data.position is None:
        max_pos = await db.execute(
            select(func.max(BinderCard.position)).where(BinderCard.binder_id == binder_id)
        )
        position = (max_pos.scalar() or 0) + 1
    else:
        position = data.position
    bc = BinderCard(binder_id=binder_id, card_id=data.card_id, position=position)
    db.add(bc)
    await db.commit()
    await db.refresh(bc)
    return bc


@router.delete("/binders/{binder_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_card_from_binder(
    binder_id: str,
    card_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_or_404(db, Binder, binder_id, user, detail="Binder not found")
    result = await db.execute(
        select(BinderCard).where(
            BinderCard.binder_id == binder_id, BinderCard.card_id == card_id
        )
    )
    bc = result.scalar_one_or_none()
    if not bc:
        raise HTTPException(status_code=404, detail="Card not in binder")
    await db.delete(bc)
    await db.commit()
