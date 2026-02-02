# Container Optimization: Design Validation

**Date:** 2025-02-02
**Documents Validated:**
- Design: `DESIGN.md`
- Architecture: `ARCHITECTURE.md`
- Scope: Full implementation

## Validation Summary

**Scenarios Validated:** 10/10 traced
**Critical Gaps Found:** 2 (all resolved)
**Important Gaps Found:** 3 (all resolved)

## Key Decisions Made

These decisions came from our conversation and should inform implementation:

### 1. Remove Unused Imports (GAP-2)

**Decision:** Remove `ModelLoader` and `ModelStorage` imports from `training_service.py` entirely. Lazy-fy `ModelStorage` import in `strategies.py`.

**Context:** Research revealed that `training_service.py` imports these classes but never uses them — they're legacy artifacts. The backend is pure orchestration.

**Import chain that must be broken:**
```
api/main.py → api/endpoints/training.py → api/services/training_service.py
  → backtesting/model_loader.py (import torch)
  → training/model_storage.py (import torch)
```

**Files to modify:**
| File | Current Import | Fix |
|------|----------------|-----|
| `api/services/training_service.py:25` | ModelLoader | Remove (unused) |
| `api/services/training_service.py:28` | ModelStorage | Remove (unused) |
| `api/endpoints/strategies.py:60` | ModelStorage | Lazy import inside function |

### 2. UV --frozen Works with Source Override (Q1/Q2)

**Decision:** Keep `--frozen` flag for all builds. No fallback needed.

**Context:** Tested locally — injecting `[tool.uv.sources]` for CPU torch at build time does not conflict with `--frozen`. The lock file pins versions; the source override only changes download location.

### 3. Same Image for Sandboxes (GAP-1)

**Decision:** Sandboxes use the same dev image for backend and workers. No separate `KTRDR_WORKER_IMAGE` variable needed.

**Context:** For dev/sandbox, we're not optimizing for size — just functionality. The CPU-only dev image (~500MB) works for everything. The split only matters for homelab production.

### 4. Workers Fail Fast on Startup (GAP-3)

**Decision:** Option B — Workers validate torch availability on startup and fail immediately if missing.

**Context:** If an operator deploys the wrong image (backend image to worker service), the health check currently passes. Better to fail fast with a clear error than fail on first operation.

**Implementation:** Add startup check in worker `__init__` or app startup event:
```python
def validate_ml_dependencies():
    try:
        import torch
    except ImportError:
        raise RuntimeError("Worker requires ML dependencies. Use ktrdr-worker-cpu or ktrdr-worker-gpu image.")
```

### 5. Hide Torch Types Behind Generic Interfaces (GAP-4)

**Decision:** Public interfaces in `model_loader.py` and `model_storage.py` should use generic types (paths, dicts), not torch types.

**Context:** If torch types appear in TYPE_CHECKING blocks and anything inspects annotations at runtime (Pydantic, FastAPI), it fails. Internal implementation uses torch; public API uses generic types.

### 6. Canary Validation Before Homelab (User Addition)

**Decision:** Add canary environment validation as a milestone before homelab deployment.

**Context:** User correctly identified risk of deploying directly to homelab. Canary environment exists at `deploy/environments/canary/` with separate ports (18000, 15003, 15004). Must audit canary first since it hasn't been used recently.

## Scenarios Validated

### Happy Paths
1. **API Endpoint Change Deploy** — Backend image rebuilt (~200MB), deployed in <1 min
2. **Backtest Worker Change Deploy** — Worker-cpu image rebuilt (~500MB), workers restarted
3. **Local Dev Build** — Dev image with CPU-only torch (~500MB), all services functional
4. **Sandbox Provision** — Sandbox uses CPU-only dev images

### Error Paths
5. **Backend Imports Torch Module** — Now prevented by removing unused imports
6. **Wrong Image Used** — Now caught by worker startup validation (fail-fast)
7. **UV Lock Conflict** — `--frozen` flag catches stale lock files

### Edge Cases
8. **Mixed Image Versions During Rolling Deploy** — Compatible, no API changes between images
9. **Lazy Import Breaks Type Hints** — Mitigated by hiding torch types behind generic interfaces

### Integration Boundaries
10. **Training Service in Backend** — Verified as pure orchestration, no torch needed

## Interface Contracts

### pyproject.toml Structure

```toml
[project]
dependencies = [
    # Core - no torch, no sklearn
    "fastapi>=0.115.12",
    "uvicorn>=0.34.3",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pydantic>=2.0.0",
    "httpx>=0.28.1",
    # ... all other non-ML deps
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

### Dockerfile Build Commands

| Image | Command | Size |
|-------|---------|------|
| Backend (prod) | `uv sync --frozen --no-dev` | ~200MB |
| Worker-CPU | `uv sync --frozen --no-dev --extra ml` + CPU source | ~500MB |
| Worker-GPU | `uv sync --frozen --no-dev --extra ml` | ~3.3GB |
| Dev | `uv sync --extra ml` + CPU source | ~500MB |

### Lazy Import Pattern

```python
# In model_loader.py, model_storage.py
def load_model(path: str):
    import torch  # Lazy import at runtime
    return torch.load(path)
