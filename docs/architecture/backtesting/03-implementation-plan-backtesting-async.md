# Implementation Plan: Backtesting Async Operations

## Document Information

**Date**: 2025-01-04 (Revised)
**Status**: READY FOR IMPLEMENTATION
**Version**: 3.1 (Pull-Based Operations - Testing-First with Model Foundation)
**Related Documents**:
- [Design Document](./01-design-backtesting-async.md) - High-level design
- [Architecture Document](./02-architecture-backtesting-async.md) - Detailed architecture
- [Testing Guide](../../testing/TESTING_GUIDE.md) - Testing infrastructure
- [Test Scenarios](../../testing/SCENARIOS.md) - Scenario templates

---

## Changes in Version 3.1

**Key Improvements**:
1. **Added Task 1.0**: Establish test foundation (models, data validation)
2. **Refined Phase 1**: Specify scenario REQUIREMENTS not implementations
3. **Added integration-test-specialist workflow** throughout all phases
4. **Explicit scenario validation gates** in Phases 2-4
5. **Model dependency resolution** with existing trained models
6. **Updated scenario expectations** to match TESTING_GUIDE.md patterns

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

**REVISED STRATEGY**: Fix first, **validate test foundation**, design scenarios, build with continuous testing, **follow training's pattern exactly**.

1. **Phase 0** (Critical): Fix broken backtesting + make OperationsService generic ✅ **COMPLETE**
2. **Phase 1** (Foundation): **Validate test models**, design comprehensive test suite
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

- ✅ **Phase 0**: Backtesting works now, OperationsService generic ✅ **COMPLETE**
- ✅ **Phase 1**: Test models validated, 17+ scenarios documented
- ✅ **Phase 2**: Local mode works, all backend+integration scenarios PASS (8/8)
- ✅ **Phase 3**: Remote mode works, all remote scenarios PASS (12/12 total)
- ✅ **Phase 4**: **All 17+ scenarios PASS (100%)**, production deployment successful

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

1. **Executing baseline tests** (Phase 0) ✅ **COMPLETE**
2. **Validating test models** (Phase 1.0)
3. **Executing incremental tests** (Phases 2-3)
4. **Executing comprehensive tests** (Phase 4)

### 2.3 Scenario Validation Requirements

**NEW**: Each scenario document created in Phase 1 must specify:

| Required Section | Purpose | Example |
|-----------------|---------|---------|
| **Prerequisites** | What must be running/available | Backend, model file, data cached |
| **Test Data** | Exact inputs with justification | Symbol, timeframe, date range, model path |
| **Commands** | Executable bash/curl/python | Full working examples (not templates) |
| **Expected Results** | Specific, measurable outcomes | Status codes, field values, performance targets |
| **Validation Checklist** | Pass/fail criteria | Checkbox list for manual/agent verification |
| **Actual Results** | Space for test execution findings | Filled during testing (initially empty) |

**Reference**: See [SCENARIOS.md](../../testing/SCENARIOS.md) for training scenario examples (1.1-4.2)

### 2.4 Test Categories

| Category | Examples | Agent Usage | Scenarios Must Pass |
|----------|----------|-------------|-------------------|
| **Backend Isolated** | Local backtest execution | Execute after each component | By end of Phase 2 |
| **Integration** | Backend + OperationsService | Execute for integration points | By end of Phase 2 |
| **Remote** | Backend → Remote container | Execute when remote ready | By end of Phase 3 |
| **Error Handling** | Invalid configs, cancellation | Execute throughout | By end of Phase 3 |

---

## 3. Phase 0: Fix Current System ✅ **COMPLETE**

**Duration**: 1-2 days

**Goal**: Make backtesting work + make OperationsService generic.

**Outcome**: Solid foundation for async implementation.

**Status**: ✅ **COMPLETE** (2025-11-04)

**Results**:
- ✅ Task 0.1: FeatureCache bug fixed
- ✅ Task 0.2: OperationsService made generic (type-aware metrics)
- ✅ Task 0.3: Baseline tests established (23/23 PASSED)

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

**Goal**: Validate test foundation, design comprehensive test scenarios following established patterns.

**Outcome**: Test models validated, complete scenario documents ready for implementation.

---

### 4.1 Task 1.0: Update Testing Reference Documents **[REVISED]**

**Duration**: 4-6 hours

**Description**: Add backtesting scenarios to existing testing reference documents used by integration-test-specialist agent.

**Problem Statement**: The integration-test-specialist agent uses `SCENARIOS.md` and `TESTING_GUIDE.md` as their knowledge base. We need to add backtesting patterns to these existing documents, NOT create separate documents.

