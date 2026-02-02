# Container Optimization - Intent Document

**Date**: 2026-02-01
**Status**: Analysis Complete, Implementation Pending

## Executive Summary

This document captures the complete analysis of KTRDR's system size, container architecture, and optimization opportunities. The goal is to reduce container sizes from ~3.3GB to right-sized images (~200MB for API, ~500MB for CPU workers, ~3.3GB only for GPU workers).

---

## 1. Current State Analysis

### 1.1 Container Sizes

**Local Docker Images:**
```
ktrdr-backend:dev                   4.03GB (801MB compressed)
ktrdr-coding-agent:latest           944MB (246MB compressed)
```

**ghcr.io Production Images:**
- Standard backend: ~3.3GB (includes CUDA/torch dependencies)
- Patch build (CPU-only): ~500MB

### 1.2 Docker Layer Analysis

Output from `docker history ktrdr-backend:dev`:

| Layer | Size | Description |
|-------|------|-------------|
| Base image (debian trixie) | 109MB | Python 3.13 slim base |
| APT packages | 279MB | curl, gcc, build tools |
| pip install uv | 49MB | UV package manager |
| **uv sync (dependencies)** | **1.38GB** | Python packages including PyTorch |
| **useradd + chown** | **1.36GB** | **DUPLICATING all files!** |

**Critical Finding**: The `useradd` + `chown -R /app` step happens AFTER installing dependencies, causing Docker to copy the entire 1.38GB of dependencies into a new layer. This is a 1.36GB waste.

### 1.3 Root Cause: PyTorch CUDA

The primary size driver is PyTorch with CUDA support:
- CUDA-enabled torch wheels: ~2.5GB
- CPU-only torch wheels: ~200MB
- Difference: ~2.3GB (85% of the bloat)

---

## 2. Codebase Analysis

### 2.1 Repository Structure

**Total Repository Size**: 1.5GB

| Directory | Size | Purpose | Status |
|-----------|------|---------|--------|
| ktrdr/ | 8.7MB | Core trading system (105,727 LOC) | ACTIVE |
| frontend/ | 1.0MB code + node_modules | React/TypeScript UI | TO BE ARCHIVED |
| orchestrator/ | 692KB | Operation orchestration (16,276 LOC) | ACTIVE |
| training-host-service/ | 6.0MB | GPU-backed training | ACTIVE |
| ib-host-service/ | 240KB | Interactive Brokers gateway | ACTIVE |
| tests/ | 21MB | Unit/integration/E2E tests (146,700 LOC) | ACTIVE |
| docs/ | 8.4MB | Architecture & guides (557 markdown files) | ACTIVE |
| mcp/ | 224KB | Claude MCP server | ACTIVE |

### 2.2 KTRDR Source Module Breakdown

Ranked by lines of code:

