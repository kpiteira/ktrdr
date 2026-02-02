---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Split Dockerfiles

**Goal:** Create four Dockerfiles that build images with correct dependencies and sizes.

**Branch:** `feature/container-optimization`

**Builds on:** M2 (lazy imports — backend can now run without torch)

---

## E2E Validation

### Success Criteria

Build all four images and verify sizes and capabilities:

| Image | Target Size | Torch? | CUDA? |
|-------|-------------|--------|-------|
| ktrdr-backend:dev | ~500MB | Yes (CPU) | No |
| ktrdr-backend:prod | ~200-300MB | No | No |
| ktrdr-worker-cpu:test | ~500MB | Yes (CPU) | No |
| ktrdr-worker-gpu:test | ~3.3GB | Yes | Yes |

### Verification Commands

```bash
# Build all images
docker build -f deploy/docker/Dockerfile.dev -t ktrdr-backend:dev .
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:prod .
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
docker build -f deploy/docker/Dockerfile.worker-gpu -t ktrdr-worker-gpu:test .

# Check sizes
docker images | grep ktrdr

# Verify torch availability
docker run --rm ktrdr-backend:dev python -c "import torch; print(f'torch OK, cuda={torch.cuda.is_available()}')"
docker run --rm ktrdr-backend:prod python -c "import torch" && echo "FAIL" || echo "SUCCESS: no torch in prod"
docker run --rm ktrdr-worker-cpu:test python -c "import torch; print(f'torch OK, cuda={torch.cuda.is_available()}')"
docker run --rm ktrdr-worker-gpu:test python -c "import torch; print(f'torch OK, cuda={torch.cuda.is_available()}')"
```

---

## Task 3.1: Create Dockerfile.backend (Production)

**File(s):** `deploy/docker/Dockerfile.backend` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Create a minimal Dockerfile for the production backend — no torch, no ML dependencies.

**Target size:** ~200-300MB

**Template:**
```dockerfile
# =============================================================================
# KTRDR Backend - Production (No ML Dependencies)
# =============================================================================
# This image runs the API backend only. It does NOT include torch or ML deps.
# Workers use separate images with ML dependencies.
#
# Build: docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend .
# =============================================================================

FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies WITHOUT ML extras
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY ktrdr ./ktrdr
COPY mcp ./mcp
COPY config ./config
COPY strategies ./strategies
COPY alembic ./alembic
COPY alembic.ini ./

# Install the project
RUN uv sync --frozen --no-dev

# =============================================================================
# Runtime Stage
# =============================================================================
FROM python:3.13-slim AS runtime

# Create non-root user FIRST (before copying files)
RUN groupadd -r ktrdr && \
    useradd -r -g ktrdr -d /app -s /sbin/nologin ktrdr

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder with correct ownership
COPY --from=builder --chown=ktrdr:ktrdr /app/.venv /app/.venv
COPY --from=builder --chown=ktrdr:ktrdr /app/ktrdr /app/ktrdr
COPY --from=builder --chown=ktrdr:ktrdr /app/mcp /app/mcp
COPY --from=builder --chown=ktrdr:ktrdr /app/config /app/config
COPY --from=builder --chown=ktrdr:ktrdr /app/strategies /app/strategies
COPY --from=builder --chown=ktrdr:ktrdr /app/alembic /app/alembic
COPY --from=builder --chown=ktrdr:ktrdr /app/alembic.ini /app/
COPY --from=builder --chown=ktrdr:ktrdr /app/pyproject.toml /app/

# Set PATH for venv
ENV PATH="/app/.venv/bin:$PATH"

USER ktrdr

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fs http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "ktrdr.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Implementation Notes:**
- NO `--extra ml` flag — this is the key difference
- Multi-stage build to minimize image size
- Create user BEFORE copying deps (fixes layer duplication issue from INTENT.md)
- Use `--chown` on COPY commands

**Testing Requirements:**

*Smoke Test:*
```bash
# Build and verify
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:prod .
docker images ktrdr-backend:prod --format "{{.Size}}"  # Should be ~200-300MB

