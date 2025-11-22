FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV for dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files from root project
COPY pyproject.toml uv.lock ./

# Install dependencies with uv sync
RUN uv sync --frozen --no-dev --no-install-project

# Copy application
COPY . .

# Runtime stage
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user
RUN useradd -m -u 1000 ktrdr && \
    mkdir -p /app/experiments /app/logs && \
    chown -R ktrdr:ktrdr /app

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /app/.venv/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app /app

# Health check endpoint (we'll add this later)
EXPOSE 3100

USER ktrdr

# MCP uses stdio
CMD ["python", "-m", "src.main"]
