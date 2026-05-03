import uuid
from app.models.card import Card
from app.models.sighting import Sighting
from sqlalchemy import select, text

async def test_check_user_match(auth_client, db_session):
    """Check if user_identifier matches between test and API."""
    from app.db import get_db
    from app.main import app
    from tests.conftest import TEST_USER
    
    # Insert sighting and card with TEST_USER
    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        status="identified",
        species_common="Debug Bird",
        species_code="dbug",
        species_scientific="Debugus birdus",
    )
    db_session.add(sighting)
    await db_session.commit()
    
    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        user_identifier=TEST_USER,
        species_common="Debug Bird",
        species_code="dbug",
        rarity_tier="common",
        pose_variant="perching",
    )
    db_session.add(card)
    await db_session.commit()
    
    # Check raw DB
    override_fn = app.dependency_overrides.get(get_db)
    gen = override_fn()
    api_session = await gen.__anext__()
    result = await api_session.execute(text("SELECT user_identifier FROM cards LIMIT 1"))
    db_user = result.scalar()
    print(f"\nDB user_identifier: '{db_user}'")
    print(f"TEST_USER: '{TEST_USER}'")
    
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass
    
    # Get sightings via API (this works in existing tests)
    response = await auth_client.get("/api/sightings")
    print(f"Sightings total: {response.json()['total']}")
    
    # Get the cards via API
    response = await auth_client.get("/api/cards")
    data = response.json()
    print(f"Cards total: {data['total']}")
    print(f"Cards response: {data}")

async def test_insert_like_sighting_fixture(auth_client, db_session):
    """Insert a card the same way sighting fixture does and check visibility."""
    from tests.conftest import sighting as sighting_fixture
    from app.db import get_db
    from app.main import app
    
    # Create a sighting using the fixture
    s = await sighting_fixture(db_session)
    
    # Now insert a card for that sighting
    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=s.id,
        user_identifier=s.user_identifier,
        species_common=s.species_common,
        species_code=s.species_code or "unk",
        rarity_tier="common",
        pose_variant="perching",
    )
    db_session.add(card)
    await db_session.commit()
    
    # Check via HTTP
    response = await auth_client.get("/api/sightings")
    print(f"\nSightings total: {response.json()['total']}")
    
    response = await auth_client.get("/api/cards")
    print(f"Cards total: {response.json()['total']}")

