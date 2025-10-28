# Implementation Plan: Data Architecture Separation

## Document Information

- **Date**: 2025-01-27
- **Status**: PROPOSED
- **Timeline**: 3-5 weeks
- **Related Documents**:
  - [Design](./01-design-data-separation.md) - WHY (solution approach)
  - [Architecture](./02-architecture-data-separation.md) - WHAT (structure)
  - **This Document** - DETAILED WHAT + WHEN + ACCEPTANCE CRITERIA

---

## Executive Summary

This plan sequences the work required to separate KTRDR's data management into two focused components: **DataRepository** (local cache CRUD) and **DataAcquisitionService** (external IB download), eliminating the current conflation of concerns in DataManager.

**Sequencing Strategy**: IB Migration → Component Creation → Cleanup

- **Phase 1**: Move IB code to host service where it can execute
- **Phase 2**: Create new Repository and Acquisition components
- **Phase 3**: Delete old monolithic DataManager

**Critical Path**: P1 → P2 → P3 (sequential)

---

## Table of Contents

1. [Milestone Overview](#milestone-overview)
2. [Phase 1: Move IB to Host Service](#phase-1-move-ib-to-host-service)
3. [Phase 2: Create Repository & Acquisition](#phase-2-create-repository--acquisition)
4. [Phase 3: Cleanup](#phase-3-cleanup)
5. [Dependencies & Risks](#dependencies--risks)

---

## Milestone Overview

| Phase | Duration | Deliverable | Blocked By | Risk |
|-------|----------|-------------|------------|------|
| **P0: Baseline Testing** | 1-2 days | All data tests pass, baseline established | None | Low |
| P1: IB Migration | 1 week | IB code in host service, backend no IB imports | P0 | Medium |
| P2: Component Creation | 2-3 weeks | Repository + Acquisition working, both systems coexist | P1 | High |
| P3: Cleanup | 3-5 days | Old code deleted, clean architecture | P2 | Low |

**Total**: 19-29 days (3.8-5.8 weeks)

**Critical**: Phase 0 must complete successfully before starting Phase 1. Each phase includes exit testing to validate no regressions.

---

## Phase 0: Baseline Testing & Test Infrastructure (1-2 days)

### Goal

Establish baseline test suite for data operations, validate current system works correctly, and create testing infrastructure for validating each phase.

### Branch Strategy

**Create feature branch**:
```bash
git checkout -b feature/data-architecture-separation
git push -u origin feature/data-architecture-separation
```

**All work for Phases 0-3 happens on this branch**. Merge to main only after Phase 3 complete and all tests pass.

### Context

**Why Phase 0**:
- Validate current data loading works before refactoring
- Establish performance baselines (cache load < 1s, IB download timing)
- Create repeatable test scenarios for regression testing
- Document known issues and quirks before changes
- Ensure test infrastructure is ready for integration-test-specialist agent

**What Gets Tested**:
1. **Backend Cache Operations** (fast): Load, range query, validation
2. **IB Host Service** (slow): Health, direct download, symbol validation
3. **Integration** (slow): Backend → IB download, progress tracking, cache save
4. **Error Handling**: Invalid symbols, service unavailable, gateway disconnected

**Success Criteria**:
- All 13 data scenarios pass (or document failures as known issues)
- Performance baselines recorded
- Test execution via integration-test-specialist works
- Ready to detect regressions in Phases 1-3

### Tasks

#### TASK 0.1: Update Testing Documentation

**Objective**: Add data testing building blocks and scenarios.

**Scope**:
- Update `docs/testing/TESTING_GUIDE.md` with data endpoints, commands, log strings
- Update `docs/testing/SCENARIOS.md` with 13 data test scenarios
- Document expected performance (cache < 1s, IB download varies)
- Add quick reference commands for data operations

**Files Modified**:
- `docs/testing/TESTING_GUIDE.md`
- `docs/testing/SCENARIOS.md`

**Acceptance Criteria**:
- [ ] TESTING_GUIDE.md has data sections (endpoints, health checks, test data)
- [ ] SCENARIOS.md has 13 data scenarios (D1.1-D1.4, D2.1-D2.3, D3.1-D3.3, D4.1-D4.3)
- [ ] Each scenario has: Purpose, Prerequisites, Commands, Expected Results
- [ ] Quick reference commands documented
- [ ] Code review approved

**Status**: ✅ COMPLETED

---

#### TASK 0.2: Verify Prerequisites

**Objective**: Ensure all services and data files needed for testing are available.

**Scope**:
- Check backend running (port 8000)
- Check IB host service running (port 5001)
- Check IB Gateway connected
- Verify EURUSD data files exist (1d, 1h, 5m)
- Document any missing prerequisites

**Commands**:
```bash
# Backend health
curl -s http://localhost:8000/health | jq '{status:.status}'

# IB host health
curl -s http://localhost:5001/health | jq '{status:.status, ib_connected:.ib_connected}'

# Check data files
ls -lh data/EURUSD_*.pkl data/EURUSD_*.csv 2>/dev/null
```

**Acceptance Criteria**:
- [x] Backend running and healthy
- [x] IB host service running
- [x] IB Gateway connection status documented (connected or not)
- [x] EURUSD data availability documented
- [x] Missing prerequisites documented for user action

**Status**: ✅ COMPLETED (2025-10-28)

---

#### TASK 0.3: Run & Fix Backend Cache Tests (D1.1-D1.4)

**Objective**: Get cache operation tests working and document actual behavior.

**Scope**:
- **Run manually** by main coding agent (not sub-agent yet!)
- Execute scenarios D1.1-D1.4 (Backend Isolated category)
- Fix any issues discovered (wrong endpoints, parameters, etc.)
- Update TESTING_GUIDE.md and SCENARIOS.md based on learnings
- Iterate until tests pass consistently
- Record actual results and performance

**Scenarios**:
- **D1.1**: Load EURUSD 1h from cache (expect < 1s)
- **D1.2**: Range query (expect < 100ms)
- **D1.3**: Data validation (expect no errors)
- **D1.4**: List available data (expect EURUSD listed)

**Iterative Process**:
1. Run D1.1 commands manually
2. If fails: Debug, fix commands, update SCENARIOS.md
3. If passes: Document actual results, record timing
4. Repeat for D1.2, D1.3, D1.4
5. Update TESTING_GUIDE.md if common patterns discovered

**Acceptance Criteria**:
- [x] All 4 scenarios executed manually
- [x] Commands corrected and working
- [x] TESTING_GUIDE.md updated if needed
- [x] SCENARIOS.md updated with actual results
- [x] Performance baselines recorded
- [x] Tests pass consistently (can run twice in a row)

**Status**: ✅ COMPLETED (2025-10-28)

**Results Summary**:

- D1.1: Load EURUSD 1h - 115,147 bars in 2.082s ✅
- D1.2: Range query - 29ms (excellent) ✅
- D1.3: Data validation - Auto-validates, 6 minor issues ✅
- D1.4: List available - 32 symbols listed ✅

**Documentation Updates Made**:

- Fixed TESTING_GUIDE.md response formats (data structure: object with arrays, not array of objects)
- Fixed TESTING_GUIDE.md range query response (point_count not row_count, no file_exists field)
- Updated quick reference commands to use correct jq paths (.data.dates | length)
- Updated available data section with actual CSV formats and bar counts
- Fixed SCENARIOS.md expected results to match actual API behavior
- All format discrepancies corrected - docs now match reality

---

#### TASK 0.4: Run & Fix IB Host Service Tests (D2.1-D2.3)

**Objective**: Get IB host service tests working and document actual behavior.

**Scope**:
- **Run manually** by main coding agent (not sub-agent yet!)
- Execute scenarios D2.1-D2.3 (IB Host Service Isolated category)
- Fix any issues discovered (wrong host service endpoints, response formats, etc.)
- Update TESTING_GUIDE.md and SCENARIOS.md based on learnings
- Iterate until tests pass consistently
- Record IB Gateway connection status and download performance

**Scenarios**:
- **D2.1**: Health check (expect `ib_connected: true` if Gateway running)
- **D2.2**: Direct download (~720 bars, expect 30-90s)
- **D2.3**: Symbol validation (EURUSD valid, AAPL valid, INVALID123 invalid)

**Iterative Process**:
1. Check IB host service running: `curl http://localhost:5001/health`
2. If not running: Document as blocker, skip D2.2-D2.3
3. If running: Execute D2.1, fix any endpoint/format issues
4. If IB Gateway connected: Execute D2.2, D2.3, fix issues
5. Update documentation with actual endpoint paths and response formats

**Acceptance Criteria**:
- [ ] D2.1 executed manually (pass or documented why not)
- [ ] IB Gateway status documented
- [ ] If IB connected: D2.2, D2.3 executed and working
- [ ] Commands corrected and working
- [ ] TESTING_GUIDE.md updated if endpoint paths wrong
- [ ] SCENARIOS.md updated with actual results
- [ ] Download timing baseline recorded (if applicable)

---

#### TASK 0.5: Run & Fix Integration Tests (D3.1-D3.3)

**Objective**: Get end-to-end download tests working through backend API.

**Scope**:
- **Run manually** by main coding agent (not sub-agent yet!)
- Execute scenarios D3.1-D3.3 (Integration category)
- Fix any issues discovered (wrong backend endpoints, operation tracking, etc.)
- Update TESTING_GUIDE.md and SCENARIOS.md based on learnings
- Iterate until tests pass consistently
- Validate progress tracking and cache save

**Scenarios**:
- **D3.1**: Small download (AAPL 1d 2024, ~250 bars, 10-30s)
- **D3.2**: Progress monitoring (EURUSD 1h Dec 2024, ~720 bars, 30-90s)
- **D3.3**: Completion & cache save (verify file saved after download)

**Iterative Process**:
1. Check prerequisites: Backend running, IB host running, IB Gateway connected
2. If prerequisites not met: Document blockers, skip scenarios
3. If prerequisites met: Execute D3.1 (small download)
   - Fix endpoint issues (POST /data/load vs correct endpoint)
   - Fix operation ID extraction issues
   - Fix progress polling issues
   - Verify cache file created
4. Execute D3.2 (progress monitoring) - validate progress updates work
5. Execute D3.3 (cache verification) - ensure workflow complete
6. Update documentation with actual response formats, timing

**Acceptance Criteria**:
- [ ] Prerequisites status documented
- [ ] If IB connected: All 3 scenarios executed and working
- [ ] If IB not connected: Scenarios skipped with clear note
- [ ] Commands corrected (endpoint paths, operation ID extraction, etc.)
- [ ] TESTING_GUIDE.md updated if response formats wrong
- [ ] SCENARIOS.md updated with actual results
- [ ] Progress tracking verified (0% → 100%)
- [ ] Cache files verified after download
- [ ] Download timing baselines recorded

---

#### TASK 0.6: Run & Fix Error Handling Tests (D4.1-D4.3)

**Objective**: Get error handling tests working and document actual error behavior.

**Scope**:
- **Run manually** by main coding agent (not sub-agent yet!)
- Execute scenarios D4.1-D4.3 (Error Handling category)
- Fix any issues discovered (error scenarios may behave differently than expected)
- Update TESTING_GUIDE.md and SCENARIOS.md based on actual error messages
- Document what actually happens (may differ from expectations)
- Iterate until error scenarios are understood and documented

**Scenarios**:
- **D4.1**: Invalid symbol (expect 400 or operation fails gracefully)
- **D4.2**: IB service not running (expect clear error message)
- **D4.3**: IB Gateway disconnected (expect clear error message)

**Iterative Process**:
1. Execute D4.1 (invalid symbol)
   - Document actual HTTP status and error message
   - If raw exception: Note as issue for future fix (not blocking)
   - Update SCENARIOS.md with actual behavior
2. Execute D4.2 (IB service down)
   - Stop IB host service temporarily
   - Run test, document actual error
   - Restart IB host service
3. Execute D4.3 (IB Gateway disconnected)
   - Document how to test (requires IB Gateway logout)
   - May skip if can't easily test
   - Document expected behavior based on code inspection
4. Update TESTING_GUIDE.md with actual error strings

**Acceptance Criteria**:
- [ ] All 3 scenarios executed (or documented why skipped)
- [ ] Actual error messages documented (even if not ideal)
- [ ] TESTING_GUIDE.md updated with actual error strings
- [ ] SCENARIOS.md updated with actual results
- [ ] Known issues documented (if errors not user-friendly)
- [ ] Error handling behavior understood

---

#### TASK 0.7: Document Baseline Results

**Objective**: Compile all test results into baseline documentation.

**Scope**:
- Update SCENARIOS.md with actual results for all 13 scenarios
- Record performance baselines
- Document known issues/limitations
- Create summary of baseline state

**Baseline Metrics**:
```
Cache Operations:
- Load EURUSD 1h (~115K bars): [X] seconds
- Range query: [X] ms
- Data validation: [X] seconds

IB Downloads (if connected):
- Direct download (720 bars): [X] seconds
- Backend download (250 bars): [X] seconds
- Backend download (720 bars): [X] seconds

Error Handling:
- Invalid symbol: [error message]
- Service unavailable: [error message]
- Gateway disconnected: [error message]
```

**Acceptance Criteria**:
- [ ] All 13 scenarios have actual results documented
- [ ] Performance baselines recorded
- [ ] Known issues documented
- [ ] Summary statistics updated in SCENARIOS.md
- [ ] Baseline commit created: `git commit -m "Phase 0: Data testing baseline established"`

#### TASK 0.8: Validate with integration-test-specialist Sub-Agent

**Objective**: Confirm tests work when run by sub-agent (final validation).

**Scope**:
- **Only after Tasks 0.3-0.7 complete!**
- Run all passing scenarios via integration-test-specialist agent
- Verify agent can execute tests successfully
- Fix any issues with test commands for agent execution
- Validate test infrastructure ready for Phase 1/2/3 regression testing

**Scenarios to Run**:
- All scenarios that passed in Tasks 0.3-0.6
- Skip scenarios that were documented as blocked

**Process**:
1. Create test execution request for integration-test-specialist
2. Agent executes all passing scenarios
3. Compare agent results with manual results
4. Fix any discrepancies (command formatting, etc.)
5. Re-run until agent results match manual results
6. Document that sub-agent testing validated

**Acceptance Criteria**:
- [ ] integration-test-specialist successfully executes all passing scenarios
- [ ] Agent results match manual results from Tasks 0.3-0.6
- [ ] Any command formatting issues fixed
- [ ] Test infrastructure validated for future regression testing
- [ ] Confirmed ready for Phase 1/2/3 exit testing

---

### Phase 0 Exit Criteria

**Documentation** (Must be current with reality):
- [ ] TESTING_GUIDE.md updated with data building blocks
- [ ] TESTING_GUIDE.md reflects actual endpoints, response formats, error strings
- [ ] SCENARIOS.md has all 13 data scenarios defined
- [ ] SCENARIOS.md updated with actual results from manual execution
- [ ] All deviations from expected behavior documented

**Test Execution** (Manual first, then sub-agent):
- [ ] Backend cache tests (D1.1-D1.4): Manually executed, results documented
- [ ] IB host tests (D2.1-D2.3): Manually executed, results documented
- [ ] Integration tests (D3.1-D3.3): Manually executed, results documented
- [ ] Error handling (D4.1-D4.3): Manually executed, results documented
- [ ] Sub-agent validation (Task 0.8): integration-test-specialist can run tests

**Performance Baselines**:
- [ ] Cache load time recorded (actual, not estimated)
- [ ] IB download time recorded (if IB available, actual timing)
- [ ] Range query time recorded (actual)

**Infrastructure**:
- [ ] Tests work when run manually (Tasks 0.3-0.6)
- [ ] Tests work when run by integration-test-specialist (Task 0.8)
- [ ] Test commands are repeatable
- [ ] Prerequisites documented and validated

**Quality Gates**:
- [ ] No blockers for Phase 1 start
- [ ] Known issues documented (including non-ideal error messages)
- [ ] Baseline commit created: `git commit -m "Phase 0: Data testing baseline - all scenarios validated"`
- [ ] Ready to detect regressions in future phases

**Known Limitations Acceptable**:
- IB Gateway not connected → IB tests skipped (user must fix before Phase 1)
- Missing data files → Download tests may fail (expected for fresh setup)
- IB download timing varies → Document range, not exact value
- Error messages not ideal → Document actual messages, note for future improvement
- Some scenarios may not work perfectly → Document as known issues

---

## Phase 1: Move IB to Host Service (1 week)

### Goal

Move all IB Gateway connection code from `ktrdr/ib/` to `ib-host-service/ib/`, enabling backend to never import IB code and establishing clean location boundaries.

### Context

**Current Problem**:
- `ktrdr/ib/` contains IB Gateway connection code
- Backend (Docker) can't connect to IB Gateway (networking limitations)
- Host service imports from `ktrdr.ib` (path manipulation)

**Solution**:
- Move IB code to `ib-host-service/ib/` (local to host service)
- Backend never imports IB code (HTTP-only via IbDataProvider in Phase 2)
- Host service imports local `ib/` package

**Why This First**:
- Establishes import boundaries before building new components
- Proves host service can be self-contained
- Removes unused IB code from backend

### Tasks

#### TASK 1.1: Create Host Service IB Directory Structure

**Objective**: Set up directory structure for IB code in host service.

**Scope**:
- Create `ib-host-service/ib/` directory
- Create `ib-host-service/ib/__init__.py`
- Keep `ib-host-service/main.py` sys.path manipulation for now (access ktrdr shared code)

**Files Created**:
- `ib-host-service/ib/__init__.py`

**Acceptance Criteria**:
- [ ] `ib-host-service/ib/` directory exists
- [ ] Empty `__init__.py` created
- [ ] Directory structure ready for file moves

---

#### TASK 1.2: Move IB Files to Host Service (Batch 1: Core)

**Objective**: Move core IB connection files.

**Scope**:
- Move 3 core files:
  - `ktrdr/ib/connection.py` → `ib-host-service/ib/connection.py`
  - `ktrdr/ib/pool.py` → `ib-host-service/ib/pool.py`
  - `ktrdr/ib/error_classifier.py` → `ib-host-service/ib/error_classifier.py`
- Update imports in moved files:
  - `from ktrdr.ib.X` → `from ib.X` (local imports)
  - `from ktrdr.logging` → keep (shared dependency)
  - `from ktrdr.config` → keep (shared dependency)

**Import Pattern**:
```python
# Before (in ktrdr/ib/connection.py)
from ktrdr.ib.error_classifier import IbErrorClassifier
from ktrdr.logging import get_logger

# After (in ib-host-service/ib/connection.py)
from ib.error_classifier import IbErrorClassifier  # Local import
from ktrdr.logging import get_logger  # Shared import (via sys.path)
```

**Acceptance Criteria**:
- [ ] Files moved to `ib-host-service/ib/`
- [ ] Imports updated (`from ktrdr.ib.X` → `from ib.X`)
- [ ] Shared imports unchanged (`from ktrdr.logging`, etc.)
- [ ] Host service starts without import errors
- [ ] Original files still in `ktrdr/ib/` (copy, not move - for safety)

---

#### TASK 1.3: Move IB Files to Host Service (Batch 2: Fetching)

**Objective**: Move data fetching and validation files.

**Scope**:
- Move 3 files:
  - `ktrdr/ib/data_fetcher.py` → `ib-host-service/ib/data_fetcher.py`
  - `ktrdr/ib/symbol_validator.py` → `ib-host-service/ib/symbol_validator.py`
  - `ktrdr/ib/trading_hours_parser.py` → `ib-host-service/ib/trading_hours_parser.py`
- Update imports in moved files (same pattern as 1.2)

**Acceptance Criteria**:
- [ ] Files moved to `ib-host-service/ib/`
- [ ] Imports updated
- [ ] Host service can import and use these modules
- [ ] No import errors

---

#### TASK 1.4: Move IB Files to Host Service (Batch 3: Management)

**Objective**: Move pool management and rate limiting files.

**Scope**:
- Move 3 files:
  - `ktrdr/ib/pool_manager.py` → `ib-host-service/ib/pool_manager.py`
  - `ktrdr/ib/pace_manager.py` → `ib-host-service/ib/pace_manager.py`
  - `ktrdr/ib/gap_filler.py` → Will move to `ktrdr/data/acquisition/` in Phase 2 (skip for now)
- Update imports in moved files

**Acceptance Criteria**:
- [ ] Files moved to `ib-host-service/ib/`
- [ ] Imports updated
- [ ] Host service can import and use these modules

---

#### TASK 1.5: Update Host Service Endpoints to Use Local IB Code

**Objective**: Update host service endpoints to import from local `ib/` package.

**Scope**:
- Update `ib-host-service/endpoints/data.py`:
  - `from ktrdr.ib import IbDataFetcher` → `from ib import IbDataFetcher`
  - `from ktrdr.ib import IbSymbolValidator` → `from ib import IbSymbolValidator`
- Update any other host service files importing IB code

**Files Modified**:
- `ib-host-service/endpoints/data.py`
- `ib-host-service/endpoints/health.py` (if imports IB code)

**Acceptance Criteria**:
- [ ] All host service imports updated to `from ib import ...`
- [ ] Host service starts successfully
- [ ] Host service endpoints respond correctly
- [ ] Integration test: Call `/data/historical` endpoint, verify works

---

#### TASK 1.6: Delete ktrdr/ib/ Directory (After Verification)

**Objective**: Remove now-unused IB code from backend codebase.

**Scope**:
- **ONLY after Tasks 1.1-1.5 complete and verified**
- Delete entire `ktrdr/ib/` directory
- Verify backend doesn't import from `ktrdr/ib` anywhere

**Verification Steps**:
```bash
# Search for IB imports in backend
grep -r "from ktrdr.ib" ktrdr/
grep -r "import ktrdr.ib" ktrdr/

# Should find ZERO results (except maybe in old tests)
```

**Files Deleted**:
- `ktrdr/ib/` directory (entire)

**Acceptance Criteria**:
- [ ] `ktrdr/ib/` directory deleted
- [ ] No imports from `ktrdr/ib` in backend code (verified via grep)
- [ ] Backend Docker image rebuilt (will fail if IB imports remain)
- [ ] Backend starts successfully (in Docker)
- [ ] Host service still works
- [ ] IB operations still functional via host service

---

#### TASK 1.7: Rebuild Backend Docker & Validate

**Objective**: Ensure backend works without ktrdr/ib/ code.

**Scope**:
- Rebuild backend Docker image (critical: will fail if IB imports remain)
- Start backend container
- Verify no import errors during startup
- Run basic health checks

**Commands**:
```bash
# Rebuild backend Docker image
docker-compose -f docker/docker-compose.yml build backend

# Restart backend
docker-compose -f docker/docker-compose.yml restart backend

# Check logs for import errors
docker-compose -f docker/docker-compose.yml logs backend --since 30s | grep -i "importerror\|modulenotfounderror"
# Should be empty

# Health check
curl -s http://localhost:8000/health | jq
```

**Acceptance Criteria**:
- [ ] Docker build succeeds (no import errors during build)
- [ ] Backend container starts successfully
- [ ] No import errors in logs
- [ ] Health endpoint responds
- [ ] Backend can serve requests

---

#### TASK 1.8: Run Phase 1 End-to-End Tests

**Objective**: Validate data operations still work after IB code moved.

**Scope**:
- Re-run subset of Phase 0 scenarios to detect regressions
- Focus on scenarios that passed in Phase 0
- Use integration-test-specialist agent if Task 0.8 succeeded
- Document any regressions

**Scenarios to Re-Run**:
- **D1.1-D1.4**: Backend cache tests (must still pass)
- **D2.1**: IB host health check (must still pass)
- **D2.2 or D2.3**: One IB host download test (if IB available)
- **D3.1**: Integration test (backend → IB host, if IB available)

**Acceptance Criteria**:
- [ ] Cache tests (D1.1-D1.4) still pass (no regression)
- [ ] IB host service still healthy (D2.1)
- [ ] If IB available: At least one download test passes (D2.2 or D3.1)
- [ ] No regressions from Phase 0 baseline
- [ ] Results documented in SCENARIOS.md

**If Regressions Found**:
- Debug and fix before proceeding
- Update code or tests as needed
- Re-run until tests pass

---

### Phase 1 Exit Criteria

**Code Location**:
- [ ] IB code lives in `ib-host-service/ib/` (8 files)
- [ ] `ktrdr/ib/` directory deleted
- [ ] Host service imports from local `ib/` package

**Import Rules**:
- [ ] Backend has ZERO imports from `ktrdr/ib`
- [ ] Host service imports from `ib/` (local)
- [ ] Shared dependencies still work (logging, config, trading_hours)

**Backend Rebuild**:
- [ ] Backend Docker image rebuilt successfully (Task 1.7)
- [ ] No import errors during build or startup
- [ ] Backend runs without IB code

**Functionality**:
- [ ] Host service starts successfully
- [ ] Host service endpoints respond (`/data/historical`, `/data/validate`, etc.)
- [ ] Backend health check passes

**End-to-End Testing** (Task 1.8):
- [ ] Cache tests pass (D1.1-D1.4)
- [ ] IB host health check passes (D2.1)
- [ ] At least one IB download test passes (if IB available)
- [ ] No regressions from Phase 0

**Quality Gates**:
- [ ] All Phase 1 tests passing
- [ ] Host service health check passes
- [ ] Backend Docker builds and runs
- [ ] Code review approved
- [ ] Commit: `git commit -m "Phase 1: IB code moved to host service - tests pass"`

---

## Phase 2: Create Repository & Acquisition (2-3 weeks)

### Goal

Create **DataRepository** (local cache) and **DataAcquisitionService** (external download), extracting from DataManager while maintaining backwards compatibility.

### Context

**Current**: DataManager handles both cache and IB download in one class

**New**: Separate concerns into two focused components

**Why Now**: Phase 1 established clean IB location, now we can build new components without IB import issues

**Strategy**:
- Build new components alongside old DataManager
- Both systems coexist (no breaking changes)
- Gradually migrate internal code to use new components
- Delete old only in Phase 3

### Tasks

#### TASK 2.1: Create DataRepository (Extract from DataManager)

**Objective**: Create standalone DataRepository for local cache operations.

**Scope**:
- Extract sync cache methods from DataManager:
  - `load()` → `load_from_cache()`
  - `get_data_summary()` → `get_summary()`
  - `repair_data()` → `repair_data()`
  - `merge_data()` → `merge_data()`
  - Cache-related helper methods
- Remove all IB, Operations, async dependencies
- Use LocalDataLoader (stays in `ktrdr/data/`)
- Move DataQualityValidator from `components/` to `repository/`

**Files Created**:
- `ktrdr/data/repository/__init__.py`
- `ktrdr/data/repository/data_repository.py`

**Files Moved**:
- `ktrdr/data/components/data_quality_validator.py` → `ktrdr/data/repository/data_quality_validator.py`

**Implementation** (key methods):
```python
class DataRepository:
    """Local cache repository. Sync operations only."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.getenv("DATA_DIR", "./data")
        self.loader = LocalDataLoader(self.data_dir)
        self.validator = DataQualityValidator()

    def load_from_cache(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Load data from local cache. Sync, fast."""
        # Implementation from DataManager.load()
        # NO IB code, NO async, NO Operations

    def save_to_cache(
        self,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> None:
        """Save data to local cache."""
        # Validate, then save via loader

    def get_data_range(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict:
        """Get date range for cached data."""
        # Implementation from DataManager

    # ... other methods
```

**Acceptance Criteria**:
- [ ] DataRepository class created in `repository/data_repository.py`
- [ ] All methods are synchronous (no async/await)
- [ ] No imports from `ktrdr/ib` (would fail now, since deleted)
- [ ] No imports from Operations service
- [ ] No imports from async_infrastructure (except generic utilities if needed)
- [ ] Uses LocalDataLoader (stays in `ktrdr/data/`)
- [ ] Uses DataQualityValidator (moved to `repository/`)
- [ ] Unit tests: `test_load_from_cache()`, `test_save_to_cache()`, etc.
- [ ] Unit tests: Mock LocalDataLoader for fast tests
- [ ] Integration tests: Real file I/O with temp directory
- [ ] Performance: `load_from_cache()` < 100ms for typical dataset
- [ ] Code review approved

---

#### TASK 2.2: Create DataAcquisitionService (Extract from DataManager)

**Objective**: Create async DataAcquisitionService for external data download.

**Scope**:
- Extract async IB methods from DataManager:
  - `load_data_async()` → `download_data()`
  - `_load_with_enhanced_orchestrator()` → internal method
  - Operations tracking logic
  - Progress management
- Inherit from ServiceOrchestrator
- Compose DataRepository (has-a, not is-a)
- Use IbDataProvider (will create in 2.3)
- Move orchestration components:
  - `data_loading_orchestrator.py` → `acquisition/`
  - `gap_analyzer.py` → `acquisition/`
  - `segment_manager.py` → `acquisition/`
  - `gap_filler.py` → `acquisition/` (from ktrdr/ib if not deleted yet)
  - `data_progress_renderer.py` → `acquisition/`
  - `external_data_interface.py` → `acquisition/`

**Files Created**:
- `ktrdr/data/acquisition/__init__.py`
- `ktrdr/data/acquisition/acquisition_service.py`

**Files Moved**:
- `ktrdr/data/data_loading_orchestrator.py` → `ktrdr/data/acquisition/data_loading_orchestrator.py`
- `ktrdr/data/components/gap_analyzer.py` → `ktrdr/data/acquisition/gap_analyzer.py`
- `ktrdr/data/components/segment_manager.py` → `ktrdr/data/acquisition/segment_manager.py`
- `ktrdr/ib/gap_filler.py` → `ktrdr/data/acquisition/gap_filler.py` (if still exists)
- `ktrdr/data/async_infrastructure/data_progress_renderer.py` → `ktrdr/data/acquisition/data_progress_renderer.py`
- `ktrdr/data/external_data_interface.py` → `ktrdr/data/acquisition/external_data_interface.py`

**Implementation** (key structure):
```python
class DataAcquisitionService(ServiceOrchestrator):
    """External data acquisition orchestrator. Async operations."""

    def __init__(self):
        super().__init__()  # ServiceOrchestrator features

        # Composition: has-a Repository
        self.repository = DataRepository()

        # External provider (to be created in 2.3)
        self.provider = IbDataProvider()

        # Gap analysis
        self.gap_analyzer = GapAnalyzer()
        self.segment_manager = SegmentManager()

        # Orchestrator
        self.orchestrator = DataLoadingOrchestrator(
            repository=self.repository,
            provider=self.provider,
        )

    async def download_data(
        self,
        symbol: str,
        timeframe: str,
        mode: str = "tail",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        progress_callback: Optional[Callable] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:  # Returns operation_id
        """
        Download data from external provider (IB).

        Flow:
        1. Create operation
        2. Check cache: self.repository.load_from_cache()
        3. Analyze gaps
        4. Download from provider
        5. Save: self.repository.save_to_cache()
        6. Complete operation
        """
        # Implementation from DataManager.load_data_async()
```

**Acceptance Criteria**:
- [ ] DataAcquisitionService created in `acquisition/acquisition_service.py`
- [ ] Inherits from ServiceOrchestrator
- [ ] Composes DataRepository (self.repository = DataRepository())
- [ ] All methods are async
- [ ] Uses Operations service for progress tracking
- [ ] Moved files have updated imports
- [ ] No circular dependencies (Repository doesn't import Acquisition)
- [ ] Unit tests: Mock Repository and Provider
- [ ] Integration tests: Real download with test IB data
- [ ] Code review approved

---

#### TASK 2.3: Refactor IbDataAdapter → IbDataProvider (HTTP-only)

**Objective**: Create HTTP-only IB provider, removing direct connection mode.

**Scope**:
- Copy `ktrdr/data/ib_data_adapter.py` → `ktrdr/data/acquisition/ib_data_provider.py`
- Remove direct connection mode:
  - Delete `use_host_service` parameter (always true now)
  - Remove IB Gateway connection code
  - Remove imports from `ktrdr/ib` (would fail, since deleted)
  - Keep only HTTP code
- Simplify: HTTP-only implementation
- Implement ExternalDataProvider interface (moved to acquisition/)

**Files Created**:
- `ktrdr/data/acquisition/ib_data_provider.py`

**Implementation Changes**:
```python
# Before (ib_data_adapter.py)
class IbDataAdapter:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 4002,
        use_host_service: bool = False,  # ← Parameter
        host_service_url: Optional[str] = None,
    ):
        self.use_host_service = use_host_service
        if use_host_service:
            # HTTP code
        else:
            # Direct IB connection code ← DELETE THIS
            from ktrdr.ib import IbDataFetcher  # ← Would fail

# After (ib_data_provider.py)
class IbDataProvider(ExternalDataProvider):
    def __init__(
        self,
        host_service_url: Optional[str] = None,
    ):
        # Always HTTP mode
        self.host_service_url = (
            host_service_url or
            os.getenv("IB_HOST_SERVICE_URL", "http://localhost:5001")
        )
        self.client = httpx.AsyncClient(timeout=300.0)
        # NO IB Gateway connection
        # NO direct imports from IB
```

**Acceptance Criteria**:
- [ ] IbDataProvider created in `acquisition/ib_data_provider.py`
- [ ] HTTP-only (no direct IB connection code)
- [ ] No imports from `ktrdr/ib` (would fail)
- [ ] Implements ExternalDataProvider interface
- [ ] All methods are async
- [ ] Unit tests: Mock HTTP responses (use respx)
- [ ] Integration tests: Real HTTP calls to host service
- [ ] Code review approved

---

#### TASK 2.4: Update DataLoadingOrchestrator to Use Repository

**Objective**: Update orchestrator to use DataRepository instead of DataManager.

**Scope**:
- Orchestrator currently references DataManager
- Change to use DataRepository for cache operations
- Change to use IbDataProvider for external operations

**Files Modified**:
- `ktrdr/data/acquisition/data_loading_orchestrator.py`

**Changes**:
```python
# Before
class DataLoadingOrchestrator:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def load_with_fallback(...):
        # Uses data_manager.load(), data_manager.save()

# After
class DataLoadingOrchestrator:
    def __init__(
        self,
        repository: DataRepository,
        provider: ExternalDataProvider,
    ):
        self.repository = repository
        self.provider = provider

    def load_with_fallback(...):
        # Uses repository.load_from_cache(), repository.save_to_cache()
        # Uses provider.fetch_historical_data()
```

**Acceptance Criteria**:
- [ ] Orchestrator accepts Repository and Provider (not DataManager)
- [ ] All cache operations use `repository.*`
- [ ] All external operations use `provider.*`
- [ ] Unit tests updated
- [ ] Code review approved

---

#### TASK 2.5: Create New API Endpoints (/data/acquire/*)

**Objective**: Create new explicit acquisition endpoints.

**Scope**:
- Create `ktrdr/api/endpoints/acquisition.py` (new file)
- Implement endpoints:
  - `POST /data/acquire/download` - Start download operation
  - `POST /data/acquire/validate-symbol` - Validate symbol with provider
  - `GET /data/acquire/provider-health` - Provider health check
- Use DataAcquisitionService (not DataManager)

**Files Created**:
- `ktrdr/api/endpoints/acquisition.py`

**Files Modified**:
- `ktrdr/api/main.py` (register new router)

**Implementation**:
```python
# acquisition.py
from fastapi import APIRouter, BackgroundTasks
from ktrdr.data.acquisition import DataAcquisitionService

router = APIRouter(prefix="/data/acquire", tags=["data-acquisition"])
acquisition_service = DataAcquisitionService()

@router.post("/download")
async def download_data(request: DownloadRequest):
    """Download data from external provider (IB)."""
    operation_id = await acquisition_service.download_data(
        symbol=request.symbol,
        timeframe=request.timeframe,
        mode=request.mode,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {
        "operation_id": operation_id,
        "status": "started",
        "message": f"Download started for {request.symbol} {request.timeframe}"
    }

@router.post("/validate-symbol")
async def validate_symbol(request: SymbolRequest):
    """Validate symbol with external provider."""
    result = await acquisition_service.validate_symbol(request.symbol)
    return result

@router.get("/provider-health")
async def provider_health():
    """Get provider health status."""
    health = await acquisition_service.health_check()
    return health
```

**Acceptance Criteria**:
- [ ] New endpoints created in `acquisition.py`
- [ ] Router registered in `main.py`
- [ ] Endpoints appear in Swagger docs
- [ ] Unit tests: Mock DataAcquisitionService
- [ ] Integration tests: Real calls to endpoints
- [ ] Code review approved

---

#### TASK 2.6: Update Existing API Endpoints to Use DataRepository

**Objective**: Update existing `/data/*` endpoints to use DataRepository.

**Scope**:
- Update `ktrdr/api/endpoints/data.py`:
  - `GET /data/{symbol}/{timeframe}` → Use DataRepository
  - `GET /data/info` → Use DataRepository
  - `GET /data/range` → Use DataRepository
  - `POST /data/load` → Add deprecation warning, route to `/data/acquire/download`

**Files Modified**:
- `ktrdr/api/endpoints/data.py`

**Changes**:
```python
# Before
from ktrdr.data.data_manager import DataManager
data_manager = DataManager()

@router.get("/data/{symbol}/{timeframe}")
async def get_data(symbol: str, timeframe: str):
    df = data_manager.load(symbol, timeframe)
    return ...

# After
from ktrdr.data.repository import DataRepository
from ktrdr.data.acquisition import DataAcquisitionService

data_repository = DataRepository()
data_acquisition = DataAcquisitionService()

@router.get("/data/{symbol}/{timeframe}")
async def get_data(symbol: str, timeframe: str):
    # Use Repository for cache
    df = data_repository.load_from_cache(symbol, timeframe)
    return ...

@router.post("/data/load")
async def load_data_deprecated(request: LoadRequest):
    # Deprecation warning
    logger.warning(
        "POST /data/load is deprecated. Use POST /data/acquire/download instead."
    )
    # Route to acquisition
    operation_id = await data_acquisition.download_data(...)
    return {
        "operation_id": operation_id,
        "status": "started",
        "deprecated": True,
        "use_instead": "/data/acquire/download"
    }
```

**Acceptance Criteria**:
- [ ] Existing endpoints use DataRepository
- [ ] `POST /data/load` deprecated but functional
- [ ] Deprecation warning in logs
- [ ] Deprecation flag in response
- [ ] Integration tests: All endpoints still work
- [ ] Code review approved

---

#### TASK 2.7: Create New CLI Commands (ktrdr data download)

**Objective**: Create explicit CLI command for data acquisition.

**Scope**:
- Create `ktrdr/cli/acquisition_commands.py` (new file)
- Implement commands:
  - `ktrdr data download` - Download data from IB
  - `ktrdr data validate` - Validate symbol
  - `ktrdr data provider-health` - Check provider health
- Use new `/data/acquire/*` endpoints
- Add deprecation warning to `ktrdr data load`

**Files Created**:
- `ktrdr/cli/acquisition_commands.py`

**Files Modified**:
- `ktrdr/cli/data_commands.py` (deprecation warning)

**Implementation**:
```python
# acquisition_commands.py
import typer
from ktrdr.cli.async_cli_client import AsyncCLIClient

app = typer.Typer(name="data")

@app.command("download")
def download_data(
    symbol: str,
    timeframe: str,
    mode: str = "tail",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Download data from external provider (IB)."""
    async def _download():
        async with AsyncCLIClient() as client:
            response = await client.post(
                "/data/acquire/download",
                json={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "mode": mode,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
            operation_id = response["operation_id"]
            # Show operation progress...

    asyncio.run(_download())
```

**Acceptance Criteria**:
- [ ] New commands created in `acquisition_commands.py`
- [ ] Commands registered in CLI
- [ ] `ktrdr data download` works
- [ ] `ktrdr data load` shows deprecation warning
- [ ] Integration tests: CLI commands work
- [ ] Code review approved

---

#### TASK 2.8: Update Internal Code to Use New Components

**Objective**: Update all internal code to use DataRepository and DataAcquisitionService.

**Scope**:
- Search for DataManager usage across codebase
- Update to use appropriate component:
  - Cache operations → DataRepository
  - Download operations → DataAcquisitionService
- Update imports

**Verification**:
```bash
# Find DataManager usage
grep -r "DataManager" ktrdr/ --exclude-dir=__pycache__

# After updates, should only find:
# - Tests for old DataManager (keeping for compatibility)
# - data_manager.py itself (will delete in Phase 3)
```

**Acceptance Criteria**:
- [ ] All service code uses new components
- [ ] All API endpoints use new components
- [ ] All CLI commands use new components
- [ ] Tests updated
- [ ] Code review approved

---

#### TASK 2.9: Run Phase 2 End-to-End Tests (COMPREHENSIVE)

**Objective**: **CRITICAL** - Validate ALL scenarios work with new architecture.

**Scope**:
- **This is the final validation before cleanup in Phase 3**
- Run ALL 13 data scenarios (D1.1-D4.3)
- ALL scenarios must pass (or have documented workarounds)
- Use both new and deprecated endpoints to ensure backwards compatibility
- Use integration-test-specialist agent for execution
- Document any issues that must be fixed before Phase 3

**Why Comprehensive**:
- Phase 3 deletes old code (DataManager, IbDataAdapter)
- If anything doesn't work, we can't go back
- This is the quality gate for the entire refactoring

**Scenarios - ALL Must Pass**:

**Backend Cache (D1.1-D1.4)**: Must pass using DataRepository
- [ ] D1.1: Load EURUSD 1h
- [ ] D1.2: Range query
- [ ] D1.3: Data validation
- [ ] D1.4: List available

**IB Host Service (D2.1-D2.3)**: Must pass (if IB available)
- [ ] D2.1: Health check
- [ ] D2.2: Direct download (if IB connected)
- [ ] D2.3: Symbol validation (if IB connected)

**Integration - NEW Endpoints (D3.1-D3.3)**: Must pass using `/data/acquire/download`
- [ ] D3.1: Small download via NEW endpoint
- [ ] D3.2: Progress monitoring via NEW endpoint
- [ ] D3.3: Completion & cache save via NEW endpoint

**Integration - DEPRECATED Endpoints (D3.1-D3.3)**: Must still work
- [ ] D3.1: Small download via OLD endpoint `/data/load` (backwards compat)
- [ ] D3.2: Progress monitoring via OLD endpoint
- [ ] D3.3: Completion & cache save via OLD endpoint

**Error Handling (D4.1-D4.3)**: Must pass
- [ ] D4.1: Invalid symbol
- [ ] D4.2: IB service not running
- [ ] D4.3: IB Gateway disconnected

**Acceptance Criteria**:
- [ ] ALL scenarios pass (or skipped with clear reason: IB not available)
- [ ] Both new AND deprecated endpoints work
- [ ] Performance meets baselines from Phase 0
- [ ] No regressions
- [ ] integration-test-specialist executes all tests successfully
- [ ] Results documented in SCENARIOS.md

**Blocking Issues**:
- If any critical scenario fails → Fix before Phase 3
- If performance regression → Investigate and fix
- If backwards compatibility broken → Fix before Phase 3

**Sign-Off Required**:
- [ ] User confirms: "All scenarios work, ready for Phase 3 cleanup"

---

### Phase 2 Exit Criteria

**Components Created**:
- [ ] DataRepository functional (sync, local cache)
- [ ] DataAcquisitionService functional (async, IB download)
- [ ] IbDataProvider functional (HTTP-only)

**Code Moves**:
- [ ] 6 files moved to `acquisition/`
- [ ] 1 file moved to `repository/`
- [ ] external_data_interface.py moved to `acquisition/`

**API Changes**:
- [ ] New endpoints: `/data/acquire/*` working
- [ ] Existing endpoints use DataRepository
- [ ] Deprecated endpoint: `POST /data/load` still works (backwards compat)

**CLI Changes**:
- [ ] New command: `ktrdr data download` working
- [ ] Deprecated command: `ktrdr data load` still works (with warning)

**Internal Code**:
- [ ] All internal code uses new components
- [ ] No new DataManager usage

**End-to-End Testing** (Task 2.9 - CRITICAL):
- [ ] ALL 13 scenarios tested
- [ ] ALL scenarios pass (or documented skip reason)
- [ ] Both new and deprecated endpoints work
- [ ] Performance meets baselines
- [ ] integration-test-specialist validation passed
- [ ] **User sign-off obtained**

**Quality Gates**:
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Performance: Repository operations < 100ms
- [ ] Performance: Acquisition operations tracked via Operations
- [ ] Code review approved for all tasks
- [ ] Commit: `git commit -m "Phase 2: Data architecture separated - all tests pass"`

**Critical**: Phase 3 cannot start until user confirms Phase 2 tests pass completely.

---

## Phase 3: Cleanup (3-5 days)

### Goal

Delete old DataManager and related files, remove deprecated endpoints/commands, finalize clean architecture.

### Context

**Phase 2 Result**: Both old and new systems work, all code uses new components

**Phase 3**: Delete old code after confirming nothing uses it

**Strategy**:
- Verify no usage of old components
- Delete old files
- Remove deprecated endpoints/commands
- Update documentation

### Tasks

#### TASK 3.1: Verify No Usage of Old Components

**Objective**: Confirm old DataManager not used before deletion.

**Scope**:
- Search for DataManager imports
- Search for ib_data_adapter imports
- Search for data_manager_builder imports
- If found, update to use new components (should be done in Phase 2)

**Verification**:
```bash
# Should find ZERO results (except in old tests and the files themselves)
grep -r "from ktrdr.data.data_manager import" ktrdr/ --exclude-dir=__pycache__
grep -r "from ktrdr.data.ib_data_adapter import" ktrdr/ --exclude-dir=__pycache__
grep -r "from ktrdr.data.data_manager_builder import" ktrdr/ --exclude-dir=__pycache__
```

**Acceptance Criteria**:
- [ ] No imports of DataManager (except in old tests)
- [ ] No imports of IbDataAdapter (except in old tests)
- [ ] No imports of DataManagerBuilder
- [ ] Ready for deletion

---

#### TASK 3.2: Delete Old Data Files

**Objective**: Remove old monolithic data management files.

**Scope**:
- Delete files:
  - `ktrdr/data/data_manager.py`
  - `ktrdr/data/ib_data_adapter.py`
  - `ktrdr/data/data_manager_builder.py`
- Delete empty directory:
  - `ktrdr/data/async_infrastructure/` (if empty after moving renderer)

**Files Deleted**:
- `ktrdr/data/data_manager.py`
- `ktrdr/data/ib_data_adapter.py`
- `ktrdr/data/data_manager_builder.py`
- `ktrdr/data/async_infrastructure/` (directory)

**Acceptance Criteria**:
- [ ] Files deleted
- [ ] Backend still starts successfully
- [ ] All tests still pass
- [ ] Code review approved

---

#### TASK 3.3: Remove Deprecated API Endpoint

**Objective**: Remove deprecated `POST /data/load` endpoint.

**Scope**:
- Remove `POST /data/load` from `data.py`
- Users must use `POST /data/acquire/download`

**Files Modified**:
- `ktrdr/api/endpoints/data.py`

**Acceptance Criteria**:
- [ ] Deprecated endpoint removed
- [ ] API docs updated
- [ ] Integration tests updated (expect 404 for old endpoint)
- [ ] Code review approved

---

#### TASK 3.4: Remove Deprecated CLI Command

**Objective**: Remove deprecated `ktrdr data load` command.

**Scope**:
- Remove `load` command from data_commands.py
- Users must use `ktrdr data download`

**Files Modified**:
- `ktrdr/cli/data_commands.py`

**Acceptance Criteria**:
- [ ] Deprecated command removed
- [ ] CLI help updated
- [ ] Code review approved

---

#### TASK 3.5: Update Documentation

**Objective**: Update CLAUDE.md and other docs with new architecture.

**Scope**:
- Update `CLAUDE.md`:
  - Add Data Architecture section
  - Document DataRepository and DataAcquisitionService
  - Document import rules (no IB imports in backend)
  - Document API changes
- Update `README.md` if needed
- Update API docs

**Files Modified**:
- `CLAUDE.md`
- `README.md` (if needed)

**Acceptance Criteria**:
- [ ] CLAUDE.md updated with data architecture
- [ ] Import rules documented
- [ ] API changes documented
- [ ] No broken links
- [ ] Code review approved

---

#### TASK 3.6: Run Phase 3 Final Validation Tests

**Objective**: Confirm cleanup didn't break anything.

**Scope**:
- Re-run critical scenarios from Phase 2
- Verify deprecated endpoints removed (should 404)
- Verify new endpoints still work
- Quick smoke test, not comprehensive (Phase 2 was comprehensive)

**Scenarios - Quick Validation**:
- **D1.1**: Cache load (via DataRepository)
- **D1.2**: Range query (via DataRepository)
- **D3.1**: Download via NEW endpoint `/data/acquire/download` (if IB available)
- **D4.2**: Error handling - deprecated endpoint returns 404

**Commands**:
```bash
# Test deprecated endpoint removed
curl -i -s -X POST http://localhost:8000/api/v1/data/load \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h","start_date":"2024-12-01","end_date":"2024-12-31"}'
# Expect: HTTP 404 Not Found

# Test new endpoint works
curl -s -X POST http://localhost:8000/api/v1/data/acquire/download \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h","mode":"tail","start_date":"2024-12-01","end_date":"2024-12-31"}' | jq
# Expect: operation_id returned
```

**Acceptance Criteria**:
- [ ] Cache operations work (D1.1, D1.2)
- [ ] New download endpoint works (D3.1 if IB available)
- [ ] Deprecated endpoints return 404 (as expected)
- [ ] No import errors
- [ ] Backend and host service healthy
- [ ] Results documented

---

### Phase 3 Exit Criteria

**Code Deleted**:
- [ ] DataManager deleted
- [ ] IbDataAdapter deleted
- [ ] DataManagerBuilder deleted
- [ ] Empty directories deleted

**API Cleanup**:
- [ ] Deprecated endpoints removed (404 response)
- [ ] Only new endpoints remain and work

**CLI Cleanup**:
- [ ] Deprecated commands removed
- [ ] Only new commands remain and work

**Documentation**:
- [ ] CLAUDE.md updated with new architecture
- [ ] README.md updated (if needed)
- [ ] API docs updated

**End-to-End Testing** (Task 3.6):
- [ ] Cache operations work (D1.1, D1.2)
- [ ] New endpoints work (D3.1)
- [ ] Deprecated endpoints properly removed (404)
- [ ] No regressions from Phase 2

**Quality Gates**:
- [ ] All tests passing
- [ ] Backend starts successfully
- [ ] Host service starts successfully
- [ ] Backend Docker builds successfully
- [ ] Code review approved
- [ ] Commit: `git commit -m "Phase 3: Cleanup complete - clean data architecture"`

**Success Indicators**:
- ✅ Clean separation: Repository (cache) vs Acquisition (IB)
- ✅ IB code in host service only
- ✅ Backend never imports IB code
- ✅ Clear import boundaries
- ✅ Old code removed
- ✅ All tests passing
- ✅ Clean architecture achieved

**Final Step**:
```bash
# Create PR for review
gh pr create --title "Data Architecture Separation" \
  --body "$(cat <<'EOF'
## Summary
- Phase 0: Baseline testing established (13 scenarios)
- Phase 1: IB code moved to host service
- Phase 2: DataRepository + DataAcquisitionService created
- Phase 3: Old code cleaned up

## Tests
- All 13 data scenarios passing
- Cache operations: <100ms
- Download operations: tracked via Operations
- Backwards compatibility maintained through Phase 2

## Breaking Changes
- Removed deprecated endpoints: POST /data/load
- Removed deprecated CLI: ktrdr data load
- Users must use: POST /data/acquire/download and ktrdr data download

EOF
)"
```

---

## Dependencies & Risks

### Critical Path

```
P1 (IB Migration) → P2 (Components) → P3 (Cleanup)
```

**No parallel work**: Each phase depends on previous completion.

### Dependencies

**P1 depends on**:
- None (starting point)

**P2 depends on**:
- P1 complete (IB code in host service, clean import boundaries)

**P3 depends on**:
- P2 complete (new components working, all code migrated)

### Risks

#### Risk 1: Import Issues After IB Move

**Impact**: High
**Probability**: Medium
**Mitigation**:
- Move files in batches (Tasks 1.2-1.4)
- Test after each batch
- Keep original files until verified
- Rollback plan: Restore ktrdr/ib/ if needed

---

#### Risk 2: DataManager Complexity

**Impact**: High (hard to extract)
**Probability**: Medium
**Mitigation**:
- Phase 2 takes longer (2-3 weeks budget)
- Task 2.1-2.2 are the critical ones
- Thorough code review
- Extensive testing

---

#### Risk 3: Breaking Changes

**Impact**: High (users disrupted)
**Probability**: Low
**Mitigation**:
- Phase 2 maintains backwards compatibility
- Deprecation warnings guide migration
- Only delete in Phase 3 after confirmation
- Rollback plan: Git revert Phase 3

---

#### Risk 4: Orchestrator Refactoring

**Impact**: Medium
**Probability**: Medium
**Mitigation**:
- Task 2.4 carefully updates orchestrator
- Keep same logic, just change dependencies
- Extensive integration tests
- Test with real IB data

---

#### Risk 5: Performance Regression

**Impact**: Medium
**Probability**: Low
**Mitigation**:
- Benchmark in Phase 2
- Repository should be FASTER (less overhead)
- Acquisition same speed (same logic)
- Rollback if performance degrades >10%

---

## Success Criteria

### Functional Success

- [ ] Local cache operations work via DataRepository
- [ ] IB downloads work via DataAcquisitionService
- [ ] Host service self-contained (local IB code)
- [ ] Backend never imports IB code
- [ ] Progress tracking works for downloads
- [ ] Backwards compatibility maintained (during Phase 2)

### Architectural Success

- [ ] Clean separation: Repository vs Acquisition
- [ ] Composition: Acquisition composes Repository
- [ ] IB code in host service only
- [ ] Import boundaries enforced
- [ ] Single responsibility per component

### Performance Success

- [ ] Repository operations < 100ms (no regression)
- [ ] Acquisition operations same speed as before
- [ ] HTTP overhead to host service < 5ms

### Operational Success

- [ ] All tests passing (100% pass rate)
- [ ] No regression in functionality
- [ ] Documentation updated
- [ ] Code review complete
- [ ] Clean git history (clear commit messages)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-27
**Next Review**: After Phase 1 completion
