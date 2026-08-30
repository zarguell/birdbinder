import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.activity import Activity
from app.models.like import Like
from app.models.comment import Comment
from app.schemas.activity import CommentCreate, CommentRead

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/feed")
async def list_feed(
    limit: int = 20,
    offset: int = 0,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated activity feed."""
    from app.services.activity import get_feed

    return await get_feed(db, current_user=user, limit=limit, offset=offset)


@router.post("/feed/{activity_id}/like", status_code=status.HTTP_201_CREATED)
async def like_activity(
    activity_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Like an activity."""
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    existing = (
        await db.execute(
            select(Like).where(
                Like.activity_id == activity_id,
                Like.user_identifier == user,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already liked")

    like = Like(activity_id=activity_id, user_identifier=user)
    db.add(like)
    activity.like_count += 1
    await db.commit()
    return {"liked": True, "like_count": activity.like_count}


@router.delete("/feed/{activity_id}/like")
async def unlike_activity(
    activity_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlike an activity."""
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    like = (
        await db.execute(
            select(Like).where(
                Like.activity_id == activity_id,
                Like.user_identifier == user,
            )
        )
    ).scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=404, detail="Not liked")

    await db.delete(like)
    activity.like_count = max(0, activity.like_count - 1)
    await db.commit()
    return {"liked": False, "like_count": activity.like_count}


@router.post(
    "/feed/{activity_id}/comments",
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    activity_id: str,
    body: CommentCreate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to an activity."""
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    comment = Comment(
        activity_id=activity_id,
        user_identifier=user,
        content=body.content,
    )
    db.add(comment)
    activity.comment_count += 1
    await db.commit()
    await db.refresh(comment)
    return CommentRead.model_validate(comment)
