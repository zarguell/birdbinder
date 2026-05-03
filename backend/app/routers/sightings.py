import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.sighting import Sighting
from app.models.job import Job
from app.models.enums import PoseVariant
from app.schemas.sighting import SightingRead, SightingList, SightingOverride
from app.services.species import get_species_by_code
from app import storage, image

logger = logging.getLogger(__name__)

router = APIRouter()

# Map common content types to extensions
CT_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


@router.post("/sightings", response_model=SightingRead, status_code=status.HTTP_201_CREATED)
async def create_sighting(
    file: UploadFile | None = File(default=None),
    notes: str | None = Form(default=None),
    location_display_name: str | None = Form(default=None),
    # Client-side EXIF fallback (when browser strips EXIF before upload)
    exif_datetime: str | None = Form(default=None),
    exif_lat: float | None = Form(default=None),
    exif_lon: float | None = Form(default=None),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sighting_id = str(uuid.uuid4())
    photo_path = None
    thumbnail_path = None
    exif_datetime_val = None
    exif_lat_val = None
    exif_lon_val = None
    exif_camera_model = None

    # Parse client-sent EXIF as fallback
    if exif_datetime:
        try:
            exif_datetime_val = datetime.strptime(exif_datetime, "%Y:%m:%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except (ValueError, TypeError):
            pass
    if exif_lat is not None:
        exif_lat_val = exif_lat
    if exif_lon is not None:
        exif_lon_val = exif_lon

    if file and file.filename:
        # Determine extension from content type
        ct = (file.content_type or "").lower()
        extension = CT_EXTENSIONS.get(ct, "jpg")

        file_content = await file.read()
        photo_path = storage.save_upload(file_content, sighting_id, extension)
        abs_photo = storage.get_file_path(photo_path)

        # Extract EXIF BEFORE any conversion (Pillow strips EXIF during save)
        # Server-side extraction (may be empty if browser already stripped EXIF)
        exif = image.extract_exif(abs_photo)
        if exif:
            exif_camera_model = exif.get("camera_model")
            if exif_lat_val is None:
                exif_lat_val = exif.get("lat")
            if exif_lon_val is None:
                exif_lon_val = exif.get("lon")
            dt_str = exif.get("datetime")
            if dt_str and exif_datetime_val is None:
                try:
                    exif_datetime_val = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError):
                    pass

        # Convert HEIC/HEIF to JPEG if needed
        if image.is_heif(abs_photo):
            try:
                abs_photo = image.convert_heif_to_jpeg(abs_photo)
                photo_path = f"sightings/{sighting_id}.jpg"
                logger.info("Converted HEIF to JPEG: %s", abs_photo)
            except ValueError:
                logger.warning("HEIF upload but pillow-heif not installed, identification may fail")

        # Generate thumbnail
        try:
            thumb_dir = storage.get_storage_path() / "sightings"
            thumb_path = thumb_dir / f"{sighting_id}_thumb.jpg"
            image.generate_thumbnail(abs_photo, thumb_path)
            thumbnail_path = f"sightings/{sighting_id}_thumb.jpg"
        except Exception:
            pass  # Thumbnail generation failure should not block sighting creation

    sighting = Sighting(
        id=sighting_id,
        user_identifier=user,
        photo_path=photo_path,
        thumbnail_path=thumbnail_path,
        exif_datetime=exif_datetime_val,
        exif_lat=exif_lat_val,
        exif_lon=exif_lon_val,
        exif_camera_model=exif_camera_model,
        location_display_name=location_display_name,
        notes=notes,
    )
    db.add(sighting)
    await db.commit()
    await db.refresh(sighting)

    # Auto-trigger identification if photo was uploaded
    if photo_path:
        try:
            from app.services.identifier import start_identification
            job_id = await start_identification(sighting_id, db)
            logger.info("Auto-triggered identification for sighting %s (job %s)", sighting_id, job_id)
        except Exception as e:
            logger.warning("Failed to auto-trigger identification for %s: %s", sighting_id, e)

    return sighting


@router.get("/sightings", response_model=SightingList)
async def list_sightings(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Sighting).where(Sighting.user_identifier == user)
    count_query = select(func.count()).select_from(Sighting).where(Sighting.user_identifier == user)

    if status_filter:
        query = query.where(Sighting.status == status_filter)
        count_query = count_query.where(Sighting.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(Sighting.submitted_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    sightings = result.scalars().all()

    return SightingList(items=sightings, total=total, limit=limit, offset=offset)


@router.get("/sightings/{sighting_id}", response_model=SightingRead)
async def get_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Sighting).where(
            Sighting.id == sighting_id, Sighting.user_identifier == user
        )
    )
    sighting = result.scalar_one_or_none()
    if not sighting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")
    return sighting


@router.delete("/sightings/{sighting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Sighting).where(
            Sighting.id == sighting_id, Sighting.user_identifier == user
        )
    )
    sighting = result.scalar_one_or_none()
    if not sighting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")

    await db.delete(sighting)
    await db.commit()


@router.patch("/sightings/{sighting_id}", response_model=SightingRead)
async def update_sighting(
    sighting_id: str,
    override: SightingOverride,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual species override or pose variant update for a sighting."""
    result = await db.execute(
        select(Sighting).where(
            Sighting.id == sighting_id, Sighting.user_identifier == user
        )
    )
    sighting = result.scalar_one_or_none()
    if not sighting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found"
        )

    if override.species_code is not None:
        species = get_species_by_code(override.species_code)
        if not species:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown species code: {override.species_code}",
            )
        sighting.species_code = species["species_code"]
        sighting.species_common = species["common_name"]
        sighting.species_scientific = species["scientific_name"]
        sighting.family = species.get("family")
        sighting.manual_species_override = True
        sighting.id_method = "manual"
        sighting.id_confidence = 1.0
        sighting.status = "identified"

    if override.pose_variant is not None:
        valid_poses = [p.value for p in PoseVariant]
        if override.pose_variant not in valid_poses:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid pose variant: {override.pose_variant}. "
                f"Must be one of: {', '.join(valid_poses)}",
            )
        sighting.pose_variant = override.pose_variant

    await db.commit()
    await db.refresh(sighting)
    return sighting


@router.get("/sightings/{sighting_id}/job")
async def get_sighting_job(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest job status for a sighting (for polling identification progress)."""
    result = await db.execute(
        select(Job)
        .where(Job.sighting_id == sighting_id, Job.type == "identify")
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"job": None}
    return {
        "job": {
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "error": job.error,
            "result": job.result,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    }


@router.post("/sightings/{sighting_id}/identify")
async def identify_sighting(
    sighting_id: str,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.identifier import start_identification

    # Verify ownership
    result = await db.execute(
        select(Sighting).where(
            Sighting.id == sighting_id, Sighting.user_identifier == user
        )
    )
    sighting = result.scalar_one_or_none()
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")
    try:
        job_id = await start_identification(sighting_id, db)
        return {"job_id": job_id, "status": "pending"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
