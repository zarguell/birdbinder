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

    order_col = getattr(model, order_field) if order_field else (
        getattr(model, "created_at", None) or getattr(model, "submitted_at")
    )
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
