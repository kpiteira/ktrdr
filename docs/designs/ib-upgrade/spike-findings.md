# Spike Findings: ib_async Migration

## Test 1: Basic API Compatibility ✅

**Date:** 2026-01-20

### Import Compatibility

All required imports work identically:
```python
from ib_async import IB, Contract, Forex, Stock, Future
```

### Dataclass Change (v2.0)

Objects are now Python dataclasses (confirmed):
```
Stock is dataclass: True
Forex is dataclass: True
```

This is a **behavioral change** but not a breaking one for our use case.

### Contract Creation Patterns

All our patterns work without modification:

| Pattern | Result |
|---------|--------|
| `Stock('AAPL', 'SMART', 'USD')` | ✅ Works |
| `Forex('EURUSD')` | ✅ Works |
| `Forex(pair='EURUSD')` | ✅ Works |
| `Future(symbol='ES', exchange='CME')` | ✅ Works |

### Event Loop Handling

Basic event loop operations work:
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
# ... operations ...
loop.close()
```

### Connection Test

Skipped (IB Gateway not running on test machine). To be tested in live environment.

---

## Migration Impact Assessment

### Files Requiring Changes

| File | Change Type | Complexity |
|------|-------------|------------|
| `ib-host-service/ib/connection.py` | Import only | Low |
| `ib-host-service/ib/data_fetcher.py` | Import only | Low |
| `ib-host-service/ib/symbol_validator.py` | Import only | Low |
| `tests/host_service/conftest.py` | Import only | Low |
| `scripts/basic_ib_connection_check.py` | Import only | Low |

### Dataclass Serialization

The symbol_validator.py caches `ContractInfo` objects which contain IB `Contract` objects.
Need to verify that the cache load/save still works with dataclass contracts.

**Investigation needed:** Does `_recreate_contract_from_data()` work with dataclass contracts?

---

## Test 4: Dataclass Serialization ✅

Cache serialization works correctly with ib_async's dataclass contracts:

- Stock, Forex, Future all have extractable attributes
- JSON serialization works
- Contract recreation from cached data works
- Full round-trip (save/load) works

**No changes needed** to symbol_validator.py caching logic.

---

## Test 2: Threading Model Evaluation ✅

### Key Finding: `getLoop()` improvements

ib_async's `getLoop()` now:
- Does NOT cache loops (prevents stale loop bugs)
- Automatically creates new loop if current is closed
- Handles running vs non-running contexts correctly

```python
# After closing a loop, getLoop() creates a new one automatically
loop1 = util.getLoop()
loop1.close()
loop2 = util.getLoop()  # Returns NEW loop, not the closed one
```

### Two Migration Options

**Option A: Minimal Change (Recommended for now)**
- Just change imports from `ib_insync` to `ib_async`
- Keep dedicated thread pattern
- Existing code works unchanged
- Lower risk

**Option B: Pure Async Refactor (Future consideration)**
- Remove dedicated thread pattern
- Use `connectAsync()` and async methods throughout
- Cleaner architecture, better FastAPI integration
- More work, higher risk

### Why Dedicated Threads Still Make Sense

The fundamental issue remains:
- FastAPI runs in async context
- IB's sync methods block the event loop
- Need thread isolation OR pure async

Our current pattern works well. The ib_async improvements just make it more robust.

### Recommendation

**Phase 1 (now):** Import-only changes, keep threading model
**Phase 2 (future):** Consider async refactor if connection issues persist

---

## Next Steps

1. [ ] Test with live IB Gateway connection
2. [x] Verify cache serialization with dataclass contracts
3. [x] Evaluate threading model simplification opportunities
4. [x] Run full host service with ib_async imports (imports work)
