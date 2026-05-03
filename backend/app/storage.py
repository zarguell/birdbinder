import os
import uuid
from pathlib import Path
from app.config import settings


def get_storage_path() -> Path:
    return Path(settings.storage_path)


def save_upload(file_content: bytes, sighting_id: str, extension: str = "jpg") -> str:
    """Save uploaded file, return relative path from storage root."""
    storage = get_storage_path()
    sightings_dir = storage / "sightings"
    sightings_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{sighting_id}.{extension}"
    filepath = sightings_dir / filename
    filepath.write_bytes(file_content)
    return f"sightings/{filename}"


def get_file_path(relative_path: str) -> Path:
    """Get absolute path for a stored file."""
    return get_storage_path() / relative_path
