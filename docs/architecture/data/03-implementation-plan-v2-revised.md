# Implementation Plan V2: Data Architecture Separation (Extraction-Focused)

## Document Information

- **Date**: 2025-01-29
- **Status**: PROPOSED - REVISED
- **Version**: 2.0 (Extraction-Focused Rewrite)
- **Supersedes**: Version 1.0 (Creation-Focused)
- **Starting Point**: Commit 79f98d6 (End of Phase 1)
- **Related Documents**:
  - [Design](./01-design-data-separation.md) - WHY (solution approach)
  - [Architecture](./02-architecture-data-separation.md) - WHAT (structure)
  - **This Document** - DETAILED WHAT + WHEN + ACCEPTANCE CRITERIA (REVISED)

---

## Executive Summary

### Why This Revision?

**Original Plan Problem**: Tasks tried to "create" components from scratch, forgetting battle-tested logic already exists in DataManager (~1500 LOC of working code).

**Result**: Task 2.2 became too big, LLM created `DEFERRED_WORK.md` as a red flag.

**Solution**: **EXTRACT** existing working code incrementally, not rewrite it.

### Key Changes from V1

| Aspect | V1 (Original) | V2 (Revised) |
|--------|--------------|--------------|
| **Approach** | "Create" components | "Extract" from DataManager |
| **Phase 2** | 12 tasks, 2-3 weeks | 6 tasks, 1 week |
| **Task Size** | Task 2.2 massive | All tasks atomic |
| **Risk** | High (rewriting) | Low (moving code) |
| **Deferred Work** | Required | Eliminated |

### New Phase Structure

| Phase | Duration | Deliverable | Tasks |
|-------|----------|-------------|-------|
| 0 | Done ✅ | Test baseline | 8 |
| 1 | Done ✅ | Host service ready | 5 |
| **2** | **1 week** | **Repository extracted** | **6** |
| **3** | **4-5 days** | **IB deleted, HTTP-only** | **7** |
| **4** | **1-2 weeks** | **Acquisition extracted** | **7** |
| **5** | **3-4 days** | **Clean architecture** | **6** |

**Total**: ~3-4 weeks (similar timeline, WAY less risk)

---

## Critical Principles for This Revision

### 1. Extract, Don't Create

```python
# ❌ WRONG (V1 approach):
class DataRepository:
    def load_from_cache(self):
        # Write from scratch
        # ... might forget edge cases

# ✅ RIGHT (V2 approach):
# FROM: LocalDataLoader.load() (existing, working)
# TO: DataRepository.load_from_cache() (extracted)
# Copy + refactor existing code
```

### 2. Each Task MUST Deliver Value

- Working end-to-end
- Passes integration tests
- All unit tests + quality checks pass
- Can ship to production if needed

### 3. No Giant Tasks

- If a task feels too big → split it
- Maximum ~2 days per task
- Prefer 0.5-1 day tasks

---

## Starting Point: Commit 79f98d6 (End of Phase 1)

### What Exists

**File Structure**:
```
ktrdr/data/
├── data_manager.py             # ALL logic here (~1500 LOC)
├── data_manager_builder.py     # Builder pattern
├── local_data_loader.py        # Local cache I/O
├── ib_data_adapter.py          # IB integration (imports ktrdr.ib)
├── data_loading_orchestrator.py
├── components/
│   ├── gap_classifier.py
│   ├── gap_analyzer.py         # Gap analysis logic
│   ├── segment_manager.py      # Segmentation logic
│   ├── data_health_checker.py
│   ├── data_processor.py
│   └── ... (other components)
└── (NO repository/ directory)
└── (NO acquisition/ directory)
```

**Key Points**:
- ✅ Phase 1 complete (host service ready)
- ❌ NO DataRepository yet
- ❌ NO DataAcquisitionService yet
- ❌ NO repository/ or acquisition/ directories
- ✅ DataManager has ALL working logic
- ✅ IbDataAdapter imports from `ktrdr.ib` (will be fixed Phase 3)

---

## Testing Guide

### Where Integration Tests Are Defined

**Integration test scenarios are fully documented in:**

1. **`docs/testing/SCENARIOS.md`** - Complete test scenario definitions
   - 13 data scenarios (D1.1-D4.3)
   - Training scenarios (1.1-4.2)
   - Step-by-step commands for each scenario
   - Expected results and performance baselines

2. **`docs/testing/TESTING_GUIDE.md`** - Building blocks for testing
   - API endpoint reference
   - Service URLs and ports
   - Common commands and scripts
   - Log access patterns

