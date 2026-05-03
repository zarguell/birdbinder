import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, date

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db import Base
from app.models.sighting import Sighting
from app.models.card import Card, PoseVariant
from app.models.set import CardSet
from app.models.trade import Trade, TradeStatus
from app.models.species import SpeciesCache
from app.models.job import Job, JobType, JobStatus
from app.models.enums import SightingStatus


@pytest.fixture
def engine():
    return create_async_engine("sqlite+aiosqlite://", echo=False)


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(engine, session_factory):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Sighting ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_sighting(session: AsyncSession):
    s = Sighting(
        id=str(uuid.uuid4()),
        user_identifier="user@example.com",
        photo_path="photos/test.jpg",
        submitted_at=datetime.now(timezone.utc),
        status="pending",
    )
    session.add(s)
    await session.commit()

    result = await session.get(Sighting, s.id)
    assert result is not None
    assert result.user_identifier == "user@example.com"
    assert result.photo_path == "photos/test.jpg"
    assert result.status == "pending"
    assert result.manual_species_override is False


@pytest.mark.asyncio
async def test_sighting_with_exif(session: AsyncSession):
    s = Sighting(
        id=str(uuid.uuid4()),
        user_identifier="user@example.com",
        exif_lat=40.7128,
        exif_lon=-74.0060,
        exif_camera_model="Canon EOS R5",
        exif_datetime=datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc),
        location_display_name="Central Park, NY",
        notes="Beautiful morning sighting",
    )
    session.add(s)
    await session.commit()

    result = await session.get(Sighting, s.id)
    assert result.exif_lat == 40.7128
    assert result.exif_lon == -74.0060
    assert result.exif_camera_model == "Canon EOS R5"
    assert result.location_display_name == "Central Park, NY"
    assert result.notes == "Beautiful morning sighting"


# ── Card ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_card(session: AsyncSession):
    card_id = str(uuid.uuid4())
    c = Card(
        id=card_id,
        user_identifier="user@example.com",
        species_common="Northern Cardinal",
        species_scientific="Cardinalis cardinalis",
        species_code="nrcard",
        family="Cardinalidae",
        pose_variant=PoseVariant.perching.value,
        rarity_tier="common",
        id_method="ai",
        id_confidence=0.95,
        duplicate_count=1,
        tradeable=True,
    )
    session.add(c)
    await session.commit()

    result = await session.get(Card, card_id)
    assert result is not None
    assert result.species_common == "Northern Cardinal"
    assert result.species_code == "nrcard"
    assert result.pose_variant == "perching"
    assert result.id_confidence == 0.95
    assert result.duplicate_count == 1
    assert result.set_ids == []


@pytest.mark.asyncio
async def test_card_json_fields(session: AsyncSession):
    c = Card(
        id=str(uuid.uuid4()),
        user_identifier="user@example.com",
        species_common="Blue Jay",
        species_code="blujay",
        set_ids=["set-uuid-1", "set-uuid-2"],
    )
    session.add(c)
    await session.commit()

    result = await session.get(Card, c.id)
    assert result.set_ids == ["set-uuid-1", "set-uuid-2"]


# ── Sighting ↔ Card relationship ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_sighting_card_relationship(session: AsyncSession):
    sighting_id = str(uuid.uuid4())
    card_id = str(uuid.uuid4())

    s = Sighting(id=sighting_id, user_identifier="user@example.com")
    c = Card(
        id=card_id,
        sighting_id=sighting_id,
        user_identifier="user@example.com",
        species_common="American Robin",
        species_code="ameroi",
    )
    session.add(s)
    session.add(c)
    await session.commit()

    # Check relationship from sighting side — must refresh for selectin loading
    result = await session.get(Sighting, sighting_id)
    await session.refresh(result, attribute_names=["cards"])
    assert result is not None
    assert len(result.cards) == 1
    assert result.cards[0].species_common == "American Robin"

    # Check relationship from card side
    card_result = await session.get(Card, card_id)
    await session.refresh(card_result, attribute_names=["sighting"])
    assert card_result is not None
    assert card_result.sighting_id == sighting_id


# ── CardSet ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_card_set(session: AsyncSession):
    cs = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier="user@example.com",
        name="Spring 2025 Collection",
        description="Birds seen in spring",
        region="Northeast US",
        season="spring",
        release_date=date(2025, 3, 20),
        expiry_date=date(2025, 6, 20),
        rules={"max_cards": 50, "min_rarity": "common"},
        card_targets=[
            {"species_code": "nrcard", "pose_variant": "perching"},
            {"species_code": "blujay", "pose_variant": "flying"},
        ],
    )
    session.add(cs)
    await session.commit()

    result = await session.get(CardSet, cs.id)
    assert result is not None
    assert result.name == "Spring 2025 Collection"
    assert result.region == "Northeast US"
    assert result.release_date == date(2025, 3, 20)
    assert result.rules["max_cards"] == 50
    assert len(result.card_targets) == 2
    assert result.card_targets[0]["species_code"] == "nrcard"


