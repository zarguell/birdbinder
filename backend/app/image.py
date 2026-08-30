from PIL import Image, ExifTags
from pathlib import Path
import io

# Register HEIF/HEIC support if pillow-heif is installed
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False


HEIF_EXTENSIONS = frozenset({".heic", ".heif"})


def is_heif(path: Path | str) -> bool:
    """Check if file is a HEIF/HEIC image."""
    return Path(path).suffix.lower() in HEIF_EXTENSIONS


def convert_heif_to_jpeg(source_path: Path, dest_path: Path | None = None, quality: int = 90) -> Path:
    """Convert a HEIF/HEIC image to JPEG.

    Returns path to the JPEG file (overwrites source if dest_path is None).
    Raises ValueError if pillow-heif is not available.
    """
    if not HEIF_SUPPORT:
        raise ValueError(
            "HEIF/HEIC support requires pillow-heif. "
            "Install with: pip install pillow-heif"
        )

    if dest_path is None:
        dest_path = source_path.with_suffix(".jpg")

    img = Image.open(source_path)
    # Convert to RGB if necessary (HEIF may be in other color spaces)
    if img.mode != "RGB":
        img = img.convert("RGB")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest_path, format="JPEG", quality=quality)

    # If we wrote to a different file, remove the original
    if dest_path != source_path:
        source_path.unlink()

    return dest_path


def normalize_image(source_path: Path) -> Path:
    """Convert HEIF to JPEG if needed. Returns the (possibly new) path."""
    if is_heif(source_path) and HEIF_SUPPORT:
        return convert_heif_to_jpeg(source_path)
    return source_path


def extract_exif(image_path: Path) -> dict:
    """Extract EXIF metadata from an image file.
    Returns dict with: datetime, lat, lon, camera_model.
    All fields may be None if not present.
    """
    result = {"datetime": None, "lat": None, "lon": None, "camera_model": None}
    try:
        # Normalize HEIF first
        img_path = normalize_image(image_path)
        img = Image.open(img_path)
        exif_data = img.getexif()
        if not exif_data:
            return result

        # DateTime
        dt_str = exif_data.get(ExifTags.Base.DateTimeOriginal) or exif_data.get(ExifTags.Base.DateTime)
        if dt_str:
            result["datetime"] = dt_str.strip()

        # Camera model
        result["camera_model"] = exif_data.get(ExifTags.Base.Model)

        # GPS coordinates (from GPSInfo IFD)
        gps_info = exif_data.get_ifd(ExifTags.Base.GPSInfo)
        if gps_info:
            gps = {}
            for tag, value in gps_info.items():
                name = ExifTags.GPSTAGS.get(tag, tag)
                gps[name] = value
            if "GPSLatitude" in gps and "GPSLatitudeRef" in gps:
                lat = _convert_gps_coord(gps["GPSLatitude"], gps["GPSLatitudeRef"])
                result["lat"] = lat
            if "GPSLongitude" in gps and "GPSLongitudeRef" in gps:
                lon = _convert_gps_coord(gps["GPSLongitude"], gps["GPSLongitudeRef"])
                result["lon"] = lon
    except Exception:
        pass  # Return empty dict for non-JPEG or corrupted files
    return result


def _convert_gps_coord(coord, ref):
    """Convert GPS coordinate from (degrees, minutes, seconds) to float.

    coord may be in nested format ((d_num, d_den), (m_num, m_den), (s_num, s_den))
    or flat format (d_num, d_den, m_num, m_den, s_num, s_den) as returned by
    different Pillow code paths.
    """
    if len(coord) == 3 and isinstance(coord[0], (tuple, list)):
        # Nested format: ((num, den), (num, den), (num, den))
        d = float(coord[0][0]) / float(coord[0][1])
        m = float(coord[1][0]) / float(coord[1][1])
        s = float(coord[2][0]) / float(coord[2][1])
    elif len(coord) == 6:
        # Flat format: (d_num, d_den, m_num, m_den, s_num, s_den)
        d = float(coord[0]) / float(coord[1])
        m = float(coord[2]) / float(coord[3])
        s = float(coord[4]) / float(coord[5])
    else:
        return None
    decimal = d + m / 60.0 + s / 3600.0
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def generate_thumbnail(source_path: Path, thumb_path: Path, size: tuple = (300, 300)) -> Path:
    """Generate a thumbnail image. Returns path to thumbnail."""
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize HEIF first
    img_path = normalize_image(source_path)
    img = Image.open(img_path)
    img.thumbnail(size)
    img.save(thumb_path, format="JPEG", quality=85)
    return thumb_path
