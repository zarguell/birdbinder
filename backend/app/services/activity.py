import logging

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.like import Like
from app.models.comment import Comment

logger = logging.getLogger(__name__)


async def publish_activity(
    db: AsyncSession,
    user_identifier: str,
    activity_type: str,
    reference_id: str,
    description: str | None = None,
) -> Activity:
    """Create and persist a new activity entry."""
    activity = Activity(
        user_identifier=user_identifier,
        activity_type=activity_type,
        reference_id=reference_id,
        description=description,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    logger.info(
        "Activity published: %s %s by %s",
        activity_type,
        reference_id,
        user_identifier,
    )
    return activity


async def get_feed(
    db: AsyncSession,
    current_user: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Return a paginated feed of activities with like/comment info."""
    count_q = select(func.count()).select_from(Activity)
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(Activity)
        .options(selectinload(Activity.likes), selectinload(Activity.comments))
        .order_by(desc(Activity.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    activities = result.scalars().all()

    items = []
    for a in activities:
        liked = (
            any(l.user_identifier == current_user for l in a.likes)
            if current_user
            else False
        )
        items.append(
            {
                "id": a.id,
                "user_identifier": a.user_identifier,
                "activity_type": a.activity_type,
                "reference_id": a.reference_id,
                "description": a.description,
                "like_count": a.like_count,
                "comment_count": a.comment_count,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "current_user_liked": liked,
                "comments": [
                    {
                        "id": c.id,
                        "user_identifier": c.user_identifier,
                        "content": c.content,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in a.comments
                ],
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}