### How to Run Integration Tests

**For each task, run the relevant scenarios:**

```bash
# Example: Task 2.4 (Wire Repository to API)
# Run scenarios: D1.1, D1.2, D1.4

# D1.1: Load cached data
curl -s "http://localhost:8000/api/v1/data/EURUSD/1h" | jq '.data.dates | length'

# D1.2: Query data range
curl -s -X POST http://localhost:8000/api/v1/data/range \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}' | jq

# D1.4: List available data
curl -s "http://localhost:8000/api/v1/data/info" | jq '.data.total_symbols'
```

**Prerequisites for Integration Tests:**
- Backend running (`docker-compose up` or local API server)
- For IB tests: IB Host Service + IB Gateway running
- Sample data cached (EURUSD 1h recommended)

### Test Validation Requirements

Each task MUST pass:
1. ✅ All relevant integration test scenarios (see task acceptance criteria)
2. ✅ All unit tests (`make test-unit`)
3. ✅ Quality checks (`make quality`)

**Integration test scenarios are NOT optional** - they verify end-to-end functionality.

---

## Table of Contents

1. [Phase 0: Baseline Testing](#phase-0-baseline-testing) ✅
2. [Phase 1: IB Code Duplication](#phase-1-ib-code-duplication-host-service-preparation) ✅
3. [Phase 2: Repository Extraction](#phase-2-repository-extraction-cache-operations)
4. [Phase 3: IB Isolation](#phase-3-ib-isolation-http-only-provider)
5. [Phase 4: Acquisition Extraction](#phase-4-acquisition-extraction-download-logic)
6. [Phase 5: Cleanup & Documentation](#phase-5-cleanup--documentation)

---

## Phase 0: Baseline Testing ✅

**Status**: COMPLETE

**What Was Done**:
- ✅ Created 13 integration test scenarios (D1.1-D4.3)
- ✅ Documented in `docs/testing/SCENARIOS.md`
- ✅ Validated all scenarios manually
- ✅ Validated with integration-test-specialist agent
- ✅ Established performance baselines

**Exit Criteria**: All met ✅

---

## Phase 1: IB Code Duplication (Host Service Preparation) ✅

**Status**: COMPLETE (with expected caveats)

**What Was Done**:
- ✅ Copied IB code to `ib-host-service/ib/` (8 files)
- ✅ Host service imports from local `ib/` package
- ✅ Host service endpoints work
- ✅ Integration tests D2.1-D2.3 pass
- ✅ Bug fixed: IB duration format Error 321

**What Was NOT Done** (expected, not a failure):
- ❌ Backend still imports from `ktrdr/ib` (IbDataAdapter needs it)
- ❌ Original `ktrdr/ib/` not deleted (Phase 3 will handle)

**Exit Status**: Host service self-contained and working ✅

---

## Phase 2: Repository Extraction (Cache Operations)

### Goal

Extract cache operations from DataManager into standalone DataRepository.

### Context

**Current State** (at commit 79f98d6):
- ❌ NO DataRepository
- ❌ NO repository/ directory
- ✅ LocalDataLoader has basic I/O (save/load CSV)
- ✅ DataManager wraps LocalDataLoader with validation
- ✅ All cache logic working in DataManager

**Code to Extract From**:
- `LocalDataLoader` (lines 1-400) - Basic I/O
- `DataManager.load_data()` (lines 267-330) - with mode="local"
- `DataManager.get_data_summary()` (lines 1219-1266)
- `DataManager.merge_data()` (lines 1295-1335)

**Why This Phase**:
- Repository is simplest component (sync, no IB, no Operations)
- Can deliver value immediately (faster cache operations)
- No chicken-and-egg with IB code

**Strategy**:
1. Create repository/ directory structure
2. Extract DataQualityValidator first (used by Repository)
3. Create DataRepository by wrapping LocalDataLoader
4. Wire to API/CLI
5. Keep DataManager for downloads (Phase 4 will extract that)

### Duration

**1 week** (6 tasks)

### Tasks

---

#### TASK 2.1: Extract DataQualityValidator

**Objective**: Move DataQualityValidator from data/ to repository/.

**What to EXTRACT**:

Looking at current code, we need to create the validator first since Repository needs it.

**Files to CREATE**:
```
ktrdr/data/repository/
├── __init__.py
└── data_quality_validator.py
```

**Extraction Pattern**:

If DataQualityValidator already exists in `data/`:
1. Move it: `git mv data/data_quality_validator.py repository/data_quality_validator.py`
2. Update imports in DataManager

If it doesn't exist:
1. Extract validation logic from DataManager
2. Create new DataQualityValidator class
3. Use in DataManager (backward compatible)

**Files Modified**:
- Create: `ktrdr/data/repository/__init__.py`
- Create: `ktrdr/data/repository/data_quality_validator.py`
- Update: `ktrdr/data/data_manager.py` (import from new location)

**Scope**:
1. Create repository/ directory
2. Extract/create DataQualityValidator
3. Update DataManager imports
4. Add unit tests for validator

**Integration Test**: Validation still works in DataManager

**Acceptance Criteria**:
- [ ] `repository/` directory created
- [ ] `DataQualityValidator` exists in `repository/`
- [ ] DataManager uses validator from new location
- [ ] All validation tests pass
- [ ] All unit tests pass
- [ ] `make quality` passes

**Estimated Duration**: 0.5 days

---

#### TASK 2.2: Create DataRepository (Core Methods)

**Objective**: Create DataRepository by extracting cache I/O from DataManager.

**What to EXTRACT**:

```python
# FROM: DataManager.load_data() with mode="local" (lines 267-330)
# Extract local cache loading

# FROM: LocalDataLoader.load() (existing)
# Wrap with Repository

# TO: DataRepository.load_from_cache()
```

**Extraction Pattern**:

1. **Create Repository class**:
   ```python
   # NEW FILE: ktrdr/data/repository/data_repository.py

   from ktrdr.data.local_data_loader import LocalDataLoader
   from ktrdr.data.repository.data_quality_validator import DataQualityValidator

   class DataRepository:
       """Local cache repository for market data."""

       def __init__(self, data_dir: Optional[str] = None):
           self.loader = LocalDataLoader(data_dir=data_dir)
           self.validator = DataQualityValidator(auto_correct=False)

       def load_from_cache(self, symbol, timeframe, start_date=None, end_date=None):
           # Delegate to LocalDataLoader
           df = self.loader.load(symbol, timeframe, start_date, end_date)
           if df is None or df.empty:
               raise DataNotFoundError(...)
           return df

       def save_to_cache(self, symbol, timeframe, data):
           # Validate before save
           self.loader._validate_dataframe(data)
           # Delegate to LocalDataLoader
           self.loader.save(data, symbol, timeframe)
   ```

2. **Extract get_data_range**:
   ```python
   # FROM: DataManager.get_data_summary() (lines 1219-1266)
   # Extract date range logic

   def get_data_range(self, symbol, timeframe):
       date_range = self.loader.get_data_date_range(symbol, timeframe)
       if not date_range:
           raise DataNotFoundError(...)
       return {
           "symbol": symbol,
           "timeframe": timeframe,
           "start_date": date_range[0],
           "end_date": date_range[1],
       }
   ```

**Files Created**:
- `ktrdr/data/repository/data_repository.py`

**Files Modified**:
- `ktrdr/data/repository/__init__.py` (export DataRepository)

**Scope**:
1. Create DataRepository class
2. Implement `load_from_cache()`
3. Implement `save_to_cache()`
4. Implement `get_data_range()`
5. Add unit tests (mock LocalDataLoader)

**Integration Test**:
- Create temp file, save data, load data, verify

**Acceptance Criteria**:
- [ ] `DataRepository` created
- [ ] `load_from_cache()` works
- [ ] `save_to_cache()` works
- [ ] `get_data_range()` works
- [ ] Unit tests pass (25+ tests)
- [ ] Integration test passes (real file I/O)
- [ ] `make quality` passes

**Estimated Duration**: 1 day

---

#### TASK 2.3: Add Repository Helper Methods

**Objective**: Add convenience methods to DataRepository.

**What to EXTRACT**:

```python
# FROM: DataManager.get_data_summary() (lines 1219-1266)
# Extract summary logic

# FROM: LocalDataLoader methods
# Wrap with Repository interface
```

**Methods to Add**:

1. **get_available_symbols()** - List cached symbols
2. **delete_from_cache()** - Delete cached data
3. **get_cache_stats()** - Cache size, file count
4. **validate_data()** - Validate cached data

**Files Modified**:
- `ktrdr/data/repository/data_repository.py`

**Scope**:
1. Add helper methods
2. Extract logic from DataManager/LocalDataLoader
3. Add unit tests

**Integration Test**: Helper methods work correctly

**Acceptance Criteria**:
- [ ] Helper methods implemented
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] `make quality` passes

**Estimated Duration**: 0.5 days

---

#### TASK 2.4: Wire Repository to API (Read-Only)

**Objective**: Update GET endpoints to use DataRepository.

**What to REFACTOR**:

```python
# FROM: ktrdr/api/endpoints/data.py
# Current:
from ktrdr.data.data_manager import DataManager
data_manager = DataManager()

@router.get("/data/{symbol}/{timeframe}")
async def get_data(...):
    df = data_manager.load_data(symbol, timeframe, mode="local")

# TO:
from ktrdr.data.repository import DataRepository
data_repository = DataRepository()

@router.get("/data/{symbol}/{timeframe}")
async def get_data(...):
    df = data_repository.load_from_cache(symbol, timeframe)
```

**Files Modified**:
- `ktrdr/api/endpoints/data.py`

**Scope**:
1. Add DataRepository import
2. Update `GET /data/{symbol}/{timeframe}`
3. Update `GET /data/range`
4. Update `GET /data/info`
5. Keep `POST /data/load` using DataManager (unchanged)

**Integration Test**: D1.1, D1.2, D1.4 via API

**Acceptance Criteria**:
- [x] GET endpoints use DataRepository
- [x] POST endpoints still use DataManager
- [x] Integration tests D1.1, D1.2, D1.4 pass (see `docs/testing/SCENARIOS.md` for details)
- [x] All unit tests pass (1776/1776)
- [x] `make quality` passes

**Test Documentation**: See [Testing Guide](#testing-guide) section above for integration test locations and commands.

**Estimated Duration**: 1 day

**Actual Duration**: 1 day ✅

**Status**: ✅ COMPLETE (Commit: 42aadb0)

---

#### TASK 2.5: Wire Repository to CLI (Read-Only)

**Status**: ❌ **NOT NEEDED** - Task based on incorrect assumption

**Why Not Needed**:

The implementation plan was written with an incorrect assumption about CLI architecture. Upon investigation, the CLI **already uses the API exclusively** and does NOT directly import DataManager or DataRepository:

```python
# ACTUAL IMPLEMENTATION (ktrdr/cli/data_commands.py)

# ktrdr data show (line 147-149)
async with AsyncCLIClient() as cli:
    data = await cli._make_request("GET", f"/data/{symbol}/{timeframe}", params=params)

# ktrdr data load (line 439)
response = await api_client.load_data(...)

# ktrdr data range (line 891)
data = await api_client.get_data_range(symbol=symbol, timeframe=timeframe)
```

**Architecture Verification**:

The CLI follows the correct architecture from CLAUDE.md:
```
CLI → AsyncCLIClient → API Endpoints → Backend Services (DataRepository/DataManager)
```

**Impact**:
- ✅ **Task 2.4 complete**: API endpoints use DataRepository
- ✅ **CLI already correct**: Uses API, not direct imports
- ✅ **Zero changes needed**: API interface unchanged
- ✅ **No breaking changes**: Everything works without CLI modifications

**Conclusion**: Since the API endpoints were updated in Task 2.4 to use DataRepository, and the CLI already uses the API (not direct imports), there are no CLI changes required. The CLI automatically benefits from the API improvements.

**Files Verified**:
- `ktrdr/cli/data_commands.py` - Confirmed uses AsyncCLIClient/API only

**Original Estimated Duration**: 0.5 days → **Actual Duration**: 0 days (not applicable)

---

#### TASK 2.6: Add Optional Repository to DataManager

**Objective**: Allow DataManager to optionally save via Repository.

**What to REFACTOR**:

```python
# FROM: DataManager.merge_data() (lines 1295-1335)
# Current:
def merge_data(self, ...):
    # ... merge logic
    if save_result:
        self.data_loader.save(merged_data, symbol, timeframe)

# TO:
def merge_data(self, ...):
    # ... merge logic
    if save_result:
        if hasattr(self, 'repository') and self.repository:
            self.repository.save_to_cache(symbol, timeframe, merged_data)
        else:
            self.data_loader.save(merged_data, symbol, timeframe)
```

**Files Modified**:
- `ktrdr/data/data_manager.py`

**Scope**:
1. Add optional `repository` parameter to `__init__`
2. Update save paths to use Repository if available
3. Maintain backward compatibility

**Integration Test**: D3.3 with Repository

**Acceptance Criteria**:
- [ ] DataManager accepts optional Repository
- [ ] Uses Repository for saves if provided
- [ ] Backward compatible without Repository
- [ ] All tests pass
- [ ] `make quality` passes

**Estimated Duration**: 0.5 days

---

### Phase 2 Exit Criteria

**Components**:
- [x] DataRepository exists and tested
- [x] DataQualityValidator in repository/
- [x] API GET endpoints use Repository
- [x] CLI read commands use Repository
- [x] DataManager optionally uses Repository

**Integration Tests**:
- [x] D1.1-D1.4 pass (cache via Repository)
- [x] D3.1-D3.3 still pass (downloads via DataManager)

**Code Quality**:
- [x] All unit tests pass
- [x] `make quality` passes
- [x] No regressions

**Total Duration**: 1 week (4-5 days)

**Ready for Phase 3**: Repository working, ready to isolate IB ✅

---

## Phase 3: IB Isolation (HTTP-Only Provider)

### Goal

Backend never imports `ktrdr/ib`, only calls IB via HTTP.

### Context

**Current Blocker**:
- `IbDataAdapter` imports from `ktrdr.ib` (line 33):
  ```python
  from ktrdr.ib import IbDataFetcher, IbErrorClassifier, IbErrorType
  ```
- Backend uses `IbDataAdapter` for download operations
- Can't delete `ktrdr/ib/` until backend stops importing it

**Solution**:
1. Move acquisition files to acquisition/ directory
2. Create `IbDataProvider` (HTTP-only, no IB imports)
3. Replace `IbDataAdapter` with `IbDataProvider`
4. Delete `IbDataAdapter`
5. Verify no IB imports
6. Delete `ktrdr/ib/` directory

### Duration

**4-5 days** (7 tasks)

### Tasks

---

#### TASK 3.1: Move Files to acquisition/ Directory

**Objective**: Organize acquisition-related files into acquisition/ directory.

**What to MOVE**:

```bash
# Create directory
mkdir ktrdr/data/acquisition/

# Move files from components/
git mv ktrdr/data/components/gap_analyzer.py ktrdr/data/acquisition/
git mv ktrdr/data/components/gap_classifier.py ktrdr/data/acquisition/
git mv ktrdr/data/components/segment_manager.py ktrdr/data/acquisition/

# Move orchestrator
git mv ktrdr/data/data_loading_orchestrator.py ktrdr/data/acquisition/

# Move interface
git mv ktrdr/data/external_data_interface.py ktrdr/data/acquisition/
```

**Files Modified**:
- Create: `ktrdr/data/acquisition/__init__.py`
- Update all imports in DataManager, tests, etc.

**Scope**:
1. Create acquisition/ directory
2. Move 5 files
3. Update imports everywhere
4. Run tests

**Integration Test**: All tests still pass

**Acceptance Criteria**:
- [ ] acquisition/ directory created
- [ ] Files moved successfully
- [ ] Imports updated
- [ ] All tests pass
- [ ] `make quality` passes

**Estimated Duration**: 0.5 days

---

#### TASK 3.2: Create IbDataProvider (HTTP-Only)

**Objective**: Extract HTTP-only code from IbDataAdapter.

**What to EXTRACT**:

From `IbDataAdapter` (735 lines), keep only HTTP code, delete direct IB code.

See detailed extraction pattern in full plan above (Phase 3, Task 3.1 from previous version).

**Files Created**:
- `ktrdr/data/acquisition/ib_data_provider.py`

**Expected Size**: ~400-500 lines (vs 735)

**Acceptance Criteria**:
- [ ] `IbDataProvider` created
- [ ] HTTP-only (no IB imports)
- [ ] Unit tests pass
- [ ] Integration test D2.2 passes

**Estimated Duration**: 1.5 days

---

#### TASK 3.3: Update DataManager to Use IbDataProvider

**Objective**: Replace IbDataAdapter with IbDataProvider in DataManager.

**Files Modified**:
- `ktrdr/data/data_manager.py`

**Scope**: Update imports and initialization

**Acceptance Criteria**:
- [ ] DataManager uses IbDataProvider
- [ ] Integration tests D3.1-D3.3 pass

**Estimated Duration**: 0.5 days

---

#### TASK 3.4: Delete IbDataAdapter

**Objective**: Remove unused IbDataAdapter.

**Files Deleted**:
- `ktrdr/data/ib_data_adapter.py`

**Acceptance Criteria**:
- [ ] File deleted
- [ ] No imports found
- [ ] All tests pass

**Estimated Duration**: 0.5 days

---

#### TASK 3.5: Verify No IB Imports

**Objective**: Ensure backend never imports `ktrdr/ib`.

**Verification**:
```bash
grep -r "from ktrdr.ib import" ktrdr/ --exclude-dir=ib
# Should be ZERO results
```

**Acceptance Criteria**:
- [ ] No IB imports in backend
- [ ] Documentation created

**Estimated Duration**: 0.5 days

---

#### TASK 3.6: Delete ktrdr/ib/ Directory

**Objective**: Remove IB code from backend.

**Files Deleted**:
- `ktrdr/ib/` (entire directory, 9 files)

**Acceptance Criteria**:
- [ ] Directory deleted
- [ ] Docker rebuilds successfully
- [ ] Backend starts without errors
- [ ] All integration tests pass

**Estimated Duration**: 0.5 days

---

#### TASK 3.7: Final Integration Test

**Objective**: Validate all operations work after IB deletion.

**What to TEST**: Run ALL Phase 0 scenarios (D1.1-D4.3)

**Acceptance Criteria**:
- [x] ALL Phase 0 tests pass
- [x] No regressions
- [x] Performance acceptable

**Estimated Duration**: 0.5 days

---

### Phase 3 Exit Criteria

**Code Removed**:
- [x] IbDataAdapter deleted
- [x] ktrdr/ib/ deleted

**Components Created**:
- [x] IbDataProvider (HTTP-only)

**Import Rules**:
- [x] Backend has ZERO imports from ktrdr/ib
- [x] Backend calls IB only via HTTP

**Integration Tests**:
- [x] ALL Phase 0 tests pass

**Total Duration**: 4-5 days

**Ready for Phase 4**: Backend IB-free ✅

---

## Phase 4: Acquisition Extraction (Download Logic)

### Goal

Extract download logic from DataManager into DataAcquisitionService.

### Context

**Current State**:
- ✅ DataRepository (Phase 2) - cache
- ✅ IbDataProvider (Phase 3) - IB HTTP
- ❌ NO DataAcquisitionService
- ✅ DataManager has ALL download logic

**Strategy**: Extract methods from DataManager incrementally.

### Duration

**1-2 weeks** (7 tasks)

### Tasks

---

#### TASK 4.1: Create DataAcquisitionService Shell

**Objective**: Create basic service structure.

**What to CREATE**:

```python
# NEW FILE: ktrdr/data/acquisition/acquisition_service.py

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator

class DataAcquisitionService(ServiceOrchestrator):
    """External data acquisition orchestrator."""

    def __init__(self, repository=None, provider=None):
        super().__init__()
        self.repository = repository or DataRepository()
        self.provider = provider or IbDataProvider()
```

**Files Created**:
- `ktrdr/data/acquisition/acquisition_service.py`

**Acceptance Criteria**:
- [ ] Service created
- [ ] Inherits from ServiceOrchestrator
- [ ] Basic structure in place

**Estimated Duration**: 0.5 days

---

#### TASK 4.2: Extract Basic Download Flow

**Objective**: Extract cache-check → download → save from DataManager.

**What to EXTRACT**: See detailed extraction in full plan above.

**Acceptance Criteria**:
- [ ] Basic download flow works
- [ ] Integration test passes

**Estimated Duration**: 2 days

---

#### TASK 4.3-4.7: [Same as previous plan]

Extract validation, progress, gap analysis, segment fetching, etc.

**Total Duration**: 1-2 weeks

---

### Phase 4 Exit Criteria

**Components**:
- [x] DataAcquisitionService working
- [x] New API endpoints
- [x] New CLI commands

**Integration Tests**:
- [x] ALL Phase 0 tests pass via new endpoints

**Total Duration**: 1-2 weeks

---

## Phase 5: Cleanup & Documentation

### Goal

Remove DataManager, deprecated code, finalize.

### Duration

**3-4 days** (6 tasks)

Same as previous plan.

---

## Final Summary

### Total Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 0 | Done ✅ | Test baseline |
| 1 | Done ✅ | Host service ready |
| 2 | 1 week | Repository extracted |
| 3 | 4-5 days | IB deleted |
| 4 | 1-2 weeks | Acquisition extracted |
| 5 | 3-4 days | Clean architecture |

**Total**: ~3-4 weeks

---

**Document Version**: 2.0 (Extraction-Focused)
**Created**: 2025-01-29
**Starting Point**: Commit 79f98d6 (End of Phase 1)
**Status**: PROPOSED - Ready for Review
