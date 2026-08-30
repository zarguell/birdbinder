"""Tests for model provenance — art_model on Card and id_model on Sighting.

Verifies that the AI model used for card art generation and identification
is correctly recorded, respecting DB override > env var > default.
"""

import json
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
        status="pending",
        species_code=None,
        species_common=None,
        species_scientific=None,
        family=None,
        pose_variant=None,
        id_confidence=None,
        id_method=None,
    )
    defaults.update(overrides)
    sighting = Sighting(**defaults)
    session.add(sighting)
    session.flush()
    return sighting


def _make_job(session, sighting_id, job_type):
    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    session.add(job)
    session.flush()
    return job


def _run_card_gen(task_db, job_id, sighting_id):
    """Run _run_card_generation with patched _sync_engine and settings."""
    from app.services.card_gen import _run_card_generation
    import app.services.card_gen as cg_mod
    with patch.object(cg_mod, "_sync_engine", task_db):
        _run_card_generation(job_id, sighting_id)


def _run_regen(task_db, job_id, card_id, prompt_hint=None, style_override=None):
    """Run _run_card_art_regeneration with patched _sync_engine."""
    from app.services.card_gen import _run_card_art_regeneration
    import app.services.card_gen as cg_mod
    with patch.object(cg_mod, "_sync_engine", task_db):
        _run_card_art_regeneration(job_id, card_id, prompt_hint, style_override)


def _run_identification(task_db, job_id, sighting_id, image_path):
    """Run _run_identification with patched _sync_engine."""
    import app.services.identifier as id_mod
    with patch.object(id_mod, "_sync_engine", task_db):
        id_mod._run_identification(job_id, sighting_id, image_path)


def _apply_settings(mock_settings, **overrides):
    """Apply default settings attributes to a mock object."""
    defaults = dict(
        ai_api_key="test-key",
        ai_base_url="https://fake.example.com/v1",
        ai_model="gpt-4o",
        ai_image_model=None,
        card_style_name="watercolor",
        database_url="sqlite+aiosqlite:///test.db",
        birdbinder_id_prompt=None,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(mock_settings, k, v)


# ---------------------------------------------------------------------------
# Card generation: art_model
# ---------------------------------------------------------------------------


@patch("app.services.card_gen.settings")
def test_card_generation_saves_art_model(mock_settings, task_db, db):
    """Card.art_model should be set to ai_model when no ai_image_model is configured."""
    _apply_settings(mock_settings, ai_image_model=None)

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, JobType.generate_card.value)
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new.png"):
        _run_card_gen(task_db, job.id, sighting.id)

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value

    from app.models.card import Card
    card = db.query(Card).filter(Card.sighting_id == sighting.id).first()
    assert card is not None
    assert card.art_model == "gpt-4o"


@patch("app.services.card_gen.settings")
def test_card_generation_saves_art_model_from_image_model(mock_settings, task_db, db):
    """Card.art_model should prefer ai_image_model over ai_model."""
    _apply_settings(mock_settings, ai_image_model="dall-e-3")

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, JobType.generate_card.value)
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new.png"):
        _run_card_gen(task_db, job.id, sighting.id)

    db.expire_all()
    from app.models.card import Card
    card = db.query(Card).filter(Card.sighting_id == sighting.id).first()
    assert card is not None
    assert card.art_model == "dall-e-3"


@patch("app.services.card_gen.settings")
def test_card_generation_saves_art_model_from_db_override(mock_settings, task_db, db):
    """DB AppSetting ai_image_model should take priority over env ai_image_model."""
    _apply_settings(mock_settings, ai_image_model="env-model")

    from app.models.app_setting import AppSetting
    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, JobType.generate_card.value)
    db.add(AppSetting(key="ai_image_model", value="db-model-xyz"))
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new.png"):
        _run_card_gen(task_db, job.id, sighting.id)

    db.expire_all()
    from app.models.card import Card
    card = db.query(Card).filter(Card.sighting_id == sighting.id).first()
    assert card is not None
    assert card.art_model == "db-model-xyz"