**Files to Update**:
1. `docs/testing/SCENARIOS.md` - Add backtesting scenarios (B1.1-B4.3)
2. `docs/testing/TESTING_GUIDE.md` - Add backtesting API endpoints and test data
3. `.claude/agents/integration-test-specialist.md` - Update knowledge base section

**Steps**:

1. **Validate Test Foundation** (2h)
   - Identify available trained models in `models/`
   - Verify model loads (torch.load) and strategy config exists
   - Check test data availability (EURUSD, AAPL)
   - Document test model: `neuro_mean_reversion v21` (63.26% val accuracy)
   - Document test data: EURUSD 1d (4,762 bars), AAPL 1d (458 bars)

2. **Add to SCENARIOS.md** (2h)
   - Add backtesting scenarios table to index (13 scenarios)
   - Add detailed scenarios B1.1-B4.3 following existing format
   - Keep scenarios concise like training/data scenarios
   - Update summary statistics section

3. **Add to TESTING_GUIDE.md** (1h)
   - Add backtesting API endpoint (`POST /api/v1/backtests/start`)
   - Add backtest worker service (port 5003)
   - Add backtesting test data parameters
   - Document test model and strategy

4. **Update integration-test-specialist.md** (30min)
   - Add backtesting to "Current Testing Knowledge Base"
   - Update reference document counts
   - Remove backtesting from "Areas WITHOUT Building Blocks"

**Acceptance Criteria**:
- ✅ At least 1 test model validated (loads successfully)
- ✅ Strategy config exists
- ✅ Test data available (EURUSD 1d, AAPL 1d)
- ✅ 13 backtesting scenarios added to SCENARIOS.md index
- ✅ 13 detailed scenario sections added (B1.1-B1.3, B2.1-B2.3, B3.1-B3.4, B4.1-B4.3)
- ✅ TESTING_GUIDE.md includes backtesting endpoints and test data
- ✅ integration-test-specialist.md updated with backtesting knowledge
- ✅ All scenarios follow existing format (concise, executable)

**Testing with Agent**:
```
NOT APPLICABLE - These are reference documents for the agent to use.
Agent will use these scenarios starting in Phase 2 when implementation begins.
```

**Deliverables**:
- Updated `docs/testing/SCENARIOS.md` with 13 backtesting scenarios
- Updated `docs/testing/TESTING_GUIDE.md` with backtesting building blocks
- Updated `.claude/agents/integration-test-specialist.md`
- Test model documented: `models/neuro_mean_reversion/1d_v21/model.pt`
- Test data documented: EURUSD 1d, AAPL 1d

**Note**: This task creates NO new files. All updates are to existing reference documents.

---

### 4.2 Tasks 1.1-1.4: Scenario Design **[CONSOLIDATED INTO TASK 1.0]**

**Status**: These tasks have been consolidated into Task 1.0.

**What Changed**:
- ❌ **Old approach**: Create separate scenario documents (BACKEND_SCENARIOS.md, INTEGRATION_SCENARIOS.md, etc.)
- ✅ **New approach**: Add scenarios directly to existing `SCENARIOS.md` (following training/data patterns)

**Scenarios Added to SCENARIOS.md** (13 total):

| Scenario ID | Name | Purpose | Expected Duration | Must Specify |
|-------------|------|---------|------------------|--------------|
| **B1.1** | Local Backtest - Smoke Test | Quick validation of basic workflow | ~5 seconds | Model path, 20-bar dataset, expected result fields |
| **B1.2** | Local Backtest - Progress Tracking | Verify ProgressBridge updates | ~15-30 seconds | 60+ bar dataset, progress checkpoints, percentage milestones |
| **B1.3** | Local Backtest - Cancellation | Verify cancellation token works | ~10 seconds (cancel mid-run) | When to cancel, expected status transitions, cleanup verification |
| **B1.4** | Local Backtest - Error Handling | Invalid strategy config | ~2 seconds | Invalid config example, expected error message format |

**Requirements for Each Scenario**:

1. **Must Specify Test Model**:
   - Exact model path from PREREQUISITES.md
   - Strategy config path
   - Expected model characteristics (if relevant to test)

2. **Must Specify Test Data**:
   - Symbol, timeframe, exact date range
   - Expected bar count
   - Justification for data choice (e.g., "20 bars for fast test")

3. **Must Define Expected Results**:
   - **Quantitative**: Exact status codes, field presence, performance targets
   - **Qualitative**: Log messages, error formats
   - **Performance**: Max duration, memory usage (if applicable)
   - **HOW to check** (critical):
     - If checking logs: Exact log message patterns to grep for, which service's logs
     - If checking status: Which API endpoint, which fields to inspect, expected values
     - If checking files: File paths, what content to verify
     - If checking behavior: What actions to take, what responses to expect

