#!/usr/bin/env python3
"""
BirdBinder – Batch Image Import
================================
Bulk-imports bird sightings from a directory of images. For each image file
the script uploads the sighting, triggers card generation, and waits for the
job to complete before moving on.

Uses only the Python standard library (no pip dependencies).

Usage:
    python batch_import.py --directory /path/to/photos [OPTIONS]

Options:
    --base-url URL      API base URL          (default: http://localhost:8000)
    --api-key KEY       Bearer token           (default: empty / local mode)
    --directory PATH    Directory of images     (required)
    --notes TEXT        Default notes for all   (default: "")

Supported image extensions: .jpg  .jpeg  .png  .webp

Examples:
    python batch_import.py --directory ./bird_photos
    python batch_import.py --directory ./photos --notes "Backyard feeder" --api-key mykey
"""

import argparse
import io
import json
import mimetypes
import pathlib
import sys
import time
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def build_request(url: str, api_key: str = "") -> urllib.request.Request:
    """Return a basic Request object with optional auth header."""
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    return req


def api_request(
    url: str,
    api_key: str = "",
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
) -> dict:
    """Perform an API request and return parsed JSON."""
    req = build_request(url, api_key)
    req.method = method
    if data is not None:
        req.data = data
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        if exc.readable():
            body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {exc.reason} — {body}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection error: {exc.reason}") from None


def upload_multipart(
    url: str, api_key: str, file_path: pathlib.Path, notes: str
) -> dict:
    """Upload a file via multipart/form-data and return parsed JSON."""
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    # Build multipart body
    boundary = "----BirdBinderBoundary" + str(int(time.time() * 1000))
    body = io.BytesIO()

    # File part
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    body.write(f"Content-Type: {mime_type}\r\n\r\n".encode())
    body.write(file_path.read_bytes())
    body.write(b"\r\n")

    # Notes part
    if notes:
        body.write(f"--{boundary}\r\n".encode())
        body.write(b'Content-Disposition: form-data; name="notes"\r\n\r\n')
        body.write(notes.encode("utf-8"))
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode())
    payload = body.getvalue()

    req = build_request(url, api_key)
    req.method = "POST"
    req.data = payload
    req.add_header(
        "Content-Type",
        f"multipart/form-data; boundary={boundary}",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        b = ""
        if exc.readable():
            b = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Upload HTTP {exc.code}: {exc.reason} — {b}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Upload connection error: {exc.reason}") from None


# ---------------------------------------------------------------------------
# Job polling
# ---------------------------------------------------------------------------

POLL_INTERVAL = 2  # seconds
MAX_POLLS = 120    # 4 minutes timeout per job


def poll_job(base_url: str, api_key: str, job_id: str) -> dict:
    """Poll a job until it completes or fails. Returns the final job dict."""
    url = f"{base_url}/api/jobs/{job_id}"
    for _ in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        job = api_request(url, api_key)
        status = (job.get("status") or "").lower()
        if status in ("completed", "done", "finished"):
            return job
        if status in ("failed", "error"):
            raise RuntimeError(
                f"Job {job_id} failed: {job.get('error', job.get('message', 'unknown'))}"
            )
        # still running — loop
    raise RuntimeError(f"Job {job_id} timed out after {MAX_POLLS * POLL_INTERVAL}s")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
RATE_LIMIT_DELAY = 0.5  # seconds between uploads


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-import bird sightings from a directory of images."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Bearer token for authentication (default: empty)",
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="Directory containing image files to import",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Default notes attached to every sighting (default: empty)",
    )
    return parser.parse_args()


def find_images(directory: pathlib.Path) -> list[pathlib.Path]:
    """Recursively find all supported image files."""
    images = sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    return images


def process_image(
    base_url: str,
    api_key: str,
    image: pathlib.Path,
    notes: str,
    index: int,
    total: int,
) -> bool:
    """Upload one image, generate its card, and poll until done. Returns True on success."""
    prefix = f"[{index}/{total}]"
    print(f"{prefix} Uploading {image.name} ...", end=" ", flush=True)

    # Step 1 – upload sighting
    try:
        sighting = upload_multipart(
            f"{base_url}/api/sightings", api_key, image, notes
        )
    except RuntimeError as exc:
        print(f"FAILED (upload): {exc}")
        return False

    sighting_id = sighting.get("sighting_id") or sighting.get("id")
    if not sighting_id:
        print(f"FAILED (no sighting_id in response)")
        return False

    # Step 2 – trigger card generation
    try:
        gen = api_request(
            f"{base_url}/api/cards/generate/{sighting_id}", api_key, method="POST"
        )
    except RuntimeError as exc:
        print(f"FAILED (generate): {exc}")
        return False

    job_id = gen.get("job_id")
    if not job_id:
        print("FAILED (no job_id in response)")
        return False

    # Step 3 – poll
    try:
        job = poll_job(base_url, api_key, job_id)
    except RuntimeError as exc:
        print(f"FAILED (poll): {exc}")
        return False

    card_url = (
        job.get("card_url")
        or (job.get("result") or {}).get("card_url")
        or (job.get("output") or {}).get("url")
        or ""
    )
    status_msg = f"Card generated! {card_url}" if card_url else "Card generated!"
    print(status_msg)
    return True


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    directory = pathlib.Path(args.directory)

    if not directory.is_dir():
        print(f"ERROR: '{directory}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    images = find_images(directory)
    if not images:
        print(f"No supported image files found in '{directory}'.")
        sys.exit(0)

    total = len(images)
    print(f"Found {total} image(s) in '{directory}'. Starting batch import...\n")

    succeeded = 0
    failed = 0
    errors: list[str] = []

    for idx, image in enumerate(images, start=1):
        ok = process_image(base_url, args.api_key, image, args.notes, idx, total)
        if ok:
            succeeded += 1
        else:
            failed += 1
            errors.append(image.name)

        # Rate-limit between uploads
        if idx < total:
            time.sleep(RATE_LIMIT_DELAY)

    # Summary
    print()
    print("=== Batch Import Summary ===")
    print(f"  Total    : {total}")
    print(f"  Succeeded: {succeeded}")
    print(f"  Failed   : {failed}")
    if errors:
        print(f"  Failed files: {', '.join(errors)}")


if __name__ == "__main__":
    main()
