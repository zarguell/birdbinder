import io
import pytest
from PIL import Image
from pathlib import Path
from unittest.mock import patch

from app.image import extract_exif, generate_thumbnail
from app.storage import save_upload, get_file_path, get_storage_path


def _make_jpeg_with_exif(
    color="red",
    datetime_original="2024:06:15 14:30:00",
    model="Canon EOS R5",
    gps_lat=None,
    gps_lon=None,
    lat_ref="N",
    lon_ref="E",
) -> bytes:
    """Create a JPEG image in memory with EXIF data, return bytes.

    gps_lat and gps_lon should be flat rationals: (d_num, d_den, m_num, m_den, s_num, s_den)
    """
    img = Image.new("RGB", (100, 100), color=color)
    exif = img.getexif()
    if datetime_original:
        exif[0x9003] = datetime_original  # DateTimeOriginal
    if model:
        exif[0x0110] = model  # Model

    # Add GPS if provided (set as a plain dict on the GPSInfo tag)
    if gps_lat is not None and gps_lon is not None:
        exif[0x8825] = {
            0: b"\x02\x02\x00\x00",  # GPSVersionID
            1: lat_ref,  # GPSLatitudeRef
            2: gps_lat,  # GPSLatitude (flat rationals)
            3: lon_ref,  # GPSLongitudeRef
            4: gps_lon,  # GPSLongitude (flat rationals)
        }

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    return buf.read()


def _make_png() -> bytes:
    """Create a PNG image in memory (no EXIF)."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


class TestExtractExif:
    def test_extract_exif_from_jpeg(self, tmp_path: Path):
        jpeg_bytes = _make_jpeg_with_exif()
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(jpeg_bytes)

        result = extract_exif(img_path)
        assert result["datetime"] == "2024:06:15 14:30:00"
        assert result["camera_model"] == "Canon EOS R5"

    def test_extract_exif_missing_gracefully(self, tmp_path: Path):
        png_bytes = _make_png()
        img_path = tmp_path / "test.png"
        img_path.write_bytes(png_bytes)

        result = extract_exif(img_path)
        assert result["datetime"] is None
        assert result["lat"] is None
        assert result["lon"] is None
        assert result["camera_model"] is None

    def test_gps_extraction(self, tmp_path: Path):
        # San Francisco: ~37.7749° N, 122.4194° W
        # DMS: 37°46'29.6"N, 122°25'10.0"W
        # Flat rationals: (d_num, d_den, m_num, m_den, s_num, s_den)
        lat = (37, 1, 46, 1, 296, 10)  # 37° 46' 29.6" N
        lon = (122, 1, 25, 1, 100, 10)  # 122° 25' 10.0" W
        jpeg_bytes = _make_jpeg_with_exif(gps_lat=lat, gps_lon=lon, lon_ref="W")
        img_path = tmp_path / "gps_test.jpg"
        img_path.write_bytes(jpeg_bytes)

        result = extract_exif(img_path)
        assert result["lat"] is not None
        assert result["lon"] is not None
        # Allow small floating point tolerance
        assert abs(result["lat"] - 37.7749) < 0.001
        assert abs(result["lon"] - (-122.4194)) < 0.001


class TestGenerateThumbnail:
    def test_generate_thumbnail(self, tmp_path: Path):
        # Create a large-ish test image
        img = Image.new("RGB", (2000, 1500), color="green")
        source_path = tmp_path / "large.jpg"
        img.save(source_path, format="JPEG")

        thumb_path = tmp_path / "thumbs" / "thumb.jpg"
        result = generate_thumbnail(source_path, thumb_path, size=(300, 300))

        assert result == thumb_path
        assert thumb_path.exists()

        thumb_img = Image.open(thumb_path)
        # Thumbnail should fit within 300x300 while maintaining aspect ratio
        assert thumb_img.width <= 300
        assert thumb_img.height <= 300
        # File should be smaller than the original
        assert thumb_path.stat().st_size < source_path.stat().st_size


class TestStorage:
    def test_save_upload_and_retrieve(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("app.storage.settings", type("S", (), {"storage_path": str(tmp_path)})())

        content = b"fake-image-data"
        sighting_id = "abc-123"

        relative = save_upload(content, sighting_id, extension="jpg")
        assert relative == "sightings/abc-123.jpg"

        abs_path = get_file_path(relative)
        assert abs_path.exists()
        assert abs_path.read_bytes() == content
