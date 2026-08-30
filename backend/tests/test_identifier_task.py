"""Tests for identification task — the _run_identification function.

These exercise the actual Huey task logic to catch data-path bugs where
identification results aren't written correctly to the sighting record.
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
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
    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
        thumbnail_path=None,
        submitted_at=datetime.now(timezone.utc),
        status="pending",
        **overrides,
    )
    session.add(sighting)
    session.flush()
    return sighting


def _make_job(session, sighting_id):
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.identify.value,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    session.add(job)
    session.flush()
    return job


AI_RESULT = json.dumps({
    "common_name": "American Flamingo",
    "scientific_name": "Phoenicopterus ruber",
    "family": "Flamingos",
    "confidence": 0.85,
    "distinguishing_traits": ["pink plumage", "long neck", "downcurved bill"],
    "pose_variant": "foraging",
})


def _run(task_func, module, task_db, job_id, sighting_id, *extra_args):
    """Run a Huey task function with patched _sync_engine pointing to our test DB."""
    import app.services.identifier as id_mod
    import app.services.card_gen as cg_mod
    target = id_mod if module == "identifier" else cg_mod
    with patch.object(target, "_sync_engine", task_db):
        task_func(job_id, sighting_id, *extra_args)


# ---------------------------------------------------------------------------
# Core: _run_identification writes ALL species fields to sighting
# ---------------------------------------------------------------------------


@patch("app.services.identifier.settings")
def test_run_identification_writes_species_to_sighting(mock_settings, task_db, db, tmp_path):
    """After successful identification, sighting.species_common MUST be set.

    This catches the critical bug where the task only set sighting.status
    but never wrote species_common, species_scientific, etc.
    """
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.birdbinder_id_prompt = None

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id)
    db.commit()

    from PIL import Image
    img = Image.new("RGB", (100, 100), (200, 100, 50))
    img.save(tmp_path / "test.jpg")

    with patch("app.services.identifier.call_vision_model", new_callable=AsyncMock, return_value=AI_RESULT):
        from app.services.identifier import _run_identification
        _run(_run_identification, "identifier", task_db, job.id, sighting.id, str(tmp_path / "test.jpg"))

    db.expire_all()

    # Job completed
    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.completed.value
    assert updated_job.result["common_name"] == "American Flamingo"

    # SIGHTING FIELDS — the critical assertion
    updated_sighting = db.get(Sighting, sighting.id)
    assert updated_sighting.status == "identified"
    assert updated_sighting.species_common == "American Flamingo"
    assert updated_sighting.species_scientific == "Phoenicopterus ruber"
    assert updated_sighting.family == "Flamingos"
    assert updated_sighting.pose_variant == "foraging"
    assert updated_sighting.id_confidence == 0.85
    assert updated_sighting.id_method == "ai"
    assert updated_sighting.manual_species_override is False


@patch("app.services.identifier.settings")
def test_run_identification_invalid_pose_maps_to_other(mock_settings, task_db, db, tmp_path):
    """AI returns an unrecognized pose_variant — should default to 'other'."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.birdbinder_id_prompt = None

    result = json.dumps({
        "common_name": "House Sparrow",
        "scientific_name": "Passer domesticus",
        "family": "Old World Sparrows",
        "confidence": 0.9,
        "distinguishing_traits": ["brown back"],
        "pose_variant": "breakdancing",
    })

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id)
    db.commit()

    from PIL import Image
    img = Image.new("RGB", (100, 100))
    img.save(tmp_path / "test.jpg")

    with patch("app.services.identifier.call_vision_model", new_callable=AsyncMock, return_value=result):
        from app.services.identifier import _run_identification
        _run(_run_identification, "identifier", task_db, job.id, sighting.id, str(tmp_path / "test.jpg"))

    db.expire_all()
    updated_sighting = db.get(Sighting, sighting.id)
    assert updated_sighting.pose_variant == "other"


@patch("app.services.identifier.settings")
def test_run_identification_failure_marks_job_failed(mock_settings, task_db, db, tmp_path):
    """AI failure should mark job as failed, sighting stays pending."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.birdbinder_id_prompt = None

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id)
    db.commit()

    from PIL import Image
    img = Image.new("RGB", (100, 100))
    img.save(tmp_path / "test.jpg")

    with patch(
        "app.services.identifier.call_vision_model",
        new_callable=AsyncMock,
        side_effect=ValueError("AI returned empty content"),
    ):
        from app.services.identifier import _run_identification
        _run(_run_identification, "identifier", task_db, job.id, sighting.id, str(tmp_path / "test.jpg"))

    db.expire_all()

    updated_job = db.get(Job, job.id)
    assert updated_job.status == JobStatus.failed.value
    assert "empty content" in updated_job.error

    updated_sighting = db.get(Sighting, sighting.id)
    assert updated_sighting.species_common is None


@patch("app.services.identifier.settings")
def test_run_identification_stores_raw_response(mock_settings, task_db, db, tmp_path):
    """Raw AI response should be stored on the job for user visibility."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = "https://fake.example.com/v1"
    mock_settings.ai_model = "test-model"
    mock_settings.birdbinder_id_prompt = None

    sighting = _make_sighting(db)
    job = _make_job(db, sighting.id)
    db.commit()

    from PIL import Image
    img = Image.new("RGB", (100, 100))
    img.save(tmp_path / "test.jpg")

    with patch("app.services.identifier.call_vision_model", new_callable=AsyncMock, return_value=AI_RESULT):
        from app.services.identifier import _run_identification
        _run(_run_identification, "identifier", task_db, job.id, sighting.id, str(tmp_path / "test.jpg"))

    db.expire_all()
    updated_job = db.get(Job, job.id)
    assert updated_job.raw_response is not None
    assert "American Flamingo" in updated_job.raw_response
