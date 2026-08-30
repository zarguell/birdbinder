"""Tests for card art regeneration task — the _run_card_art_regeneration function.

These tests exercise the actual Huey task logic (not just the API endpoint)
to catch data-path bugs where results aren't written correctly to the DB.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

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


def _make_card(session, sighting_id, **overrides):
    defaults = dict(
        id=str(uuid.uuid4()),
        sighting_id=sighting_id,
        user_identifier=TEST_USER,
        species_common="American Flamingo",
        species_scientific="Phoenicopterus ruber",
        species_code="amefl",
        family="Flamingos",
        pose_variant="foraging",
        rarity_tier="common",
        card_art_url="/storage/card_art/old.png",
        id_method="ai",
        id_confidence=0.85,
        generated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    card = Card(**defaults)
    session.add(card)
    session.flush()
    return card


def _make_job(session, sighting_id, job_type="regenerate_art"):
    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    session.add(job)
    session.flush()
    return job


def _run_regen(task_db, job_id, card_id, prompt_hint=None, style_override=None):
    """Run _run_card_art_regeneration with patched _sync_engine."""
    from app.services.card_gen import _run_card_art_regeneration
    import app.services.card_gen as cg_mod
    with patch.object(cg_mod, "_sync_engine", task_db):
        _run_card_art_regeneration(job_id, card_id, prompt_hint, style_override)


# ---------------------------------------------------------------------------
# Core: _run_card_art_regeneration updates card art URL
# ---------------------------------------------------------------------------


@patch("app.services.card_gen.settings")
def test_regen_updates_card_art_url(mock_settings, task_db, db):
    """Regeneration should update card.card_art_url with the new art path."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    old_url = card.card_art_url

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new123.png"):
        _run_regen(task_db, job.id, card.id)

    db.expire_all()

    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value
    assert updated_job.result == {"card_id": card.id}

    updated_card = db.get(Card, card.id)
    assert updated_card.card_art_url == "/storage/card_art/new123.png"
    assert updated_card.card_art_url != old_url


@patch("app.services.card_gen.settings")
def test_regen_builds_species_info_from_card(mock_settings, task_db, db):
    """species_info must be built from Card fields, not re-fetched from sighting."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    # Card has different species info than sighting (as if user corrected it)
    card = _make_card(
        db, sighting.id,
        species_common="Greater Flamingo",
        species_scientific="Phoenicopterus roseus",
        species_code="grfla1",
        pose_variant="standing",
        rarity_tier="rare",
    )
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    captured_info = None

    async def capture_generate(image_path, species_info, **kwargs):
        nonlocal captured_info
        captured_info = species_info
        return "card_art/x.png"

    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id)

    assert captured_info is not None
    # Must use card's species, NOT sighting's
    assert captured_info["common_name"] == "Greater Flamingo"
    assert captured_info["scientific_name"] == "Phoenicopterus roseus"
    assert captured_info["pose_variant"] == "standing"
    assert captured_info["rarity_tier"] == "rare"


@patch("app.services.card_gen.settings")
def test_regen_sources_original_sighting_photo(mock_settings, task_db, db, tmp_path):
    """Regen must source the original sighting photo for image-to-image."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db, photo_path="sightings/my_photo.jpg")
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    captured_path = None

    async def capture_generate(image_path, species_info, **kwargs):
        nonlocal captured_path
        captured_path = image_path
        return "card_art/x.png"

    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id)

    assert captured_path is not None
    # Must be absolute path from get_file_path, not the relative DB value
    assert "my_photo.jpg" in captured_path
    assert captured_path != "sightings/my_photo.jpg"


@patch("app.services.card_gen.settings")
def test_regen_no_photo_sends_empty_path(mock_settings, task_db, db):
    """When sighting has no photo, image_path should be empty string."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db, photo_path=None)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    captured_path = None

    async def capture_generate(image_path, species_info, **kwargs):
        nonlocal captured_path
        captured_path = image_path
        return "card_art/x.png"

    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id)

    assert captured_path == ""


@patch("app.services.card_gen.settings")
def test_regen_passes_prompt_hint(mock_settings, task_db, db):
    """prompt_hint should be forwarded to generate_card_art."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    captured_hint = None

    async def capture_generate(image_path, species_info, prompt_hint=None, **kwargs):
        nonlocal captured_hint
        captured_hint = prompt_hint
        return "card_art/x.png"

    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id, prompt_hint="make it more vibrant")

    assert captured_hint == "make it more vibrant"


