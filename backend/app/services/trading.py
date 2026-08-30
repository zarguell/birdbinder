from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trade import Trade
from app.models.card import Card
from app.models.enums import TradeStatus


async def validate_trade(
    db: AsyncSession,
    offered_by: str,
    offered_to: str,
    offered_card_ids: list[str],
    requested_card_ids: list[str],
) -> list[str]:
    """Validate a trade. Returns list of error messages. Empty if valid."""
    errors = []
    if offered_by == offered_to:
        errors.append("Cannot trade with yourself")
    if not offered_card_ids:
        errors.append("Must offer at least one card")
    # Verify offered cards exist and belong to offerer and are tradeable
    for card_id in offered_card_ids:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if not card:
            errors.append(f"Offered card {card_id} not found")
        elif card.user_identifier != offered_by:
            errors.append(f"Card {card_id} does not belong to you")
        elif not card.tradeable:
            errors.append(f"Card {card_id} is not tradeable")
    # Verify requested cards exist and belong to recipient
    for card_id in requested_card_ids:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if not card:
            errors.append(f"Requested card {card_id} not found")
        elif card.user_identifier != offered_to:
            errors.append(f"Card {card_id} does not belong to recipient")
    return errors


async def claim_pending_trade(
    db: AsyncSession,
    trade_id: str,
    to_status: TradeStatus,
) -> bool:
    """Atomically transition a trade from pending to *to_status*.

    Returns True on success. Concurrent resolutions (e.g. two accepts racing)
    are serialized by the status guard in the UPDATE — only one wins.
    Must be followed by a commit (or rollback to undo the claim).
    """
    result = await db.execute(
        update(Trade)
        .where(Trade.id == trade_id, Trade.status == TradeStatus.pending.value)
        .values(
            status=to_status.value,
            resolved_at=datetime.now(timezone.utc),
        )
    )
    return result.rowcount > 0


async def execute_trade(
    db: AsyncSession,
    trade: Trade,
) -> None:
    """Execute an accepted trade: swap card ownership.

    Caller must have claimed the trade via claim_pending_trade (status is
    already 'accepted') and must commit afterwards. Re-validates every card
    at accept time; raises ValueError if any card is missing or no longer
    owned by the expected party — the caller must rollback in that case so
    the claim is undone too.
    """
    # Bulk-load all referenced cards and re-validate ownership
    all_ids = list(trade.offered_card_ids) + list(trade.requested_card_ids)
    rows = (await db.execute(select(Card).where(Card.id.in_(all_ids)))).scalars().all()
    cards_by_id = {c.id: c for c in rows}

    offered_cards = []
    for card_id in trade.offered_card_ids:
        card = cards_by_id.get(card_id)
        if card is None or card.user_identifier != trade.offered_by:
            raise ValueError(f"Offered card {card_id} is no longer available")
        if not card.tradeable:
            raise ValueError(f"Card {card_id} is no longer tradeable")
        offered_cards.append(card)

    requested_cards = []
    for card_id in trade.requested_card_ids:
        card = cards_by_id.get(card_id)
        if card is None or card.user_identifier != trade.offered_to:
            raise ValueError(f"Requested card {card_id} is no longer available")
        requested_cards.append(card)

    # Transfer offered cards to recipient
    for card in offered_cards:
        card.user_identifier = trade.offered_to
        card.duplicate_count = max(1, card.duplicate_count - 1)
    # Transfer requested cards to offerer
    for card in requested_cards:
        card.user_identifier = trade.offered_by
        card.duplicate_count = max(1, card.duplicate_count - 1)