| Module | Lines | Files | Purpose |
|--------|-------|-------|---------|
| api/ | 22,431 | 18 | FastAPI endpoints & models |
| cli/ | 16,860 | 32 | Command-line interface |
| training/ | 13,301 | 29 | Training pipeline & workers |
| data/ | 9,158 | 14 | Data loading & IB integration |
| indicators/ | 8,795 | 38 | Technical indicators |
| agents/ | 6,319 | 16 | Research agents |
| config/ | 5,734 | 16 | Configuration management |
| backtesting/ | 4,981 | 16 | Backtesting engine |
| async_infrastructure/ | 4,171 | 11 | Service orchestration |
| **visualization/** | **2,482** | **6** | **UNUSED - TO BE DELETED** |
| fuzzy/ | 2,117 | 8 | Fuzzy logic engine |
| errors/ | 1,898 | 10 | Exception hierarchy |
| workers/ | 1,256 | 5 | Worker base classes |
| decision/ | 1,237 | 7 | Decision engine |
| logging/ | 1,132 | 9 | Observability & tracing |
| checkpoint/ | 923 | 8 | Training checkpoints |
| llm/ | 720 | 2 | LLM integration (HaikuBrain) |
| monitoring/ | 680 | 9 | Metrics & monitoring |
| neural/ | 578 | 4 | Neural network models |
| utils/ | 474 | 5 | Utilities |

### 2.3 Dead Code Identified

#### 2.3.1 Visualization Module (DELETE)

**Location**: `ktrdr/visualization/`
**Size**: 2,482 lines of code across 6 files
**Files**:
- `visualizer.py` (748 LOC)
- `template_manager.py` (718 LOC)
- `data_adapter.py` (397 LOC)
- `config_builder.py` (373 LOC)
- `renderer.py` (232 LOC)
- `__init__.py` (14 LOC)

**Evidence of non-use**:
- Zero imports found in production code (verified via grep)
- Only 1 smoke test exists (`tests/visualization/test_visualization_smoke.py`)
- Last meaningful commit was for Streamlit UI work (2024)
- Streamlit UI was already removed (commit `1186462e`)

**Verdict**: Delete this module entirely.

#### 2.3.2 Empty Directories (DELETE)

| Directory | Contents | Action |
|-----------|----------|--------|
| `research_agents/` | Empty | Delete |
| `models/` | Empty | Delete |
| `output/` | Empty | Delete |

#### 2.3.3 Frontend (ARCHIVE)

**Location**: `frontend/`
**Size**: 1.0MB of code (79 TypeScript/JavaScript files, ~14,500 LOC)
**Status**: Active React app with TradingView Lightweight Charts v5

**Decision**: Move to `archive/frontend/` for future reference. Remove from containers and dependencies.

---

## 3. Dependency Analysis

### 3.1 Production Dependencies (47 packages)

**Core Infrastructure:**
- fastapi>=0.115.12 - API framework
- uvicorn>=0.34.3 - ASGI server
- sqlalchemy[asyncio]>=2.0.0 - ORM
- alembic>=1.13.0 - Database migrations
- asyncpg>=0.30.0 - Async PostgreSQL driver
- aiosqlite>=0.21.0 - Async SQLite support

**Data & Computation:**
- pandas>=2.0.0 - Data manipulation (used in 76 files)
- numpy>=1.24.0 - Numerical computing (used in 24 files)
- torch>=2.7.1 - Neural networks (used in 32 files)
- scikit-learn>=1.6.1 - Machine learning utilities

**Observability & Monitoring:**
- opentelemetry-api>=1.21.0
- opentelemetry-sdk>=1.21.0
- opentelemetry-instrumentation-fastapi>=0.42b0
- opentelemetry-instrumentation-httpx>=0.42b0
- opentelemetry-instrumentation-logging>=0.42b0
- opentelemetry-exporter-otlp>=1.21.0
- opentelemetry-exporter-prometheus>=0.42b0
- prometheus-client>=0.19.0
- structlog>=23.0.0
- python-json-logger>=4.0.0

### 3.2 Unused Dependencies (REMOVE)

| Package | Size | Imports Found | Recommendation |
|---------|------|---------------|----------------|
| **streamlit>=1.22.0** | ~4.5MB | 0 | REMOVE |
| **plotly>=5.13.0** | ~5.5MB | 0 | REMOVE |
| **redis>=6.2.0** | ~1MB | 0 | REMOVE |
| **openai>=1.93.0** | ~1MB | 0 | REMOVE |

**Total savings from unused deps**: ~12MB + transitive dependencies

### 3.3 Redundant HTTP Clients

Currently installed:
- `httpx>=0.28.1` - Modern, async-first (PRIMARY)
- `aiohttp>=3.12.14` - Legacy async
- `requests>=2.32.4` - Sync fallback

**Decision**: Standardize on `httpx` only. The CLI was already harmonized to use httpx.

### 3.4 Dependency Size Breakdown

| Package | Estimated Size | Used? |
|---------|----------------|-------|
| torch (CUDA) | ~2.5GB | YES (32 files) |
| torch (CPU) | ~200MB | Alternative |
| pandas | ~20MB | YES (76 files) |
| scikit-learn | ~15MB | YES (core) |
| numpy | ~10MB | YES (24 files) |
| aiohttp | ~7.8MB | Redundant |
| plotly | ~5.5MB | NO |
| streamlit | ~4.5MB | NO |

---

## 4. Import Pattern Analysis

### 4.1 CLI Startup: EXCELLENT

**Pattern**: Uses `__getattr__` magic method for lazy loading
**Location**: `ktrdr/cli/__init__.py`
**Result**: `ktrdr --help` runs in <100ms

Heavy command modules deferred until first access:
- data_commands (loads pandas)
- deploy_commands (loads SSH)
- sandbox, ib_commands, checkpoints_commands

### 4.2 API Startup: PROBLEMATIC

**Current behavior**: API loads ALL endpoints at startup, which triggers torch import.

**Startup time**: 3.22 seconds
**Modules loaded**: 179 ktrdr modules
**Heavy deps loaded**: torch, pandas, numpy, sklearn, fastapi, opentelemetry

### 4.3 Torch Import Chain (THE PROBLEM)

```
api/main.py
  └─ api/endpoints/__init__.py (imports ALL routers at module level)
       ├─ endpoints/training.py (line 24)
       │    └─ imports TrainingService (line 71)
       │         └─ imports ModelLoader (module level, line 25)
       │              └─ import torch (LINE 6 of model_loader.py)
       │
       ├─ endpoints/models.py (line 21)
       │    └─ imports TrainingService (line 14)
       │
       └─ endpoints/strategies.py (line 23)
            └─ imports ModelStorage (line 60)
                 └─ import torch (LINE 10 of model_storage.py)
```

### 4.4 Files With Module-Level Torch Imports

**Must be fixed for torch-free backend:**

1. `ktrdr/backtesting/model_loader.py` - line 6: `import torch`
2. `ktrdr/training/model_storage.py` - line 10: `import torch`

**Fix**: Move `import torch` inside functions that actually need it.

### 4.5 Workers: CLEAN

**File**: `ktrdr/workers/base.py`
- Only imports core framework (fastapi, asyncio, pydantic)
- PyTorch GPU detection deferred to `_build_registration_payload()` (lines 908-920)
- No heavy dependencies at module level

---

## 5. Docker Configuration Analysis

### 5.1 Dockerfiles Inventory

| Dockerfile | Location | Purpose | Base Image | Multi-stage |
|-----------|----------|---------|------------|-------------|
| Dockerfile | /deploy/docker/ | Production backend | python:3.13-slim | YES |
| Dockerfile.dev | /deploy/docker/ | Dev backend | python:3.13-slim | NO |
| Dockerfile.patch | /deploy/docker/ | CPU-only patch | python:3.13-slim | YES |
| Dockerfile.dev | /docker/backend/ | **DUPLICATE** dev | python:3.13-slim | NO |
| Dockerfile | /frontend/ | Production frontend | node:18-alpine | YES |
| Dockerfile.dev | /frontend/ | Dev frontend | node:18-alpine | NO |
| Dockerfile | /deploy/docker/coding-agent/ | Claude Code | ubuntu:24.04 | NO |

**Issue**: Duplicate `Dockerfile.dev` in two locations. Should consolidate.

### 5.2 Production Dockerfile Analysis

**File**: `/deploy/docker/Dockerfile`

**Stage 1 - Builder:**
```dockerfile
FROM python:3.13-slim AS builder
RUN apt-get install build-essential gcc
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
```

**Stage 2 - Runtime:**
```dockerfile
FROM python:3.13-slim AS runtime
RUN useradd -r -g ktrdr ...
RUN apt-get install tini curl
COPY --from=builder /app/.venv/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app/ktrdr /app/ktrdr
COPY --from=builder /app/mcp /app/mcp
COPY --from=builder /app/config /app/config
COPY --from=builder /app/strategies /app/strategies
COPY --from=builder /app/alembic /app/alembic
```

**Good practices**:
- Multi-stage build separates build tools from runtime
- BuildKit cache mounts for UV cache
- Non-root user for security
- Only copies necessary files

### 5.3 Dev Dockerfile Issue

**File**: `/docker/backend/Dockerfile.dev`

**Problem** (lines 36-41):
```dockerfile
# Install Python dependencies with UV sync
RUN uv sync --frozen --no-install-project  # Creates 1.38GB of deps

# Create non-root user AFTER deps (BAD!)
RUN useradd -m ktrdr && \
    chown -R ktrdr:ktrdr /app  # COPIES 1.38GB into new layer!
```

**Fix**: Create user BEFORE installing dependencies, or use `COPY --chown` pattern.

### 5.4 Patch Dockerfile (CPU-Only)

**File**: `/deploy/docker/Dockerfile.patch`

**Key innovation**: Modifies pyproject.toml at build time to use CPU-only PyTorch:
```toml
[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
```

**Result**: ~500MB image vs ~3.3GB standard

### 5.5 .dockerignore Analysis

**Current exclusions** (well configured):
- Version control: .git, .gitignore, .github
- Python cache: __pycache__, .pytest_cache, .venv
- Distribution: .eggs, *.egg-info, build/, dist/
- Project files: tests/, exploration/, docs/, scripts/, *.md
- Development: .vscode, .idea, *.swp
- Temporary: *.log, *.tmp, output/, *.pkl
- Docker files: Dockerfile, docker-compose.yml

**Could add**:
- research_agents/
- memory/
- frontend/ (after archiving)

---

## 6. CI/CD Analysis

### 6.1 Build Pipeline Structure

**File**: `.github/workflows/build-images.yml`

**Architecture**: Multi-architecture, two-stage Docker build pipeline

**Stage 1 - Platform-Specific Builds**:
- Builds for `linux/amd64` and `linux/arm64` in parallel matrix
- Uses `docker/build-push-action@v5`
- Push-by-digest approach

**Stage 2 - Manifest Merge**:
- Creates unified multi-architecture manifest
- Uses `docker buildx imagetools create`

**Triggers**:
- Push to `main` branch (automatic)
- Manual `workflow_dispatch`

**Registry**: ghcr.io (GitHub Container Registry)
**Image**: `ghcr.io/kpiteira/ktrdr-backend`

### 6.2 Caching Strategy

```yaml
cache-from: type=gha,scope=${{ matrix.platform }}
cache-to: type=gha,mode=max,scope=${{ matrix.platform }}
```

Uses BuildKit cache with GitHub Actions cache backend, per-platform.

### 6.3 Current Tagging

```yaml
tags: |
  type=sha,prefix=sha-,format=short  # e.g., sha-a1b2c3d
  type=raw,value=latest
```

---

## 7. Proposed Architecture

### 7.1 Three-Container Strategy

| Container | Purpose | Torch | Target Size | Update Frequency |
|-----------|---------|-------|-------------|------------------|
| `ktrdr-backend` | Backend routing | None | ~200-300MB | Often (API changes) |
| `ktrdr-worker-cpu` | Backtest inference | CPU-only | ~500MB | Sometimes |
| `ktrdr-worker-gpu` | Training | CUDA | ~3.3GB | Rarely |

### 7.2 Why This Architecture

1. **Backend** (~200-300MB)
   - Receives API calls, routes to workers
   - Does NOT run training or backtesting itself
   - Has light agent/assessment workers
   - No ML dependencies needed after lazy import fix

2. **CPU Workers** (~500MB)
   - Backtest workers that load models and run inference
   - CPU-only torch is sufficient for inference (fast enough)
   - Includes: pandas, numpy, sklearn, torch-cpu

3. **GPU Workers** (~3.3GB)
   - Training workers that train neural networks
   - Need CUDA torch for fast training
   - Only image that needs full CUDA stack

### 7.3 Deployment Benefits

**Faster deployments**:
- Backend changes (most common): Deploy 200MB, not 3.3GB
- Backtest fixes: Deploy 500MB
- Training changes: Only then deploy 3.3GB

**Resource allocation**:
- GPU workers scheduled on GPU nodes only
- CPU workers can run anywhere
- Backend is lightweight, can scale horizontally

**Parallel pulls**:
- First deploy: ~4GB total (all 3 images)
- Subsequent: Only changed images (usually just API)

---

## 8. Implementation Plan

### Phase 1: Dead Code Removal (Low Risk)

1. Remove unused deps from `pyproject.toml`:
   - streamlit
   - plotly
   - redis
   - openai

2. Delete `ktrdr/visualization/` module

3. Delete empty directories:
   - research_agents/
   - models/
   - output/

4. Archive frontend:
   - Move `frontend/` to `archive/frontend/`
   - Update .dockerignore to exclude archive/

### Phase 2: Dependency Consolidation (Low Risk)

1. Audit aiohttp and requests usage
2. Migrate remaining code to httpx
3. Remove aiohttp and requests from dependencies

### Phase 3: Lazy Torch Imports (Medium Risk)

1. Modify `ktrdr/backtesting/model_loader.py`:
   - Move `import torch` inside functions that need it
   - Update type hints to use string annotations or TYPE_CHECKING

2. Modify `ktrdr/training/model_storage.py`:
   - Same pattern as model_loader

3. Test API startup without torch:
   ```bash
   python -c "from ktrdr.api.main import app; print('torch' in str(sys.modules))"
   ```

4. Verify all tests still pass

### Phase 4: Docker Layer Fix (Low Risk)

1. Fix `docker/backend/Dockerfile.dev`:
   - Create user BEFORE uv sync
   - Or use `COPY --chown` pattern

2. Consolidate duplicate Dockerfile.dev files

### Phase 5: Three-Image Build (Medium Risk)

1. Create new Dockerfiles:
   - `Dockerfile.backend` - No torch, minimal deps
   - `Dockerfile.worker-cpu` - CPU torch (based on patch)
   - `Dockerfile.worker-gpu` - CUDA torch (current production)

2. Update CI/CD (`build-images.yml`):
   - Build matrix for 3 images
   - Separate caching per image type
   - Push to ghcr with appropriate tags

3. Update homelab docker-compose:
   - Use `ktrdr-backend` for backend service
   - Use `ktrdr-worker-cpu` for backtest workers
   - Use `ktrdr-worker-gpu` for training workers

### Phase 6: Dependency Groups (Optional, Future)

Restructure pyproject.toml with optional dependency groups:
```toml
[project.optional-dependencies]
core = ["fastapi", "pydantic", ...]  # ~200MB
training = ["torch", "scikit-learn"]  # +2.5GB (CUDA) or +200MB (CPU)
```

---

## 9. Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Remove unused deps | Low | Run tests, verify no imports |
| Delete visualization | Low | Grep confirmed zero imports |
| Archive frontend | Low | Just moving files |
| Lazy torch imports | Medium | Extensive testing, gradual rollout |
| Docker layer fix | Low | Only affects dev builds |
| Three-image build | Medium | Test in canary first, keep old image available |

---

## 10. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| API image size | 3.3GB | 200-300MB |
| CPU worker image size | 3.3GB | 500MB |
| GPU worker image size | 3.3GB | 3.3GB (unchanged) |
| API startup time | 3.2s | <1s |
| Deploy time (API changes) | ~5min | <1min |
| Unused dependencies | 5 packages | 0 |
| Dead code | 2,482 LOC | 0 |

---

## 11. Open Questions

1. **ib_async dependency**: Listed but 0 imports found. Is IB integration planned? Keep or remove?

2. **anthropic dependency**: Used in 1 file only (assessment_parser). Should this be an optional dependency?

3. **mcp[cli] dependency**: Only used in /mcp directory. Should MCP server have its own container?

4. **Backtest workers**: Do they actually need torch for inference, or could they call a model-serving endpoint?

---

## 12. References

### Files Analyzed
- `/deploy/docker/Dockerfile` - Production build
- `/deploy/docker/Dockerfile.dev` - Development build
- `/deploy/docker/Dockerfile.patch` - CPU-only build
- `/docker/backend/Dockerfile.dev` - Duplicate dev build
- `/.dockerignore` - Build context exclusions
- `/.github/workflows/build-images.yml` - CI/CD pipeline
- `/pyproject.toml` - Dependencies
- `/ktrdr/api/endpoints/__init__.py` - Router imports
- `/ktrdr/backtesting/model_loader.py` - Torch import
- `/ktrdr/training/model_storage.py` - Torch import

### Commands Used for Analysis
```bash
# Check Docker image sizes
docker images | grep ktrdr

# Check Docker layer history
docker history ktrdr-backend:dev

# Find torch imports
grep -r "import torch\|from torch" ktrdr/ --include="*.py"

# Find unused imports
grep -r "from ktrdr.visualization" ktrdr/ --include="*.py"

# Profile API startup
python -c "import time; start=time.time(); from ktrdr.api.main import app; print(f'{time.time()-start:.2f}s')"

# Check what's loaded at startup
python -c "from ktrdr.api.main import app; import sys; print([m for m in sys.modules if 'torch' in m])"
```

---

## 13. CI/CD Detailed Analysis

### 13.1 Current Workflow Structure

**File**: `.github/workflows/build-images.yml`

```yaml
name: Build and Push Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository_owner }}/ktrdr-backend
```

**Triggers**:
- Automatic on push to `main` branch
- Manual via `workflow_dispatch`

**Current output**: Single image `ghcr.io/kpiteira/ktrdr-backend`

### 13.2 Job Structure

**Job 1: `build`** (runs in parallel matrix)
```yaml
strategy:
  fail-fast: false
  matrix:
    platform:
      - linux/amd64
      - linux/arm64
```

Steps:
1. Checkout code
2. Free disk space (removes .NET, GHC, Boost, toolsdirs)
3. Set up QEMU (for cross-platform builds)
4. Set up Docker Buildx
5. Log in to ghcr.io
6. Extract metadata (labels)
7. Build and push by digest
8. Export digest to file
9. Upload digest as artifact

**Job 2: `merge`** (runs after both platforms complete)
```yaml
needs: build
```

Steps:
1. Download digests from both platforms
2. Set up Docker Buildx
3. Log in to ghcr.io
4. Extract metadata (tags)
5. Create manifest list combining both architectures
6. Inspect final image

### 13.3 Build Configuration

**Dockerfile used**: `deploy/docker/Dockerfile`
**Platforms**: linux/amd64, linux/arm64
**Cache strategy**:
```yaml
cache-from: type=gha,scope=${{ matrix.platform }}
cache-to: type=gha,mode=max,scope=${{ matrix.platform }}
```

**Tagging**:
```yaml
tags: |
  type=sha,prefix=sha-,format=short  # e.g., sha-a1b2c3d
  type=raw,value=latest
```

### 13.4 Existing Patch Build (Manual)

**File**: `Makefile`

The project already has a manual CPU-only build process:

```makefile
PATCH_IMAGE := ghcr.io/kpiteira/ktrdr-backend:patch
PATCH_TARBALL := ktrdr-patch.tar.gz

docker-build-patch:
    docker buildx build --platform linux/amd64 \
        -f deploy/docker/Dockerfile.patch \
        -t $(PATCH_IMAGE) \
        --load .
    docker save $(PATCH_IMAGE) | gzip > $(PATCH_TARBALL)
```

**Key differences from CI build**:
- Uses `Dockerfile.patch` (CPU-only)
- Only builds amd64 (preprod is x86_64)
- Saves to tarball for manual transfer
- Not pushed to ghcr.io

### 13.5 Proposed Three-Image Workflow

**New image names**:
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_BASE: ${{ github.repository_owner }}/ktrdr
  # Results in:
  # - ghcr.io/kpiteira/ktrdr-backend
  # - ghcr.io/kpiteira/ktrdr-worker-cpu
  # - ghcr.io/kpiteira/ktrdr-worker-gpu
```

**New matrix structure**:
```yaml
strategy:
  fail-fast: false
  matrix:
    include:
      # Backend image - both platforms, no torch
      - image: backend
        dockerfile: deploy/docker/Dockerfile.backend
        platforms: linux/amd64,linux/arm64

      # CPU worker - both platforms, CPU torch
      - image: worker-cpu
        dockerfile: deploy/docker/Dockerfile.worker-cpu
        platforms: linux/amd64,linux/arm64

      # GPU worker - amd64 only (no ARM GPUs in homelab)
      - image: worker-gpu
        dockerfile: deploy/docker/Dockerfile.worker-gpu
        platforms: linux/amd64
```

### 13.6 New Dockerfiles Required

**1. `Dockerfile.backend` (NEW)**
```dockerfile
# Backend-only image - no torch dependencies
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc

# Install UV
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies WITHOUT torch
# Option A: Use uv sync with exclusions (if supported)
# Option B: Use modified pyproject.toml without torch
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim AS runtime

# Create user FIRST (before copying deps)
RUN groupadd -r ktrdr && \
    useradd -r -g ktrdr -d /app -s /sbin/nologin ktrdr

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini curl && \
    rm -rf /var/lib/apt/lists/*

# Copy with correct ownership
COPY --from=builder --chown=ktrdr:ktrdr /app/.venv /app/.venv
COPY --from=builder --chown=ktrdr:ktrdr /app/ktrdr /app/ktrdr
COPY --from=builder --chown=ktrdr:ktrdr /app/mcp /app/mcp
COPY --from=builder --chown=ktrdr:ktrdr /app/config /app/config
COPY --from=builder --chown=ktrdr:ktrdr /app/strategies /app/strategies
COPY --from=builder --chown=ktrdr:ktrdr /app/alembic /app/alembic
COPY --from=builder --chown=ktrdr:ktrdr /app/pyproject.toml /app/

USER ktrdr

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fs http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "ktrdr.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**2. `Dockerfile.worker-cpu` (Based on Dockerfile.patch)**
```dockerfile
# CPU worker image - CPU-only torch
# Same as Dockerfile.patch but with proper multi-stage
FROM python:3.13-slim AS builder

# ... (similar to patch, uses pytorch-cpu index)

# Runtime stage
FROM python:3.13-slim AS runtime

# Create user FIRST
RUN groupadd -r ktrdr && useradd -r -g ktrdr ktrdr

# ... (copy deps with --chown)

CMD ["python", "-m", "uvicorn", "ktrdr.backtesting.backtest_worker:app", "--host", "0.0.0.0", "--port", "5003"]
```

**3. `Dockerfile.worker-gpu` (Rename current `Dockerfile`)**
- Rename from `Dockerfile` to `Dockerfile.worker-gpu`
- Full CUDA torch for training workers

### 13.7 CI/CD Changes Required

> **Note:** The path-filtering approach below was considered but **superseded by DESIGN.md decision** to keep it simple — always build all images on push to main. Path filtering adds complexity for marginal CI minute savings.

**Simplified workflow structure** (builds all images on every push):

```yaml
name: Build and Push Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_BASE: ${{ github.repository_owner }}/ktrdr

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - image: backend
            dockerfile: deploy/docker/Dockerfile.backend
            platforms: linux/amd64,linux/arm64
          - image: worker-cpu
            dockerfile: deploy/docker/Dockerfile.worker-cpu
            platforms: linux/amd64,linux/arm64
          - image: worker-gpu
            dockerfile: deploy/docker/Dockerfile.worker-gpu
            platforms: linux/amd64
    # ... build and push each image
```

### 13.8 Homelab Compose Changes

**Current** (single image):
```yaml
services:
  backend:
    image: ghcr.io/kpiteira/ktrdr-backend:latest

  backtest-worker-1:
    image: ghcr.io/kpiteira/ktrdr-backend:latest
    command: ["python", "-m", "uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]

  training-worker-1:
    image: ghcr.io/kpiteira/ktrdr-backend:latest
    command: ["python", "-m", "uvicorn", "ktrdr.training.training_worker:app", ...]
```

**Proposed** (three images):
```yaml
services:
  backend:
    image: ghcr.io/kpiteira/ktrdr-backend:latest  # 200-300MB

  backtest-worker-1:
    image: ghcr.io/kpiteira/ktrdr-worker-cpu:latest  # 500MB
    command: ["python", "-m", "uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]

  backtest-worker-2:
    image: ghcr.io/kpiteira/ktrdr-worker-cpu:latest  # 500MB
    command: ["python", "-m", "uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]

  training-worker-gpu:
    image: ghcr.io/kpiteira/ktrdr-worker-gpu:latest  # 3.3GB
    command: ["python", "-m", "uvicorn", "ktrdr.training.training_worker:app", ...]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### 13.9 Build Time Estimates

| Image | Current | Proposed | Notes |
|-------|---------|----------|-------|
| Full rebuild (all) | ~15min | ~20min | 3 images instead of 1 |
| API only change | ~15min | ~5min | Only builds small API image |
| Worker change | ~15min | ~15min | Builds both worker images |
| Cache hit | ~3min | ~3min per image | Same caching benefits |

### 13.10 Migration Strategy

**Phase 1: Create new Dockerfiles** (no CI changes yet)
- Create `Dockerfile.api`
- Create `Dockerfile.worker-cpu` (adapt from patch)
- Keep existing `Dockerfile` as `Dockerfile.worker-gpu`
- Test locally with `docker build`

**Phase 2: Add new images to CI** (parallel with existing)
- Add new build jobs for api and worker-cpu
- Keep existing ktrdr-backend build
- Both old and new images published

**Phase 3: Update homelab compose**
- Switch to new images one service at a time
- Validate each service works

**Phase 4: Deprecate old image**
- Remove ktrdr-backend build from CI
- Clean up ghcr.io

### 13.11 Rollback Plan

If issues arise:
1. Homelab compose can switch back to `ktrdr-backend:latest` instantly
2. Old image continues to be built during transition
3. SHA-tagged images available for pinning specific versions
