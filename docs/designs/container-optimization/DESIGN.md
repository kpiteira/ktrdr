# Container Optimization: Design

## Problem Statement

KTRDR uses a single 3.3GB monolithic container image for all components (backend, backtest workers, training workers), even though the backend only orchestrates requests and doesn't need PyTorch (~2.5GB). This causes slow deployments (~5 min for API changes), wasted storage across homelab nodes, and unnecessary build times. Additionally, dead code (visualization module, unused dependencies, archived frontend) inflates the codebase.

## Goals

What we're trying to achieve:

- **Right-sized production images**: Backend ~200-300MB, CPU workers ~500MB, GPU workers ~3.3GB
- **Lightweight dev images**: Dev/sandbox images ~500MB (CPU-only torch), down from ~4GB
- **Faster deployments**: Backend changes deploy in <1 min instead of ~5 min
- **Clean codebase**: Remove all dead code and unused dependencies
- **Modern dependency management**: Use UV dependency groups for selective installation
- **Maintain multi-arch support**: Continue supporting amd64 and arm64

## Non-Goals (Out of Scope)

What we're explicitly not doing:

- **Changing the distributed worker architecture** — The backend-orchestrates, workers-execute pattern stays
- **Optimizing GPU worker size** — 3.3GB is inherent to CUDA torch; we accept this for training
- **Model serving microservice** — Workers will continue to load models directly, not call a separate serving endpoint
- **Kubernetes migration** — Staying with Docker Compose for homelab deployment

## User Experience

How deployment workflows change:

### Scenario 1: API Endpoint Change

**Before**: Push to main → CI builds 3.3GB image (~15 min) → Homelab pulls 3.3GB (~5 min) → Restart all containers

**After**: Push to main → CI builds 200MB backend image (~5 min) → Homelab pulls 200MB (~30 sec) → Restart only backend container

### Scenario 2: Backtest Logic Change

**Before**: Same as above — full 3.3GB rebuild and pull

**After**: Push to main → CI builds 500MB worker-cpu image (~8 min) → Homelab pulls 500MB (~1 min) → Restart backtest workers only

### Scenario 3: Training Algorithm Change

**Before**: Same — no differentiation

**After (CPU training)**: Push to main → CI builds 500MB worker-cpu image (~8 min) → Homelab pulls (~1 min) → Restart CPU training workers

**After (GPU training)**: Push to main → CI builds 3.3GB worker-gpu image (~15 min) → Homelab pulls on GPU node only (~5 min) → Restart GPU training workers

### Scenario 4: Local Development

**Before**: `docker compose up` builds 4GB+ images with CUDA torch (unused on Mac)

**After**: `docker compose up` builds ~500MB images with CPU-only torch. Same functionality, 87% smaller.

## Key Decisions

### Decision 1: Three Container Images

**Choice**: Split into `ktrdr-backend`, `ktrdr-worker-cpu`, `ktrdr-worker-gpu`

**Alternatives considered**:
- Single image with runtime torch detection (current state)
- Two images: backend+cpu-worker combined, gpu-worker separate

**Rationale**: Backend truly doesn't need torch at all — it only routes to workers. CPU workers need torch for model inference but not CUDA. Clean separation matches actual runtime requirements.

**Worker image usage**:
- `ktrdr-worker-cpu`: Used for backtest workers AND CPU training workers
- `ktrdr-worker-gpu`: Used only for GPU training workers (nodes with NVIDIA GPUs)

### Decision 2: UV Dependency Groups

**Choice**: Use `[project.optional-dependencies]` groups with selective `uv sync`

**Alternatives considered**:
- Separate pyproject.toml per image (maintenance overhead)
- Build-time sed manipulation of pyproject.toml (fragile)

**Rationale**: Single source of truth, explicit dependency boundaries, UV-native approach, easier to understand and maintain.

### Decision 3: Lazy Torch Imports and Import Chain Cleanup

**Choice**:
1. Remove unused `ModelLoader` and `ModelStorage` imports from `training_service.py` (they're instantiated but never used)
2. Move `ModelStorage` import inside `list_strategies()` function in `strategies.py`
3. Move `import torch` inside functions in `model_loader.py` and `model_storage.py`

**Alternatives considered**:
- Remove torch from backend entirely (breaks if someone imports these modules)
- Keep torch but don't load it (complex conditional imports)

**Rationale**: The import chain `api/main.py → training_service.py → model_loader.py → torch` must be broken. Research revealed that `training_service.py` imports `ModelLoader` and `ModelStorage` but never uses them — they're legacy artifacts. Removing these unused imports and lazy-fying the remaining imports in `strategies.py` eliminates torch from the API startup path.

### Decision 4: Archive Frontend (Don't Delete)

**Choice**: Move `frontend/` to `archive/frontend/` rather than deleting

**Alternatives considered**:
- Delete entirely (loses history context)
- Keep in place but exclude from containers (confusing)

**Rationale**: Preserves code for reference while clearly marking it as inactive. Archive pattern is explicit.

### Decision 5: Remove Unused Dependencies

**Choice**: Remove streamlit, plotly, redis, openai from dependencies

**Alternatives considered**:
- Keep for potential future use

**Rationale**: Zero imports found for any of these. If needed later, they can be re-added. Dead dependencies add confusion and build time.

### Decision 6: Standardize on httpx

**Choice**: Remove aiohttp and requests, use httpx everywhere

**Alternatives considered**:
- Keep all three (redundant)
- Keep requests for sync code (unnecessary, httpx has sync API)

**Rationale**: httpx is modern, supports both sync and async, already the primary client in the codebase. One HTTP client simplifies testing and reduces dependencies.

### Decision 7: CPU-Only Torch for Dev/Sandbox

**Choice**: Dev image (`Dockerfile.dev`) uses CPU-only PyTorch, not CUDA

**Alternatives considered**:
- Keep CUDA torch in dev (wastes ~3GB, unused on Mac)
- Split dev images like production (unnecessary complexity)

**Rationale**: Mac dev machines and sandboxes have no GPU. CUDA torch is pure waste. GPU training uses either training-host-service (native Python on Mac) or homelab GPU workers. This saves ~3.5GB per dev environment and per sandbox.

### Decision 8: Worker Startup Validation

**Choice**: Workers validate torch availability on startup and fail immediately if missing

**Alternatives considered**:
- Add capability to health endpoint (still starts, reports capability)
- Accept late detection (error on first operation)

**Rationale**: If an operator deploys the wrong image (backend image to worker service), the container should fail fast with a clear error rather than appearing healthy and failing on the first operation. This makes misconfiguration obvious immediately.

## Open Questions

Issues to resolve during implementation:

1. **UV group installation syntax**: Need to verify exact `uv sync` flags for installing specific dependency groups. Documentation check required.

## Resolved Questions

- **ib_async dependency**: Only used by ib-host-service (runs natively on Mac, not in containers). Move to separate optional group or remove from main dependencies.

- **anthropic dependency**: Stays in backend. Agent/assessment workers currently live in backend; will be moved to separate workers later.

- **CI path filtering**: Keep it simple — always build all images on push to main. Path filtering adds complexity for marginal CI minute savings.

- **Image tagging strategy**: Keep current approach (`sha-xxxxx` + `latest`). Simple and sufficient for homelab deployment.
