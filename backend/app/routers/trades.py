from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.trade import Trade
from app.models.enums import TradeStatus
from app.schemas.trade import TradeCreate, TradeRead, TradeList
from app.services.trading import validate_trade, execute_trade

router = APIRouter()


@router.post("/trades", response_model=TradeRead, status_code=status.HTTP_201_CREATED)
async def create_trade(
    data: TradeCreate,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    errors = await validate_trade(
        db, user, data.offered_to, data.offered_card_ids, data.requested_card_ids
    )
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    trade = Trade(
        offered_by=user,
        offered_to=data.offered_to,
        offered_card_ids=data.offered_card_ids,
        requested_card_ids=data.requested_card_ids,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.get("/trades", response_model=TradeList)
async def list_trades(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Trade).where(
        (Trade.offered_by == user) | (Trade.offered_to == user)
    )
    count_query = select(func.count()).select_from(Trade).where(
        (Trade.offered_by == user) | (Trade.offered_to == user)
    )
    if status_filter:
        query = query.where(Trade.status == status_filter)
        count_query = count_query.where(Trade.status == status_filter)
    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Trade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = result.scalars().all()
    return TradeList(items=trades, total=total, limit=limit, offset=offset)


@router.get("/trades/{trade_id}", response_model=TradeRead)
async def get_trade(
    trade_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.offered_by != user and trade.offered_to != user:
        raise HTTPException(status_code=403, detail="Not your trade")
    return trade


@router.post("/trades/{trade_id}/accept", response_model=TradeRead)
async def accept_trade(
    trade_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.offered_to != user:
        raise HTTPException(status_code=403, detail="Only the recipient can accept")
    if trade.status != TradeStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
    await execute_trade(db, trade)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.post("/trades/{trade_id}/decline", response_model=TradeRead)
async def decline_trade(
    trade_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.offered_to != user:
        raise HTTPException(status_code=403, detail="Only the recipient can decline")
    if trade.status != TradeStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
    trade.status = TradeStatus.declined.value
    trade.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(trade)
    return trade


@router.post("/trades/{trade_id}/cancel", response_model=TradeRead)
async def cancel_trade(
    trade_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.offered_by != user:
        raise HTTPException(status_code=403, detail="Only the offerer can cancel")
    if trade.status != TradeStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
    trade.status = TradeStatus.cancelled.value
    trade.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(trade)
    return trade
