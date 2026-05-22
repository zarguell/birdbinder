from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import get_owned_or_404, paginated_owned_list
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

    sighting = await get_owned_or_404(db, Sighting, sighting_id, user, detail="Sighting not found")
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
    """Delete a card by ID."""
    card = await get_owned_or_404(db, Card, card_id, user, detail="Card not found")
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

    card = await get_owned_or_404(db, Card, card_id, user, detail="Card not found")

    prompt_hint = None
    style_override = None
    if body:
        prompt_hint = body.get("prompt_hint")
        style_override = body.get("style_override")

    job_id = await start_card_art_regeneration(card_id, db, prompt_hint=prompt_hint, style_override=style_override)
    return {"job_id": job_id, "status": "pending"}
