"""Tests for job endpoint ownership and duplicate-generation guards."""

import uuid

import pytest

from app.main import app
from app.models.card import Card
from app.models.job import Job
from app.models.sighting import Sighting
from tests.conftest import TEST_USER

OTHER_USER = "other-user@example.com"


async def _make_sighting_with_job(db, user, job_status="running"):
    sighting = Sighting(id=str(uuid.uuid4()), user_identifier=user, status="pending")
    db.add(sighting)
    await db.flush()
    job = Job(
        id=str(uuid.uuid4()),
        type="identify",
        sighting_id=sighting.id,
        user_identifier=user,
        status=job_status,
    )
    db.add(job)
    await db.commit()
    return sighting, job


@pytest.mark.asyncio
async def test_get_job_requires_ownership(auth_client, db_session):
    """A user cannot read another user's job (including raw AI response)."""
    _sighting, job = await _make_sighting_with_job(db_session, OTHER_USER)

    resp = await auth_client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_allowed_for_owner(auth_client, db_session):
    sighting, job = await _make_sighting_with_job(db_session, TEST_USER)

    resp = await auth_client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job.id


@pytest.mark.asyncio
async def test_start_card_generation_rejects_existing_card(auth_client, db_session):
    """A second generate request for an already-carded sighting must fail."""
    sighting = Sighting(id=str(uuid.uuid4()), user_identifier=TEST_USER, status="identified")
    db_session.add(sighting)
    await db_session.flush()
    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        user_identifier=TEST_USER,
        species_common="Robin",
        species_code="robin",
        pose_variant="perching",
        id_method="ai",
        duplicate_count=1,
    )
    db_session.add(card)
    await db_session.commit()

    resp = await auth_client.post(f"/api/cards/generate/{sighting.id}")
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]
