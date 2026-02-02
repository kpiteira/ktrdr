# Container Optimization: Architecture

## Overview

This architecture splits the monolithic `ktrdr-backend` container into three right-sized images through dependency restructuring and lazy imports. The core mechanism is UV's optional dependency groups: ML dependencies (torch, sklearn) move to an `ml` extra, allowing the backend image to exclude them entirely. Worker images include the `ml` extra, with CPU workers using a PyTorch CPU-only source override at build time.

The codebase cleanup (removing dead code, archiving frontend) is straightforward file operations with no architectural impact.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            pyproject.toml                                    │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   [dependencies]    │  │ [optional-deps: ml] │  │ [dependency-groups] │  │
│  │   fastapi, pandas,  │  │   torch, sklearn    │  │   dev: pytest, etc  │  │
│  │   httpx, otel, ...  │  │                     │  │                     │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                │                       │                       │
    ┌───────────┴───────────┬───────────┴───────────┬───────────┴───────────┐
    ▼                       ▼                       ▼                       ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Dockerfile.dev │  │Dockerfile.back │  │Dockerfile.cpu  │  │Dockerfile.gpu  │
│                │  │                │  │                │  │                │
│ uv sync        │  │ uv sync        │  │ uv sync        │  │ uv sync        │
│ --extra ml     │  │ (no --extra)   │  │ --extra ml     │  │ --extra ml     │
│ +pytorch-cpu   │  │                │  │ +pytorch-cpu   │  │ (CUDA default) │
└────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
        │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ktrdr-backend   │  │ ktrdr-backend  │  │ktrdr-worker-cpu│  │ktrdr-worker-gpu│
│    :dev        │  │   (prod)       │  │                │  │                │
│   ~500MB       │  │  ~200-300MB    │  │   ~500MB       │  │   ~3.3GB       │
│                │  │                │  │                │  │                │
│ Local dev      │  │ Homelab API    │  │ Homelab workers│  │ Homelab GPU    │
│ Sandboxes      │  │ (no torch)     │  │ (CPU torch)    │  │ (CUDA torch)   │
└────────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
```

### Component Relationships (Structured Summary)

| Component | Type | Inputs | Outputs |
|-----------|------|--------|---------|
| pyproject.toml | Config | Dependency specs | Lock file, install groups |
| Dockerfile.dev | Build | Core + ml deps, CPU torch source | ktrdr-backend:dev (~500MB) |
| Dockerfile.backend | Build | Core deps only | ktrdr-backend (~200MB) |
| Dockerfile.worker-cpu | Build | Core + ml deps, CPU torch source | ktrdr-worker-cpu (~500MB) |
| Dockerfile.worker-gpu | Build | Core + ml deps, CUDA torch | ktrdr-worker-gpu (~3.3GB) |
| build-images.yml | CI/CD | Dockerfiles, triggers | ghcr.io images |

## Components

### 1. Dependency Configuration (pyproject.toml)

**Location**: `/pyproject.toml`
**Purpose**: Define dependency groups for selective installation

**Key changes**:
- Move `torch` and `scikit-learn` from `[project.dependencies]` to `[project.optional-dependencies] ml`
- Remove unused: `streamlit`, `plotly`, `redis`, `openai`, `aiohttp`, `requests`
- Move `ib_async` to separate optional group (only used by ib-host-service)

**Structure**:
```toml
[project]
dependencies = [
    # Core - API, config, data, observability
    "fastapi>=0.115.12",
    "uvicorn>=0.34.3",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pydantic>=2.0.0",
    "httpx>=0.28.1",
    "structlog>=23.0.0",
    "anthropic>=0.57.1",  # Stays in core for agent/assessment workers (future: separate worker)
    # ... (all non-ML deps)
]

[project.optional-dependencies]
ml = [
    "torch>=2.7.1",
    "scikit-learn>=1.6.1",
]
ib = [
    "ib_async>=2.1.0",
]
```

### 2. Backend Dockerfile

**Location**: `/deploy/docker/Dockerfile.backend` (NEW)
**Purpose**: Build lightweight backend image without ML dependencies

**Key behaviors**:
- Multi-stage build (builder → runtime)
- Installs only core dependencies: `uv sync --frozen --no-dev`
- Creates non-root user BEFORE copying deps (fixes layer duplication)
- ~200-300MB final image

**Interface** (build args):
```dockerfile
# No special build args needed - simplest case
FROM python:3.13-slim AS builder
# ...
RUN uv sync --frozen --no-dev --no-install-project
```

### 3. Worker CPU Dockerfile

**Location**: `/deploy/docker/Dockerfile.worker-cpu` (NEW)
**Purpose**: Build CPU worker image with CPU-only PyTorch

**Key behaviors**:
- Multi-stage build
- Injects PyTorch CPU source before install
- Installs ML dependencies: `uv sync --frozen --no-dev --extra ml`
- ~500MB final image

**Interface** (build-time modification):
```dockerfile
FROM python:3.13-slim AS builder
# ...
# Inject CPU-only PyTorch source
RUN cat >> pyproject.toml << 'EOF'

