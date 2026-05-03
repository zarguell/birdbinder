"""Tests for card generation task — the _run_card_generation function.

These tests exercise the actual Huey task logic (not just the API endpoint)
to catch data-path bugs where results aren't written correctly to the DB.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models.card import Card
from app.models.enums import JobStatus, JobType
from app.models.job import Job
from app.models.sighting import Sighting

TEST_USER = "test-user"


@pytest.fixture(scope="function")
def task_db(tmp_path):
    """Create a synchronous SQLite engine matching what Huey tasks use."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(task_db):
    """Session bound to the same DB the task will use."""
    with Session(task_db) as session:
        yield session


def _make_sighting(session, **overrides):
    defaults = dict(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
        thumbnail_path=None,
        submitted_at=datetime.now(timezone.utc),
        status="identified",
        species_code="amefl",
        species_common="American Flamingo",
        species_scientific="Phoenicopterus ruber",
        family="Flamingos",
        pose_variant="foraging",
        id_confidence=0.85,
        id_method="ai",
    )
    defaults.update(overrides)
    sighting = Sighting(**defaults)
    session.add(sighting)
    session.flush()
    return sighting


def _make_job(session, sighting_id, job_type="generate_card"):
    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    session.add(job)
    session.flush()
    return job


def _run(task_func, module, task_db, job_id, sighting_id):
    """Run a Huey task function with patched _sync_engine pointing to our test DB."""
    import app.services.card_gen as cg_mod
    with patch.object(cg_mod, "_sync_engine", task_db):
        task_func(job_id, sighting_id)


# ---------------------------------------------------------------------------
# Core: _run_card_generation writes correct fields to Card
# ---------------------------------------------------------------------------


@patch("app.services.card_gen.settings")
def test_run_card_generation_writes_all_fields(mock_settings, task_db, db):
    """Card generation must write all species/art fields to the Card record."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/abc123.png"):
        _run(_run_card_generation, "card_gen", task_db, job.id, sighting.id)

    db.expire_all()

    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value
    assert updated_job.result is not None
    assert "card_id" in updated_job.result

    card = db.get(Card, updated_job.result["card_id"])
    assert card is not None
    assert card.species_common == "American Flamingo"
    assert card.species_scientific == "Phoenicopterus ruber"
    assert card.family == "Flamingos"
    assert card.pose_variant == "foraging"
    assert card.rarity_tier == "common"
    assert card.id_method == "ai"
    assert card.id_confidence == 0.85
    assert card.user_identifier == TEST_USER
    assert card.sighting_id == sighting.id


@patch("app.services.card_gen.settings")
def test_run_card_generation_fallback_to_original_photo(mock_settings, task_db, db):
    """When AI art generation fails, card should use original photo as fallback."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, side_effect=Exception("AI down")):
        _run(_run_card_generation, "card_gen", task_db, job.id, sighting.id)

    db.expire_all()

    card = db.query(Card).filter_by(sighting_id=sighting.id).first()
    assert card is not None
    # Fallback URL must NOT have /api/ prefix
    assert card.card_art_url == "/storage/sightings/test.jpg"
    assert not card.card_art_url.startswith("/api/")


@patch("app.services.card_gen.settings")
def test_run_card_generation_no_photo_no_ai(mock_settings, task_db, db):
    """Sighting with no photo and no AI key should still create a card."""
    mock_settings.ai_api_key = None

    sighting = _make_sighting(db, photo_path=None)
    job = _make_job(db, sighting.id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation
    _run(_run_card_generation, "card_gen", task_db, job.id, sighting.id)

    db.expire_all()
    card = db.query(Card).filter_by(sighting_id=sighting.id).first()
    assert card is not None
    assert card.card_art_url is None


@patch("app.services.card_gen.settings")
def test_run_card_generation_uses_absolute_image_path(mock_settings, task_db, db, tmp_path):
    """generate_card_art must receive an absolute file path, not a relative one."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db, photo_path="sightings/test.jpg")
    job = _make_job(db, sighting.id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation

    captured_path = None

    async def fake_generate(image_path, species_info, **kwargs):
        nonlocal captured_path
        captured_path = image_path
        return "card_art/fake.png"

    # Patch at the source module since card_gen imports it locally
    with patch("app.services.ai.generate_card_art", side_effect=fake_generate):
        _run(_run_card_generation, "card_gen", task_db, job.id, sighting.id)

    assert captured_path is not None
    # Must be absolute, not the relative "sightings/test.jpg"
    assert not captured_path == "sightings/test.jpg"


@patch("app.services.card_gen.settings")
def test_run_card_generation_ai_art_url_format(mock_settings, task_db, db):
    """AI-generated art path must use /storage/, not /api/storage/."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/generated123.png"):
        _run(_run_card_generation, "card_gen", task_db, job.id, sighting.id)

    db.expire_all()
    card = db.query(Card).filter_by(sighting_id=sighting.id).first()
    assert card.card_art_url == "/storage/card_art/generated123.png"
    assert not card.card_art_url.startswith("/api/")


@patch("app.services.card_gen.settings")
def test_run_card_generation_sighting_not_found_fails_job(mock_settings, task_db, db):
    """Missing sighting should mark job as failed, no card created."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"

    fake_id = str(uuid.uuid4())
    job = _make_job(db, fake_id, job_type="generate_card")
    db.commit()

    from app.services.card_gen import _run_card_generation
    _run(_run_card_generation, "card_gen", task_db, job.id, fake_id)

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.failed.value
    assert "not found" in updated_job.error.lower()
    assert db.query(Card).filter_by(sighting_id=fake_id).count() == 0