# Verify no torch
docker run --rm ktrdr-backend:prod python -c "import torch" 2>&1 | grep -q "No module" && echo "SUCCESS"

# Verify API starts
docker run --rm -d --name test-backend ktrdr-backend:prod
sleep 5
docker exec test-backend curl -s http://localhost:8000/api/v1/health | grep -q "healthy" && echo "SUCCESS"
docker stop test-backend
```

**Acceptance Criteria:**
- [ ] Dockerfile.backend created
- [ ] Image builds successfully
- [ ] Image size is ~200-300MB
- [ ] `import torch` fails inside container
- [ ] API health endpoint responds

---

## Task 3.2: Create Dockerfile.worker-cpu

**File(s):** `deploy/docker/Dockerfile.worker-cpu` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Create Dockerfile for CPU workers with CPU-only PyTorch.

**Target size:** ~500MB

**Key technique:** Inject CPU-only PyTorch source before `uv sync`:

```dockerfile
# Inject CPU-only PyTorch source
RUN cat >> pyproject.toml << 'EOF'

[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
EOF
```

**Template:**
```dockerfile
# =============================================================================
# KTRDR Worker - CPU (CPU-only PyTorch)
# =============================================================================
# This image runs backtest and training workers with CPU-only torch.
# ~500MB vs ~3.3GB for CUDA version.
#
# Build: docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu .
# =============================================================================

FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Inject CPU-only PyTorch source
RUN cat >> pyproject.toml << 'EOF'

[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
EOF

# Install with ML dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra ml --no-install-project

COPY ktrdr ./ktrdr
COPY config ./config
COPY strategies ./strategies

RUN uv sync --frozen --no-dev --extra ml

# =============================================================================
# Runtime Stage
# =============================================================================
FROM python:3.13-slim AS runtime

RUN groupadd -r ktrdr && \
    useradd -r -g ktrdr -d /app -s /sbin/nologin ktrdr

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder --chown=ktrdr:ktrdr /app/.venv /app/.venv
COPY --from=builder --chown=ktrdr:ktrdr /app/ktrdr /app/ktrdr
COPY --from=builder --chown=ktrdr:ktrdr /app/config /app/config
COPY --from=builder --chown=ktrdr:ktrdr /app/strategies /app/strategies
COPY --from=builder --chown=ktrdr:ktrdr /app/pyproject.toml /app/

ENV PATH="/app/.venv/bin:$PATH"

USER ktrdr

# Default: backtest worker (can be overridden)
EXPOSE 5003

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "ktrdr.backtesting.backtest_worker:app", "--host", "0.0.0.0", "--port", "5003"]
```

**Implementation Notes:**
- Uses `--extra ml` to include torch and sklearn
- Injects CPU source BEFORE uv sync
- We tested that `--frozen` works with source injection (Q1/Q2 resolution)

**Testing Requirements:**

*Smoke Test:*
```bash
# Build and verify
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
docker images ktrdr-worker-cpu:test --format "{{.Size}}"  # Should be ~500MB

# Verify torch works, CUDA is not available
docker run --rm ktrdr-worker-cpu:test python -c "import torch; print(f'cuda={torch.cuda.is_available()}')" | grep -q "cuda=False" && echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] Dockerfile.worker-cpu created
- [ ] Image builds successfully
- [ ] Image size is ~500MB
- [ ] `import torch` succeeds
- [ ] `torch.cuda.is_available()` returns False

---

## Task 3.3: Rename/Create Dockerfile.worker-gpu

**File(s):**
- Rename: `deploy/docker/Dockerfile` → `deploy/docker/Dockerfile.worker-gpu`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Rename the existing production Dockerfile to clearly indicate it's for GPU workers.