@patch("app.services.card_gen.settings")
def test_regen_param_style_overrides_db_style(mock_settings, task_db, db):
    """style_override param should take precedence over DB AppSetting."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")

    # Set DB style to "pencil"
    from app.models.app_setting import AppSetting
    db.add(AppSetting(key="card_style_name", value="pencil"))
    db.commit()

    captured_style = None

    async def capture_generate(image_path, species_info, style_override=None, **kwargs):
        nonlocal captured_style
        captured_style = style_override
        return "card_art/x.png"

    # Pass "oil painting" as param — should win over DB "pencil"
    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id, style_override="oil painting")

    assert captured_style == "oil painting"


@patch("app.services.card_gen.settings")
def test_regen_db_style_used_when_no_param(mock_settings, task_db, db):
    """When no style_override param, DB AppSetting should be used."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")

    from app.models.app_setting import AppSetting
    db.add(AppSetting(key="card_style_name", value="pencil sketch"))
    db.commit()

    captured_style = None

    async def capture_generate(image_path, species_info, style_override=None, **kwargs):
        nonlocal captured_style
        captured_style = style_override
        return "card_art/x.png"

    with patch("app.services.ai.generate_card_art", side_effect=capture_generate):
        _run_regen(task_db, job.id, card.id)

    assert captured_style == "pencil sketch"


def test_regen_card_not_found_fails_job(task_db, db):
    """Non-existent card should mark job as failed."""
    fake_card_id = str(uuid.uuid4())
    job = _make_job(db, str(uuid.uuid4()), job_type="regenerate_art")
    db.commit()

    _run_regen(task_db, job.id, fake_card_id)

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.failed.value
    assert "not found" in updated_job.error.lower()


def test_regen_sighting_not_found_fails_job(task_db, db):
    """Card with no matching sighting should mark job as failed."""
    # Create card pointing to a non-existent sighting
    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        species_common="Ghost Bird",
        species_scientific="Aves phantasma",
        species_code="ghost",
        card_art_url="/storage/card_art/old.png",
        id_method="ai",
        id_confidence=0.9,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(card)
    job = _make_job(db, card.sighting_id, job_type="regenerate_art")
    db.commit()

    _run_regen(task_db, job.id, card.id)

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.failed.value
    assert "not found" in updated_job.error.lower()
    # Card art URL should NOT have changed
    updated_card = db.get(Card, card.id)
    assert updated_card.card_art_url == "/storage/card_art/old.png"


@patch("app.services.card_gen.settings")
def test_regen_ai_failure_fails_job(mock_settings, task_db, db):
    """When AI art generation fails, job should be marked failed (no fallback)."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id)
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    old_url = card.card_art_url

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, side_effect=Exception("API overloaded")):
        _run_regen(task_db, job.id, card.id)

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.failed.value
    assert "API overloaded" in updated_job.error

    # Card art URL should NOT have changed on failure
    updated_card = db.get(Card, card.id)
    assert updated_card.card_art_url == old_url


@patch("app.services.card_gen.settings")
def test_regen_ai_returns_none_does_not_update_url(mock_settings, task_db, db):
    """When AI returns None (e.g. no image generated), card URL stays unchanged."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.ai_image_model = None
    mock_settings.card_style_name = "watercolor"

    sighting = _make_sighting(db)
    card = _make_card(db, sighting.id, card_art_url="/storage/card_art/original.png")
    job = _make_job(db, sighting.id, job_type="regenerate_art")
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value=None):
        _run_regen(task_db, job.id, card.id)

    db.expire_all()
    # Job should still complete (no exception), but URL unchanged
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value

    updated_card = db.get(Card, card.id)
    assert updated_card.card_art_url == "/storage/card_art/original.png"
