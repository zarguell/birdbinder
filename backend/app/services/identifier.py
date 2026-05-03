import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.huey_instance import huey
from app.models.enums import JobStatus, JobType, PoseVariant
from app.services.ai import DEFAULT_ID_PROMPT, call_vision_model

logger = logging.getLogger(__name__)

# NOTE: Huey tasks run synchronously, so we use synchronous SQLAlchemy for DB access
_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
_sync_engine = create_engine(_sync_db_url)


def _run_identification(job_id: str, sighting_id: str, image_path: str):
    """Huey task: send image to AI, parse result, update sighting and job."""
    from app.models.job import Job
    from app.models.sighting import Sighting

    logger.info("Identification job %s starting for sighting %s", job_id, sighting_id)

    with Session(_sync_engine) as session:
        try:
            # Update job status to running
            job = session.get(Job, job_id)
            job.status = JobStatus.running.value
            session.commit()
            logger.info("Job %s: calling AI vision model...", job_id)

            # Call AI
            prompt = settings.birdbinder_id_prompt or DEFAULT_ID_PROMPT
            result_text = asyncio.run(call_vision_model(image_path, prompt))
            logger.info("Job %s: AI response received (%d chars)", job_id, len(result_text))

            # Parse JSON response
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = (
                    result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                )
            result = json.loads(result_text)

            # Validate pose_variant
            valid_poses = [p.value for p in PoseVariant]
            pose = result.get("pose_variant", "other")
            if pose not in valid_poses:
                pose = "other"

            common_name = result.get("common_name", "Unknown")
            confidence = result.get("confidence", 0)
            logger.info(
                "Job %s: identified as %s (%.0f%% confidence)",
                job_id, common_name, confidence * 100,
            )

            # Update sighting
            sighting = session.get(Sighting, sighting_id)
            sighting.status = "identified"
            sighting.manual_species_override = False

            # Update job
            job.status = JobStatus.completed.value
            job.completed_at = datetime.now(timezone.utc)
            job.result = {
                "common_name": result.get("common_name"),
                "scientific_name": result.get("scientific_name"),
                "family": result.get("family"),
                "confidence": result.get("confidence"),
                "distinguishing_traits": result.get("distinguishing_traits"),
                "pose_variant": pose,
            }
            session.commit()
            logger.info("Job %s: identification complete", job_id)
        except Exception as e:
            logger.error("Job %s: identification failed: %s", job_id, e, exc_info=True)
            job = session.get(Job, job_id)
            job.status = JobStatus.failed.value
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()


# Register as huey task
identify_task = huey.task(_run_identification)


async def start_identification(sighting_id: str, db) -> str:
    """Start an identification job. Returns job_id.

    db is an async session - we create the job record, then enqueue the huey task.
    """
    from app.models.job import Job
    from app.models.sighting import Sighting
    from app.storage import get_file_path

    # Get sighting
    sighting = await db.get(Sighting, sighting_id)
    if not sighting:
        raise ValueError(f"Sighting {sighting_id} not found")

    # Get image path
    if not sighting.photo_path:
        raise ValueError("Sighting has no photo")

    image_abs = str(get_file_path(sighting.photo_path))

    # Create job record
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.identify.value,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    db.add(job)

    # Update sighting status
    sighting.status = "pending"  # still pending, awaiting AI

    await db.commit()
    await db.refresh(job)

    # Enqueue huey task
    identify_task(job.id, sighting_id, image_abs)
    logger.info("Enqueued identification job %s for sighting %s", job.id, sighting_id)

    return job.id
