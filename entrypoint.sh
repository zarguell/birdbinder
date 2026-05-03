#!/bin/sh
set -e

# Ensure data directories exist and are writable
# (Bind mounts may be root-owned on host, so fix perms if running as root)
mkdir -p /app/data /app/storage
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /app/data /app/storage
    exec gosu appuser "$0" "$@"
fi

# Run Alembic migrations
echo "Running database migrations..."
PYTHONPATH=/app alembic upgrade head
echo "Migrations complete."

# Start uvicorn and huey consumer in the background
echo "Starting BirdBinder..."

uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

python -m huey.bin.huey_consumer app.huey_instance --worker-type process --workers 2 &
HUEY_PID=$!

# Graceful shutdown on SIGTERM
trap "kill $UVICORN_PID $HUEY_PID; wait" EXIT TERM INT

wait
