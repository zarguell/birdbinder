#!/bin/sh
set -e

# Ensure data directories exist before starting
# (Volume mounts overlay image-created dirs, so we must create at runtime)
mkdir -p /app/data /app/storage

# Run Alembic migrations
echo "Running database migrations..."
PYTHONPATH=/app alembic upgrade head
echo "Migrations complete."

# Start uvicorn and huey consumer in the background
echo "Starting BirdBinder..."

uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

huey_consumer.py app.huey_instance --worker-type process --workers 2 &
HUEY_PID=$!

# Graceful shutdown on SIGTERM
trap "kill $UVICORN_PID $HUEY_PID; wait" EXIT TERM INT

wait
