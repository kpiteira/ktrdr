# Handoff: M4 - Canary Validation

## Task 4.1 Complete: Audit Existing Canary Environment

**What was done:**
- Audited canary docker-compose.yml and test script
- Established baseline: canary works with monolithic image

**Gotcha: Which image to use for baseline?**
- Dockerfile.dev: NOT suitable - uses `--no-install-project` (expects volume mounts)
- Dockerfile.worker-cpu: Lacks alembic (can't run migrations)
- Dockerfile.worker-gpu: The true "monolithic" image - includes torch, ktrdr, AND alembic

**For baseline testing, use Dockerfile.worker-gpu:**
```bash
docker build -f deploy/docker/Dockerfile.worker-gpu -t ktrdr-backend:test .
```

**Gotcha: Fresh canary needs migrations**
After starting canary with a new DB, run:
```bash
docker exec ktrdr-backend-canary python -m alembic upgrade head
```

**Test script issue:**
The `scripts/test-canary.sh` uses strategy `neuro_mean_reversion` which doesn't exist.
This causes the training test to fail. The infrastructure works - only the test data is wrong.
Valid strategies are: `v3_minimal`, `v3_single_indicator`, etc.

**Baseline Test Results:**
| Test | Result |
|------|--------|
| Backend Health | ✅ PASS |
| Workers Registered | ✅ PASS |
| Training Lifecycle | ⚠️ Test script issue |
| Backtest Lifecycle | ✅ PASS |

## Task 4.2 Complete: Update Canary for Split Images

**What was done:**
- Updated docker-compose.yml image references for split architecture
- Backend: `ktrdr-backend:test` (no torch)
- Workers: `ktrdr-worker-cpu:test` (CPU torch)

## Task 4.3 Complete: Build and Start Canary with Split Images

**What was done:**
- Built both split images successfully
- Started canary with split image configuration
- Verified all services healthy

**Correction: Dockerfile.backend DOES have alembic**
Previous handoff note was incorrect. The backend Dockerfile includes alembic at lines 36-37 and 65-66.

**Image sizes (as expected):**
| Image | Size | Torch |
|-------|------|-------|
| ktrdr-backend:test | 533MB | None |
| ktrdr-worker-cpu:test | 1.35GB | 2.8.0+cpu |

**Verification:**
- Backend: healthy, no torch (ModuleNotFoundError as expected)
- Workers: healthy, torch 2.8.0+cpu available

**Canary is running on:**
- Backend: http://localhost:18000
- Backtest Worker: http://localhost:15003
- Training Worker: http://localhost:15004

**Next Task Notes:**
Task 4.4 runs functional tests. Remember:
- Test script uses invalid strategy `neuro_mean_reversion`
- DB may need migrations if fresh: `docker exec ktrdr-backend-canary python -m alembic upgrade head`
