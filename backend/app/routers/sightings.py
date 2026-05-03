import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.sighting import Sighting
from app.models.job import Job
from app.schemas.sighting import SightingRead, SightingList
from app import storage, image

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
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sighting_id = str(uuid.uuid4())
    photo_path = None
    thumbnail_path = None
    exif_datetime = None
    exif_lat = None
    exif_lon = None
    exif_camera_model = None

    if file and file.filename:
        # Determine extension from content type
        ct = (file.content_type or "").lower()
        extension = CT_EXTENSIONS.get(ct, "jpg")

        file_content = await file.read()
        photo_path = storage.save_upload(file_content, sighting_id, extension)

        # Extract EXIF from saved image
        abs_photo = storage.get_file_path(photo_path)
        exif = image.extract_exif(abs_photo)
        if exif:
            exif_camera_model = exif.get("camera_model")
            exif_lat = exif.get("lat")
            exif_lon = exif.get("lon")
            dt_str = exif.get("datetime")
            if dt_str:
                try:
                    exif_datetime = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError):
                    pass

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
        exif_datetime=exif_datetime,
        exif_lat=exif_lat,
        exif_lon=exif_lon,
        exif_camera_model=exif_camera_model,
        location_display_name=location_display_name,
        notes=notes,
    )
    db.add(sighting)
    await db.commit()
    await db.refresh(sighting)
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