4. **Must Include Validation Checklist**:
   - Checkbox format for manual/agent verification
   - Each item specifies HOW to verify (not just what)
   - Example:
     ```markdown
     ### Validation Checklist
     - [ ] Operation created: Check response has HTTP 200 + `operation_id` field
     - [ ] Status completed: GET /operations/{id}, verify `status: "completed"`
     - [ ] Duration < 5 seconds: Check `result_summary.execution_time < 5.0`
     - [ ] All result fields present: Verify response has `total_return`, `sharpe_ratio`, `max_drawdown`
     - [ ] No errors in logs: `docker-compose logs backend --since 60s | grep -i error` returns empty
     - [ ] Bridge registered: Backend logs contain `Registered.*bridge.*{operation_id}`
     ```

**What NOT to Include** (too much detail):
- ❌ Full bash command implementations (provide templates/structure only)
- ❌ Specific operation IDs (these are runtime values)
- ❌ Implementation details (how code works internally)

**Files to Create**:
- `docs/testing/scenarios/backtesting/BACKEND_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ backend scenarios documented
- ✅ Following SCENARIOS.md pattern (all required sections present)
- ✅ Model paths from PREREQUISITES.md
- ✅ Test data fully specified (symbol, timeframe, date range, bar count)
- ✅ Expected results are specific and measurable
- ✅ Validation checklists provided
- ✅ Commands are executable templates (not pseudocode)

**Testing with Agent**:
```
Task: "Review BACKEND_SCENARIOS.md for completeness"
Expected:
- All 4 scenarios have required sections
- Model paths match PREREQUISITES.md
- Expected results are specific and measurable
- Commands are valid bash/curl/python syntax
```

---

### 4.3 Task 1.2: Design Integration Scenarios

**Duration**: 1 day

**Description**: Design scenarios for API integration (backend + OperationsService, local mode).

**Scenarios to Design** (4 minimum):

| Scenario ID | Name | Purpose | Expected Duration | Must Specify |
|-------------|------|---------|------------------|--------------|
| **B2.1** | Backtest via API - Local Mode | Full API workflow | ~10 seconds | API endpoint, request payload, response format |
| **B2.2** | API Progress Polling | Verify progress updates via API | ~20 seconds | Polling interval, expected progress updates |
| **B2.3** | API Cancellation | Cancel via DELETE endpoint | ~10 seconds | Cancel timing, status transitions, cleanup |
| **B2.4** | API Error Handling | Missing data error via API | ~2 seconds | Error response format, HTTP status codes |

**Additional Requirements** (beyond Task 1.1 requirements):

1. **Must Specify API Contracts**:
   - Exact endpoint paths
   - Request payload format (JSON schema)
   - Response format (with field types)
   - HTTP status codes for success/error cases

2. **Must Specify Service State**:
   - Backend running (port 8000)
   - Environment variables (USE_REMOTE_BACKTEST_SERVICE=false)
   - Data cached (specific files)

3. **Must Define Progress Expectations**:
   - Polling intervals (e.g., every 2-5 seconds)
   - Expected progress milestones (0% → 25% → 50% → 75% → 100%)
   - Progress update frequency

**Files to Create**:
- `docs/testing/scenarios/backtesting/INTEGRATION_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ integration scenarios documented
- ✅ API contracts fully specified (endpoints, payloads, responses)
- ✅ Environment configuration specified
- ✅ Progress polling patterns detailed
- ✅ Following SCENARIOS.md pattern

**Testing with Agent**:
```
Task: "Review INTEGRATION_SCENARIOS.md for API completeness"
Expected:
- All endpoints documented with full paths
- Request/response formats specified
- HTTP status codes defined
- Progress expectations quantified
```

---

### 4.4 Task 1.3: Design Remote Scenarios

**Duration**: 1 day

**Description**: Design scenarios for remote container execution (Phase 3 preparation).

**Scenarios to Design** (4 minimum):

| Scenario ID | Name | Purpose | Expected Duration | Must Specify |
|-------------|------|---------|------------------|--------------|
| **B3.1** | Remote Backtest - Direct Start | Standalone remote service | ~10 seconds | Remote port (5003), data/model accessibility |
| **B3.2** | Backend → Remote Proxy | Full backend-to-remote flow | ~10 seconds | Proxy registration logs, operation ID mapping |
| **B3.3** | Remote Progress Updates | Progress polling from backend | ~20 seconds | Two-level progress tracking (backend + remote) |
| **B3.4** | Remote Cancellation | Cancel remote operation | ~10 seconds | Cancellation propagation, cleanup on both services |

**Additional Requirements**:

1. **Must Specify Remote Service Configuration**:
   - Remote container port (5003)
   - Data/model volume mounts
   - Environment variables (USE_REMOTE_BACKTEST_SERVICE=true for backend)

