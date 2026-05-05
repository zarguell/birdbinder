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
            from app.models.app_setting import AppSetting
            db_model = session.query(AppSetting).filter(AppSetting.key == "ai_model").first()
            db_prompt = session.query(AppSetting).filter(AppSetting.key == "birdbinder_id_prompt").first()
            model_override = db_model.value if db_model else None
            prompt = (db_prompt.value if db_prompt else None) or settings.birdbinder_id_prompt or DEFAULT_ID_PROMPT

            # Inject location + date context into prompt
            sighting = session.get(Sighting, sighting_id)
            context_lines = []

            if sighting.location_display_name:
                context_lines.append(f"This photo was taken in {sighting.location_display_name}. Use this to narrow down likely species and subspecies.")
            elif sighting.exif_lat is not None and sighting.exif_lon is not None:
                context_lines.append(f"GPS coordinates {sighting.exif_lat:.4f}, {sighting.exif_lon:.4f}. Use this to narrow down likely species and subspecies.")

            if sighting.exif_datetime:
                date_str = sighting.exif_datetime.strftime("%B %d, %Y")
                context_lines.append(f"The photo was taken on {date_str}. Consider seasonal plumage, migration status, and expected species for that time of year.")

            context_block = "\n\nLocation/date context: " + " ".join(context_lines) if context_lines else ""
            effective_prompt = prompt + context_block

            result_text = asyncio.run(call_vision_model(image_path, effective_prompt, model_override=model_override))
            logger.info("Job %s: AI response received (%d chars): %s", job_id, len(result_text), result_text[:500])

            # Store raw response on job (visible to user via API)
            job.raw_response = result_text[:5000]

            # Parse JSON response
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = (
                    result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                )
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Model may have returned prose with JSON embedded — try to extract it
                import re
                json_match = re.search(r'\{[^{}]*\}', result_text)
                if json_match:
                    logger.info("Job %s: extracted JSON from prose response", job_id)
                    result_text = json_match.group(0)
                    try:
                        result = json.loads(result_text)
                    except json.JSONDecodeError:
                        # Try balanced brace matching for nested JSON
                        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                        if json_match:
                            try:
                                result = json.loads(json_match.group(0))
                            except json.JSONDecodeError as e:
                                logger.error(
                                    "Job %s: failed to parse AI JSON response: %s | raw text: %s",
                                    job_id, e, result_text[:1000],
                                )
                                raise
                        else:
                            raise
                else:
                    logger.error(
                        "Job %s: failed to parse AI JSON response: no JSON found in prose | raw text: %s",
                        job_id, result_text[:1000],
                    )
                    raise json.JSONDecodeError("No JSON found in response", result_text, 0)

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

            # Update sighting with identification results
            sighting.status = "identified"
            sighting.manual_species_override = False
            sighting.species_common = result.get("common_name", "Unknown")
            sighting.species_scientific = result.get("scientific_name")
            sighting.family = result.get("family")
            sighting.pose_variant = pose
            sighting.id_confidence = confidence
            sighting.id_method = "ai"
            sighting.id_model = model_override or settings.ai_model

            # Reverse lookup species_code from common_name or scientific_name
            def _load_birds_data():
                from pathlib import Path
                import json
                path = Path(__file__).parent.parent / "data" / "birds.json"
                with open(path) as f:
                    return json.load(f)

            common = result.get("common_name", "")
            scientific = result.get("scientific_name", "")
            birds = _load_birds_data()
            matched = next(
                (b for b in birds if b["common_name"] == common or b["scientific_name"] == scientific),
                None
            )
            if matched:
                sighting.species_code = matched["species_code"]
            else:
                logger.warning("Could not find species_code for %s / %s", common, scientific)

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

            # Publish activity
            try:
                from app.models.activity import Activity
                activity = Activity(
                    user_identifier=sighting.user_identifier,
                    activity_type="sighting",
                    reference_id=sighting_id,
                    description=f"spotted a {common_name}",
                )
                session.add(activity)
                session.commit()
            except Exception:
                logger.warning("Failed to publish sighting activity", exc_info=True)
        except Exception as e:
            logger.error("Job %s: identification failed: %s", job_id, e, exc_info=True)
            job = session.get(Job, job_id)
            if not job:
                logger.error("Job %s not found during error handling", job_id)
                return
            job.status = JobStatus.failed.value
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()


# Register as huey task
@huey.task()
def identify_task(job_id: str, sighting_id: str, image_path: str):
    _run_identification(job_id, sighting_id, image_path)


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

    # Check for existing active job (prevent duplicates)
    from sqlalchemy import select
    existing = (await db.execute(
        select(Job).where(
            Job.sighting_id == sighting_id,
            Job.type == JobType.identify.value,
            Job.status.in_(["pending", "running"]),
        )
    )).scalar_one_or_none()
    if existing:
        logger.info("Existing active job %s for sighting %s, skipping", existing.id, sighting_id)
        return existing.id

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
