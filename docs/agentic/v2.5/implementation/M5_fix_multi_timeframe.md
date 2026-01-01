---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Fix Multi-Timeframe Pipeline

**Branch:** `feature/v2.5-m5-multi-timeframe`
**Depends on:** M4 (fix multi-symbol)

**Goal:** Debug and fix the multi-timeframe training pipeline so agent can use 1h + 5m data together and get valid results.

---

## E2E Test Scenario

**Purpose:** Verify multi-timeframe research completes with valid metrics

```bash
# Prerequisites: Backend running, real workers, data available for both timeframes

# 1. Trigger multi-timeframe research
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Use both 1h and 5m timeframes for EURUSD. RSI on both timeframes.",
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

# 4. Verify experiment metrics
LATEST=$(ls -t memory/experiments/*.yaml | head -1)
cat "$LATEST" | grep -E "test_accuracy|total_trades|status"
# Expected: test_accuracy > 0, total_trades > 0, status: completed
```

**Success Criteria:**
- [ ] Multi-timeframe research completes (not FAILED)
- [ ] `test_accuracy > 0` (not silent zeros)
- [ ] `total_trades > 0` (backtest ran successfully)
- [ ] Experiment saved with `status: completed`

---

## Task 5.1: Add Debugging to Multi-Timeframe Data Loading

**File:** `ktrdr/data/multi_timeframe_coordinator.py`
**Type:** RESEARCH + CODING
**Estimated time:** 2-3 hours

**What to do:**

Add detailed logging to `MultiTimeframeCoordinator.load_multi_timeframe_data()`:

```python
def load_multi_timeframe_data(
    self,
    symbol: str,
    timeframes: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    """Load and align data for multiple timeframes."""

    logger.info(f"Loading multi-TF data: {symbol} {timeframes} from {start_date} to {end_date}")

    # Load each timeframe
    tf_data = {}
    for tf in timeframes:
        df = self._load_single_timeframe(symbol, tf, start_date, end_date)
        logger.info(f"  {tf}: {len(df)} rows, range: {df.index.min()} to {df.index.max()}")
        tf_data[tf] = df

    # Align timeframes
    aligned = self._align_timeframes(tf_data)
    for tf, df in aligned.items():
        logger.info(f"  After alignment {tf}: {len(df)} rows")

    # Check for empty result
    if any(len(df) == 0 for df in aligned.values()):
        logger.error("Alignment produced empty DataFrame!")
        return {}

    return aligned
```

Likely root causes to investigate:
- 5m bars don't align to 1h bar boundaries
- Feature name collisions between timeframes (both have "rsi"?)
- Incorrect indexing when combining
- Resampling/aggregation issues

**Tests:**

- Unit: Test alignment logic in isolation
  - [ ] 1h and 5m data align correctly
  - [ ] Features prefixed with timeframe to avoid collision
  - [ ] Edge case: 5m bars at 1h boundaries handled

**Acceptance Criteria:**

- [ ] Root cause identified and documented
- [ ] Clear error message when alignment fails
- [ ] Logging shows where data is lost

---

## Task 5.2: Fix the Multi-Timeframe Bug

**File:** `ktrdr/data/multi_timeframe_coordinator.py` (and possibly feature code)
**Type:** CODING
**Estimated time:** 2-4 hours (depends on root cause)

**What to do:**

Fix whatever Task 5.1 identifies. Common fixes:

**If alignment issue:**
```python
# Align 5m to 1h by taking the 5m bar that ends at the 1h boundary
def align_to_higher_tf(low_tf_data, high_tf_data):
    # For each 1h bar, take the last 5m bar within that hour
    aligned = low_tf_data.resample('1H', label='right', closed='right').last()
    return aligned.dropna()
```

**If feature name collision:**
```python
# Prefix features with timeframe
for tf, df in tf_data.items():
    df.columns = [f"{tf}_{col}" for col in df.columns]
```

**If indexing issue:**
```python
# Ensure all DataFrames have same index before combining
common_index = reduce(lambda a, b: a.intersection(b), [df.index for df in tf_data.values()])
aligned = {tf: df.loc[common_index] for tf, df in tf_data.items()}
```

**Tests:**

- Integration: `tests/integration/data/test_multi_timeframe_loading.py`
  - [ ] Multi-TF loading with 1h + 5m produces aligned data
  - [ ] Feature names don't collide
  - [ ] Backtest can run on multi-TF data

**Acceptance Criteria:**

- [ ] Multi-timeframe loading produces valid aligned data
- [ ] Backtest produces non-zero trades
- [ ] Clear error for invalid configs

---

## Task 5.3: E2E Test for Multi-Timeframe Research

**File:** `tests/e2e/agent/test_multi_timeframe_e2e.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Create E2E test that runs full multi-timeframe research:

```python
@pytest.mark.e2e
async def test_multi_timeframe_research_completes():
    """Multi-timeframe research produces valid metrics."""

    # Trigger with multi-TF brief
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/agent/trigger",
            json={
                "brief": "Use both 1h and 5m timeframes for EURUSD. RSI on both.",
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
    assert status == "completed", f"Expected completed, got {status}"

    # Verify metrics
    latest = max(Path("memory/experiments").glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    with open(latest) as f:
        exp = yaml.safe_load(f)

    assert exp["training_result"]["test_accuracy"] > 0
    assert exp["backtest_result"]["total_trades"] > 0
```

**Acceptance Criteria:**

- [ ] Test runs full multi-TF research cycle
- [ ] Test verifies non-zero metrics
- [ ] Test passes consistently

---

## Milestone 5 Completion Checklist

- [ ] Task 5.1: Root cause identified with logging
- [ ] Task 5.2: Bug fixed
- [ ] Task 5.3: E2E test passes
- [ ] M1-M4 E2E tests still pass
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m5-multi-timeframe`

---

## Notes

**This is a debugging milestone.** Similar approach to M4.

**Root cause from investigation doc:** Unknown. Candidates:
- 5m/1h bar alignment issues
- Feature name collisions
- Incorrect indexing

**Next:** M6 (Combined Multi) - verify both fixes work together