2. **Must Define Proxy Behavior**:
   - Backend operation ID format
   - Remote operation ID format
   - Operation ID mapping logging
   - Progress proxying expectations

3. **Must Specify Two-Level Behavior**:
   - Backend behavior (proxy mode)
   - Remote service behavior (local mode within remote)
   - Expected log messages in both services

**Files to Create**:
- `docs/testing/scenarios/backtesting/REMOTE_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 4+ remote scenarios documented
- ✅ Remote container configuration specified
- ✅ Proxy patterns documented (following training model)
- ✅ Two-level architecture expectations clear
- ✅ Operation ID mapping specified

**Testing with Agent**:
```
Task: "Review REMOTE_SCENARIOS.md for distributed architecture coverage"
Expected:
- Remote service config documented
- Proxy behavior specified
- Operation ID mapping defined
- Two-level expectations clear
```

---

### 4.5 Task 1.4: Design Error Handling Scenarios

**Duration**: 4 hours

**Description**: Design scenarios for error conditions and edge cases.

**Scenarios to Design** (5 minimum):

| Scenario ID | Name | Purpose | Expected Duration | Must Specify |
|-------------|------|---------|------------------|--------------|
| **B4.1** | Invalid Strategy Config | Missing required fields | ~2 seconds | Invalid config content, expected error message |
| **B4.2** | Missing Historical Data | Data file not found | ~2 seconds | Non-existent symbol/timeframe, error response |
| **B4.3** | Cancellation During Execution | Mid-run cancellation | ~10 seconds | Cancel timing, cleanup verification |
| **B4.4** | Model File Not Found | Invalid model path | ~2 seconds | Invalid path, expected error format |
| **B4.5** | Insufficient Data | Less than minimum bars | ~2 seconds | Insufficient date range, minimum bar requirement |

**Requirements for Error Scenarios**:

1. **Must Specify Error Trigger**:
   - Exact invalid input (config content, file path, date range)
   - Why it should fail (missing field, file not found, insufficient data)

2. **Must Define Expected Error Behavior**:
   - HTTP status code (400, 404, 500, etc.)
   - Error message format (specific string or pattern)
   - Operation status (if operation created before failure)
   - No partial state corruption

3. **Must Specify Recovery**:
   - System remains stable after error
   - No resource leaks
   - Can run successful operation after error

**Files to Create**:
- `docs/testing/scenarios/backtesting/ERROR_SCENARIOS.md`

**Acceptance Criteria**:
- ✅ 5+ error scenarios documented
- ✅ Cover config, data, cancellation, and file errors
- ✅ Expected error messages specified (exact strings or patterns)
- ✅ Error recovery verified
- ✅ Following SCENARIOS.md pattern

**Testing with Agent**:
```
Task: "Review ERROR_SCENARIOS.md for error handling coverage"
Expected:
- All error triggers specified
- Error messages defined
- Recovery validated
- No gaps in error coverage
```

---

### 4.6 Phase 1 Validation

**Gate Criteria**:

- ✅ **Task 1.0 Complete**: Test models validated, prerequisites documented
- ✅ **All scenario categories documented**:
  - Backend Isolated (4+)
  - Integration (4+)
  - Remote (4+)
  - Error Handling (5+)
- ✅ **Total: 17+ test scenarios**
- ✅ **All scenarios follow SCENARIOS.md pattern** (verified by agent)
- ✅ **Model paths specified** (from PREREQUISITES.md)
- ✅ **Expected results specific and measurable**
- ✅ **Validation checklists provided**

**Deliverables**:
- `docs/testing/scenarios/backtesting/PREREQUISITES.md`
- `docs/testing/scenarios/backtesting/BACKEND_SCENARIOS.md`
- `docs/testing/scenarios/backtesting/INTEGRATION_SCENARIOS.md`
- `docs/testing/scenarios/backtesting/REMOTE_SCENARIOS.md`
- `docs/testing/scenarios/backtesting/ERROR_SCENARIOS.md`

**Testing with Agent**:
```
Task: "Validate Phase 1 completion - all scenario documents ready for implementation"
Expected:
- All 5 documents exist
- All scenarios follow template
- Test foundation validated
- Ready to begin Phase 2 implementation
```

---

## 5. Phase 2: Service and Local Mode

**Duration**: 1-2 weeks

**Goal**: Implement BacktestingService with local execution (following training's pattern).

**Outcome**: Local backtesting works with progress tracking and cancellation.

**NEW REQUIREMENT**: **All Backend + Integration scenarios (B1.x, B2.x) MUST PASS before Phase 2 completion.**

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
- ✅ Engine accepts bridge and cancellation_token parameters
- ✅ Progress updates every 50 bars
- ✅ Cancellation checked every 100 bars
- ✅ Unit tests pass
- ✅ **Scenario B1.2 MUST PASS** (Progress Tracking)
- ✅ **Scenario B1.3 MUST PASS** (Cancellation)

**Testing with Agent**:
```
Task: "Execute scenarios B1.2 and B1.3 after ProgressBridge implementation"
Expected: BOTH scenarios PASS
If FAIL: Fix code, not scenario (unless requirements changed)
```

**Scenario Validation Protocol**:
1. Run scenario with integration-test-specialist
2. If PASS: Mark scenario validated, proceed
3. If FAIL:
   a. **First**: Investigate code issue (90% of cases)
   b. **Second**: Check if requirements changed (10% of cases)
   c. Fix code OR update scenario with justification
   d. Re-run until PASS
4. Document results in scenario "Actual Results" section

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
- ✅ **Scenario B1.1 MUST PASS** (Smoke Test - uses bridge)

**Testing with Agent**:
```
Task: "Execute scenario B1.1 (Smoke Test) with BacktestProgressBridge"
Expected: Scenario PASSES, progress updates visible
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
- ✅ Runs engine in thread (asyncio.to_thread)
- ✅ Unit tests pass
- ✅ **Scenarios B2.1 and B2.2 MUST PASS** (API integration)

