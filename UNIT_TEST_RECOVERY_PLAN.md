# Unit Test Recovery Plan

## Status: Comprehensive Audit Complete - 523 Tests Passing!

**Last Updated**: 2025-06-14  
**Current State**: 56 test files (523 tests) passing, 18 files failing, 11 files with import errors  

## Comprehensive Test Audit Results

### ✅ PASSING TESTS: 56 files (523 individual tests)
**Strong foundation** across API, Config, Data, Fuzzy Logic, Indicators, etc.
- API Tests: 13 files passing cleanly
- Fuzzy Logic: 7 files, comprehensive coverage
- Indicators: 4 files, solid test suite
- Configuration: 3 files, validation working

### ❌ FAILING TESTS: 18 files (116 failing tests)
**Need investigation and fixes**
- API endpoint tests (data, fuzzy endpoints)
- Core system tests (backtesting, neural, decision orchestrator)
- Data management tests

### 🚫 OBSOLETE TESTS: 4 files (SHOULD BE DELETED)
**Import non-existent refactored modules:**
- `test_ib_data_range_discovery.py` → imports `ib_data_fetcher_sync`
- `test_ib_integration_complete.py` → imports `ib_connection_sync`
- `test_ib_resume.py` → imports `ib_resume_handler`
- `test_ib_scenarios.py` → imports `ib_connection_manager`

### 🔧 FIXABLE IMPORT ERRORS: 7 files
**Simple fixes needed:**
- Missing `psutil` dependency (1 file)
- Relative import issues (2 files)
- Missing CLI plot command (1 file)
- Visualization test fixtures (3 files)

### ⏱️ TIMEOUT TESTS: 3 files
**Complex async/IB connection issues:**
- `test_ib_connection_pool_unified.py`
- `test_ib_pace_manager.py`
- `test_ib_unified_integration.py`

## Recovery Phases

### Phase 1: Cleanup and Quick Wins (IMMEDIATE)
**Goal**: Remove obsolete tests and fix simple import issues

1. **Delete obsolete tests** (4 files) - 10 min
2. **Add missing psutil dependency** - 5 min  
3. **Fix relative imports** (5 files) - 15 min
4. **Fix pytest config conflict** - 5 min

**Expected Result**: Clean test run with 523+ passing tests

### Phase 2: Fix Failing Tests (NEXT SESSION) 
**Goal**: Address the 18 files with 116 failing tests

**Priority Order:**
1. **High Priority**: Core system tests (8 files)
   - `test_backtesting_system.py`
   - `test_decision_orchestrator.py` 
   - `test_neural_foundation.py`

2. **Medium Priority**: API endpoint tests (5 files)
   - `test_data_endpoints.py`
   - `test_fuzzy_endpoint.py`
   - Data service tests

3. **Low Priority**: Data management tests (5 files)
   - May require IB connection setup

### Phase 3: Investigate Timeout Tests (FUTURE)
**Goal**: Debug and fix async/connection issues

- `test_ib_connection_pool_unified.py`
- `test_ib_pace_manager.py` 
- `test_ib_unified_integration.py`

**Likely Issues**: Blocking async operations, missing mocks

## Current Module Mapping

### IB Modules (Refactored)
**Old** → **New**
- `ib_data_fetcher_sync` → `ib_data_fetcher_unified` 
- `ib_connection_sync` → `ib_connection_pool`
- `ib_connection_manager` → `ib_connection_pool`
- `ib_resume_handler` → ??? (investigate)

### CLI Commands (Refactored)
**Old** → **New**
- `plot` in `commands.py` → `plot` in `data_commands.py` or similar

## Session Notes

### Session 1 (2025-06-14)
- Added development best practices to CLAUDE.md ✅
- Ran initial test assessment - found 7 critical errors ✅
- Created this recovery plan ✅
- **Next**: Start Phase 1 fixes

---

## Usage Notes
- This plan persists across sessions
- Update status as fixes are completed
- Add new issues discovered during testing
- Keep module mapping updated as code evolves