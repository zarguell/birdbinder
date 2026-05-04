from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.card import Card
from app.models.activity import Activity
from app.services.region_service import get_region_codes


router = APIRouter()


@router.get("/users")
async def list_users(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users except the current user."""
    stmt = select(User).where(User.email != current_user).order_by(User.display_name, User.email)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "avatar_path": u.avatar_path,
            "region": u.region,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/users/{email}")
async def get_user_profile(
    email: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get public user profile with collection stats."""
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    card_stmt = select(
        func.count(Card.id).label("total_cards"),
        func.count(func.distinct(Card.species_code)).label("unique_species"),
    ).where(Card.user_identifier == email)
    card_result = await db.execute(card_stmt)
    card_row = card_result.one()

    total_cards = card_row.total_cards or 0
    unique_species = card_row.unique_species or 0

    region_codes = get_region_codes(user.region or "us")
    total_region_species = len(region_codes)

    if total_region_species > 0:
        collection_percent = round(unique_species / total_region_species, 4)
    else:
        collection_percent = 0.0

    activity_stmt = (
        select(Activity)
        .where(Activity.user_identifier == email)
        .order_by(Activity.created_at.desc())
        .limit(5)
    )
    activity_result = await db.execute(activity_stmt)
    activities = activity_result.scalars().all()

    recent_activity = [
        {
            "id": a.id,
            "activity_type": a.activity_type,
            "reference_id": a.reference_id,
            "description": a.description,
            "like_count": a.like_count,
            "comment_count": a.comment_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_path": user.avatar_path,
        "region": user.region,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "stats": {
            "total_cards": total_cards,
            "unique_species": unique_species,
            "collection_percent": collection_percent,
        },
        "recent_activity": recent_activity,
    }