**Testing with Agent**:
```
Task: "Execute scenarios B2.1 (API Local Mode) and B2.2 (API Cancellation)"
Expected: BOTH scenarios PASS
```

**Critical**: If scenarios fail, follow validation protocol (see Task 2.1)

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
- ✅ API documentation (Swagger) updated
- ✅ **All Integration scenarios MUST PASS** (B2.1-B2.4)

**Testing with Agent**:
```
Task: "Execute all Integration scenarios (B2.1-B2.4) after API implementation"
Expected: All 4 scenarios PASS
Regression check: All Backend scenarios (B1.1-B1.4) still PASS
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
- ✅ **Manual validation**: Run full workflow via CLI

**Testing**:
```bash
# Manual test workflow
ktrdr backtest run --symbol AAPL --timeframe 1d \
  --strategy neuro_mean_reversion \
  --start-date 2024-01-01 --end-date 2024-01-31

# Verify output matches scenario B2.1 expectations
```

---

### 5.6 Phase 2 Validation

**Gate Criteria** (STRICT):

- ✅ All unit tests pass (90%+ coverage)
- ✅ All integration tests pass
- ✅ **ALL Backend scenarios PASS** (B1.1-B1.4) - NO EXCEPTIONS
- ✅ **ALL Integration scenarios PASS** (B2.1-B2.4) - NO EXCEPTIONS
- ✅ Manual smoke test successful
- ✅ Performance: No regression (<1% overhead vs baseline)
- ✅ Code review approved
- ✅ No errors in service logs during scenario execution

**Scenario Pass Rate Required**: **8/8 (100%)**

**Testing Report Required**:
- Scenario execution results (8/8 PASS)
- Performance metrics (duration, memory)
- Coverage report (90%+)
- Integration-test-specialist execution logs

**What to Do if Scenarios Fail**:
1. **First**: Fix the code (90% of failures)
2. **Second**: Verify scenario is correct (check against TESTING_GUIDE.md examples)
3. **Third**: If requirements genuinely changed, update scenario with:
   - Justification in "Actual Results" section
   - Version number increment
   - Review with team
4. **Never**: Skip failing scenarios or mark them as "known issues"

**Deliverables**:
- Working code (all Phase 2 tasks)
- Test report (8/8 scenarios PASS)
- Updated SCENARIOS.md with actual results

---

## 6. Phase 3: Remote Execution

**Duration**: 1-2 weeks

**Goal**: Enable remote execution using OperationServiceProxy (reuse from training).

**Outcome**: Remote backtesting works across machines.

**NEW REQUIREMENT**: **All Remote scenarios (B3.x) MUST PASS before Phase 3 completion.**

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
- ✅ Uses OperationServiceProxy (no new proxy code!)
- ✅ Registers proxy with OperationsService
- ✅ Integration tests pass
- ✅ **Scenario B3.2 MUST PASS** (Backend → Remote Proxy)

**Testing with Agent**:
```
Task: "Execute scenario B3.2 (Backend → Remote Proxy)"
Expected: Scenario PASSES
Regression check: All Phase 2 scenarios still PASS (B1.x, B2.x)
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
- ✅ Remote container runs BacktestingService in LOCAL mode
- ✅ Exposes OperationsService endpoints
- ✅ **Scenario B3.1 MUST PASS** (Remote Direct Start)

