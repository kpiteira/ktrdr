---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Environment Rollout

**Goal:** Update all environments to use split images.

**Branch:** `feature/container-optimization`

**Builds on:** M5 (CI now builds and pushes all three images)

---

## E2E Validation

### Success Criteria

All environments work with split images:
- Local dev: `docker compose up` works
- Sandbox: `kinfra sandbox provision` + `docker compose up` works
- Homelab: All services healthy with correct images

### Verification

```bash
# Local
cd deploy/environments/local
docker compose up -d
curl http://localhost:8000/api/v1/health

# Sandbox
kinfra sandbox provision 1
cd ~/.ktrdr/sandboxes/slot-1
docker compose up -d
curl http://localhost:8001/api/v1/health
```

---

## Task 6.1: Update Local Docker Compose

**File(s):** `deploy/environments/local/docker-compose.yml`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Update local docker-compose with comments showing how to use CI-built split images.

**Current state:**
- Uses build mode with local Dockerfile.dev
- Comments show how to switch to image mode

**Changes needed:**
1. Update image mode comments to reference split images
2. Ensure build mode uses updated Dockerfile.dev (from M3)

**Image mode comments (to add/update):**
```yaml
# =============================================================================
# Image Mode (uncomment to test with CI-built images)
# =============================================================================
# Backend (no torch):
#   image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}
#
# Workers (CPU torch):
#   image: ghcr.io/kpiteira/ktrdr-worker-cpu:${IMAGE_TAG:-latest}
#
# For GPU training (if you have a GPU):
#   image: ghcr.io/kpiteira/ktrdr-worker-gpu:${IMAGE_TAG:-latest}
# =============================================================================
```

**Implementation Notes:**
- Local dev typically uses build mode (not image mode)
- Build mode uses Dockerfile.dev which we updated in M3 for CPU-only torch
- Just update the comments for when someone wants to test CI images

**Testing Requirements:**

*Smoke Test:*
```bash
cd deploy/environments/local
docker compose up -d
curl -s http://localhost:8000/api/v1/health | grep healthy && echo "SUCCESS"
docker compose down
```

**Acceptance Criteria:**
- [ ] Image mode comments updated
- [ ] Local compose works with build mode
- [ ] All services start and are healthy

---

## Task 6.2: Update Sandbox Template

**File(s):** `ktrdr/cli/kinfra/templates/docker-compose.base.yml`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Update sandbox template for consistency. No separate worker image variable needed (per GAP-1 resolution).

**Current:**
- Uses `${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}` for everything

**After:**
- Same pattern, but dev image is now CPU-only torch (~500MB vs ~4GB)
- Add comments explaining the images

**Changes:**
```yaml
# Add header comment
# =============================================================================
# KTRDR Sandbox - Uses dev image (CPU-only torch, ~500MB)
# For CI images, override in .env.sandbox:
#   KTRDR_BACKEND_IMAGE=ghcr.io/kpiteira/ktrdr-backend:latest
#   (workers would need separate KTRDR_WORKER_IMAGE but not implemented)
# =============================================================================

services:
  backend:
    image: ${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}
    # ...

  backtest-worker:
    image: ${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}  # Same dev image, includes CPU torch
    # ...

  training-worker:
    image: ${KTRDR_BACKEND_IMAGE:-ktrdr-backend:dev}  # Same dev image, includes CPU torch
    # ...
```

**Implementation Notes:**
- Per GAP-1 resolution: sandboxes use same image for everything
- The dev image (from M3 Dockerfile.dev) now has CPU-only torch
- This is simpler and sandboxes don't need size optimization

**Testing Requirements:**

*Smoke Test:*
```bash
# Provision a test sandbox
kinfra sandbox provision 9  # Use high slot to avoid conflicts

# Check the generated compose file
cat ~/.ktrdr/sandboxes/slot-9/docker-compose.yml | head -30

# Clean up
kinfra sandbox destroy 9
```

**Acceptance Criteria:**
- [ ] Template updated with clarifying comments
- [ ] Sandboxes still work
- [ ] Dev image is CPU-only (~500MB)

---

## Task 6.3: Add Worker Startup Validation

**File(s):**
- `ktrdr/backtesting/backtest_worker.py`
- `ktrdr/training/training_worker.py`

**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Background/Async, Configuration

**Description:**
Add fail-fast validation so workers crash on startup if torch is missing.

**Per Decision 8:** Workers should fail immediately with a clear error if deployed with wrong image.

**Implementation:**

```python
# Add to both worker files, call during app startup

def validate_ml_dependencies() -> None:
    """Validate that ML dependencies are available.

    Workers require torch for model loading/inference.
    If torch is missing, the container was likely deployed
    with the wrong image (backend instead of worker).

    Raises:
        RuntimeError: If torch is not available.
    """
    try:
        import torch
    except ImportError as e:
        raise RuntimeError(
            "Worker requires ML dependencies but torch is not installed. "
            "This usually means the wrong Docker image was deployed. "
            "Workers should use 'ktrdr-worker-cpu' or 'ktrdr-worker-gpu', "
            "not 'ktrdr-backend'. "
            f"Original error: {e}"
        ) from e


# In app startup (FastAPI lifespan or startup event)
@app.on_event("startup")
async def startup_event():
    validate_ml_dependencies()
    # ... rest of startup
```

