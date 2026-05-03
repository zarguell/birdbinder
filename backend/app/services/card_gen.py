import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.huey_instance import huey

logger = logging.getLogger(__name__)

# NOTE: Huey tasks run synchronously, so we use synchronous SQLAlchemy for DB access
_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
_sync_engine = create_engine(_sync_db_url)

CARD_ART_PROMPT_TEMPLATE = """Create a collectible trading card illustration of a {common_name} ({scientific_name}) in a {pose} pose.
The style should be {style}. The illustration should be suitable for a birding card collection.
The image should show the bird prominently with a clean background suitable for card art."""


def _run_card_generation(job_id: str, sighting_id: str):
    """Huey task: generate card art for a sighting."""
    import asyncio
    from app.models.card import Card
    from app.models.enums import JobStatus
    from app.models.job import Job
    from app.models.sighting import Sighting
    from app.storage import get_file_path

    with Session(_sync_engine) as session:
        try:
            # Update job status to running
            job = session.get(Job, job_id)
            job.status = JobStatus.running.value
            session.commit()

            sighting = session.get(Sighting, sighting_id)
            if not sighting:
                raise ValueError(f"Sighting {sighting_id} not found")

            # Get rarity tier (needed for species_info and card creation)
            rarity_tier = "common"
            try:
                from app.services.rarity import get_rarity_tier
                rarity_tier = get_rarity_tier(sighting.species_code)
            except ImportError:
                pass

            # Determine card art path
            card_art_url = None
            if settings.ai_api_key:
                try:
                    from app.services.ai import generate_card_art
                    from app.models.app_setting import AppSetting

                    image_path = ""
                    if sighting.photo_path:
                        image_path = str(get_file_path(sighting.photo_path))

                    # Read DB overrides for image model and style
                    db_image_model = session.query(AppSetting).filter(AppSetting.key == "ai_image_model").first()
                    db_style = session.query(AppSetting).filter(AppSetting.key == "card_style_name").first()
                    image_model_override = db_image_model.value if db_image_model else None
                    style_override = db_style.value if db_style else None

                    species_info = {
                        "common_name": sighting.species_common or "Unknown",
                        "scientific_name": sighting.species_scientific or "Unknown",
                        "pose_variant": sighting.pose_variant or "perching",
                        "rarity_tier": rarity_tier,
                    }
                    art_path = asyncio.run(
                        generate_card_art(
                            image_path=image_path,
                            species_info=species_info,
                            image_model_override=image_model_override,
                            style_override=style_override,
                        )
                    )
                    if art_path:
                        card_art_url = f"/storage/{art_path}"
                except Exception as e:
                    logger.warning("AI card art generation failed: %s", e, exc_info=True)

            # Fallback: use original photo
            if not card_art_url and sighting.photo_path:
                card_art_url = f"/storage/{sighting.photo_path}"

            # Create card
            card = Card(
                id=str(uuid.uuid4()),
                sighting_id=sighting_id,
                user_identifier=sighting.user_identifier,
                species_common=sighting.species_common or "Unknown",
                species_scientific=sighting.species_scientific,
                species_code=sighting.species_code or "unknown",
                family=sighting.family,
                pose_variant=sighting.pose_variant or "other",
                rarity_tier=rarity_tier,
                card_art_url=card_art_url,
                id_method=sighting.id_method or "ai",
                id_confidence=sighting.id_confidence,
            )
            session.add(card)

            # Update job
            job.status = JobStatus.completed.value
            job.completed_at = datetime.now(timezone.utc)
            job.result = {"card_id": card.id}
            session.commit()

            # Publish activity
            try:
                from app.models.activity import Activity
                activity = Activity(
                    user_identifier=sighting.user_identifier,
                    activity_type="card",
                    reference_id=card.id,
                    description=f"unlocked a {card.species_common} card",
                )
                session.add(activity)
                session.commit()
            except Exception:
                logger.warning("Failed to publish card activity", exc_info=True)
        except Exception as e:
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
def generate_card_task(job_id: str, sighting_id: str):
    _run_card_generation(job_id, sighting_id)


async def start_card_generation(sighting_id: str, db) -> str:
    """Start card generation for a sighting. Returns job_id.

    db is an async session - we create the job record, then enqueue the huey task.
    """
    from app.models.enums import JobStatus, JobType
    from app.models.job import Job
    from app.models.sighting import Sighting

    # Get sighting
    sighting = await db.get(Sighting, sighting_id)
    if not sighting:
        raise ValueError(f"Sighting {sighting_id} not found")

    # Create job record
    job = Job(
        id=str(uuid.uuid4()),
        type=JobType.generate_card.value,
        sighting_id=sighting_id,
        status=JobStatus.pending.value,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue huey task
    generate_card_task(job.id, sighting_id)

    return job.id
