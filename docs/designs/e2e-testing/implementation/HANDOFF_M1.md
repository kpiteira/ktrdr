# Handoff: Milestone 1 - Skill Foundation

## Critical Lesson: E2E Tests Must Actually Execute

The original M1 "E2E test scenario" was:
1. Load the skill
2. Find training/smoke in catalog
3. Navigate to test recipe
4. Confirm sections present

**This was a structural test, not a behavioral test.** It verified "do files exist and link correctly" but would never catch:

| Issue Found | Would Original E2E Have Caught It? |
|-------------|-----------------------------------|
| Wrong env var (`API_PORT` vs `KTRDR_API_PORT`) | No |
| Wrong health endpoint (`/health` vs `/api/v1/health`) | No |
| Broken docker compose json parsing | No |
| Strategy/test timeframe mismatch | No |
| Wrong field paths in sanity check command | No |

**Takeaway for future milestones:** E2E test scenarios must include at least one real execution step, not just navigation/structure checks.

---

## Gotchas

### Sandbox Environment Variables

The sandbox uses `KTRDR_API_PORT`, not `API_PORT`. All skill files must use:
```bash
source .env.sandbox 2>/dev/null
API_PORT=${KTRDR_API_PORT:-8000}
```

### Health Endpoint

The correct health endpoint is `/api/v1/health`, not `/health`.

### Docker Compose JSON Parsing

`docker compose ps --format json` output varies by version. Safer to use:
```bash
docker compose ps --format "table {{.State}}" | grep -v "STATE" | grep -v "running" | wc -l
```

### Training Metrics Field Paths

The API returns metrics at different paths than intuition suggests:
- Test accuracy: `.data.result_summary.test_metrics.test_accuracy`
- Val accuracy: `.data.result_summary.training_metrics.final_val_accuracy`
- Val loss: `.data.result_summary.training_metrics.final_val_loss`

---

## Strategy Configuration

The `test_e2e_local_pull.yaml` strategy was updated to use `timeframe: 1d` (was `5m`). This matches the smoke test parameters. If the strategy is reverted, the smoke test will fail with "No features computed".

---

## Next Task Notes

M2 will add more test recipes. When creating new tests:
1. Verify strategy timeframe matches test parameters
2. Run the actual test, don't just check file structure
3. Use the updated sanity check command format from smoke.md