# ── Trade ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_trade(session: AsyncSession):
    trade = Trade(
        id=str(uuid.uuid4()),
        offered_by="user1@example.com",
        offered_to="user2@example.com",
        offered_card_ids=["card-1", "card-2"],
        requested_card_ids=["card-3"],
        status=TradeStatus.pending.value,
    )
    session.add(trade)
    await session.commit()

    result = await session.get(Trade, trade.id)
    assert result is not None
    assert result.offered_by == "user1@example.com"
    assert result.offered_to == "user2@example.com"
    assert result.offered_card_ids == ["card-1", "card-2"]
    assert result.requested_card_ids == ["card-3"]
    assert result.status == "pending"


# ── Job ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job(session: AsyncSession):
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.identify.value,
        status=JobStatus.pending.value,
        result={"species": "Northern Cardinal", "confidence": 0.92},
    )
    session.add(job)
    await session.commit()

    result = await session.get(Job, job.id)
    assert result is not None
    assert result.type == "identify"
    assert result.status == "pending"
    assert result.result["species"] == "Northern Cardinal"
    assert result.result["confidence"] == 0.92
    assert result.error is None


@pytest.mark.asyncio
async def test_job_with_sighting_fk(session: AsyncSession):
    sighting_id = str(uuid.uuid4())
    s = Sighting(id=sighting_id, user_identifier="user@example.com")
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.generate_card.value,
        sighting_id=sighting_id,
        status=JobStatus.completed.value,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(s)
    session.add(job)
    await session.commit()

    result = await session.get(Job, job.id)
    assert result.sighting_id == sighting_id
    assert result.status == "completed"
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_job_error(session: AsyncSession):
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.identify.value,
        status=JobStatus.failed.value,
        error="AI service unavailable",
    )
    session.add(job)
    await session.commit()

    result = await session.get(Job, job.id)
    assert result.status == "failed"
    assert result.error == "AI service unavailable"


# ── SpeciesCache ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_species_cache(session: AsyncSession):
    sp = SpeciesCache(
        species_code="nrcard",
        common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis",
        category="species",
        taxon_order=8200,
        family="Cardinalidae",
        family_common="Cardinals",
    )
    session.add(sp)
    await session.commit()

    result = await session.get(SpeciesCache, "nrcard")
    assert result is not None
    assert result.common_name == "Northern Cardinal"
    assert result.scientific_name == "Cardinalis cardinalis"
    assert result.family_common == "Cardinals"


@pytest.mark.asyncio
async def test_species_cache_spuh(session: AsyncSession):
    sp = SpeciesCache(
        species_code="dowwoo1",
        common_name="Dove/Pigeon sp.",
        scientific_name="",
        category="spuh",
        taxon_order=3150,
    )
    session.add(sp)
    await session.commit()

    result = await session.get(SpeciesCache, "dowwoo1")
    assert result.category == "spuh"


# ── Enum values ───────────────────────────────────────────────────────────

def test_sighting_status_values():
    assert SightingStatus.pending.value == "pending"
    assert SightingStatus.identified.value == "identified"
    assert SightingStatus.failed.value == "failed"
    assert SightingStatus.cancelled.value == "cancelled"


def test_pose_variant_values():
    assert PoseVariant.perching.value == "perching"
    assert PoseVariant.flying.value == "flying"
    assert PoseVariant.other.value == "other"


def test_job_type_and_status():
    assert JobType.identify.value == "identify"
    assert JobType.generate_card.value == "generate_card"
    assert JobStatus.pending.value == "pending"
    assert JobStatus.running.value == "running"
    assert JobStatus.completed.value == "completed"
    assert JobStatus.failed.value == "failed"


def test_trade_status_values():
    assert TradeStatus.pending.value == "pending"
    assert TradeStatus.accepted.value == "accepted"
    assert TradeStatus.declined.value == "declined"
    assert TradeStatus.cancelled.value == "cancelled"


# ── Query by indexed field ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_sighting_by_user(session: AsyncSession):
    for i in range(3):
        session.add(Sighting(
            id=str(uuid.uuid4()),
            user_identifier=f"user{i}@example.com",
        ))
    await session.commit()

    stmt = select(Sighting).where(Sighting.user_identifier == "user1@example.com")
    result = (await session.execute(stmt)).scalars().all()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_query_card_by_species_code(session: AsyncSession):
    session.add(Card(
        id=str(uuid.uuid4()),
        user_identifier="user@example.com",
        species_common="Northern Cardinal",
        species_code="nrcard",
    ))
    session.add(Card(
        id=str(uuid.uuid4()),
        user_identifier="user@example.com",
        species_common="Blue Jay",
        species_code="blujay",
    ))
    await session.commit()

    stmt = select(Card).where(Card.species_code == "nrcard")
    result = (await session.execute(stmt)).scalars().all()
    assert len(result) == 1
    assert result[0].species_common == "Northern Cardinal"
