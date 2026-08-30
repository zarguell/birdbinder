from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.trade import Trade
from app.models.card import Card
from app.models.enums import TradeStatus
from app.schemas.trade import TradeCardInfo, TradeCreate, TradeRead, TradeList
from app.services.trading import validate_trade, execute_trade, claim_pending_trade

router = APIRouter()


async def _attach_card_details(db: AsyncSession, trades: list[Trade]) -> None:
    """Resolve card UUIDs into species summaries for display.

    Sets offered_cards/requested_cards on each Trade; IDs referencing deleted
    cards are silently dropped.
    """
    all_ids = {
        card_id
        for t in trades
        for card_id in list(t.offered_card_ids) + list(t.requested_card_ids)
    }
    if not all_ids:
        return
    rows = (await db.execute(select(Card).where(Card.id.in_(all_ids)))).scalars().all()
    cards_by_id = {c.id: c for c in rows}

    def summaries(card_ids: list) -> list[TradeCardInfo]:
        return [
            TradeCardInfo(
                id=card_id,
                species_common=cards_by_id[card_id].species_common,
                species_code=cards_by_id[card_id].species_code,
                rarity_tier=cards_by_id[card_id].rarity_tier,
                card_art_url=cards_by_id[card_id].card_art_url,
            )
            for card_id in card_ids
            if card_id in cards_by_id
        ]

    for t in trades:
        t.offered_cards = summaries(t.offered_card_ids)
        t.requested_cards = summaries(t.requested_card_ids)


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
    await _attach_card_details(db, [trade])
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
    trades = list(result.scalars().all())
    await _attach_card_details(db, trades)
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
    await _attach_card_details(db, [trade])
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
    # Atomically claim the trade so a concurrent accept/decline/cancel cannot
    # double-execute, then re-validate and swap card ownership
    claimed = await claim_pending_trade(db, trade.id, TradeStatus.accepted)
    if not claimed:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
    try:
        await execute_trade(db, trade)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
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
    claimed = await claim_pending_trade(db, trade.id, TradeStatus.declined)
    if not claimed:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
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
    claimed = await claim_pending_trade(db, trade.id, TradeStatus.cancelled)
    if not claimed:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Trade is {trade.status}")
    await db.commit()
    await db.refresh(trade)
    return trade
