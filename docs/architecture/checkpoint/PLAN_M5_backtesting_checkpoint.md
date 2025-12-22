---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 5: Backtesting Checkpoint + Resume

**Branch:** `feature/checkpoint-m5-backtesting-checkpoint`
**Depends On:** M4 (Training Resume)
**Estimated Tasks:** 6

---

## Capability

When M5 is complete:
- Backtesting saves periodic checkpoints (every N bars)
- Backtesting saves checkpoint on cancellation
- User can resume cancelled/failed backtests
- Portfolio state (cash, positions, trades) restored
- Indicators recomputed on resume
- Final results match uninterrupted run

---

## E2E Test Scenario

```bash
#!/bin/bash
# M5 E2E Test: Backtesting Checkpoint + Resume

set -e

echo "=== M5 E2E Test: Backtesting Checkpoint + Resume ==="

# 1. Start long backtest
echo "Step 1: Start backtest..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/backtests/start \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_name": "test_strategy",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "start_date": "2020-01-01",
        "end_date": "2024-01-01",
        "checkpoint_interval": 5000
    }')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Wait for progress (5000+ bars)
echo "Step 2: Waiting for progress..."
for i in {1..60}; do
    sleep 2
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_message')
    echo "  Progress: $PROGRESS"
    BAR=$(echo $PROGRESS | grep -oP 'bar \K[0-9]+' || echo "0")
    if [ "$BAR" -gt 5000 ]; then
        break
    fi
done

# 3. Cancel backtest
echo "Step 3: Cancel backtest..."
curl -s -X DELETE http://localhost:8000/api/v1/operations/$OP_ID/cancel
sleep 3

# 4. Check checkpoint
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_BAR=$(echo $CHECKPOINT | jq -r '.data.state.bar_index')
CP_CASH=$(echo $CHECKPOINT | jq -r '.data.state.cash')
echo "Checkpoint at bar $CP_BAR, cash: $CP_CASH"

# 5. Resume backtest
echo "Step 5: Resume backtest..."
RESUME_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/operations/$OP_ID/resume)
RESUMED_BAR=$(echo $RESUME_RESPONSE | jq -r '.data.resumed_from.bar_index')
echo "Resumed from bar $RESUMED_BAR"

# 6. Wait for completion
echo "Step 6: Waiting for completion..."
for i in {1..180}; do
    sleep 2
    STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.status')
    if [ "$STATUS" == "COMPLETED" ]; then
        break
    fi
    if [ "$STATUS" == "FAILED" ]; then
        echo "FAIL: Backtest failed after resume"
        exit 1
    fi
done

# 7. Verify results
echo "Step 7: Verify results..."
RESULT=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq '.data.result')
TOTAL_TRADES=$(echo $RESULT | jq -r '.total_trades')
FINAL_EQUITY=$(echo $RESULT | jq -r '.final_equity')

echo "Total trades: $TOTAL_TRADES"
echo "Final equity: $FINAL_EQUITY"

if [ "$STATUS" == "COMPLETED" ] && [ "$TOTAL_TRADES" != "null" ]; then
    echo ""
    echo "=== M5 E2E TEST PASSED ==="
else
    echo ""
    echo "=== M5 E2E TEST FAILED ==="
    exit 1
fi
```

---

## Tasks

### Task 5.1: Define Backtesting Checkpoint State Shape

**File(s):**
- `ktrdr/checkpointing/schemas.py` (modify)
- `ktrdr/backtesting/checkpoint_builder.py` (new)

**Type:** CODING

**Description:**
Define the data structure for backtesting checkpoint state.

**State Shape:**
```python
@dataclass
class BacktestCheckpointState:
    # Resume point
    bar_index: int
    current_date: str  # ISO format

    # Portfolio state
    cash: float
    positions: list[dict]  # [{symbol, quantity, entry_price, entry_date}]

    # Trade history
    trades: list[dict]  # [{symbol, side, quantity, price, date, pnl}]

    # Performance tracking (sampled)
    equity_samples: list[dict]  # [{bar_index, equity}] every N bars

    # Original request for resume
    original_request: dict
```

**Notes:**
- No filesystem artifacts for backtesting (all state fits in DB)
- Equity curve is sampled, not full (to limit size)
- Original request needed to reload data on resume

**Acceptance Criteria:**
- [ ] State dataclass defined
- [ ] Builder can extract state from BacktestEngine
- [ ] No artifacts (artifacts=None)
- [ ] Equity sampled at reasonable intervals

---

### Task 5.2: Integrate Checkpoint Save into Backtest Worker

**File(s):**
- `ktrdr/backtesting/backtest_worker.py` (modify)
- `ktrdr/backtesting/engine.py` (modify if needed)

**Type:** CODING

**Description:**
Integrate checkpoint saving into backtest worker.

**Implementation Notes:**
- CheckpointPolicy with bar_interval (e.g., 10000 bars)
- Save checkpoint on cancellation
- No artifacts (state only)

**Integration:**
```python
class BacktestWorker(WorkerAPIBase):
    async def _run_backtest(self, operation_id: str, request: BacktestRequest):
        engine = BacktestEngine(...)
        checkpoint_policy = CheckpointPolicy(unit_interval=10000)

        for bar_index in range(total_bars):
            await engine.process_bar(bar_index)

            # Periodic checkpoint
            if checkpoint_policy.should_checkpoint(bar_index):
                state = build_backtest_checkpoint_state(engine, request)
                await self.checkpoint_service.save_checkpoint(
                    operation_id, "periodic", state.to_dict(), artifacts=None
                )
                checkpoint_policy.record_checkpoint(bar_index)

            # Check cancellation
            if self._cancellation_token.is_cancelled():
                state = build_backtest_checkpoint_state(engine, request)
                await self.checkpoint_service.save_checkpoint(
                    operation_id, "cancellation", state.to_dict(), artifacts=None
                )
                raise CancellationError("Backtest cancelled")

        # Success - delete checkpoint
        await self.checkpoint_service.delete_checkpoint(operation_id)
```

