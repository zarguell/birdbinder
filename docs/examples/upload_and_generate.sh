#!/usr/bin/env bash
# =============================================================================
# BirdBinder – Upload & Generate Card
# =============================================================================
# Demonstrates the full sighting-to-card workflow:
#   1. Upload a photo as a sighting  (POST /api/sightings)
#   2. Trigger card generation       (POST /api/cards/generate/{sighting_id})
#   3. Poll for job completion       (GET /api/jobs/{job_id})
#
# Usage:
#   ./upload_and_generate.sh <image_path> [notes]
#
# Examples:
#   ./upload_and_generate.sh photo.jpg
#   ./upload_and_generate.sh photo.jpg "Seen at the park"
#
# Environment variables (override defaults):
#   BASE_URL   – API base URL (default: http://localhost:8000)
#   API_KEY    – Bearer token for authentication (default: empty / local mode)
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

# --- Dependency checks -------------------------------------------------------
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: '$cmd' is required but not found in PATH." >&2
    echo "Install it and try again.  (e.g. apt install curl jq)" >&2
    exit 1
  fi
done

# --- Argument parsing --------------------------------------------------------
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <image_path> [notes]" >&2
  exit 1
fi

IMAGE_PATH="$1"
NOTES="${2:-}"

if [[ ! -f "$IMAGE_PATH" ]]; then
  echo "ERROR: File not found: $IMAGE_PATH" >&2
  exit 1
fi

# --- Helper: build auth header -----------------------------------------------
AUTH_HEADER=()
if [[ -n "$API_KEY" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${API_KEY}")
fi

# --- Step 1: Upload sighting -------------------------------------------------
echo "Uploading sighting: $IMAGE_PATH"

UPLOAD_RESPONSE=$(curl -s \
  "${AUTH_HEADER[@]}" \
  -F "file=@${IMAGE_PATH}" \
  -F "notes=${NOTES}" \
  "${BASE_URL}/api/sightings")

SIGHTING_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.sighting_id // .id // empty')

if [[ -z "$SIGHTING_ID" ]]; then
  echo "ERROR: Failed to upload sighting. Server response:" >&2
  echo "$UPLOAD_RESPONSE" | jq . >&2
  exit 1
fi

echo "  ✓ Sighting created with id: $SIGHTING_ID"

# --- Step 2: Trigger card generation -----------------------------------------
echo "Triggering card generation..."

GENERATE_RESPONSE=$(curl -s \
  -X POST \
  "${AUTH_HEADER[@]}" \
  "${BASE_URL}/api/cards/generate/${SIGHTING_ID}")

JOB_ID=$(echo "$GENERATE_RESPONSE" | jq -r '.job_id // empty')

if [[ -z "$JOB_ID" ]]; then
  echo "ERROR: Failed to start card generation. Server response:" >&2
  echo "$GENERATE_RESPONSE" | jq . >&2
  exit 1
fi

echo "  ✓ Card generation job started: $JOB_ID"

# --- Step 3: Poll for job completion -----------------------------------------
echo "Polling job status (every 2 s)..."

while true; do
  sleep 2

  JOB_RESPONSE=$(curl -s \
    "${AUTH_HEADER[@]}" \
    "${BASE_URL}/api/jobs/${JOB_ID}")

  STATUS=$(echo "$JOB_RESPONSE" | jq -r '.status // empty')

  case "$STATUS" in
    completed|done|finished)
      CARD_URL=$(echo "$JOB_RESPONSE" | jq -r '.card_url // .result.card_url // .output.url // empty')
      if [[ -n "$CARD_URL" ]]; then
        echo ""
        echo "========================================="
        echo "  Card generated successfully!"
        echo "  URL: ${CARD_URL}"
        echo "========================================="
      else
        echo ""
        echo "Job completed. Full response:"
        echo "$JOB_RESPONSE" | jq .
      fi
      break
      ;;
    failed|error)
      ERROR_MSG=$(echo "$JOB_RESPONSE" | jq -r '.error // .message // "unknown error"')
      echo "ERROR: Card generation failed: $ERROR_MSG" >&2
      echo "$JOB_RESPONSE" | jq . >&2
      exit 1
      ;;
    pending|processing|running|"")
      # Still in progress — print a dot and keep polling
      printf "."
      ;;
    *)
      echo "WARNING: Unknown job status '$STATUS' — continuing to poll..." >&2
      printf "."
      ;;
  esac
done
