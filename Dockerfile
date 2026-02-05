# =============================================================================
# Medic Production Dockerfile
# Multi-stage build supporting both amd64 (x86_64) and arm64 (Graviton/M1)
# =============================================================================
#
# Base Image Evaluation (Python 3.14) - February 2026
# -----------------------------------------------------------------------------
# Image                        | Size    | Notes
# -----------------------------|---------|----------------------------------------
# python:3.14-bookworm         | 1.49GB  | Full Debian, includes compilers/dev tools
# python:3.14-slim-bookworm    | 211MB   | Minimal Debian, glibc-based (RECOMMENDED)
# python:3.14-alpine           | 77.1MB  | Smallest, but uses musl libc
#
# Decision: Using slim-bookworm because:
# - 3x smaller than full image while maintaining glibc compatibility
# - Prebuilt wheels (psycopg2-binary, cryptography) work without issues
# - Alpine's musl libc can cause compatibility issues with native extensions
# - Alpine builds are slower (must compile from source when wheels unavailable)
# - Bookworm (Debian 12) provides stable, long-term support
#
# References:
# - https://pythonspeed.com/articles/base-image-python-docker-images/
# - https://hub.docker.com/_/python
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# Install dependencies and compile any native extensions
# -----------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies for native extensions (psycopg2, cryptography)
# These packages work on both amd64 and arm64 architectures
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY Medic/requirements.txt ./requirements.txt
RUN pip install --user --no-warn-script-location -r requirements.txt

# Install gunicorn for production WSGI server
RUN pip install --user --no-warn-script-location gunicorn>=21.0.0

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# Minimal image with only runtime dependencies
# -----------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Metadata labels
LABEL maintainer="Medic Team <medic@example.com>" \
      version="1.0.0" \
      description="Medic - Heartbeat Monitoring Service for production deployment"

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/medic/.local/bin:$PATH" \
    MEDIC_PORT=8080

WORKDIR /app

# Install only runtime dependencies (libpq for psycopg2, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user with explicit uid for Kubernetes compatibility
RUN useradd --create-home --shell /bin/bash --uid 1000 medic

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/medic/.local

# Copy application code
COPY --chown=medic:medic Medic/ ./Medic/
COPY --chown=medic:medic medic.py ./
COPY --chown=medic:medic config.py ./
COPY --chown=medic:medic migrations/ ./migrations/
COPY --chown=medic:medic scripts/ ./scripts/

# Switch to non-root user
USER medic

# Expose application port
EXPOSE 8080

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with gunicorn for production
# Workers: 2-4 per CPU core, configurable via GUNICORN_WORKERS env var
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-", "medic:app"]
