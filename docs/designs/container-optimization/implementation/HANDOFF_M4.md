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

**Next Task Notes:**
Task 4.2 updates canary docker-compose to use split images:
- Backend: `ktrdr-backend:test` (from Dockerfile.backend, no torch)
- Workers: `ktrdr-worker-cpu:test` (from Dockerfile.worker-cpu, CPU torch)
