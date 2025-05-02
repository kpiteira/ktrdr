# KTRDR Backend Dockerfile
# Multi-stage build for optimized size and security

# --------------------------------------
# STAGE 1: Builder stage
# --------------------------------------
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY requirements.txt ./

# Install Python dependencies with uv
# Note: Using the --system flag to install in the system Python environment
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Build the package with uv
RUN uv pip install --system --no-cache-dir -e .

# --------------------------------------
# STAGE 2: Runtime stage
# --------------------------------------
FROM python:3.11-slim AS runtime

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
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/ktrdr $APP_HOME/ktrdr
COPY --from=builder /app/setup_dev.sh $APP_HOME/
COPY --from=builder /app/pyproject.toml $APP_HOME/

# Change ownership of the app directory
RUN chown -R $APP_USER:$APP_USER $APP_HOME

# Setup volume for data persistence
VOLUME ["$APP_HOME/data", "$APP_HOME/logs"]

# Configure health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fs http://localhost:8000/api/health || exit 1

# Expose the API port
EXPOSE 8000

# Switch to non-root user
USER $APP_USER

# Set up entrypoint with tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command to run the FastAPI server
CMD ["uvicorn", "ktrdr.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "/home/ktrdr/app/ktrdr/config/logging_config.json"]