**Testing with Agent**:
```
Task: "Execute scenario B3.1 (Remote Direct Start)"
Expected: Scenario PASSES
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
- ✅ **ALL Remote scenarios MUST PASS** (B3.1-B3.4)

**Testing with Agent**:
```
Task: "Execute all Remote scenarios (B3.1-B3.4) with Docker Compose"
Expected: All 4 scenarios PASS
Regression check: All Phase 2 scenarios still PASS
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

### 6.5 Task 3.5: Remove Dead Code from Old Implementation

**Duration**: 1-2 hours

**Description**: Remove obsolete code paths that were replaced during Phase 1-3 implementation.

**Analysis Findings**:

During implementation, new async architecture replaced old synchronous patterns, leaving dead code:

1. **Old API Service** (683 lines)
   - File: `ktrdr/api/services/backtesting_service.py`
   - Reason: Replaced by `ktrdr/backtesting/backtesting_service.py` (ServiceOrchestrator pattern)
   - Not imported anywhere
   - Last modified: Before async migration

2. **Old CLI Commands** (380 lines)
   - File: `ktrdr/cli/backtesting_commands.py`
   - Reason: Replaced by `ktrdr/cli/backtest_commands.py` (AsyncOperationExecutor pattern)
   - Not imported in `ktrdr/cli/__init__.py`
   - Uses obsolete `get_api_client` pattern

3. **Old Service Tests** (15KB)
   - File: `tests/api/test_backtesting_service.py`
   - Reason: Tests obsolete service, replaced by `tests/unit/backtesting/test_backtesting_service.py`
   - Imports dead `ktrdr.api.services.backtesting_service`

4. **Backup File**
   - File: `tests/api/test_backtesting_endpoints.py.bak`
   - Reason: Development artifact, should not be in repo

**Files to Delete**:
```bash
rm ktrdr/api/services/backtesting_service.py
rm ktrdr/cli/backtesting_commands.py
rm tests/api/test_backtesting_service.py
rm tests/api/test_backtesting_endpoints.py.bak
```

**Verification Steps**:

1. Search codebase for imports of deleted files:

   ```bash
   grep -r "from ktrdr.api.services.backtesting_service import" .
   grep -r "from ktrdr.cli.backtesting_commands import" .
   ```

   Should return: No results

2. Run all tests to ensure no regressions:

   ```bash
   make test-unit
   ```

3. Check for any other references:

   ```bash
   grep -r "BacktestingService" . --include="*.py" | grep "api.services.backtesting"
   ```

**Acceptance Criteria**:
- ✅ All 4 dead code files removed
- ✅ No import errors after deletion
- ✅ All unit tests still passing
- ✅ No references to deleted files in codebase

---

### 6.6 Task 3.6: Update MCP Server (If Needed)

**Duration**: 30 minutes

**Description**: Verify MCP server doesn't need updates for new backtesting architecture.

**Analysis Findings**:

MCP server was checked for backtesting endpoint usage:

1. **MCP Server Current State**:
   - File: `mcp/src/server.py`
   - Uses generic operations endpoints: `/api/v1/operations/*`
   - No direct backtesting endpoint calls
   - Only mentions "backtesting" as operation_type filter option

2. **Endpoint Changes**:
   - Old: Unknown (no documented old endpoints)
   - New: `/api/v1/backtests/start` (returns operation_id)
   - Operations endpoints: UNCHANGED (`/api/v1/operations/*`)

3. **Impact Assessment**:
   - ✅ MCP uses operations endpoints (unchanged)
   - ✅ No MCP tools call backtesting-specific endpoints
   - ✅ MCP `list_operations()` supports `operation_type="backtesting"` (still valid)

**Conclusion**: NO MCP UPDATES NEEDED

**Verification Steps**:

```bash
# Verify MCP doesn't import backtesting endpoints
grep -r "backtests/start" mcp/
# Should return: No results

# Verify operations endpoints still work
curl http://localhost:8000/api/v1/operations?operation_type=backtesting
```

**Acceptance Criteria**:

- ✅ MCP server verified to not use backtesting-specific endpoints
- ✅ Operations endpoints still functional
- ✅ No MCP code changes required

---

### 6.7 Phase 3 Validation

**Gate Criteria** (STRICT):

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ **ALL Remote scenarios PASS** (B3.1-B3.4) - NO EXCEPTIONS
- ✅ **Regression**: All Phase 2 scenarios still PASS (B1.x, B2.x)
- ✅ Manual testing successful (both modes)
- ✅ Performance acceptable (remote overhead <20%)
- ✅ Code review approved

**Scenario Pass Rate Required**: **12/12 (100%)** (8 from Phase 2 + 4 from Phase 3)

**Testing Report Required**:
- All scenario results (12/12 PASS)
- Performance metrics (local vs remote)
- Coverage report
- Mode switching validation

