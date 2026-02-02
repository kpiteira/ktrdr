---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Canary Validation

**Goal:** Validate split images work in canary environment before CI/CD changes.

**Branch:** `feature/container-optimization`

**Builds on:** M3 (split Dockerfiles exist and build locally)

---

## E2E Validation

### Success Criteria

Split images must pass all canary tests:

```bash
# Start canary with split images
cd deploy/environments/canary
docker compose up -d

# Run functional tests
make test-canary-functional

# Run a real backtest
curl -X POST http://localhost:18000/api/v1/backtest/...
```

### Why Canary First

1. Canary uses production-like configuration
2. Canary is isolated (ports 18000, 15003, 15004)
3. If canary fails, we fix before touching CI/CD
4. User explicitly requested this validation step

---

## Task 4.1: Audit Existing Canary Environment

**File(s):** `deploy/environments/canary/docker-compose.yml`
**Type:** RESEARCH
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Before changing anything, verify canary works with the current monolithic image. This establishes a baseline.

**Steps:**
1. Read canary docker-compose.yml
2. Check if required make targets exist
3. Start canary with current image
4. Run existing tests
5. Document any issues found

**Commands to run:**
```bash
# Check current canary status
cd deploy/environments/canary

# Build current monolithic image for testing
docker build -f ../../docker/Dockerfile -t ktrdr-backend:test ../../../

# Start canary
docker compose up -d

# Wait for healthy
docker compose ps

# Check health endpoints
curl -s http://localhost:18000/api/v1/health
curl -s http://localhost:15003/health
curl -s http://localhost:15004/health

# Run functional tests if they exist
make test-canary-functional 2>/dev/null || echo "No canary tests found"

# Check logs for errors
docker compose logs --tail=50 | grep -i error

# Stop canary
docker compose down
```

**Implementation Notes:**
- If canary is broken, fix it BEFORE proceeding to Task 4.2
- Document any configuration drift or issues
- Canary hasn't been used recently — expect possible issues

**Acceptance Criteria:**
- [ ] Canary docker-compose.yml reviewed
- [ ] Canary starts with current monolithic image
- [ ] All services report healthy
- [ ] Any issues documented and fixed
- [ ] Baseline established: "canary works with monolithic image"

---

## Task 4.2: Update Canary for Split Images

**File(s):** `deploy/environments/canary/docker-compose.yml`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Update canary docker-compose to use split images.

**Current (all services use same image):**
```yaml
backend:
  image: ktrdr-backend:test

backtest-worker:
  image: ktrdr-backend:test

training-worker:
  image: ktrdr-backend:test
```

**Target:**
```yaml
backend:
  image: ktrdr-backend:test  # Will be prod backend (no torch)

backtest-worker:
  image: ktrdr-worker-cpu:test  # CPU torch

training-worker:
  image: ktrdr-worker-cpu:test  # CPU torch (GPU uses different compose)
```

**Implementation Notes:**
- Backend uses `ktrdr-backend:test` (no torch)
- Workers use `ktrdr-worker-cpu:test` (CPU torch)
- No GPU worker in canary (Mac has no GPU)
- Keep all other configuration unchanged

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify image references updated
grep "image:" deploy/environments/canary/docker-compose.yml
```

**Acceptance Criteria:**
- [ ] Backend service uses `ktrdr-backend:test`
- [ ] Backtest worker uses `ktrdr-worker-cpu:test`
- [ ] Training worker uses `ktrdr-worker-cpu:test`
- [ ] All other configuration unchanged

---

## Task 4.3: Build and Start Canary with Split Images

**File(s):** None (execution task)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration, Background/Async

**Description:**
Build the split images with `:test` tag and start canary.

**Build commands:**
```bash
# From repo root
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:test .
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
```

**Start canary:**
```bash
cd deploy/environments/canary
docker compose up -d

# Wait for healthy
sleep 30
docker compose ps
```

**Verify health:**
```bash
# Backend health (should work without torch)
curl -s http://localhost:18000/api/v1/health | jq

# Worker health (should work with CPU torch)
curl -s http://localhost:15003/health | jq
curl -s http://localhost:15004/health | jq
```

**Check logs:**
```bash
# Look for any import errors or startup issues
docker compose logs backend | grep -i "error\|import\|torch"
docker compose logs backtest-worker | grep -i "error\|import"
docker compose logs training-worker | grep -i "error\|import"
```

**Implementation Notes:**
- If backend fails with torch import error, M2 lazy imports need more work
- If workers fail, check the Dockerfile.worker-cpu
- Compare logs between this run and Task 4.1 baseline

**Acceptance Criteria:**
- [ ] Both images build successfully
- [ ] Canary starts without errors
- [ ] All services report healthy
- [ ] No torch-related errors in backend logs
- [ ] Workers can import torch successfully

---

## Task 4.4: Run Canary Functional Tests

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Run functional tests against canary with split images.

**Test 1: API Health**
```bash
curl -s http://localhost:18000/api/v1/health | jq
# Expected: {"status": "healthy", ...}
```

**Test 2: Worker Registration**
```bash
curl -s http://localhost:18000/api/v1/workers | jq
# Expected: Workers listed and healthy
```

**Test 3: Run a Backtest (Critical)**
```bash
# This tests the full flow: backend dispatches to worker, worker uses torch
curl -X POST http://localhost:18000/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "test-strategy",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'

# Check operation status
curl -s http://localhost:18000/api/v1/operations/{operation_id} | jq
```

**Test 4: Check for Regressions**
```bash
# Run existing canary tests if available
make test-canary-functional

# Or run specific API tests
pytest tests/integration/api/ -v --timeout=60
```

**Implementation Notes:**
- The backtest test is most critical — it proves:
  - Backend can orchestrate without torch
  - Worker can load models with CPU torch
  - Inter-service communication works
- If any test fails, investigate before proceeding

**Acceptance Criteria:**
- [ ] API health check passes
- [ ] Workers register successfully
- [ ] Backtest completes end-to-end
- [ ] No regressions from baseline (Task 4.1)
- [ ] All functional tests pass

---

## Milestone 4 Completion Checklist

- [ ] Task 4.1: Canary audited, baseline established
- [ ] Task 4.2: Canary docker-compose updated for split images
- [ ] Task 4.3: Split images built and canary started
- [ ] Task 4.4: All functional tests pass
- [ ] Canary stopped: `docker compose down`
- [ ] All changes committed
- [ ] M1, M2, M3 functionality verified
- [ ] Ready for CI/CD changes (M5)

---

## Rollback Plan

If canary fails with split images:

1. Stop canary: `docker compose down`
2. Revert docker-compose changes: `git checkout deploy/environments/canary/docker-compose.yml`
3. Investigate which image/service failed
4. Fix the issue (likely in M2 or M3)
5. Retry from Task 4.3
