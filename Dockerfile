# syntax=docker/dockerfile:1
#
# AeroNerds SIH26011 — production image.
# Single container: FastAPI serves the API and the static frontend on one port,
# so there is no separate web server to keep in sync.

# ---------- build stage: compile wheels once ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements-auth.txt .
RUN pip wheel --wheel-dir /wheels -r requirements-auth.txt

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # random per container unless you set a real secret — see docs/DEPLOY_AWS.md
    AERONERDS_TOKEN_SECRET="" \
    # the variable backend/main.py actually reads; must match exactly
    AERONERDS_AUTH_DB=/data/aeronerds_auth.db \
    PORT=8000

# curl is used by the compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements-auth.txt .
RUN pip install --no-index --find-links=/wheels -r requirements-auth.txt \
    && rm -rf /wheels

# run as an unprivileged user
RUN useradd --create-home --uid 10001 aeronerds \
    && mkdir -p /data /app \
    && chown -R aeronerds:aeronerds /data /app

WORKDIR /app

# Copy only what the server needs. Tests, docs and raw datasets stay out.
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run_server.py run_demo.py ./

USER aeronerds

EXPOSE 8000

# The SQLite auth store must live on a mounted volume, not in the image layer.
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/meta/health" || exit 1

CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
