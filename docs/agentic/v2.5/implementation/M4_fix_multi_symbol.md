---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Fix Multi-Symbol Pipeline

**Branch:** `feature/v2.5-m4-multi-symbol`
**Depends on:** M3 (baby gates + brief)

**Goal:** Debug and fix the multi-symbol training pipeline so agent can train on EURUSD + GBPUSD + USDJPY and get valid results.

---

## E2E Test Scenario

**Purpose:** Verify multi-symbol research completes with valid metrics

```bash
# Prerequisites: Backend running, real workers, data available for all symbols

# 1. Trigger multi-symbol research
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Train on EURUSD, GBPUSD, and USDJPY together. Use RSI indicator on all symbols.",
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
- [ ] Multi-symbol research completes (not FAILED)
- [ ] `test_accuracy > 0` (not silent zeros)
- [ ] `total_trades > 0` (backtest ran successfully)
- [ ] Experiment saved with `status: completed`

---

## Task 4.1: Add Debugging to Multi-Symbol Data Combination

**File:** `ktrdr/training/training_pipeline.py`
**Type:** RESEARCH + CODING
**Estimated time:** 2-3 hours

**What to do:**

This is a debugging task. The root cause is unknown. Add detailed logging to `combine_multi_symbol_data()` to identify where data is lost.

```python
def combine_multi_symbol_data(
    symbol_data: dict[str, pd.DataFrame],
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Combine data from multiple symbols for training."""

    logger.info(f"Combining data for symbols: {list(symbol_data.keys())}")

    for symbol, df in symbol_data.items():
        logger.info(f"  {symbol}: {len(df)} rows, columns: {list(df.columns)}")
        logger.info(f"  {symbol}: date range: {df.index.min()} to {df.index.max()}")

    # Step 1: Align dates
    aligned = self._align_dates(symbol_data)
    logger.info(f"After date alignment: {len(aligned)} rows")

    if len(aligned) == 0:
        logger.error("Date alignment produced 0 rows - date ranges don't overlap!")
        # Log each symbol's date range for debugging
        return None, None

    # Step 2: Combine features
    combined = self._combine_features(aligned)
    logger.info(f"After feature combination: shape {combined.shape}")

    # Step 3: Train/test split
    X_train, X_test, y_train, y_test = self._split_data(combined)
    logger.info(f"After split: X_train={X_train.shape if X_train is not None else None}, X_test={X_test.shape if X_test is not None else None}")

    return X_test, y_test
```

Likely root causes to investigate:
- Different date ranges across symbols causing empty intersection
- Feature alignment issues when combining DataFrames
- Train/test split failing on combined data
- Index mismatch after combining

**Tests:**

- Unit: Test each step of combine_multi_symbol_data in isolation
  - [ ] Date alignment with overlapping ranges works
  - [ ] Date alignment with non-overlapping ranges returns None/raises
  - [ ] Feature combination preserves all features
  - [ ] Split works on combined data

**Acceptance Criteria:**

- [ ] Root cause identified and documented
- [ ] Clear error message when combination fails
- [ ] Logging shows where data is lost

---

## Task 4.2: Fix the Multi-Symbol Bug

**File:** `ktrdr/training/training_pipeline.py` (and possibly data loading code)
**Type:** CODING
**Estimated time:** 2-4 hours (depends on root cause)

**What to do:**

Fix whatever Task 4.1 identifies. Common fixes:

**If date alignment issue:**
```python
# Use inner join on dates, but validate result is not empty
common_dates = reduce(lambda a, b: a.intersection(b), [df.index for df in symbol_data.values()])
if len(common_dates) == 0:
    raise TrainingDataError(
        f"No overlapping dates between symbols. "
        f"Ranges: {[(s, df.index.min(), df.index.max()) for s, df in symbol_data.items()]}"
    )
```

**If feature name collision:**
```python
# Prefix features with symbol name
for symbol, df in symbol_data.items():
    df.columns = [f"{symbol}_{col}" for col in df.columns]
```

**If index mismatch:**
```python
# Reset index before combining
combined = pd.concat([df.reset_index(drop=True) for df in symbol_data.values()], axis=1)
```

**Tests:**

- Integration: `tests/integration/training/test_multi_symbol_training.py`
  - [ ] Multi-symbol training with 3 symbols produces valid X_test
  - [ ] Multi-symbol training produces accuracy > 0
  - [ ] Error case: non-overlapping dates raises TrainingDataError

**Acceptance Criteria:**

- [ ] Multi-symbol training produces valid results
- [ ] X_test is not None for valid multi-symbol configs
- [ ] Clear error for invalid configs (no overlap, etc.)

---

## Task 4.3: E2E Test for Multi-Symbol Research

**File:** `tests/e2e/agent/test_multi_symbol_e2e.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Create E2E test that runs full multi-symbol research:

```python
@pytest.mark.e2e
async def test_multi_symbol_research_completes():
    """Multi-symbol research produces valid metrics."""

    # Trigger with multi-symbol brief
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/agent/trigger",
            json={
                "brief": "Train on EURUSD, GBPUSD, USDJPY. Use RSI.",
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

- [ ] Test runs full multi-symbol research cycle
- [ ] Test verifies non-zero metrics
- [ ] Test passes consistently (not flaky)

---

## Milestone 4 Completion Checklist

- [ ] Task 4.1: Root cause identified with logging
- [ ] Task 4.2: Bug fixed
- [ ] Task 4.3: E2E test passes
- [ ] M1-M3 E2E tests still pass
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m4-multi-symbol`

---

## Notes

**This is a debugging milestone.** Task 4.1 is research. Task 4.2 depends on 4.1's findings.

**Root cause from investigation doc:** Unknown. Candidates:
- Date range intersection produces empty result
- Feature alignment issues
- Train/test split edge case

**Next:** M5 (Fix Multi-Timeframe) - similar debugging approach