[tool.uv.sources]
torch = { index = "pytorch-cpu" }

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
EOF

RUN uv sync --frozen --no-dev --extra ml --no-install-project
```

### 4. Worker GPU Dockerfile

**Location**: `/deploy/docker/Dockerfile.worker-gpu` (rename of current `Dockerfile`)
**Purpose**: Build GPU worker image with CUDA PyTorch

**Key behaviors**:
- Multi-stage build
- Installs ML dependencies with default (CUDA) torch
- ~3.3GB final image (CUDA overhead is unavoidable)

**Interface**:
```dockerfile
FROM python:3.13-slim AS builder
# ...
RUN uv sync --frozen --no-dev --extra ml --no-install-project
```

### 5. CI/CD Workflow

**Location**: `/.github/workflows/build-images.yml`
**Purpose**: Build and push all three images to ghcr.io

**Key behaviors**:
- Matrix build for three images
- Multi-architecture (amd64 + arm64) for backend and worker-cpu
- amd64-only for worker-gpu (no ARM GPUs in homelab)
- BuildKit cache per image type

### 6. Lazy Import Modifications

**Locations**:
- `/ktrdr/backtesting/model_loader.py`
- `/ktrdr/training/model_storage.py`

**Purpose**: Prevent torch import at module load time

**Key behaviors**:
- Move `import torch` inside functions that use it
- Use `TYPE_CHECKING` for type hints if needed
- Backend image won't have torch, so these modules become non-importable there (correct behavior)

## Data Flow

### Build Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   GitHub    │────▶│  CI Workflow │────▶│  Dockerfiles│────▶│   ghcr.io    │
│   Push      │     │  (3 matrix)  │     │  (3 types)  │     │  (3 images)  │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

**Flow Steps**:
1. Push to main triggers `build-images.yml`
2. CI runs three parallel matrix jobs (backend, worker-cpu, worker-gpu)
3. Each job builds for its target platforms (amd64, arm64 where applicable)
4. Images pushed to ghcr.io with `sha-xxxxx` and `latest` tags
5. Manifest merge creates multi-arch manifests

### Deploy Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Homelab    │────▶│  docker pull │────▶│  Container  │
│  Compose    │     │  (3 images)  │     │  Start      │
└─────────────┘     └──────────────┘     └─────────────┘
```

**Flow Steps**:
1. docker-compose.yml references three image names
2. `docker compose pull` fetches only changed images
3. `docker compose up -d` starts/restarts affected services

## State Management

| State | Where | Lifecycle |
|-------|-------|-----------|
| Dependency lock | `uv.lock` | Updated on dep changes, committed to repo |
| Build cache | GitHub Actions cache | Per-platform, per-image, cleared on workflow changes |
| Container images | ghcr.io | Retained indefinitely, tagged by SHA and `latest` |
| Running containers | Homelab Docker | Replaced on deploy |

## Error Handling

| Situation | Error Type | Behavior |
|-----------|------------|----------|
| Backend imports torch | ImportError | Expected - torch not installed. Module unusable in backend. |
| UV sync fails | Build failure | CI job fails, no image pushed |
| Image pull fails | Deploy failure | Previous image continues running |
| Missing ML extra | Runtime error | Worker fails to load models - fix by adding `--extra ml` |
| Wrong image on worker | Startup failure | Worker validates torch on startup, fails fast with clear error |

### Worker Startup Validation

Workers must validate ML dependencies are available before accepting work:

```python
# In backtest_worker.py and training_worker.py startup
def validate_ml_dependencies():
    try:
        import torch
    except ImportError:
        raise RuntimeError(
            "Worker requires ML dependencies. "
            "Use ktrdr-worker-cpu or ktrdr-worker-gpu image."
        )
```

This fail-fast behavior ensures misconfiguration is detected immediately rather than on first operation.

