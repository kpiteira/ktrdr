# KTRDR Backend Dockerfile
# Multi-stage build for optimized size and security

# --------------------------------------
# STAGE 1: Builder stage
# --------------------------------------
FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    TMPDIR=/tmp

# Set work directory
WORKDIR /app

# Ensure tmp directory exists and is writable
RUN mkdir -p /tmp && chmod 1777 /tmp

# Install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc

# Install UV for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv sync (creates .venv)
# Use BuildKit cache mount to persist uv package cache between CI builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy the project files
COPY . .

# Install the project package
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --------------------------------------
# STAGE 2: Runtime stage
# --------------------------------------
FROM python:3.13-slim AS runtime

# Set metadata labels following best practices
LABEL org.opencontainers.image.title="KTRDR Backend"
LABEL org.opencontainers.image.description="KTRDR trading system backend API"
LABEL org.opencontainers.image.version="1.0.5.5"
LABEL org.opencontainers.image.licenses="Proprietary"
LABEL org.opencontainers.image.authors="KTRDR Team"
LABEL org.opencontainers.image.source="https://github.com/username/ktrdr"
LABEL org.opencontainers.image.documentation="https://ktrdr.io/docs"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_USER=ktrdr \
    APP_HOME=/home/ktrdr/app

# Create a non-root user
RUN groupadd -r $APP_USER && \
    useradd -r -g $APP_USER -d $APP_HOME -s /bin/bash -c "KTRDR user" $APP_USER && \
    mkdir -p $APP_HOME && \
    mkdir -p $APP_HOME/logs && \
    mkdir -p $APP_HOME/data

# Set the working directory
WORKDIR $APP_HOME

# Install runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl

# Copy from builder stage - only what's needed for production
COPY --from=builder /app/.venv/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app/ktrdr $APP_HOME/ktrdr
COPY --from=builder /app/mcp $APP_HOME/mcp
COPY --from=builder /app/config $APP_HOME/config
COPY --from=builder /app/strategies $APP_HOME/strategies
COPY --from=builder /app/pyproject.toml $APP_HOME/

# Change ownership of the app directory
RUN chown -R $APP_USER:$APP_USER $APP_HOME

# Setup volume for data persistence
VOLUME ["$APP_HOME/data", "$APP_HOME/logs"]

# Configure health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fs http://localhost:8000/api/v1/health || exit 1

# Expose the API port
EXPOSE 8000

# Switch to non-root user
USER $APP_USER

# Set up entrypoint with tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command to run the FastAPI server
CMD ["python", "-m", "uvicorn", "ktrdr.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "/home/ktrdr/app/ktrdr/config/logging_config.json"]