---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Combined Multi-Symbol + Multi-Timeframe

**Branch:** `feature/v2.5-m6-combined`
**Depends on:** M4 (multi-symbol) + M5 (multi-timeframe)

**Goal:** Verify that multi-symbol AND multi-timeframe work together. Catch "works separately, breaks together" issues.

---

## E2E Test Scenario

**Purpose:** Verify combined multi-symbol + multi-timeframe research completes

```bash
# Prerequisites: Backend running, real workers, data available

# 1. Trigger combined research
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Train on EURUSD and GBPUSD using both 1h and 5m timeframes. RSI on all symbol/timeframe combinations.",
    "model": "haiku"
  }'

OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.operation_id')

# 2. Poll until cycle completes
for i in {1..180}; do
  PHASE=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.phase')
  echo "Phase: $PHASE"
  if [ "$PHASE" = "idle" ]; then break; fi
  sleep 5
done

# 3. Check operation status
curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq '{status: .data.status, error: .data.error_message}'
# Expected: {"status": "completed", "error": null}

# 4. Verify experiment includes all combinations
LATEST=$(ls -t memory/experiments/*.yaml | head -1)
cat "$LATEST" | grep -E "symbols|timeframes"
# Expected: symbols: [EURUSD, GBPUSD], timeframes: [1h, 5m]

# 5. Verify valid metrics
cat "$LATEST" | grep -E "test_accuracy|total_trades|status"
# Expected: test_accuracy > 0, total_trades > 0, status: completed
```

**Success Criteria:**
- [ ] Combined research completes (not FAILED)
- [ ] Strategy uses multiple symbols AND multiple timeframes
- [ ] `test_accuracy > 0`
- [ ] `total_trades > 0`
- [ ] Experiment saved with `status: completed`

---

## Task 6.1: Integration Test for Combined Pipeline

**File:** `tests/integration/training/test_combined_multi.py`
**Type:** CODING
**Estimated time:** 2 hours

**What to do:**

Create integration test that exercises the combined pipeline:

```python
@pytest.mark.integration
def test_multi_symbol_multi_timeframe_training():
    """Training with both multi-symbol AND multi-timeframe produces valid results."""

    # Setup: 2 symbols, 2 timeframes
    config = {
        "symbols": ["EURUSD", "GBPUSD"],
        "timeframes": ["1h", "5m"],
        "indicators": [{"name": "rsi", "period": 14}],
    }

    # Load data for all combinations
    data = load_multi_symbol_multi_timeframe_data(config)

    # Verify data structure
    assert len(data) == 4  # 2 symbols * 2 timeframes
    for key, df in data.items():
        assert len(df) > 0, f"Empty data for {key}"

    # Run training pipeline
    result = training_pipeline.train(config, data)

    # Verify valid results
    assert result["test_accuracy"] > 0
    assert result["X_test"] is not None
    assert result["y_test"] is not None


@pytest.mark.integration
def test_multi_symbol_multi_timeframe_backtest():
    """Backtest with multi-symbol + multi-timeframe produces trades."""

    # Setup similar to above...

    # Run backtest
    result = backtest_runner.run(config, trained_model, data)

    # Verify valid results
    assert result["total_trades"] > 0
```

**Tests to include:**

- [ ] Data loading for all symbol/timeframe combinations
- [ ] Feature alignment across all combinations
- [ ] Training produces valid metrics
- [ ] Backtest produces trades

**Acceptance Criteria:**

- [ ] Integration test passes
- [ ] No "works separately, breaks together" issues

---

## Task 6.2: E2E Test for Combined Research

**File:** `tests/e2e/agent/test_combined_multi_e2e.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Create E2E test for full combined research cycle:

```python
@pytest.mark.e2e
async def test_combined_multi_symbol_multi_timeframe():
    """Combined multi-symbol + multi-timeframe research completes."""

    # Trigger with combined brief
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/agent/trigger",
            json={
                "brief": "Train on EURUSD and GBPUSD using 1h and 5m timeframes. RSI on all combinations.",
                "model": "haiku",
            }
        )
        assert resp.status_code == 200
        op_id = resp.json()["operation_id"]

    # Poll until complete
    for _ in range(180):
        resp = await client.get(f"{BACKEND_URL}/api/v1/operations/{op_id}")
        status = resp.json()["data"]["status"]
        if status in ("completed", "failed"):
            break
        await asyncio.sleep(5)

    # Verify success
    assert status == "completed", f"Expected completed, got {status}: {resp.json()['data'].get('error_message')}"

    # Verify metrics
    latest = max(Path("memory/experiments").glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        exp = yaml.safe_load(f)

    # Verify combined config
    strategy = exp.get("strategy_config", {})
    assert len(strategy.get("symbols", [])) >= 2, "Expected multiple symbols"
    assert len(strategy.get("timeframes", [])) >= 2, "Expected multiple timeframes"

    # Verify metrics
    assert exp["training_result"]["test_accuracy"] > 0
    assert exp["backtest_result"]["total_trades"] > 0
```

**Acceptance Criteria:**

- [ ] E2E test completes successfully
- [ ] Strategy uses both multi-symbol and multi-timeframe
- [ ] Valid metrics produced

---

## Milestone 6 Completion Checklist

- [ ] Task 6.1: Integration test passes
- [ ] Task 6.2: E2E test passes
- [ ] M1-M5 E2E tests still pass (full regression)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m6-combined`

---

## Notes

**This milestone may be trivial** if M4 and M5 fixes are properly orthogonal. But it catches edge cases where the combination creates new failure modes.

**Potential issues:**
- Feature count explosion (2 symbols * 2 timeframes * N features = 4N features)
- Memory pressure with large combined datasets
- Index alignment more complex with multiple dimensions

**If this milestone fails:**
- Debug with same approach as M4/M5 (add logging, identify where data is lost)
- May need to refactor data loading to handle combined case explicitly

---

## v2.5 Complete

When M6 passes:

- [ ] All E2E tests pass (M1-M6)
- [ ] `make test-unit` passes
- [ ] `make quality` passes
- [ ] Create PR: `feature/v2.5-agent-reliability`
- [ ] Update DESIGN.md status to "Implemented"
- [ ] Update ARCHITECTURE.md status to "Implemented"