## Integration Points

| Component | Current State | Change Needed |
|-----------|---------------|---------------|
| `ktrdr/api/endpoints/__init__.py` | Imports all routers at module level | No change - routers don't import torch directly |
| `ktrdr/api/services/training_service.py` | Imports ModelLoader at module level | Make import lazy or accept ImportError in backend |
| `ktrdr/backtesting/model_loader.py` | `import torch` at line 6 | Move inside functions |
| `ktrdr/training/model_storage.py` | `import torch` at line 10 | Move inside functions |

## Environment-Specific Changes

### Local Development (`deploy/environments/local/docker-compose.yml`)

**Strategy**: Single dev image with **CPU-only torch**. Mac has no GPU — CUDA is wasted space.

| Service | Current | After |
|---------|---------|-------|
| backend | `ktrdr-backend:dev` (4GB, CUDA) | `ktrdr-backend:dev` (~500MB, CPU torch) |
| backtest-worker-* | `ktrdr-backend:dev` | `ktrdr-backend:dev` (CPU torch) |
| training-worker-* | `ktrdr-backend:dev` | `ktrdr-backend:dev` (CPU torch) |
| mcp-local/preprod | `ktrdr-backend:dev` | `ktrdr-backend:dev` (CPU torch) |

**Key change**: `Dockerfile.dev` injects CPU-only PyTorch source (same technique as `Dockerfile.patch`).

**Rationale**:
- Mac dev machines have no GPU
- GPU training uses training-host-service (native Python) or homelab GPU worker
- Backtest inference is CPU-only anyway
- Saves ~3.5GB per dev environment

**Image mode change**: When testing with CI images (uncommented), use:
```yaml
# Image mode (uncomment to test with CI-built images)
# Backend
image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}
# Workers (backtest and CPU training)
image: ghcr.io/kpiteira/ktrdr-worker-cpu:${IMAGE_TAG:-latest}
```

### Sandbox (`ktrdr/cli/kinfra/templates/docker-compose.base.yml`)

**Strategy**: Add separate image variables for backend vs workers. Dev image now uses CPU-only torch.

| Service | Current | After |
|---------|---------|-------|
| backend | `${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}` (4GB) | `${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}` (~500MB) |
| backtest-worker | `${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}` | `${KTRDR_WORKER_IMAGE:-ktrdr-backend:dev}` |
| training-worker | `${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}` | `${KTRDR_WORKER_IMAGE:-ktrdr-backend:dev}` |

**Benefit**: Each sandbox saves ~3.5GB because dev image now uses CPU-only torch.

**New .env.sandbox variables**:
```bash
KTRDR_BACKEND_IMAGE=ktrdr-backend:dev  # CPU-only torch (~500MB)
KTRDR_WORKER_IMAGE=ktrdr-backend:dev   # CPU-only torch (~500MB)
# Or for production images:
# KTRDR_BACKEND_IMAGE=ghcr.io/kpiteira/ktrdr-backend:latest
# KTRDR_WORKER_IMAGE=ghcr.io/kpiteira/ktrdr-worker-cpu:latest
```

### Homelab Core (`deploy/environments/homelab/docker-compose.core.yml`)

| Service | Current | After |
|---------|---------|-------|
| backend | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` (now ~200MB!) |
| mcp | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` |

### Homelab Workers (`deploy/environments/homelab/docker-compose.workers.yml`)

| Service | Current | After |
|---------|---------|-------|
| backtest-worker-* | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` | `ghcr.io/.../ktrdr-worker-cpu:${IMAGE_TAG}` |
| training-worker-* | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` | `ghcr.io/.../ktrdr-worker-cpu:${IMAGE_TAG}` |

### Homelab GPU Worker (`deploy/environments/homelab/docker-compose.gpu-worker.yml`)

| Service | Current | After |
|---------|---------|-------|
| training-worker-gpu | `ghcr.io/.../ktrdr-backend:${IMAGE_TAG}` | `ghcr.io/.../ktrdr-worker-gpu:${IMAGE_TAG}` |

## Files to Create

| File | Location | Purpose |
|------|----------|---------|
| `Dockerfile.backend` | `/deploy/docker/` | Backend image build |
| `Dockerfile.worker-cpu` | `/deploy/docker/` | CPU worker image build |
| `Dockerfile.worker-gpu` | `/deploy/docker/` | GPU worker image build (rename from `Dockerfile`) |

