from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.binder import BinderCard
from app.models.card import Card
from app.models.sighting import Sighting
from app.schemas.card import CardList, CardRead

router = APIRouter()


@router.post("/cards/generate/{sighting_id}", status_code=status.HTTP_202_ACCEPTED)
async def generate_card(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a card from an identified sighting."""
    from app.services.card_gen import start_card_generation

    # Verify ownership
    result = await db.execute(
        select(Sighting).where(
            Sighting.id == sighting_id, Sighting.user_identifier == user
        )
    )
    sighting = result.scalar_one_or_none()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")
    if sighting.status != "identified":
        raise HTTPException(
            status_code=400, detail="Sighting must be identified before generating card"
        )

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
    """List cards for the authenticated user, optionally filtered by rarity."""
    query = select(Card).where(Card.user_identifier == user)
    count_query = (
        select(func.count()).select_from(Card).where(Card.user_identifier == user)
    )

    if rarity:
        query = query.where(Card.rarity_tier == rarity)
        count_query = count_query.where(Card.rarity_tier == rarity)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Card.generated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    cards = result.scalars().all()

    return CardList(items=cards, total=total, limit=limit, offset=offset)


@router.get("/cards/{card_id}", response_model=CardRead)
async def get_card(
    card_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single card by ID."""
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_identifier == user)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a card by ID."""
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_identifier == user)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    await db.execute(sa_delete(BinderCard).where(BinderCard.card_id == card_id))
    await db.delete(card)
    await db.commit()


@router.post("/cards/{card_id}/regenerate-art", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_card_art(
    card_id: str,
    body: dict | None = None,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate card art for an existing card."""
    from app.services.card_gen import start_card_art_regeneration

    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_identifier == user)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    prompt_hint = None
    style_override = None
    if body:
        prompt_hint = body.get("prompt_hint")
        style_override = body.get("style_override")

    job_id = await start_card_art_regeneration(card_id, db, prompt_hint=prompt_hint, style_override=style_override)
    return {"job_id": job_id, "status": "pending"}