**Deliverables**:
- Remote execution working
- Switch script functional
- Test report (12/12 scenarios PASS)

---

## 7. Phase 4: Production Readiness

**Duration**: 1 week

**Goal**: E2E testing, documentation, production deployment.

**Outcome**: Production-ready system.

**NEW REQUIREMENT**: **ALL scenarios including Error Handling (B4.x) MUST PASS.**

---

### 7.1 Task 4.1: Error Scenario Validation

**Duration**: 2 days

**Description**: Execute all error handling scenarios.

**Testing with Agent**:
```
Task: "Execute all Error Handling scenarios (B4.1-B4.5)"
Expected:
- All 5 scenarios PASS
- Errors handled gracefully
- No resource leaks
- System remains stable after errors
```

**Acceptance Criteria**:
- ✅ **ALL Error scenarios PASS** (B4.1-B4.5) - NO EXCEPTIONS
- ✅ Error recovery verified
- ✅ No resource leaks

---

### 7.2 Task 4.2: End-to-End Testing

**Duration**: 2 days

**Description**: Execute all scenarios with agent.

**Testing with Agent**:
```
Task: "Execute complete scenario suite (all categories)"
Expected:
- Backend scenarios PASS (B1.1-B1.4)
- Integration scenarios PASS (B2.1-B2.4)
- Remote scenarios PASS (B3.1-B3.4)
- Error scenarios PASS (B4.1-B4.5)
Total: 17 scenarios, 100% PASS rate
```

**Acceptance Criteria**:
- ✅ **ALL 17 scenarios PASS** - NO EXCEPTIONS
- ✅ No regressions
- ✅ Performance acceptable across all scenarios

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
- ✅ No performance regressions vs Phase 0 baseline

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
- ✅ Examples tested with agent
- ✅ Links verified

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
- ✅ **ALL 17 scenarios PASS in staging**
- ✅ Production deployment successful
- ✅ **Smoke tests PASS in production** (B1.1, B2.1, B3.1)

---

### 7.5 Phase 4 Validation

**Final Gate Criteria** (STRICTEST):

- ✅ **ALL 17 scenarios PASS** (100% success rate) - NO EXCEPTIONS
- ✅ **Performance benchmarks met** (all targets)
- ✅ **Documentation complete** (all 6 documents)
- ✅ **Production deployment successful**
- ✅ **Zero incidents** (48 hours post-deployment)
- ✅ **All Phase 0 baseline tests still PASS** (no regressions to original system)

**Final Deliverables**:
- Production system deployed
- All scenario documents with "Actual Results" filled
- Performance benchmarks documented
- Complete documentation set
- Zero known issues

---

## 8. Testing Specialist Integration

### 8.1 Agent Usage Pattern

**For each task with scenario requirements**:

```
1. Developer implements code
   ↓
2. Developer reviews implementation
   ↓
3. Use integration-test-specialist agent:
   - Agent reads scenario document
   - Agent executes all commands
   - Agent fills "Actual Results" section
   - Agent reports PASS/FAIL with details
   ↓
4. If FAIL:
   a. Developer investigates (check logs, debug)
   b. Developer fixes code (90% of cases)
   c. OR developer updates scenario with justification (10% of cases)
   d. Re-run agent until PASS
   ↓
5. If PASS:
   - Mark scenario as validated
   - Update scenario document with actual results
   - Proceed to next task
```

### 8.2 Scenario Failure Protocol

**When scenario fails**:

1. **Investigate** (30 minutes)
   - Check service logs
   - Verify prerequisites met
   - Review error messages

2. **Categorize** (5 minutes)
   - Code bug (90%): Implementation doesn't match requirements
   - Scenario bug (5%): Scenario has wrong expectations
   - Requirements change (5%): Design changed since Phase 1

3. **Fix** (varies)
   - Code bug: Fix implementation, re-test
   - Scenario bug: Fix scenario, document correction
   - Requirements change: Update scenario + design docs, get approval

4. **Validate** (agent)
   - Re-run scenario with agent
   - Verify PASS
   - Check for regressions (other scenarios still PASS)

5. **Document** (5 minutes)
   - Fill "Actual Results" in scenario
   - Note any issues found
   - Mark scenario validated

### 8.3 Example Agent Tasks

**Task 2.3 Completion**:
```
Agent Task: "Execute scenarios B2.1 and B2.2"
Expected:
- B2.1: Backtest via API works, operation_id returned, results correct
- B2.2: Cancellation works, status transitions correct
Agent Report: PASS/FAIL with details for each scenario
```

