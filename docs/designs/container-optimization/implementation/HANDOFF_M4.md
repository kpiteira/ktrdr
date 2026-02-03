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

**Reminder for Task 4.3:**
The Dockerfile.backend doesn't have alembic. For canary with split images, either:
1. Run migrations using worker image: `docker run --rm ktrdr-worker-cpu:test ...`
2. Or add alembic to Dockerfile.backend (future consideration)

**Next Task Notes:**
Task 4.3 builds the split images and starts canary. Build commands:
```bash
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:test .
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
```
