# ── Stage 1: Build SvelteKit frontend ──────────────────────────────────
FROM node:24-slim AS frontend-build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build
# adapter-static outputs to ../backend/app/static relative to frontend/

# ── Stage 2: Python backend ────────────────────────────────────────────
FROM python:3.13-slim

ARG GIT_SHA=dev

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN adduser --system --group appuser && \
    apt-get update && apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend code first (needed by hatchling to discover packages)
COPY backend/pyproject.toml ./
COPY backend/app/ ./app/
COPY backend/migrations/ ./migrations/
COPY backend/alembic.ini ./

# Install Python dependencies (non-editable — Docker doesn't need it)
RUN uv pip install --system --no-cache .

# Copy built frontend static files from stage 1
COPY --from=frontend-build /backend/app/static/ ./app/static/

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Data directories — entrypoint.sh also creates them at runtime
# to survive volume mounts, but permissions are preset here
RUN mkdir -p /app/data /app/storage && \
    chown -R appuser:appuser /app/data /app/storage && \
    chmod 777 /app/data /app/storage

ENV GIT_SHA=${GIT_SHA}

# Don't set USER here — entrypoint runs as root to fix volume permissions,
# then drops to appuser via exec-su
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