**Implementation Notes:**
- Call validation EARLY in startup (before registering with backend)
- Clear error message explaining the likely cause
- This prevents confusing errors later when loading models

**Testing Requirements:**

*Unit Tests:*
```python
# tests/unit/backtesting/test_backtest_worker.py
def test_validate_ml_dependencies_passes_with_torch():
    """Should not raise when torch is available."""
    from ktrdr.backtesting.backtest_worker import validate_ml_dependencies
    validate_ml_dependencies()  # Should not raise

def test_validate_ml_dependencies_fails_without_torch(monkeypatch):
    """Should raise RuntimeError when torch is missing."""
    import sys
    # Block torch import
    monkeypatch.setitem(sys.modules, 'torch', None)
    # ... test that RuntimeError is raised
```

*Integration Test:*
```bash
# In canary with wrong image (would fail startup)
# This is a manual test - don't actually do this in prod
```

**Acceptance Criteria:**
- [ ] `validate_ml_dependencies()` added to both worker files
- [ ] Called during app startup
- [ ] Clear error message includes image recommendation
- [ ] Unit tests pass
- [ ] Workers still start correctly with proper images

---

## Task 6.4: Update Homelab Compose Files

**File(s):**
- `deploy/environments/homelab/docker-compose.workers.yml`
- `deploy/environments/homelab/docker-compose.gpu-worker.yml`

**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Update homelab compose files to use the new split images.

**docker-compose.workers.yml changes:**
```yaml
# Before
backtest-worker-1:
  image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}

training-worker-1:
  image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}

# After
backtest-worker-1:
  image: ghcr.io/kpiteira/ktrdr-worker-cpu:${IMAGE_TAG:-latest}

training-worker-1:
  image: ghcr.io/kpiteira/ktrdr-worker-cpu:${IMAGE_TAG:-latest}
```

**docker-compose.gpu-worker.yml changes:**
```yaml
# Before
training-worker-gpu:
  image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}

# After
training-worker-gpu:
  image: ghcr.io/kpiteira/ktrdr-worker-gpu:${IMAGE_TAG:-latest}
```

**Implementation Notes:**
- Backend (docker-compose.core.yml) keeps using `ktrdr-backend` image
- CPU workers use `ktrdr-worker-cpu`
- GPU worker uses `ktrdr-worker-gpu`
- Keep IMAGE_TAG variable for version pinning

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify image references
grep "image:" deploy/environments/homelab/docker-compose.workers.yml
grep "image:" deploy/environments/homelab/docker-compose.gpu-worker.yml

# Should see worker-cpu and worker-gpu, not ktrdr-backend for workers
```

**Acceptance Criteria:**
- [ ] Workers use `ktrdr-worker-cpu` image
- [ ] GPU worker uses `ktrdr-worker-gpu` image
- [ ] Backend still uses `ktrdr-backend` image
- [ ] IMAGE_TAG variable preserved

---

## Milestone 6 Completion Checklist

- [ ] Task 6.1: Local docker-compose updated
- [ ] Task 6.2: Sandbox template updated
- [ ] Task 6.3: Worker startup validation added
- [ ] Task 6.4: Homelab compose files updated
- [ ] All unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Local environment works
- [ ] Sandbox works
- [ ] All changes committed
- [ ] PR ready for review

---

## Final Verification

Before merging:

```bash
# 1. Local test
cd deploy/environments/local
docker compose up -d
curl http://localhost:8000/api/v1/health
docker compose down

# 2. Sandbox test
kinfra sandbox provision 9
cd ~/.ktrdr/sandboxes/slot-9
docker compose up -d
curl http://localhost:8009/api/v1/health
docker compose down
kinfra sandbox destroy 9

# 3. Tests
make test-unit
make quality
```

---

## Post-Merge: Homelab Deployment

After PR is merged and CI builds complete:

```bash
# On homelab
cd /path/to/ktrdr
git pull
docker compose -f docker-compose.core.yml pull
docker compose -f docker-compose.workers.yml pull
docker compose -f docker-compose.gpu-worker.yml pull

# Rolling restart (backend first, then workers)
docker compose -f docker-compose.core.yml up -d backend
sleep 30
docker compose -f docker-compose.workers.yml up -d
docker compose -f docker-compose.gpu-worker.yml up -d

# Verify
docker compose ps
curl http://localhost:8000/api/v1/health
```

---

## Rollback Plan

If homelab deployment fails:

1. **Immediate:** Revert to old images:
   ```bash
   # Edit compose files to use ktrdr-backend:previous-sha
   docker compose pull
   docker compose up -d
   ```

2. **Investigate:** Check logs for which service failed

3. **Fix forward:** Most likely issues:
   - Import error in backend → M2 incomplete
   - Worker can't load models → Dockerfile issue
   - Wrong image deployed → Compose file typo
