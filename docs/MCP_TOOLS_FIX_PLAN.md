# MCP Tools Fix Plan

**Date:** 2025-10-05
**Context:** PR #73 refactored MCP server to remove local storage and delegate all operations to backend API. Several MCP tools are now broken due to missing client methods.

## Executive Summary

The recent MCP refactoring (PR #73) introduced breaking changes by migrating from a monolithic `KTRDRAPIClient` to domain-specific clients (`DataAPIClient`, `TrainingAPIClient`, etc.). The MCP server tools still call deprecated methods that no longer exist on the unified client facade.

**Root Cause:** Missing delegation methods in `KTRDRAPIClient` for methods that were removed during the refactoring.

### Quick Reference

**Branch:** `fix/mcp-tools-broken-endpoints`

**Development Approach:**

- ✅ TDD (Test-Driven Development) - write tests FIRST
- ✅ `make test-unit` must pass before each commit
- ✅ `make quality` must pass before each commit
- ✅ One logical change per commit

**Estimated Time:** 2-3 hours (including TDD, tests, quality checks)

**Phases:**

1. Fix keyword arguments (5 min)
2. Add domain clients (20 min)
3. Extend DataAPIClient (10 min)
4. Update unified facade (15 min)
5. Fix training tool signature (20 min)
6. Integration tests (30 min)
7. Update docs (15 min)

---

## Error Analysis

### 1. ✅ `check_backend_health` - **WORKING**

**Status:** OK
**Why it works:** Properly delegates to `self.system.health_check()`

```python
# mcp/src/api_client.py:129
async def health_check(self) -> dict[str, Any]:
    return await self.system.health_check()
```

---

### 2. ❌ `get_available_symbols` - **BROKEN**

**Error:** `'KTRDRAPIClient' object has no attribute 'get_symbols'`

**Root Cause:**
- MCP server calls `client.get_symbols()` ([mcp/src/server.py:55](mcp/src/server.py#L55))
- `KTRDRAPIClient` has no `get_symbols()` delegation method
- Backend API endpoint exists at `GET /symbols` ([ktrdr/api/endpoints/data.py:134](ktrdr/api/endpoints/data.py#L134))
- `DataAPIClient` is missing the `get_symbols()` method

**Fix Required:**
1. Add `get_symbols()` method to `DataAPIClient`
2. Add delegation method to `KTRDRAPIClient`

**Backend Endpoint:**
```python
# ktrdr/api/endpoints/data.py:134
@router.get("/symbols", response_model=SymbolsResponse)
async def get_symbols(data_service: DataService = Depends(get_data_service))
```

---

### 3. ❌ `get_available_indicators` - **BROKEN**

**Error:** `'KTRDRAPIClient' object has no attribute 'get_indicators'`

**Root Cause:**
- MCP server calls `client.get_indicators()` ([mcp/src/server.py:162](mcp/src/server.py#L162))
- `KTRDRAPIClient` has no `get_indicators()` delegation method
- Backend API endpoint exists at `GET /indicators/` ([ktrdr/api/endpoints/indicators.py:36](ktrdr/api/endpoints/indicators.py#L36))
- No domain client exists for indicators

**Fix Required:**
1. Create new `IndicatorsAPIClient` in `mcp/src/clients/indicators_client.py`
2. Add to `KTRDRAPIClient.__init__()`
3. Add delegation method to `KTRDRAPIClient`

**Backend Endpoint:**
```python
# ktrdr/api/endpoints/indicators.py:36
@router.get("/", response_model=IndicatorsListResponse)
async def list_indicators(indicator_service: IndicatorService = Depends(get_indicator_service))
```

---

### 4. ❌ `get_market_data` - **BROKEN**

**Error:** `KTRDRAPIClient.get_cached_data() takes 1 positional argument but 6 were given`

**Root Cause:**
- MCP server calls `client.get_cached_data(symbol, timeframe, start_date, end_date, trading_hours_only, limit=effective_limit)` ([mcp/src/server.py:98-104](mcp/src/server.py#L98-L104))
- Delegation method exists: `async def get_cached_data(self, **kwargs)` ([api_client.py:93](mcp/src/api_client.py#L93))
- MCP is passing **positional arguments** instead of **keyword arguments**
- Backend method signature in `DataAPIClient` expects keyword args

**Fix Required:**
Fix the MCP server call to use keyword arguments instead of positional:

```python
# Current (BROKEN):
data = await client.get_cached_data(
    symbol,           # positional
    timeframe,        # positional
    start_date,       # positional
    end_date,         # positional
    trading_hours_only,  # positional
    limit=effective_limit,
)

# Fixed:
data = await client.get_cached_data(
    symbol=symbol,
    timeframe=timeframe,
    start_date=start_date,
    end_date=end_date,
    trading_hours_only=trading_hours_only,
    limit=effective_limit,
)
```

**Backend Method:**
```python
# mcp/src/clients/data_client.py:11
async def get_cached_data(
    self,
    symbol: str,
    timeframe: str = "1h",
    start_date: Optional[str] = None,
    ...
)
```

---

### 5. ❌ `get_data_summary` - **BROKEN**

**Error:** `KTRDRAPIClient.get_cached_data() takes 1 positional argument but 3 were given`

**Root Cause:**
- MCP server calls `client.get_cached_data(symbol, timeframe, limit=1)` ([mcp/src/server.py:135](mcp/src/server.py#L135))
- Same issue as `get_market_data` - using positional args instead of keyword args

**Fix Required:**
```python
# Current (BROKEN):
data = await client.get_cached_data(symbol, timeframe, limit=1)

# Fixed:
data = await client.get_cached_data(symbol=symbol, timeframe=timeframe, limit=1)
```

---

### 6. ❌ `get_available_strategies` - **BROKEN**

**Error:** `'KTRDRAPIClient' object has no attribute 'get_strategies'`

**Root Cause:**
- MCP server calls `client.get_strategies()` ([mcp/src/server.py:179](mcp/src/server.py#L179))
- `KTRDRAPIClient` has no `get_strategies()` delegation method
- Backend API endpoint exists at `GET /strategies/` ([ktrdr/api/endpoints/strategies.py:77](ktrdr/api/endpoints/strategies.py#L77))
- No domain client exists for strategies

**Fix Required:**
1. Create new `StrategiesAPIClient` in `mcp/src/clients/strategies_client.py`
2. Add to `KTRDRAPIClient.__init__()`
3. Add delegation method to `KTRDRAPIClient`

**Backend Endpoint:**
```python
# ktrdr/api/endpoints/strategies.py:77
@router.get("/", response_model=StrategiesResponse)
async def list_strategies() -> StrategiesResponse
```

---

### 7. ✅ Operations Tools - **ALL WORKING**

**Status:** OK
- `list_operations` ✓
- `get_operation_status` ✓
- `cancel_operation` ✓
- `get_operation_results` ✓

**Why they work:** Properly use domain-specific client pattern:
```python
result = await client.operations.list_operations(...)
```

---

### 8. ✅ `trigger_data_loading` - **WORKING**

**Status:** OK
**Why it works:** Properly uses domain-specific client:
```python
result = await client.data.load_data_operation(...)
```

---

### 9. ❌ `start_training` - **BROKEN**

**Error:** `HTTP 422: Field required` for `timeframes` and `strategy_name`

**Root Cause:**
- MCP tool has incorrect parameter mapping
- MCP accepts: `symbols`, `timeframe` (singular), `config` dict with `strategy_name` inside
- Backend expects: `symbols`, `timeframes` (plural), `strategy_name` (top-level)

**MCP Tool Signature ([mcp/src/server.py:426](mcp/src/server.py#L426)):**
```python
async def start_training(
    symbols: list[str],
    timeframe: str = "1h",         # SINGULAR
    config: Optional[dict[str, Any]] = None,  # strategy_name INSIDE config
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
)
```

**Backend Endpoint Signature ([ktrdr/api/endpoints/training.py:38](ktrdr/api/endpoints/training.py#L38)):**
```python
class TrainingRequest(BaseModel):
    symbols: list[str]
    timeframes: list[str]          # PLURAL ✓
    strategy_name: str             # TOP-LEVEL ✓
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    task_id: Optional[str] = None
    detailed_analytics: bool = False
```

**Fix Required:**
1. Update MCP tool signature to match backend
2. Extract `strategy_name` from tool parameters (not from config)
3. Convert singular `timeframe` to plural `timeframes` list
4. Update tool docstring

**Correct Implementation:**
```python
@mcp.tool()
async def start_training(
    symbols: list[str],
    timeframes: list[str],         # FIXED: plural
    strategy_name: str,            # FIXED: top-level parameter
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Train a neural network model on market data"""
    try:
        async with get_api_client() as client:
            result = await client.training.start_neural_training(
                symbols=symbols,
                timeframes=timeframes,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
            )
            return result
    except Exception as e:
        logger.error("Failed to start training", error=str(e))
        raise
```

---

## Fix Implementation Plan

### Phase 1: Quick Wins (Keyword Arguments)

**Files to modify:**
- `mcp/src/server.py`

**Changes:**
1. Fix `get_market_data()` - use keyword args in `get_cached_data()` call
2. Fix `get_data_summary()` - use keyword args in `get_cached_data()` call

**Estimated Time:** 5 minutes

---

### Phase 2: Add Missing Domain Clients

**Files to create:**
- `mcp/src/clients/indicators_client.py`
- `mcp/src/clients/strategies_client.py`

**Pattern to follow:**
```python
# mcp/src/clients/indicators_client.py
from typing import Any
from .base import BaseAPIClient

class IndicatorsAPIClient(BaseAPIClient):
    """API client for indicators operations"""

    async def list_indicators(self) -> list[dict[str, Any]]:
        """List all available indicators"""
        response = await self._request("GET", "/indicators/")
        return response.get("data", [])
```

**Estimated Time:** 15 minutes

---

### Phase 3: Extend Existing Clients

**File to modify:**
- `mcp/src/clients/data_client.py`

**Changes:**
Add `get_symbols()` method to `DataAPIClient`:

```python
async def get_symbols(self) -> list[dict[str, Any]]:
    """Get available trading symbols"""
    response = await self._request("GET", "/symbols")
    return response.get("data", [])
```

**Estimated Time:** 5 minutes

---

### Phase 4: Update Unified Client Facade

**File to modify:**
- `mcp/src/api_client.py`

**Changes:**
1. Import new clients: `IndicatorsAPIClient`, `StrategiesAPIClient`
2. Initialize in `__init__()`:
   ```python
   self.indicators = IndicatorsAPIClient(base_url, timeout)
   self.strategies = StrategiesAPIClient(base_url, timeout)
   ```
3. Add to async context managers (`__aenter__`, `__aexit__`)
4. Add backward-compat delegation methods:
   ```python
   async def get_symbols(self) -> list[dict[str, Any]]:
       return await self.data.get_symbols()

   async def get_indicators(self) -> list[dict[str, Any]]:
       return await self.indicators.list_indicators()

   async def get_strategies(self) -> dict[str, Any]:
       return await self.strategies.list_strategies()
   ```

**Estimated Time:** 10 minutes

---

### Phase 5: Fix Training Tool Signature

**Files to modify:**
- `mcp/src/server.py`
- `mcp/src/clients/training_client.py`

**Changes:**

**Step 1: Fix TrainingAPIClient** (`mcp/src/clients/training_client.py`)
- Change `timeframe: str` → `timeframes: list[str]`
- Add `strategy_name: str` as top-level parameter
- Remove `config: dict[str, Any]` parameter
- Add `detailed_analytics: bool = False` parameter
- Update payload to match backend API contract

```python
async def start_neural_training(
    self,
    symbols: list[str],
    timeframes: list[str],         # FIXED: plural
    strategy_name: str,            # FIXED: top-level
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_id: Optional[str] = None,
    detailed_analytics: bool = False,
) -> dict[str, Any]:
    """Start neural network training (async, returns operation_id)"""
    payload = {
        "symbols": symbols,
        "timeframes": timeframes,
        "strategy_name": strategy_name,
    }
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    if task_id:
        payload["task_id"] = task_id
    if detailed_analytics:
        payload["detailed_analytics"] = detailed_analytics

    return await self._request("POST", "/trainings/start", json=payload)
```

**Step 2: Fix MCP Tool** (`mcp/src/server.py`)
- Update signature to match backend API
- Update docstring with clear parameter descriptions
- Add usage example in docstring
- Remove config dict handling

```python
@mcp.tool()
async def start_training(
    symbols: list[str],
    timeframes: list[str],         # FIXED: plural
    strategy_name: str,            # FIXED: top-level parameter
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Train a neural network model on market data

    Trains a neural network to predict trading signals using historical market data.
    Training runs in the background. Returns immediately with operation_id for
    tracking progress. Use get_operation_status() to monitor training progress.

    Args:
        symbols: List of trading symbols to train on (e.g., ["AAPL", "MSFT"])
        timeframes: List of data timeframes to use (e.g., ["1h", "4h", "1d"])
        strategy_name: Name of the strategy configuration to use (e.g., "neuro_mean_reversion")
        start_date: Training data start date (YYYY-MM-DD, optional)
        end_date: Training data end date (YYYY-MM-DD, optional)

    Returns:
        dict with operation_id for tracking the training operation

    Example:
        result = await start_training(
            symbols=["AAPL"],
            timeframes=["1h"],
            strategy_name="neuro_mean_reversion",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        operation_id = result["operation_id"]
    """
    try:
        async with get_api_client() as client:
            result = await client.training.start_neural_training(
                symbols=symbols,
                timeframes=timeframes,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info(
                "Training started",
                symbols=symbols,
                operation_id=result.get("operation_id"),
            )
            return result
    except Exception as e:
        logger.error("Failed to start training", error=str(e))
        raise
```

**Key Point:** The tool description is critical for Claude Code/MCP clients to understand how to properly call the tool. The updated docstring now clearly shows:
1. `timeframes` is plural and expects a list
2. `strategy_name` is a required top-level parameter (not inside a config dict)
3. Includes a complete usage example

**Estimated Time:** 15 minutes

---

### Phase 6: Update Tests

**Files to modify:**
- `tests/unit/mcp/test_base_client.py`
- Create: `tests/unit/mcp/test_indicators_client.py`
- Create: `tests/unit/mcp/test_strategies_client.py`
- Create: `tests/unit/mcp/test_data_client.py`

**Test patterns:**
- Test each new client method
- Test delegation methods in unified client
- Test MCP tool parameter handling

**Estimated Time:** 20 minutes

---

### Phase 7: Update Documentation

**Files to modify:**
- `mcp/MCP_TOOLS.md`

**Changes:**
1. Update `start_training` tool documentation with correct parameters
2. Verify all other tool docs are accurate
3. Add migration notes for API consumers

**Estimated Time:** 10 minutes

---

## Testing Strategy

### Manual Testing Checklist

After implementation, test each tool:

```bash
# Start backend
./start_ktrdr.sh

# Test MCP tools (use Claude Desktop or MCP inspector)
```

**Tools to test:**
- [ ] `check_backend_health` (should still work)
- [ ] `get_available_symbols` (should now work)
- [ ] `get_available_indicators` (should now work)
- [ ] `get_market_data` (should now work with keyword args)
- [ ] `get_data_summary` (should now work with keyword args)
- [ ] `get_available_strategies` (should now work)
- [ ] `list_operations` (should still work)
- [ ] `get_operation_status` (should still work)
- [ ] `cancel_operation` (should still work)
- [ ] `get_operation_results` (should still work)
- [ ] `trigger_data_loading` (should still work)
- [ ] `start_training` (should now work with correct params)

### Unit Tests

Run existing MCP tests:
```bash
uv run pytest tests/unit/mcp/ -v
```

Expected result: All tests pass

---

## Implementation Order

### Step 0: Setup Branch

**BEFORE STARTING ANY WORK:**

```bash
# Ensure on latest main
git checkout main
git pull origin main

# Create feature branch
git checkout -b fix/mcp-tools-broken-endpoints

# Verify clean state
git status
```

---

### Development Workflow (TDD Required)

#### ⚠️ CRITICAL: Follow Test-Driven Development (TDD) for ALL code changes

For each phase:

1. **Write tests FIRST** (RED phase)

   ```bash
   # Create/update test file
   # Write failing test that defines expected behavior
   uv run pytest tests/unit/mcp/test_<module>.py -v
   # Test should FAIL (proving it tests something)
   ```

2. **Implement code** (GREEN phase)

   ```bash
   # Write minimal code to make test pass
   uv run pytest tests/unit/mcp/test_<module>.py -v
   # Test should PASS
   ```

3. **Verify full test suite**

   ```bash
   # Run ALL unit tests to ensure no regressions
   make test-unit
   # ALL tests must pass (<2s execution time)
   ```

4. **Run quality checks**

   ```bash
   # Run complete quality suite (lint + format + typecheck)
   make quality
   # ALL checks must pass
   ```

5. **Commit if and only if everything passes**

   ```bash
   # Only commit when make test-unit AND make quality both pass
   git add <files>
   git commit -m "fix(mcp): <description>"
   ```

---

### Phase-by-Phase Implementation

**Recommended sequence (each phase must complete TDD cycle above):**

1. **Phase 1** - Fix keyword arguments (immediate impact, no new code)
   - Write tests for `get_market_data` and `get_data_summary` with correct params
   - Fix MCP server calls to use keyword args
   - Run `make test-unit && make quality`

2. **Phase 2** - Add domain clients (infrastructure)
   - Write tests for `IndicatorsAPIClient` and `StrategiesAPIClient`
   - Implement client classes
   - Run `make test-unit && make quality`

3. **Phase 3** - Extend DataAPIClient (infrastructure)
   - Write test for `DataAPIClient.get_symbols()`
   - Implement method
   - Run `make test-unit && make quality`

4. **Phase 4** - Update unified facade (ties everything together)
   - Write tests for facade delegation methods
   - Update `KTRDRAPIClient`
   - Run `make test-unit && make quality`

5. **Phase 5** - Fix training tool (last breaking change)
   - Write tests for new training client signature
   - Update `TrainingAPIClient` and MCP tool
   - Run `make test-unit && make quality`

6. **Phase 6** - Integration tests (validation)
   - Write integration tests for all MCP tools
   - Run `make test-unit && make quality`

7. **Phase 7** - Update docs (communication)
   - Update `mcp/MCP_TOOLS.md`
   - No tests needed for docs
   - Run `make quality` (check formatting)

---

## Code Quality Checklist

**Before EACH commit:**

- [ ] Tests written FIRST (TDD)
- [ ] All unit tests pass: `make test-unit` ✓ (<2s)
- [ ] All quality checks pass: `make quality` ✓
  - [ ] Linting passes (ruff)
  - [ ] Formatting passes (black)
  - [ ] Type checking passes (mypy)
- [ ] Commit message follows convention: `fix(mcp): <description>`
- [ ] Changes are focused (one logical change per commit)

**Before creating PR:**

- [ ] All phases completed with TDD
- [ ] All tools manually tested and working
- [ ] Integration tests added and passing
- [ ] Documentation updated (`mcp/MCP_TOOLS.md`)
- [ ] PR description includes:
  - [ ] Problem statement
  - [ ] Root cause analysis
  - [ ] Solution approach
  - [ ] Before/after testing results
  - [ ] Breaking changes noted (training tool signature)

---

## Risk Assessment

**Low Risk:**
- Phase 1 (keyword args) - pure bug fix
- Phase 3 (extend DataAPIClient) - additive only

**Medium Risk:**
- Phase 2 (new clients) - new code, potential bugs
- Phase 4 (facade updates) - touches central integration point

**High Risk:**
- Phase 5 (training signature) - **BREAKING CHANGE** for any existing MCP consumers

**Mitigation:**
- Test each phase independently
- Keep commits focused (one phase per commit)
- Add deprecation warnings if needed for backward compat

---

## Expected Outcome

After all fixes:
- ✅ All 12 MCP tools working
- ✅ Clean separation of concerns (domain clients)
- ✅ Backward compatibility maintained via facade
- ✅ Tests passing
- ✅ Documentation accurate

**Total estimated time with TDD:** ~2-3 hours

**Note:** Original estimate was 75 minutes for code-only. With TDD (tests-first approach), quality checks, and proper git workflow, realistic time is 2-3 hours for high-quality, well-tested implementation.

---

## Architectural Notes

### Why This Happened

The refactoring (PR #73) correctly moved to domain-specific clients but:
1. Didn't update MCP server tools to use new patterns
2. Didn't add all necessary delegation methods to facade
3. Didn't align MCP tool signatures with backend API contracts

### Best Practice Going Forward

**When adding new MCP tools:**
1. Check backend API endpoint signature first
2. Create domain client method if missing
3. Add delegation to unified facade for backward compat
4. Match MCP tool signature to backend contract exactly
5. Use keyword arguments for all client calls
6. Write tests before implementation

**Pattern to follow:**
```
Backend API Endpoint
    ↓ (implements)
Domain Client Method (e.g., DataAPIClient.get_symbols)
    ↓ (exposes via)
Unified Facade Delegation (e.g., KTRDRAPIClient.get_symbols)
    ↓ (called by)
MCP Tool (e.g., @mcp.tool() get_available_symbols)
```

---

## Appendix: File Reference

### Backend API Endpoints

| Endpoint | File | Line |
|----------|------|------|
| `GET /symbols` | `ktrdr/api/endpoints/data.py` | 134 |
| `GET /indicators/` | `ktrdr/api/endpoints/indicators.py` | 36 |
| `GET /strategies/` | `ktrdr/api/endpoints/strategies.py` | 77 |
| `POST /trainings/start` | `ktrdr/api/endpoints/training.py` | 173 |

### MCP Client Files

| File | Purpose |
|------|---------|
| `mcp/src/api_client.py` | Unified facade |
| `mcp/src/clients/base.py` | Base client class |
| `mcp/src/clients/data_client.py` | Data operations |
| `mcp/src/clients/operations_client.py` | Async operations |
| `mcp/src/clients/system_client.py` | Health checks |
| `mcp/src/clients/training_client.py` | Training operations |
| `mcp/src/clients/indicators_client.py` | **TO CREATE** |
| `mcp/src/clients/strategies_client.py` | **TO CREATE** |

### MCP Tools

| Tool | File | Line |
|------|------|------|
| `get_available_symbols` | `mcp/src/server.py` | 50 |
| `get_available_indicators` | `mcp/src/server.py` | 153 |
| `get_market_data` | `mcp/src/server.py` | 63 |
| `get_data_summary` | `mcp/src/server.py` | 118 |
| `get_available_strategies` | `mcp/src/server.py` | 170 |
| `start_training` | `mcp/src/server.py` | 425 |