```

### Worker Startup Validation

```python
# In backtest_worker.py, training_worker.py startup
def validate_ml_dependencies():
    try:
        import torch
    except ImportError:
        raise RuntimeError(
            "Worker requires ML dependencies. "
            "Use ktrdr-worker-cpu or ktrdr-worker-gpu image."
        )
```

## Implementation Milestones

### Milestone 1: Dead Code Removal & Dependency Cleanup

**What's E2E Testable:** `make test-unit && make quality` passes with reduced dependencies

**Scope:**
- Archive frontend to `archive/frontend/`
- Delete visualization module
- Delete empty directories (research_agents, models, output)
- Remove unused dependencies from pyproject.toml
- Run `uv lock` to update lock file

**E2E Test:**
```
Given: Current codebase
When: Remove dead code and deps, run uv lock
Then: make test-unit passes, make quality passes
```

---

### Milestone 2: Lazy Torch Imports

**What's E2E Testable:** Backend API starts without torch installed

**Scope:**
- Remove unused ModelLoader/ModelStorage imports from training_service.py
- Lazy-fy ModelStorage import in strategies.py
- Lazy imports in model_loader.py and model_storage.py
- Verify import chain is broken

**E2E Test:**
```
Given: Python environment with core deps only (no torch)
When: python -c "from ktrdr.api.main import app"
Then: No ImportError, app object created
```

---

### Milestone 3: Split Dockerfiles

**What's E2E Testable:** Four images build successfully with correct sizes

**Scope:**
- Create Dockerfile.backend (no ML)
- Create Dockerfile.worker-cpu (ML + CPU torch)
- Rename Dockerfile to Dockerfile.worker-gpu
- Update Dockerfile.dev for CPU-only torch

**E2E Test:**
```
Given: New Dockerfiles
When: Build all four images
Then:
  - backend:dev ~500MB, torch.cuda.is_available() = False
  - backend (prod) ~200MB, import torch fails
  - worker-cpu ~500MB, torch works, cuda = False
  - worker-gpu ~3.3GB, torch works, cuda = True
```

---

### Milestone 4: Canary Validation

**What's E2E Testable:** Split images pass all canary tests

**Task 4.1: Audit existing canary environment**
- Verify canary works with current monolithic image
- Run existing canary tests
- Fix any issues before proceeding

**Task 4.2: Update canary for split images**
- Update canary docker-compose for split images
- Backend uses `ktrdr-backend:test`
- Workers use `ktrdr-worker-cpu:test`

**Task 4.3: Test split images in canary**
- Build split images with `:test` tag
- Start canary, run functional tests
- Run real backtest through canary

**E2E Test:**
```
Given: Split images built with :test tag
When: Start canary, run make test-canary-functional
Then: All tests pass, backtest completes successfully
```

---

### Milestone 5: CI/CD Updates

**What's E2E Testable:** GitHub Actions builds and pushes all three images

**Scope:**
- Update build-images.yml for matrix build
- Configure BuildKit cache per image type
- Multi-arch for backend and worker-cpu (amd64 + arm64)
- amd64-only for worker-gpu

**E2E Test:**
```
Given: Push to main branch
When: CI workflow runs
Then: Three images appear in ghcr.io with correct tags
```

---

### Milestone 6: Environment Rollout

**What's E2E Testable:** All environments work with split images

**Scope:**
- Update local docker-compose.yml
- Update sandbox template (CPU-only dev image for all services)
- Update homelab compose files (split production images)
- Add worker startup validation (fail-fast if torch missing)

**E2E Test:**
```
Given: Updated compose files
When: Deploy to each environment
Then: All services start, backtest completes, training dispatches correctly
```

---

## Appendix: Files Changed Summary

### Files to Create
- `deploy/docker/Dockerfile.backend`
- `deploy/docker/Dockerfile.worker-cpu`
- `deploy/docker/Dockerfile.worker-gpu` (rename from Dockerfile)

### Files to Modify
- `pyproject.toml` — dependency restructuring
- `ktrdr/api/services/training_service.py` — remove unused imports
- `ktrdr/api/endpoints/strategies.py` — lazy import
- `ktrdr/backtesting/model_loader.py` — lazy torch import
- `ktrdr/training/model_storage.py` — lazy torch import
- `ktrdr/backtesting/backtest_worker.py` — startup validation
- `ktrdr/training/training_worker.py` — startup validation
- `deploy/docker/Dockerfile.dev` — CPU-only torch
- `deploy/environments/canary/docker-compose.yml` — split images
- `deploy/environments/local/docker-compose.yml` — comments for split images
- `deploy/environments/homelab/docker-compose.workers.yml` — worker-cpu image
- `deploy/environments/homelab/docker-compose.gpu-worker.yml` — worker-gpu image
- `.github/workflows/build-images.yml` — matrix build
- `.dockerignore` — add archive/ exclusion

### Files to Delete
- `ktrdr/visualization/` — dead code
- `docker/backend/Dockerfile.dev` — duplicate of `deploy/docker/Dockerfile.dev`
- `research_agents/` — empty directory
- `models/` — empty directory
- `output/` — empty directory

### Files to Archive
- `frontend/` → `archive/frontend/`

### Dependencies to Remove
- `streamlit>=1.22.0`
- `plotly>=5.13.0`
- `redis>=6.2.0`
- `openai>=1.93.0`
- `aiohttp>=3.12.14`
- `requests>=2.32.4`