**Acceptance Criteria:**
- [ ] Periodic checkpoint every N bars
- [ ] Cancellation checkpoint saves
- [ ] No filesystem artifacts
- [ ] Portfolio state captured correctly

---

### Task 5.3: Implement Backtest Restore

**File(s):**
- `ktrdr/backtesting/backtest_worker.py` (modify)
- `ktrdr/backtesting/checkpoint_restore.py` (new)

**Type:** CODING

**Description:**
Implement restore logic for backtesting.

**Implementation Notes:**
- Load checkpoint state
- Reload data for full range (need lookback for indicators)
- Restore portfolio state
- Restore trade history
- Continue from checkpoint bar

**Code:**
```python
async def restore_backtest_from_checkpoint(self, operation_id: str) -> BacktestResumeContext:
    checkpoint = await self.checkpoint_service.load_checkpoint(operation_id)

    if checkpoint is None:
        raise ValueError(f"No checkpoint for {operation_id}")

    state = checkpoint.state
    original_request = state["original_request"]

    return BacktestResumeContext(
        start_bar=state["bar_index"],  # Resume from this bar
        cash=state["cash"],
        positions=state["positions"],
        trades=state["trades"],
        equity_samples=state["equity_samples"],
        original_request=original_request,
    )
```

**Acceptance Criteria:**
- [ ] Checkpoint loaded
- [ ] Portfolio state restored
- [ ] Trade history restored
- [ ] Original request extracted for data reload

---

### Task 5.4: Implement Indicator Recomputation on Resume

**File(s):**
- `ktrdr/backtesting/engine.py` (modify)

**Type:** CODING

**Description:**
On backtest resume, reload data and recompute indicators before continuing.

**Implementation Notes:**
- Load full data range (start_date to end_date from original request)
- Compute all indicators
- Seek to checkpoint bar
- Continue processing from there

**Code:**
```python
async def resume_from_context(self, context: BacktestResumeContext):
    """Resume backtesting from checkpoint."""
    # 1. Load data for full range
    data = await self.data_service.load_data(
        symbol=context.original_request["symbol"],
        timeframe=context.original_request["timeframe"],
        start_date=context.original_request["start_date"],
        end_date=context.original_request["end_date"],
    )

    # 2. Compute indicators for full range
    self._compute_indicators(data)

    # 3. Restore portfolio state
    self.portfolio.cash = context.cash
    self.portfolio.positions = context.positions
    self.portfolio.trades = context.trades

    # 4. Set starting bar
    self._current_bar = context.start_bar

    # Note: Bars 0 to start_bar-1 are NOT re-processed
    # Indicators are available for lookback, but no trades executed
```

**Acceptance Criteria:**
- [ ] Full data loaded on resume
- [ ] Indicators computed for full range
- [ ] Portfolio restored from checkpoint
- [ ] Processing continues from checkpoint bar
- [ ] Previous bars not re-processed

---

### Task 5.5: Add Resume Endpoint to Backtest Worker API

**File(s):**
- `ktrdr/backtesting/remote_api.py` (modify)

**Type:** CODING

**Description:**
Add endpoint for backend to dispatch backtest resume requests.

**Endpoint:**
```python
@app.post("/backtests/resume")
async def resume_backtest(request: BacktestResumeRequest):
    """Resume backtest from checkpoint."""
    operation_id = request.operation_id

    context = await worker.restore_backtest_from_checkpoint(operation_id)

    asyncio.create_task(
        worker.run_resumed_backtest(operation_id, context)
    )

    return {"success": True, "operation_id": operation_id}
```

**Acceptance Criteria:**
- [ ] Endpoint accepts operation_id
- [ ] Loads checkpoint
- [ ] Starts resumed backtest
- [ ] Returns success

---

### Task 5.6: Integration Test for Backtest Resume

**File(s):**
- `tests/integration/test_m5_backtesting_checkpoint.py` (new)

**Type:** CODING

**Description:**
Integration test for backtest checkpoint and resume.

**Test Scenarios:**
1. Start backtest, wait for periodic checkpoint
2. Cancel backtest
3. Resume backtest
4. Verify continues from correct bar
5. Verify final results are valid
6. Optional: Compare results to uninterrupted run

**Acceptance Criteria:**
- [ ] Test covers save and resume
- [ ] Test verifies correct resume bar
- [ ] Test verifies portfolio restoration
- [ ] Tests pass: `make test-integration`

---

## Milestone 5 Verification Checklist

Before marking M5 complete:

- [ ] All 6 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1-M4 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/checkpointing/schemas.py` | Modify | 5.1 |
| `ktrdr/backtesting/checkpoint_builder.py` | Create | 5.1 |
| `ktrdr/backtesting/backtest_worker.py` | Modify | 5.2, 5.3 |
| `ktrdr/backtesting/checkpoint_restore.py` | Create | 5.3 |
| `ktrdr/backtesting/engine.py` | Modify | 5.4 |
| `ktrdr/backtesting/remote_api.py` | Modify | 5.5 |
| `tests/integration/test_m5_backtesting_checkpoint.py` | Create | 5.6 |