# ---------------------------------------------------------------------------
# Card regeneration: art_model
# ---------------------------------------------------------------------------


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


@patch("app.services.card_gen.settings")
def test_regen_updates_art_model(mock_settings, task_db, db):
    """Card regeneration should update card.art_model to the resolved model."""
    _apply_settings(mock_settings, ai_image_model=None)

    sighting = _make_sighting(db, status="identified", species_common="American Flamingo",
                              species_scientific="Phoenicopterus ruber", species_code="amefl",
                              family="Flamingos", pose_variant="foraging")
    card = _make_card(db, sighting.id, art_model=None)
    job = _make_job(db, sighting.id, JobType.regenerate_art.value)
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new123.png"):
        _run_regen(task_db, job.id, card.id)

    db.expire_all()
    updated_card = db.get(Card, card.id)
    assert updated_card.art_model == "gpt-4o"
    assert updated_card.card_art_url == "/storage/card_art/new123.png"


@patch("app.services.card_gen.settings")
def test_regen_uses_db_override_for_art_model(mock_settings, task_db, db):
    """Card regeneration should use DB AppSetting ai_image_model override."""
    _apply_settings(mock_settings, ai_image_model="env-image-model")

    from app.models.app_setting import AppSetting
    sighting = _make_sighting(db, status="identified", species_common="American Flamingo",
                              species_scientific="Phoenicopterus ruber", species_code="amefl",
                              family="Flamingos", pose_variant="foraging")
    card = _make_card(db, sighting.id, art_model=None)
    job = _make_job(db, sighting.id, JobType.regenerate_art.value)
    db.add(AppSetting(key="ai_image_model", value="db-model-xyz"))
    db.commit()

    with patch("app.services.ai.generate_card_art", new_callable=AsyncMock, return_value="card_art/new123.png"):
        _run_regen(task_db, job.id, card.id)

    db.expire_all()
    updated_card = db.get(Card, card.id)
    assert updated_card.art_model == "db-model-xyz"


# ---------------------------------------------------------------------------
# Identification: id_model
# ---------------------------------------------------------------------------

VALID_AI_RESPONSE = json.dumps({
    "common_name": "American Flamingo",
    "scientific_name": "Phoenicopterus ruber",
    "family": "Flamingos",
    "pose_variant": "foraging",
    "confidence": 0.92,
    "distinguishing_traits": "pink plumage",
})


@patch("app.services.ai.settings")
@patch("app.services.identifier.settings")
def test_identification_saves_id_model(mock_id_settings, mock_ai_settings, task_db, db):
    """Sighting.id_model should be set to ai_model after successful identification."""
    _apply_settings(mock_id_settings)
    _apply_settings(mock_ai_settings)

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, JobType.identify.value)
    db.commit()

    with patch("app.services.identifier.call_vision_model", new_callable=AsyncMock, return_value=VALID_AI_RESPONSE):
        _run_identification(task_db, job.id, sighting.id, "/tmp/fake_photo.jpg")

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value

    updated_sighting = db.get(Sighting, sighting.id)
    assert updated_sighting.id_model == "gpt-4o"
    assert updated_sighting.status == "identified"


@patch("app.services.ai.settings")
@patch("app.services.identifier.settings")
def test_identification_saves_id_model_from_db_override(mock_id_settings, mock_ai_settings, task_db, db):
    """DB AppSetting ai_model should override env ai_model for id_model."""
    _apply_settings(mock_id_settings)
    _apply_settings(mock_ai_settings)

    from app.models.app_setting import AppSetting
    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id, JobType.identify.value)
    db.add(AppSetting(key="ai_model", value="gpt-4o-override"))
    db.commit()

    with patch("app.services.identifier.call_vision_model", new_callable=AsyncMock, return_value=VALID_AI_RESPONSE):
        _run_identification(task_db, job.id, sighting.id, "/tmp/fake_photo.jpg")

    db.expire_all()
    updated_sighting = db.get(Sighting, sighting.id)
    assert updated_sighting.id_model == "gpt-4o-override"