**Phase 2 Gate**:
```
Agent Task: "Execute all Backend and Integration scenarios (B1.1-B2.4)"
Expected:
- All 8 scenarios PASS
- Performance within targets
- No errors in logs
Agent Report: Summary table with PASS/FAIL for each scenario
```

---

## 9. Success Criteria

### 9.1 Phase Completion Criteria

**Phase 0**:
- ✅ Backtesting works now ✅ **COMPLETE**
- ✅ OperationsService generic ✅ **COMPLETE**
- ✅ Baselines established ✅ **COMPLETE**

**Phase 1**:
- ✅ Test models validated
- ✅ 17+ scenarios documented
- ✅ All scenarios follow SCENARIOS.md template
- ✅ Prerequisites documented

**Phase 2**:
- ✅ Local mode works
- ✅ **Backend + Integration scenarios PASS (8/8)** - NO EXCEPTIONS

**Phase 3**:
- ✅ Remote mode works
- ✅ **Remote scenarios PASS (4/4)** - NO EXCEPTIONS
- ✅ **Phase 2 scenarios still PASS (8/8)** - Regression check

**Phase 4**:
- ✅ **ALL 17 scenarios PASS (100%)** - NO EXCEPTIONS
- ✅ **Error scenarios PASS (5/5)** - NO EXCEPTIONS
- ✅ **Production deployment successful**
- ✅ **Zero incidents (48 hours)**

### 9.2 Overall Success Criteria

**Functional**:
- ✅ Local and remote backtesting work
- ✅ Progress tracking via OperationsService
- ✅ Cancellation support
- ✅ Error handling robust

**Technical**:
- ✅ Follows training's pattern exactly
- ✅ Reuses OperationsService, OperationServiceProxy
- ✅ 90%+ test coverage
- ✅ No performance regression vs Phase 0 baseline

**Testing** (MOST CRITICAL):
- ✅ **17 scenarios executed with integration-test-specialist**
- ✅ **100% pass rate (17/17 PASS)** - NO EXCEPTIONS
- ✅ **Continuous validation** (scenarios re-run after each phase)
- ✅ **All scenarios documented with actual results**

**Scenario Pass Requirement**:
```
Phase 1: Scenarios designed (17)
Phase 2: 8/17 scenarios PASS (Backend + Integration)
Phase 3: 12/17 scenarios PASS (+ Remote)
Phase 4: 17/17 scenarios PASS (+ Error Handling)
```

**Zero Tolerance for Scenario Failures**:
- Cannot proceed to next phase with failing scenarios
- Cannot mark scenarios as "known issues" or "will fix later"
- Cannot skip scenario execution
- All failures must be resolved (code fix or justified scenario update)

---

## Appendix A: Key Architectural Decisions

| Decision | Rationale | Impact |
|----------|-----------|--------|
| **Reuse OperationsService** | Already proven in training | 1 small fix needed (DONE) |
| **Reuse OperationServiceProxy** | Already generic | Zero changes |
| **Use ProgressBridge** | Same as training | Fast writes, no async issues |
| **Client-driven pull** | Current architecture | No polling, simple |
| **ENV-based mode** | Same as training | Consistent, simple |
| **Test models first** | Scenarios need models | Prevents Phase 2 blockers |
| **integration-test-specialist** | Consistent validation | Reproducible results |
| **100% scenario pass rate** | Quality gate | Ensures production readiness |

## Appendix B: Code Estimates

| Component | Lines of Code | Complexity | Scenarios to Validate |
|-----------|--------------|------------|---------------------|
| **Engine hooks** | +50 | Low | B1.2, B1.3 |
| **BacktestProgressBridge** | ~100 | Low | B1.1, B1.2 |
| **BacktestingService** | ~300 | Medium | B2.1, B2.2, B2.3 |
| **Remote API** | ~150 | Low | B3.1 |
| **API endpoints** | ~150 | Low | B2.1-B2.4 |
| **CLI commands** | ~200 | Low | Manual validation |
| **Total New** | ~950 | Medium | 17 scenarios |

## Appendix C: Scenario Summary

| Phase | Scenario IDs | Count | Pass Required |
|-------|-------------|-------|---------------|
| **Phase 1** | B1.1-B1.4, B2.1-B2.4, B3.1-B3.4, B4.1-B4.5 | 17 | Design only |
| **Phase 2** | B1.1-B1.4, B2.1-B2.4 | 8 | 8/8 (100%) |
| **Phase 3** | B1.1-B1.4, B2.1-B2.4, B3.1-B3.4 | 12 | 12/12 (100%) |
| **Phase 4** | ALL (B1-B4) | 17 | 17/17 (100%) |

---

**Document Version**: 3.1 (Testing-First with Model Foundation)
**Last Updated**: 2025-01-04
**Status**: READY FOR IMPLEMENTATION
