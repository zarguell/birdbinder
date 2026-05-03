from datetime import datetime, timezone
from sqlalchemy import select
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


async def execute_trade(
    db: AsyncSession,
    trade: Trade,
) -> None:
    """Execute an accepted trade: swap card ownership."""
    now = datetime.now(timezone.utc)
    # Transfer offered cards to recipient
    for card_id in trade.offered_card_ids:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        card.user_identifier = trade.offered_to
        card.duplicate_count = max(1, card.duplicate_count - 1)
    # Transfer requested cards to offerer
    for card_id in trade.requested_card_ids:
        result = await db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one()
        card.user_identifier = trade.offered_by
        card.duplicate_count = max(1, card.duplicate_count - 1)
    trade.status = TradeStatus.accepted.value
    trade.resolved_at = now
