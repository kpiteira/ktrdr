# Implementation Plan: Backtesting Async Operations

## Document Information

**Date**: 2025-01-03 (Revised)
**Status**: READY FOR IMPLEMENTATION
**Version**: 3.0 (Pull-Based Operations - Testing-First)
**Related Documents**:
- [Design Document](./01-design-backtesting-async.md) - High-level design
- [Architecture Document](./02-architecture-backtesting-async.md) - Detailed architecture
- [Testing Guide](../../testing/TESTING_GUIDE.md) - Testing infrastructure
- [Test Scenarios](../../testing/SCENARIOS.md) - Scenario templates

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Testing-First Strategy](#2-testing-first-strategy)
3. [Phase 0: Fix Current System](#3-phase-0-fix-current-system)
4. [Phase 1: Test Suite Design](#4-phase-1-test-suite-design)
5. [Phase 2: Service and Local Mode](#5-phase-2-service-and-local-mode)
6. [Phase 3: Remote Execution](#6-phase-3-remote-execution)
7. [Phase 4: Production Readiness](#7-phase-4-production-readiness)
8. [Testing Specialist Integration](#8-testing-specialist-integration)
9. [Success Criteria](#9-success-criteria)

---

## 1. Executive Summary

### 1.1 Implementation Approach

**REVISED STRATEGY**: Fix first, test continuously, build incrementally, **follow training's pattern exactly**.

1. **Phase 0** (Critical): Fix broken backtesting + make OperationsService generic
2. **Phase 1** (Foundation): Design comprehensive test suite
3. **Phase 2** (Build): Implement async with continuous testing
4. **Phase 3** (Extend): Add remote execution with testing
5. **Phase 4** (Polish): Production readiness

### 1.2 Key Architectural Decisions

**Following Training's Pattern**:
- ✅ **Reuse OperationsService** (1 fix needed)
- ✅ **Reuse OperationServiceProxy** (no changes)
- ✅ **Use ProgressBridge** (not callbacks)
- ✅ **Client-driven pull** (NO polling)
- ✅ **ENV-based mode selection** (switch script)

### 1.3 Timeline

- **Phase 0**: 1-2 days (Fix current backtesting + make OperationsService generic)
- **Phase 1**: 2-3 days (Test suite design)
- **Phase 2**: 1-2 weeks (Service + Local Mode + Testing)
- **Phase 3**: 1-2 weeks (Remote Execution + Testing)
- **Phase 4**: 1 week (Production polish)
- **Total**: 4-5 weeks

### 1.4 Success Metrics

- ✅ **Phase 0**: Backtesting works now, OperationsService generic
- ✅ **Phase 1**: 15+ scenarios documented
- ✅ **Phase 2**: Local mode works, all tests pass
- ✅ **Phase 3**: Remote mode works, all tests pass
- ✅ **Phase 4**: Production deployment successful

### 1.5 Branch Strategy

**Branch Name**: `feature/backtesting-async-operations`

**Strategy**:

- All implementation work will be done on the `feature/backtesting-async-operations` branch
- Branch created from `main` after design/architecture documentation complete
- Commits will be organized by phase:
  - Phase 0: Fix commits (FeatureCache, OperationsService)
  - Phase 1: Test scenario documentation
  - Phase 2: Local mode implementation
  - Phase 3: Remote mode implementation
  - Phase 4: Production readiness
- Each phase gate will have a merge commit summarizing completion
- Final PR to `main` will use **merge commit** (not squash) to preserve history
- Branch will be deleted after successful merge to `main`

**Commit Discipline**:

- Keep commits focused and under 30 files
- Each commit represents one logical change
- Run `make test-unit` before committing
- Run `make quality` before committing
- Meaningful commit messages following conventional commits style

---

## 2. Testing-First Strategy

### 2.1 Testing Approach

**Principle**: Build with validation gates at each step.

```
Fix (Phase 0) → Test Design (Phase 1) → Build + Test (Phases 2-3) → Validate (Phase 4)
```

### 2.2 Testing Specialist Agent Integration

**Throughout implementation**, use the integration-test-specialist agent for:

1. **Executing baseline tests** (Phase 0)
2. **Executing incremental tests** (Phases 2-3)
3. **Executing comprehensive tests** (Phase 4)

### 2.3 Test Categories

| Category | Examples | Agent Usage |
|----------|----------|-------------|
| **Backend Isolated** | Local backtest execution | Execute after each component |
| **Integration** | Backend + OperationsService | Execute for integration points |
| **Remote** | Backend → Remote container | Execute when remote ready |
| **Error Handling** | Invalid configs, cancellation | Execute throughout |

---

## 3. Phase 0: Fix Current System

**Duration**: 1-2 days

**Goal**: Make backtesting work + make OperationsService generic.

**Outcome**: Solid foundation for async implementation.

### 3.1 Task 0.1: Fix FeatureCache Bug

**Duration**: 2-4 hours

**Description**: Fix missing `feature_id` in IndicatorConfig.

**Problem**: `FeatureCache._setup_indicator_engine()` creates IndicatorConfig without required `feature_id` field → ValidationError.

**Fix**:
```python
# ktrdr/backtesting/feature_cache.py lines 35-66
def _setup_indicator_engine(self):
    """Setup indicator engine from strategy config."""
    # Strategy config already has feature_id - just use it!
    indicator_configs = self.strategy_config["indicators"]
    self.indicator_engine = IndicatorEngine(indicators=indicator_configs)
```

**Files Changed**:
- `ktrdr/backtesting/feature_cache.py` (simplify lines 35-66)

**Acceptance Criteria**:
- ✅ FeatureCache initializes without error
- ✅ BacktestingEngine can be instantiated
- ✅ Test `test_backtesting_engine_initialization` passes

**Testing with Agent**:
```
Task: "Run backtesting initialization test and verify FeatureCache fix"
Expected: test_backtesting_engine_initialization PASSES
```

---

### 3.2 Task 0.2: Make OperationsService Generic

**Duration**: 2-4 hours

**Description**: Make `_refresh_from_bridge()` operation-type aware (not just training).

**Problem**: Lines 704-707 in `operations_service.py` only handle TRAINING type.

**Current Code**:
```python
# ❌ TRAINING-ONLY:
if operation.operation_type == OperationType.TRAINING:
    if "epochs" not in operation.metrics:
        operation.metrics["epochs"] = []
    operation.metrics["epochs"].extend(new_metrics)
```

**Fixed Code**:
```python
# ✅ GENERIC (type-aware):
if new_metrics:
    if operation.metrics is None:
        operation.metrics = {}

    if operation.operation_type == OperationType.TRAINING:
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
        operation.metrics["epochs"].extend(new_metrics)

    elif operation.operation_type == OperationType.BACKTESTING:
        if "bars" not in operation.metrics:
            operation.metrics["bars"] = []
        operation.metrics["bars"].extend(new_metrics)

    elif operation.operation_type == OperationType.DATA_LOADING:
        if "segments" not in operation.metrics:
            operation.metrics["segments"] = []
        operation.metrics["segments"].extend(new_metrics)

    else:
        # Generic fallback
        if "history" not in operation.metrics:
            operation.metrics["history"] = []
        operation.metrics["history"].extend(new_metrics)
```

**Files Changed**:
- `ktrdr/api/services/operations_service.py` (lines 704-707, expand to ~720)

**Acceptance Criteria**:
- ✅ Code updated with type-aware metrics storage
- ✅ Training tests still pass (no regression)
- ✅ Ready for backtesting metrics

**Testing with Agent**:
```
Task: "Run training tests to verify OperationsService changes didn't break anything"
Expected: All training tests PASS, no regressions
```

---

### 3.3 Task 0.3: Establish Baseline Tests

**Duration**: 2-4 hours

**Description**: Run all existing backtesting tests, establish baselines.

**Baselines to Establish**:
1. **Functionality**: All tests pass
2. **Performance**: Execution time
3. **Coverage**: Current % (aim to maintain/improve)

**Testing with Agent**:
```
Task: "Execute all backtesting tests and document baseline metrics"
Expected: 11/11 tests PASS (PositionManager 5, PerformanceTracker 4, Engine 1, Service 1)
```

**Acceptance Criteria**:
- ✅ All 11 existing tests pass
- ✅ Baselines documented (time, coverage)
- ✅ No regressions

---

### 3.4 Phase 0 Validation

**Gate Criteria**:

- ✅ FeatureCache bug fixed
- ✅ OperationsService generic (type-aware)
- ✅ All existing tests pass (11/11)
- ✅ Baselines documented
- ✅ No regressions

**Deliverables**:
- Fixed code (2 files)
- Test baseline report
- Green CI/CD

---

## 4. Phase 1: Test Suite Design

**Duration**: 2-3 days

**Goal**: Design comprehensive test scenarios following established patterns.

**Outcome**: Complete test scenario documents ready for implementation.

### 4.1 Task 1.1: Design Backend Scenarios

**Duration**: 1 day

**Description**: Design scenarios for local backtesting (following SCENARIOS.md pattern).

**Scenarios to Design**:

```markdown
## B1.1: Local Backtest - Smoke Test

**Category**: Backend Isolated
**Duration**: ~5 seconds

### Test Data
- Symbol: AAPL
- Timeframe: 1d
- Date Range: 2024-01-01 to 2024-01-31 (20 bars)
- Strategy: strategies/rsi_mean_reversion.yaml
- Model: models/rsi_mlp_v1.0.0.pt

### Commands
python
# Create BacktestingService
service = BacktestingService(operations_service)

# Run backtest (local mode)
operation_id = await service.run_backtest(
    symbol="AAPL",
    timeframe="1d",
    strategy_config_path="strategies/rsi_mean_reversion.yaml",
    model_path="models/rsi_mlp_v1.0.0.pt",
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)

# Wait for completion
while True:
    op = await operations_service.get_operation(operation_id)
    if op.status in ("COMPLETED", "FAILED"):
        break
    await asyncio.sleep(1)


### Expected Results
- Operation created successfully
- Bridge registered with OperationsService
- Engine runs in thread
- Progress updates via bridge
- Results returned
- Duration: <5 seconds
```

**Additional Scenarios**:
- B1.2: Progress Tracking (verify ProgressBridge updates)
- B1.3: Cancellation (verify token works)
- B1.4: Error Handling (invalid config)

**Files to Create**:
- `docs/testing/scenarios/backtesting/BACKEND_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ backend scenarios documented
- ✅ Following SCENARIOS.md pattern
- ✅ Test data specified
- ✅ Commands detailed

---

### 4.2 Task 1.2: Design Integration Scenarios

**Duration**: 1 day

**Description**: Design scenarios for API integration.

**Scenarios to Design**:

```markdown
## B2.1: Backtest via API - Local Mode

**Category**: Integration (Backend)
**Duration**: ~10 seconds

### Prerequisites
- Backend running (port 8000)
- USE_REMOTE_BACKTEST_SERVICE=false
- AAPL 1d data available

### Commands
bash
# Start backtest
curl -X POST http://localhost:8000/api/v1/backtests/start \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol": "AAPL",
    "timeframe": "1d",
    "strategy_config_path": "strategies/rsi_mean_reversion.yaml",
    "model_path": "models/rsi_mlp_v1.0.0.pt",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "initial_capital": 100000.0
  }'

# Extract operation_id
OP_ID=$(... | jq -r '.operation_id')

# Poll progress
for i in {1..10}; do
  sleep 2
  curl "http://localhost:8000/api/v1/operations/$OP_ID" | \
    jq '{status, progress}'
done


### Expected Results
- Operation created
- Status: RUNNING → COMPLETED
- Progress: 0% → 100%
- Results include: total_return, sharpe_ratio, max_drawdown
- Duration: ~10 seconds
```

**Additional Scenarios**:
- B2.2: Cancellation via API
- B2.3: Multiple Concurrent Backtests
- B2.4: Error Handling (missing data)

**Files to Create**:
- `docs/testing/scenarios/backtesting/INTEGRATION_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ integration scenarios documented
- ✅ API contracts specified
- ✅ Progress polling detailed

---

### 4.3 Task 1.3: Design Remote Scenarios

**Duration**: 1 day

**Description**: Design scenarios for remote container execution.

**Scenarios to Design**:

```markdown
## B3.1: Remote Backtest - Direct Start

**Category**: Remote Service Isolated
**Duration**: ~10 seconds

### Prerequisites
- Remote container running (port 5003)
- Data/models accessible in remote

### Commands
bash
# Direct to remote container
curl -X POST http://localhost:5003/backtests/start \
  -H 'Content-Type: application/json' \
  -d '{...}'

# Get remote operation_id
REMOTE_OP_ID=$(... | jq -r '.operation_id')

# Poll remote directly
curl "http://localhost:5003/api/v1/operations/$REMOTE_OP_ID"


### Expected Results
- Remote OperationsService creates operation
- Bridge registered in remote
- Engine runs in remote container
- Results retrievable
```

**Additional Scenarios**:
- B3.2: Backend → Remote Proxy (full flow)
- B3.3: Remote Progress Updates (polling)
- B3.4: Remote Cancellation

**Files to Create**:
- `docs/testing/scenarios/backtesting/REMOTE_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ remote scenarios documented
- ✅ Remote container patterns specified

---

### 4.4 Task 1.4: Design Error Handling Scenarios

**Duration**: 4 hours

**Description**: Design scenarios for error conditions and edge cases.

**Scenarios to Design**:

```markdown
## B4.1: Invalid Strategy Configuration

**Category**: Error Handling
**Duration**: ~2 seconds

### Test Data
- Invalid strategy: strategies/invalid_missing_required.yaml (missing 'indicators' field)

### Commands

```python
# Attempt backtest with invalid config
operation_id = await service.run_backtest(
    symbol="AAPL",
    timeframe="1d",
    strategy_config_path="strategies/invalid_missing_required.yaml",
    model_path="models/rsi_mlp_v1.0.0.pt",
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
)

# Check operation status
op = await operations_service.get_operation(operation_id)
```

### Expected Results

- Operation created but fails immediately
- Status: FAILED
- Error message: "ValidationError: Strategy config missing required field 'indicators'"
- No bridge writes (fails before engine starts)
```

**Additional Scenarios**:
- B4.2: Missing Historical Data (data not available for symbol/timeframe/range)
- B4.3: Cancellation During Execution (cancel while running, verify clean shutdown)
- B4.4: Model File Not Found (invalid model path)
- B4.5: Insufficient Data (less than minimum bars required)

**Files to Create**:
- `docs/testing/scenarios/backtesting/ERROR_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 5+ error scenarios documented
- ✅ Cover config, data, cancellation, and file errors
- ✅ Expected error messages specified

---

### 4.5 Phase 1 Validation

**Gate Criteria**:

- ✅ All scenario categories documented:
  - Backend Isolated (4+)
  - Integration (4+)
  - Remote (4+)
  - Error Handling (5+)
- ✅ **Total: 17+ test scenarios**
- ✅ Following SCENARIOS.md pattern
- ✅ Commands and expected results clear

**Deliverables**:
- 4 scenario documents
- Test data specifications
- Expected results documented

---

## 5. Phase 2: Service and Local Mode

**Duration**: 1-2 weeks

**Goal**: Implement BacktestingService with local execution (following training's pattern).

**Outcome**: Local backtesting works with progress tracking and cancellation.

### 5.1 Task 2.1: Add ProgressBridge Hooks to Engine

**Duration**: 2-3 days

**Description**: Add ProgressBridge parameter and writes to BacktestingEngine.

**Changes**:
```python
# ktrdr/backtesting/engine.py

class BacktestingEngine:
    def run(
        self,
        bridge: Optional[ProgressBridge] = None,  # NEW
        cancellation_token: Optional[CancellationToken] = None,  # NEW
    ) -> BacktestResults:
        data = self._load_historical_data()
        total_bars = len(data)

        for bar_idx, (timestamp, bar) in enumerate(data.iterrows()):
            # Existing logic
            decision = self.orchestrator.get_decision(bar, timestamp)
            self.position_manager.process_decision(decision, bar, timestamp)

            # NEW: Report progress (every 50 bars)
            if bridge and bar_idx % 50 == 0:
                bridge.update_progress(
                    current_bar=bar_idx,
                    total_bars=total_bars,
                    current_date=str(timestamp),
                    current_pnl=self.position_manager.unrealized_pnl,
                    total_trades=len(self.position_manager.closed_positions),
                    win_rate=self.performance_tracker.win_rate,
                )

            # NEW: Check cancellation (every 100 bars)
            if cancellation_token and bar_idx % 100 == 0:
                if cancellation_token.is_cancelled_requested:
                    raise asyncio.CancelledError("Backtest cancelled")

        return self._generate_results()
```

**Files Changed**:
- `ktrdr/backtesting/engine.py` (+50 lines)

**Acceptance Criteria**:
- ✅ Engine accepts bridge parameter
- ✅ Progress updates every 50 bars
- ✅ Cancellation checked every 100 bars
- ✅ **Scenario B1.2 PASSES** (with agent)
- ✅ **Scenario B1.3 PASSES** (with agent)

**Testing with Agent**:
```
Task: "Execute scenario B1.2 (Progress Tracking) and B1.3 (Cancellation)"
Expected: Both scenarios PASS
```

---

### 5.2 Task 2.2: Create BacktestProgressBridge

**Duration**: 1 day

**Description**: Create ProgressBridge subclass for backtesting.

**Implementation**:
```python
# ktrdr/backtesting/progress_bridge.py

from ktrdr.api.services.training.progress_bridge import ProgressBridge

class BacktestProgressBridge(ProgressBridge):
    """Backtesting-specific progress bridge (follows training pattern)."""

    def __init__(self, operation_id: str, symbol: str, timeframe: str, total_bars: int):
        super().__init__()
        self.operation_id = operation_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.total_bars = total_bars

    def update_progress(
        self,
        current_bar: int,
        total_bars: int,
        current_date: str,
        current_pnl: float,
        total_trades: int,
        win_rate: float,
    ) -> None:
        """Update backtest progress (called by engine)."""
        percentage = (current_bar / max(1, total_bars)) * 100.0
        message = f"Backtesting {self.symbol} {self.timeframe} [{current_date}]"

        self._update_state(
            percentage=percentage,
            message=message,
            current_bar=current_bar,
            total_bars=total_bars,
            current_date=current_date,
            current_pnl=current_pnl,
            total_trades=total_trades,
            win_rate=win_rate,
        )
```

**Files Created**:
- `ktrdr/backtesting/progress_bridge.py` (~100 lines)

**Acceptance Criteria**:
- ✅ Inherits from ProgressBridge
- ✅ Implements update_progress()
- ✅ Thread-safe (via base class)
- ✅ Unit tests pass

**Testing with Agent**:
```
Task: "Execute unit tests for BacktestProgressBridge"
Expected: All unit tests PASS
```

---

### 5.3 Task 2.3: Create BacktestingService (Local Mode)

**Duration**: 3-4 days

**Description**: Create BacktestingService following training's pattern exactly.

**Implementation**:
```python
# ktrdr/backtesting/backtesting_service.py

from ktrdr.async_infrastructure import ServiceOrchestrator

class BacktestingService(ServiceOrchestrator):
    """Backtesting service (follows TrainingService pattern)."""

    def __init__(self, operations_service: OperationsService):
        super().__init__()
        self.operations_service = operations_service
        self._use_remote = self._should_use_remote_service()

    async def run_backtest(self, ...) -> str:
        # Create operation
        operation_id = await self.operations_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            ...
        )

        # Route: local or remote
        if self._use_remote:
            await self._run_remote_backtest(operation_id, ...)
        else:
            await self._run_local_backtest(operation_id, ...)

        return operation_id

    async def _run_local_backtest(self, operation_id, ...) -> None:
        # Create bridge
        bridge = BacktestProgressBridge(...)

        # Register with OperationsService
        self.operations_service.register_local_bridge(operation_id, bridge)

        # Build engine
        engine = BacktestingEngine(config)

        # Run in thread
        async def run_in_thread():
            try:
                results = await asyncio.to_thread(
                    engine.run,
                    bridge=bridge,
                    cancellation_token=self.operations_service.get_cancellation_token(operation_id)
                )
                await self.operations_service.complete_operation(operation_id, results=results.to_dict())
            except Exception as e:
                await self.operations_service.fail_operation(operation_id, error=str(e))

        asyncio.create_task(run_in_thread())
```

**Files Created**:
- `ktrdr/backtesting/backtesting_service.py` (~300 lines, local mode only in Phase 2)

**Acceptance Criteria**:
- ✅ Inherits from ServiceOrchestrator
- ✅ Creates operations correctly
- ✅ Registers bridge with OperationsService
- ✅ Runs engine in thread
- ✅ **Scenario B2.1 PASSES** (with agent)
- ✅ **Scenario B2.2 PASSES** (with agent)

**Testing with Agent**:
```
Task: "Execute scenarios B2.1 and B2.2 (API integration)"
Expected: Both scenarios PASS
```

---

### 5.4 Task 2.4: Add API Endpoints

**Duration**: 2 days

**Description**: Add FastAPI endpoints for backtesting.

**Files Created**:
- `ktrdr/api/endpoints/backtesting.py` (~150 lines)
- `ktrdr/api/models/backtesting.py` (~100 lines)

**Endpoints**:
```python
@router.post("/api/v1/backtests/start")
async def start_backtest(request: BacktestStartRequest):
    service = BacktestingService(operations_service)
    operation_id = await service.run_backtest(...)
    return {"operation_id": operation_id, "status": "started"}

# Progress/cancellation via existing /operations/* endpoints
```

**Acceptance Criteria**:
- ✅ POST /backtests/start works
- ✅ Returns operation_id
- ✅ **All Integration scenarios PASS** (B2.1-B2.4, with agent)

**Testing with Agent**:
```
Task: "Execute all Integration scenarios (B2.1-B2.4)"
Expected: All 4 scenarios PASS
```

---

### 5.5 Task 2.5: Add CLI Commands

**Duration**: 2 days

**Description**: Add async CLI commands for backtesting.

**Files Modified**:
- `ktrdr/cli/backtest_commands.py` (+200 lines)

**Commands**:
```python
@backtest.command("run")
async def run_backtest(...):
    async with AsyncCLIClient() as client:
        response = await client.post("/backtests/start", json={...})
        operation_id = response.json()["operation_id"]
        await poll_operation_progress(client, operation_id)
```

**Acceptance Criteria**:
- ✅ `ktrdr backtest run` works
- ✅ Shows real-time progress
- ✅ `ktrdr backtest cancel` works
- ✅ CLI tests pass

**Testing with Agent**:
```
Task: "Execute CLI scenarios"
Expected: CLI tests PASS
```

---

### 5.6 Phase 2 Validation

**Gate Criteria**:

- ✅ All unit tests pass (90%+ coverage)
- ✅ All integration tests pass
- ✅ **All Backend scenarios PASS** (B1.1-B1.4, with agent)
- ✅ **All Integration scenarios PASS** (B2.1-B2.4, with agent)
- ✅ Manual smoke test successful
- ✅ Performance: No regression (<1% overhead)
- ✅ Code review approved

**Testing Report Required**:
- Scenario execution results (8/8 PASS)
- Performance metrics
- Coverage report (90%+)

---

## 6. Phase 3: Remote Execution

**Duration**: 1-2 weeks

**Goal**: Enable remote execution using OperationServiceProxy (reuse from training).

**Outcome**: Remote backtesting works across machines.

### 6.1 Task 3.1: Add Remote Mode to BacktestingService

**Duration**: 2-3 days

**Description**: Add `_run_remote_backtest()` method (follows training's pattern).

**Implementation**:
```python
# ktrdr/backtesting/backtesting_service.py

async def _run_remote_backtest(self, operation_id, ...) -> None:
    """Run backtest remotely (follows training pattern)."""
    from ktrdr.api.services.adapters.operation_service_proxy import OperationServiceProxy

    # (1) Start remote backtest
    remote_url = self._get_remote_service_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{remote_url}/backtests/start",
            json={...}
        )
        remote_operation_id = response.json()["operation_id"]

    # (2) Create proxy
    proxy = OperationServiceProxy(base_url=remote_url)

    # (3) Register proxy with OperationsService
    self.operations_service.register_remote_proxy(
        backend_operation_id=operation_id,
        proxy=proxy,
        host_operation_id=remote_operation_id,
    )

    # Done! OperationsService handles all queries via proxy
```

**Files Modified**:
- `ktrdr/backtesting/backtesting_service.py` (+100 lines)

**Acceptance Criteria**:
- ✅ Remote mode implemented
- ✅ Uses OperationServiceProxy (no new code!)
- ✅ Registers proxy with OperationsService
- ✅ Integration tests pass

**Testing with Agent**:
```
Task: "Execute scenario B3.2 (Backend → Remote)"
Expected: Scenario B3.2 PASS
```

---

### 6.2 Task 3.2: Create Remote Container API

**Duration**: 2-3 days

**Description**: Create FastAPI app for remote container.

**Implementation**:
```python
# ktrdr/backtesting/remote_api.py

from fastapi import FastAPI
from ktrdr.backtesting.backtesting_service import BacktestingService

app = FastAPI()
operations_service = OperationsService()
backtest_service = BacktestingService(operations_service)

@app.post("/backtests/start")
async def start_backtest(request: BacktestRequest):
    # Runs BacktestingService in LOCAL mode
    operation_id = await backtest_service.run_backtest(...)
    return {"operation_id": operation_id, "status": "started"}

# Operations endpoints (same as backend)
@app.get("/api/v1/operations/{operation_id}")
async def get_operation(operation_id: str):
    return await operations_service.get_operation(operation_id)
```

**Files Created**:
- `ktrdr/backtesting/remote_api.py` (~150 lines)

**Acceptance Criteria**:
- ✅ Remote container runs BacktestingService locally
- ✅ Exposes OperationsService endpoints
- ✅ **Scenario B3.1 PASSES** (with agent)

**Testing with Agent**:
```
Task: "Execute scenario B3.1 (Remote Direct Start)"
Expected: Scenario B3.1 PASS
```

---

### 6.3 Task 3.3: Docker Compose Configuration

**Duration**: 1 day

**Description**: Add remote container to Docker Compose.

**Files Modified**:
- `docker/docker-compose.yml` (+15 lines)

**Configuration**:
```yaml
services:
  backtest-worker:
    image: ktrdr-backend  # Same image
    ports:
      - "5003:5003"
    environment:
      - USE_REMOTE_BACKTEST_SERVICE=false  # Force local mode
    volumes:
      - ./data:/data
      - ./models:/models
      - ./strategies:/strategies
    command: ["uvicorn", "ktrdr.backtesting.remote_api:app", "--host", "0.0.0.0", "--port", "5003"]
```

**Acceptance Criteria**:
- ✅ Remote container starts
- ✅ Backend can connect
- ✅ **All Remote scenarios PASS** (B3.1-B3.4, with agent)

**Testing with Agent**:
```
Task: "Execute all Remote scenarios (B3.1-B3.4)"
Expected: All 4 scenarios PASS
```

---

### 6.4 Task 3.4: Create Switch Script

**Duration**: 1 day

**Description**: Create mode switching script (follows training's pattern).

**Files Created**:
- `scripts/switch-backtest-mode.sh` (~50 lines, copy from training script)

**Script**:
```bash
#!/bin/bash
case "$1" in
    local)
        export USE_REMOTE_BACKTEST_SERVICE=false
        ;;
    remote)
        export USE_REMOTE_BACKTEST_SERVICE=true
        ;;
esac
cd docker && docker-compose up -d backend
```

**Acceptance Criteria**:
- ✅ Script switches modes
- ✅ Backend restarts with new config
- ✅ Mode switch works

---

### 6.5 Phase 3 Validation

**Gate Criteria**:

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ **All Remote scenarios PASS** (B3.1-B3.4, with agent)
- ✅ Manual testing successful
- ✅ Performance acceptable
- ✅ Code review approved

**Testing Report Required**:
- All scenario results (12/12 PASS)
- Performance metrics (local vs remote)
- Coverage report

---

## 7. Phase 4: Production Readiness

**Duration**: 1 week

**Goal**: E2E testing, documentation, production deployment.

**Outcome**: Production-ready system.

### 7.1 Task 4.1: End-to-End Testing

**Duration**: 2 days

**Description**: Execute all scenarios with agent.

**Testing with Agent**:
```
Task: "Execute complete scenario suite (all categories)"
Expected:
- Backend scenarios PASS (B1.1-B1.4)
- Integration scenarios PASS (B2.1-B2.4)
- Remote scenarios PASS (B3.1-B3.4)
- Error scenarios PASS (B4.1-B4.3)
Total: 15+ scenarios, 100% PASS
```

**Acceptance Criteria**:
- ✅ **All 15+ scenarios PASS**
- ✅ No regressions
- ✅ Performance acceptable

---

### 7.2 Task 4.2: Performance Benchmarking

**Duration**: 1-2 days

**Description**: Benchmark with agent.

**Testing with Agent**:
```
Task: "Execute performance benchmarks"
Expected:
- Local mode: <1% overhead
- Bridge writes: <1μs
- Remote HTTP: <5ms per request
```

**Acceptance Criteria**:
- ✅ All benchmarks meet targets
- ✅ No performance regressions

---

### 7.3 Task 4.3: Documentation

**Duration**: 2 days

**Description**: Complete documentation.

**Documents to Create/Update**:
1. User guide
2. API documentation
3. CLI documentation
4. Developer guide
5. Operations guide
6. Migration guide

**Acceptance Criteria**:
- ✅ All documentation complete
- ✅ Examples tested (with agent)

---

### 7.4 Task 4.4: Production Deployment

**Duration**: 1 day

**Description**: Deploy with agent validation.

**Steps**:
1. Deploy to staging
2. Execute all scenarios in staging (with agent)
3. Monitor 24 hours
4. Deploy to production
5. Execute smoke tests (with agent)

**Acceptance Criteria**:
- ✅ Staging deployment successful
- ✅ **All scenarios PASS in staging**
- ✅ Production deployment successful
- ✅ **Smoke tests PASS in production**

---

### 7.5 Phase 4 Validation

**Final Gate Criteria**:

- ✅ **All tests pass** (100% success)
- ✅ **Performance benchmarks met**
- ✅ **Documentation complete**
- ✅ **Production deployment successful**
- ✅ **Zero incidents** (48 hours)

---

## 8. Testing Specialist Integration

### 8.1 Agent Usage Pattern

**For each task completion**:

```
1. Implement (Developer)
   ↓
2. Validate (integration-test-specialist Agent)
   - Execute relevant scenarios
   - Run integration tests
   - Report results
   ↓
3. Review (Developer)
   - Analyze results
   - Fix failures
   - Re-validate
   ↓
4. Document (Developer)
   - Update metrics
   - Mark complete
```

### 8.2 Example Agent Tasks

**Task 2.3 Completion**:
```
Agent Task: "Execute scenarios B2.1 and B2.2"
Expected:
- B2.1: Backtest via API works, progress visible
- B2.2: Cancellation works
Agent Report: PASS/FAIL with details
```

---

## 9. Success Criteria

### 9.1 Phase Completion Criteria

**Phase 0**:
- ✅ Backtesting works now
- ✅ OperationsService generic
- ✅ Baselines established

**Phase 1**:
- ✅ 15+ scenarios documented

**Phase 2**:
- ✅ Local mode works
- ✅ Backend + Integration scenarios PASS (8/8)

**Phase 3**:
- ✅ Remote mode works
- ✅ Remote scenarios PASS (4/4)

**Phase 4**:
- ✅ **All 15+ scenarios PASS (100%)**
- ✅ **Production deployment successful**

### 9.2 Overall Success Criteria

**Functional**:
- ✅ Local and remote backtesting work
- ✅ Progress tracking via OperationsService
- ✅ Cancellation support

**Technical**:
- ✅ Follows training's pattern exactly
- ✅ Reuses OperationsService, OperationServiceProxy
- ✅ 90%+ test coverage
- ✅ No performance regression

**Testing**:
- ✅ **15+ scenarios executed with agent**
- ✅ **100% pass rate**
- ✅ **Continuous validation**

---

## Appendix A: Key Architectural Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| **Reuse OperationsService** | Already proven | 1 small fix needed |
| **Reuse OperationServiceProxy** | Already generic | Zero changes |
| **Use ProgressBridge** | Same as training | Fast writes, no async issues |
| **Client-driven pull** | Current architecture | No polling, simple |
| **ENV-based mode** | Same as training | Consistent, simple |

## Appendix B: Code Estimates

| Component | Lines of Code | Complexity |
|-----------|--------------|------------|
| **Engine hooks** | +50 | Low |
| **BacktestProgressBridge** | ~100 | Low |
| **BacktestingService** | ~300 | Medium |
| **Remote API** | ~150 | Low |
| **API endpoints** | ~150 | Low |
| **CLI commands** | ~200 | Low |
| **OperationsService fix** | +15 | Low |
| **Total New** | ~950 | Medium |

---

**Document Version**: 3.0 (Pull-Based Operations)
**Last Updated**: 2025-01-03
**Status**: READY FOR IMPLEMENTATION
