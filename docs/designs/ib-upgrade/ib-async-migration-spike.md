# Spike: IB Host Service Migration to ib_async

## Context

Issue #248 proposes migrating from the archived `ib_insync` library to its actively maintained successor `ib_async`. The original maintainer (Ewald de Wit) passed away in early 2024, and the library is now archived.

**Current state:**
- `ib_insync` is only used in `ib-host-service/` (3 files) and test fixtures
- Backend/workers do NOT use IB directly (verified and dependency removed)
- The host service has a sophisticated threading model that deserves scrutiny

## Goals

1. **Validate migration feasibility** - Can we swap libraries with minimal changes?
2. **Assess threading model** - Is our current model optimal, or can `ib_async` simplify it?
3. **Identify risks** - What behavioral differences could cause issues?
4. **Prototype improvements** - Can we make the connection more robust?

## Research Findings

### ib_async Changes (from changelog)

**Event Loop Handling (v2.1.0):**
> "Non-cached event loop access to avoid stale loop issues"

This is directly relevant - our `connection.py` manually creates/destroys event loops to handle threading issues. The new library may handle this better.

**Breaking Changes (v2.0.0):**
- `qualifyContractsAsync()` now returns `None` for failed contracts (we use `reqContractDetails()` instead)
- Type system modernized to Python 3.10+ syntax
- Objects now use dataclasses (not base Object inheritance)

**Minimum Python:** 3.10+ (we're on 3.12-3.13, OK)

### Current Threading Model Analysis

Our `connection.py` uses a dedicated thread pattern:

```
Main Thread (FastAPI)
    │
    └── IbConnection Thread (dedicated, daemon)
            │
            ├── Creates own event loop
            ├── Maintains persistent IB connection
            ├── Processes requests via queue
            └── 3-minute idle timeout with cleanup
```

**Why this exists:**
- IB connections died when async API contexts ended (destroying event loops)
- Thread isolation prevents this
- Queue-based communication for thread safety

**Known issues in current code:**
1. `ib.isConnected()` can "lie" about connection state (line 269 comment)
2. Sleep/wake cycle detection needed (lines 654-678)
3. Manual event loop management is complex (lines 211-223, 287-299)

## Spike Tasks

### Task 1: Basic Migration Test (2-4 hours)

Create a minimal test script that:
1. Uses `ib_async` instead of `ib_insync`
2. Tests `IB.connect()` and `IB.connectAsync()`
3. Tests `reqContractDetails()` and `reqHistoricalData()`
4. Verifies Contract classes work identically

**Success criteria:** API calls work with just import changes

### Task 2: Threading Model Evaluation (4-6 hours)

Questions to answer:
1. Does `ib_async` still need our dedicated thread pattern?
2. Does the "non-cached event loop access" solve our issues?
3. Can we simplify the event loop management?

**Experiment:**
- Try running IB connection in main FastAPI thread
- Test connection persistence across multiple API requests
- Test behavior after simulated sleep/wake

### Task 3: Connection Reliability Testing (2-4 hours)

Test scenarios:
1. IB Gateway restart (does reconnect work?)
2. Network interruption simulation
3. Long idle periods (>3 minutes)
4. System sleep/wake cycle
5. Multiple rapid requests (pacing)

**Compare:** Current `ib_insync` behavior vs `ib_async` behavior

### Task 4: Dataclass Compatibility Check (1-2 hours)

Verify our code handles:
- `Contract` objects as dataclasses
- `Stock`, `Forex`, `Future` creation
- Serialization to/from JSON (for caching)

## Files to Modify

| File | Changes Expected |
|------|------------------|
| `ib-host-service/ib/connection.py` | Import + potential threading simplification |
| `ib-host-service/ib/data_fetcher.py` | Import only (uses Stock, Forex, Contract) |
| `ib-host-service/ib/symbol_validator.py` | Import + dataclass handling for cache |
| `tests/host_service/conftest.py` | Import only |
| `scripts/basic_ib_connection_check.py` | Import only |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API behavioral differences | Medium | High | Spike testing |
| Threading model incompatibility | Low | High | Evaluate in Task 2 |
| Dataclass serialization issues | Low | Medium | Test cache load/save |
| New bugs in maintained library | Low | Medium | Pin version, test thoroughly |

## Decision Points

After the spike, decide:

1. **Migration scope:**
   - Minimal (import changes only)
   - Moderate (import + simplify threading)
   - Full (rearchitect connection model)

2. **Threading model:**
   - Keep dedicated thread pattern
   - Try main-thread with improved event loop handling
   - Hybrid approach

3. **Timeline:**
   - Do it now (if spike shows minimal risk)
   - Defer (if significant rework needed)

## References

- [ib_async GitHub](https://github.com/ib-api-reloaded/ib_async)
- [ib_async Documentation](https://ib-api-reloaded.github.io/ib_async/)
- [ib_async Changelog](https://ib-api-reloaded.github.io/ib_async/changelog.html)
- [Issue #248](https://github.com/kpiteira/ktrdr/issues/248)

## Spike Output

After completing the spike, document:
1. Test results for each task
2. Recommended migration approach
3. Estimated effort for full migration
4. Any blockers or concerns discovered