**Target size:** ~3.3GB (unchanged — CUDA is inherently large)

**Changes needed:**
1. Rename file
2. Update header comments
3. Update CMD to worker entry point
4. Add `--extra ml` if not already present

**Implementation Notes:**
- This is mostly a rename — the existing Dockerfile already builds with CUDA torch
- Verify it uses `--extra ml` after M1 changes

**Testing Requirements:**

*Smoke Test:*
```bash
# Build and verify
docker build -f deploy/docker/Dockerfile.worker-gpu -t ktrdr-worker-gpu:test .
docker images ktrdr-worker-gpu:test --format "{{.Size}}"  # Should be ~3.3GB

# Verify torch works (CUDA availability depends on host)
docker run --rm ktrdr-worker-gpu:test python -c "import torch; print('torch OK')"
```

**Acceptance Criteria:**
- [ ] Dockerfile renamed to Dockerfile.worker-gpu
- [ ] Header comments updated
- [ ] Uses `--extra ml` flag
- [ ] Image builds successfully
- [ ] Image size is ~3.3GB

---

## Task 3.4: Update Dockerfile.dev for CPU-Only Torch

**File(s):** `deploy/docker/Dockerfile.dev`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Update the dev Dockerfile to use CPU-only torch, reducing image from ~4GB to ~500MB.

**Target size:** ~500MB

**Key change:** Add the same CPU source injection as Dockerfile.worker-cpu.

**Implementation Notes:**
- Dev image should have ALL dependencies (including dev group)
- But torch should be CPU-only
- Mac dev machines have no GPU — CUDA torch is wasted space

**Template additions:**
```dockerfile
# Before uv sync, inject CPU source
RUN cat >> pyproject.toml << 'EOF'

[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
EOF

# Then install with all extras
RUN uv sync --extra ml
```

**Testing Requirements:**

*Smoke Test:*
```bash
# Build and verify
docker build -f deploy/docker/Dockerfile.dev -t ktrdr-backend:dev .
docker images ktrdr-backend:dev --format "{{.Size}}"  # Should be ~500MB, NOT ~4GB

# Verify torch works, CUDA not available
docker run --rm ktrdr-backend:dev python -c "import torch; print(f'cuda={torch.cuda.is_available()}')" | grep -q "cuda=False" && echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] Dockerfile.dev updated with CPU source injection
- [ ] Image builds successfully
- [ ] Image size is ~500MB (down from ~4GB)
- [ ] `import torch` succeeds
- [ ] `torch.cuda.is_available()` returns False

---

## Task 3.5: Update .dockerignore

**File(s):** `.dockerignore`
**Type:** CODING
**Estimated time:** 10 min

**Task Categories:** Configuration

**Description:**
Add `archive/` to .dockerignore to exclude archived frontend from builds.

**Changes:**
```
# Add to .dockerignore
archive/
```

**Implementation Notes:**
- This prevents archived code from bloating build context
- Should already exclude most unnecessary files; just add archive/

**Testing Requirements:**

*Smoke Test:*
```bash
grep "^archive" .dockerignore && echo "SUCCESS" || echo "FAIL"
```

**Acceptance Criteria:**
- [ ] `archive/` added to .dockerignore
- [ ] Build context doesn't include archive/ directory

---

## Milestone 3 Completion Checklist

- [ ] Task 3.1: Dockerfile.backend created (~200-300MB, no torch)
- [ ] Task 3.2: Dockerfile.worker-cpu created (~500MB, CPU torch)
- [ ] Task 3.3: Dockerfile.worker-gpu created (~3.3GB, CUDA torch)
- [ ] Task 3.4: Dockerfile.dev updated (~500MB, CPU torch)
- [ ] Task 3.5: .dockerignore updated
- [ ] All four images build successfully
- [ ] Image sizes match targets
- [ ] Torch availability correct per image
- [ ] All changes committed
- [ ] M1, M2 functionality still works
