"""Tests for AI bird identification with async job queue."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from app.models.enums import PoseVariant
from app.models.job import Job
from app.models.sighting import Sighting

TEST_API_KEY = "***"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


# ---------------------------------------------------------------------------
# Unit tests: parsing logic
# ---------------------------------------------------------------------------


def test_parse_ai_result_clean_json():
    """Parse clean JSON response."""
    result_str = json.dumps({
        "common_name": "American Robin",
        "scientific_name": "Turdus migratorius",
        "family": "Thrushes",
        "confidence": 0.95,
        "distinguishing_traits": ["orange breast", "dark head"],
        "pose_variant": "perching",
    })
    result = json.loads(result_str)
    assert result["common_name"] == "American Robin"
    assert result["pose_variant"] == "perching"
    assert result["confidence"] == 0.95


def test_parse_ai_result_markdown_wrapped():
    """Parse JSON wrapped in markdown code blocks."""
    result_str = '```json\n{"common_name": "Bald Eagle", "confidence": 0.9, "pose_variant": "flying", "distinguishing_traits": ["white head"], "family": "Hawks", "scientific_name": "Haliaeetus leucocephalus"}\n```'
    cleaned = result_str.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(cleaned)
    assert result["common_name"] == "Bald Eagle"
    assert result["pose_variant"] == "flying"


def test_invalid_pose_maps_to_other():
    """Invalid pose_variant should map to 'other'."""
    valid_poses = [p.value for p in PoseVariant]
    pose = "breakdancing"
    assert pose not in valid_poses
    pose = pose if pose in valid_poses else "other"
    assert pose == "other"


def test_all_valid_poses_pass_through():
    """All enum values should be recognized as valid."""
    valid_poses = [p.value for p in PoseVariant]
    for pose_value in valid_poses:
        pose = pose_value if pose_value in valid_poses else "other"
        assert pose == pose_value


def test_parse_ai_response_with_backticks_no_lang():
    """Parse JSON with ``` backticks but no language tag."""
    result_str = '```\n{"common_name": "Blue Jay", "confidence": 0.85, "pose_variant": "perching"}\n```'
    cleaned = result_str.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(cleaned)
    assert result["common_name"] == "Blue Jay"


# ---------------------------------------------------------------------------
# Integration tests: API endpoints (mocked AI, no real huey consumer)
# ---------------------------------------------------------------------------


async def test_identify_sighting_creates_job(auth_client):
    """POST /api/sightings/{id}/identify should create a job and return job_id."""
    # Create a sighting with a photo via the API
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    resp = await auth_client.post(
        "/api/sightings",
        files={"file": ("test.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 201
    sighting_id = resp.json()["id"]

    fake_job_id = str(uuid.uuid4())

    # Mock start_identification to just return a fake job_id
    async def mock_start_identification(sighting_id_arg, db):
        return fake_job_id

    with patch("app.services.identifier.start_identification", side_effect=mock_start_identification):
        response = await auth_client.post(f"/api/sightings/{sighting_id}/identify")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == fake_job_id
    assert data["status"] == "pending"


async def test_get_job_status(auth_client, db_session):
    """GET /api/jobs/{id} should return job details."""
    job = Job(
        id=str(uuid.uuid4()),
        type="identify",
        sighting_id=str(uuid.uuid4()),
        status="completed",
        result={"common_name": "Test Bird", "confidence": 0.9},
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()

    response = await auth_client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job.id
    assert data["type"] == "identify"
    assert data["status"] == "completed"
    assert data["result"]["common_name"] == "Test Bird"
    assert data["created_at"] is not None
    assert data["completed_at"] is not None


async def test_get_job_not_found(auth_client):
    """GET /api/jobs/{id} with unknown id should return 404."""
    response = await auth_client.get(f"/api/jobs/{str(uuid.uuid4())}")
    assert response.status_code == 404


async def test_identify_no_photo_returns_400(auth_client):
    """POST /identify on a sighting without a photo should return 400."""
    # Create sighting without photo via API
    resp = await auth_client.post("/api/sightings", data={"notes": "no photo"})
    assert resp.status_code == 201
    sighting_id = resp.json()["id"]

    response = await auth_client.post(f"/api/sightings/{sighting_id}/identify")
    assert response.status_code == 400
    assert "no photo" in response.json()["detail"].lower()


async def test_identify_not_found_returns_404(auth_client):
    """POST /identify on a non-existent sighting should return 404."""
    response = await auth_client.post(f"/api/sightings/{str(uuid.uuid4())}/identify")
    assert response.status_code == 404


async def test_job_status_pending(auth_client, db_session):
    """Job with pending status should have null completed_at."""
    job = Job(
        id=str(uuid.uuid4()),
        type="identify",
        sighting_id=str(uuid.uuid4()),
        status="pending",
    )
    db_session.add(job)
    await db_session.commit()

    response = await auth_client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["completed_at"] is None
    assert data["error"] is None
    assert data["result"] is None


async def test_job_status_failed(auth_client, db_session):
    """Job with failed status should have error message."""
    job = Job(
        id=str(uuid.uuid4()),
        type="identify",
        sighting_id=str(uuid.uuid4()),
        status="failed",
        error="AI service unavailable",
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()

    response = await auth_client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "AI service unavailable"


async def test_identify_unauthenticated_returns_401(client):
    """POST /identify without auth should return 401."""
    response = await client.post(f"/api/sightings/{str(uuid.uuid4())}/identify")
    assert response.status_code == 401


async def test_job_status_unauthenticated_returns_401(client):
    """GET /jobs/{id} without auth should return 401."""
    response = await client.get(f"/api/jobs/{str(uuid.uuid4())}")
    assert response.status_code == 401