## Files to Modify

| File | Location | Changes Required |
|------|----------|------------------|
| `pyproject.toml` | `/` | Move torch/sklearn to `[optional-dependencies] ml`, remove unused deps |
| `model_loader.py` | `/ktrdr/backtesting/` | Lazy torch import |
| `model_storage.py` | `/ktrdr/training/` | Lazy torch import |
| `build-images.yml` | `/.github/workflows/` | Matrix build for three images |
| `.dockerignore` | `/` | Add `archive/` exclusion |
| `Dockerfile.dev` | `/docker/backend/` | Inject CPU-only PyTorch source |
| `docker-compose.base.yml` | `/ktrdr/cli/kinfra/templates/` | Add `KTRDR_WORKER_IMAGE` variable |
| `docker-compose.yml` | `/deploy/environments/local/` | Update image mode comments for split images |
| `docker-compose.workers.yml` | `/deploy/environments/homelab/` | Use `ktrdr-worker-cpu` image |
| `docker-compose.gpu-worker.yml` | `/deploy/environments/homelab/` | Use `ktrdr-worker-gpu` image |

## Files to Delete

| File/Directory | Reason |
|----------------|--------|
| `/ktrdr/visualization/` | Dead code - 0 imports |
| `/docker/backend/Dockerfile.dev` | Duplicate of `/deploy/docker/Dockerfile.dev` |
| `/research_agents/` | Empty directory |
| `/models/` | Empty directory |
| `/output/` | Empty directory |

## Files to Archive

| Source | Destination | Reason |
|--------|-------------|--------|
| `/frontend/` | `/archive/frontend/` | Inactive, preserved for reference |

## Dependencies to Remove

| Package | Reason |
|---------|--------|
| `streamlit>=1.22.0` | 0 imports |
| `plotly>=5.13.0` | 0 imports |
| `redis>=6.2.0` | 0 imports |
| `openai>=1.93.0` | 0 imports |
| `aiohttp>=3.12.14` | Redundant - httpx preferred |
| `requests>=2.32.4` | Redundant - httpx preferred |

## Verification Approach

| Component | How to Verify |
|-----------|---------------|
| pyproject.toml changes | `uv lock` succeeds, `uv sync` succeeds |
| Lazy imports | `python -c "from ktrdr.api.main import app"` doesn't load torch |
| Dev image (CPU torch) | `docker images ktrdr-backend:dev` shows ~500MB, not ~4GB |
| Dev image torch check | `docker run ktrdr-backend:dev python -c "import torch; print(torch.cuda.is_available())"` → False |
| Backend image | Build succeeds, `docker run ... python -c "import torch"` fails (expected) |
| Worker-cpu image | Build succeeds, runs backtest, torch is CPU-only |
| Worker-gpu image | Build succeeds, runs training with CUDA |
| CI/CD | All three images build and push to ghcr.io |
| Dead code removal | `make test-unit` passes, `make quality` passes |
| Sandbox size | New sandbox uses ~500MB image instead of ~4GB |

## Migration Considerations

The migration is staged to minimize risk:

1. **Phase 1 (Safe)**: Remove dead code, archive frontend — no runtime impact
2. **Phase 2 (Safe)**: Remove unused dependencies — `uv lock` verifies no breakage
3. **Phase 3 (Low risk)**: Lazy torch imports — tests verify functionality
4. **Phase 4 (Medium risk)**: New Dockerfiles — test builds locally first
5. **Phase 5 (Medium risk)**: Canary validation — test split images in canary environment before CI/CD changes
6. **Phase 6 (Medium risk)**: CI/CD changes — keep old image building during transition
7. **Phase 7 (Final)**: Update homelab compose — one service at a time

### Canary Validation (Phase 5)

Before updating CI/CD, validate split images work in the canary environment (`deploy/environments/canary/`):

1. **Audit existing canary**: Verify canary works with current monolithic image first
2. **Update canary compose**: Use `ktrdr-backend:test` for backend, `ktrdr-worker-cpu:test` for workers
3. **Build and test**: Build split images with `:test` tag, run `make test-canary-functional`
4. **Smoke test**: Run a real backtest through canary environment

This catches integration issues before they affect CI/CD or production.

Rollback: Homelab can switch back to monolithic `ktrdr-backend:latest` at any point.

## Sources

- [UV Managing Dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)
- [UV Deep Dive Guide](https://www.saaspegasus.com/guides/uv-deep-dive/)
