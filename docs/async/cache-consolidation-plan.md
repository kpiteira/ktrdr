# Backend Symbol Cache Consolidation Plan (Short-term)

## 🎯 OBJECTIVE

**Simple Goal**: Add symbol validation caching to the backend at the **DataLoadingOrchestrator** level, ensuring the intelligent data management layer manages the cache instead of the IB layer.

## 🚨 CURRENT PROBLEM

- **Host Service Cache**: `/ib-host-service/data/symbol_discovery_cache.json` (has GOOG, AAPL, etc.)
- **Backend**: No cache - validates same symbols repeatedly via host service
- **Issue**: DataLoadingOrchestrator calls validation every time, causing unnecessary host service calls

## 💡 SOLUTION DESIGN

**Cache Management at the Intelligent Layer**: Add caching to `DataLoadingOrchestrator` where symbol validation is triggered, not at the IB layer.

### Current Flow (No Backend Cache):
```
DataLoadingOrchestrator.load_with_fallback()
├─ Always calls: external_provider.validate_and_get_metadata(symbol)
├─ IbDataAdapter makes HTTP call to host service
├─ Host service uses its own cache
└─ Returns validation result (not cached in backend)
```

### New Flow (Backend Cache):
```
DataLoadingOrchestrator.load_with_fallback()
├─ Check backend cache first: symbol_cache.get(symbol)
│  ├─ Cache HIT: Use cached data, skip host service call
│  └─ Cache MISS: Continue to host service validation
├─ external_provider.validate_and_get_metadata(symbol)
├─ Cache validation result: symbol_cache.store(symbol, result)
└─ Continue with data loading
```

## 📋 IMPLEMENTATION STEPS

### Step 1: Create SymbolCache Component

**New file**: `/ktrdr/data/components/symbol_cache.py`

```python
@dataclass
class CachedSymbolInfo:
    """Cached symbol validation information."""
    validation_result: ValidationResult
    cached_at: float
    ttl_seconds: int = 86400 * 30  # 30 days like IB cache
    
    def is_expired(self) -> bool:
        return time.time() - self.cached_at > self.ttl_seconds
        
    def to_validation_result(self) -> ValidationResult:
        return self.validation_result

class SymbolCache:
    """Backend symbol validation cache managed by DataManager layer."""
    
    def __init__(self, cache_file: str = "data/backend_symbol_cache.json"):
        self._cache: dict[str, CachedSymbolInfo] = {}
        self._cache_file = Path(cache_file)
        self._load_cache()
    
    def get(self, symbol: str) -> Optional[CachedSymbolInfo]:
        """Get cached symbol info if valid."""
        info = self._cache.get(symbol.upper())
        if info and not info.is_expired():
            return info
        return None
    
    def store(self, symbol: str, validation_result: ValidationResult):
        """Cache validation result."""
        info = CachedSymbolInfo(
            validation_result=validation_result,
            cached_at=time.time()
        )
        self._cache[symbol.upper()] = info
        self._save_cache()
```

### Step 2: Integrate Cache into DataLoadingOrchestrator

**File to modify**: `/ktrdr/data/data_loading_orchestrator.py`

**Add to `__init__()` method**:
```python
# Add symbol cache for backend validation caching
from ktrdr.data.components.symbol_cache import SymbolCache
self.symbol_cache = SymbolCache()
```

**Modify validation logic** (around lines 80-91):
```python
# STEP 0A: Symbol validation and metadata lookup
logger.info("📋 STEP 0A: Symbol validation and metadata lookup")
self.data_manager._check_cancellation(cancellation_token, "symbol validation")

validation_result = None
cached_head_timestamp = None

if self.data_manager.external_provider:
    # NEW: Check backend cache first
    cached_info = self.symbol_cache.get(symbol)
    if cached_info:
        logger.info(f"💾 Backend cache HIT for {symbol}")
        validation_result = cached_info.to_validation_result()
    else:
        logger.info(f"💾 Backend cache MISS for {symbol} - validating via host service")
        try:
            # Existing validation call
            async def validate_async():
                return await self.data_manager.external_provider.validate_and_get_metadata(
                    symbol, [timeframe]
                )
            
            validation_result = asyncio.run(validate_async())
            
            # NEW: Cache the result in backend  
            self.symbol_cache.store(symbol, validation_result)
            logger.info(f"💾 Cached validation result for {symbol} in backend")
            
        except Exception as e:
            # ... existing error handling
```

### Step 3: Add Cache Management to DataManager

**File to modify**: `/ktrdr/data/data_manager.py`

**Add cache management methods**:
```python
def clear_symbol_cache(self):
    """Clear backend symbol cache."""
    if hasattr(self.data_loading_orchestrator, 'symbol_cache'):
        self.data_loading_orchestrator.symbol_cache.clear()
        
def get_symbol_cache_stats(self) -> dict:
    """Get backend symbol cache statistics."""
    if hasattr(self.data_loading_orchestrator, 'symbol_cache'):
        return self.data_loading_orchestrator.symbol_cache.get_stats()
    return {"cached_symbols": 0}
```

## ✅ SUCCESS CRITERIA

### Functional Requirements:
- [ ] Backend caches validation results from host service
- [ ] Cache hit/miss properly logged  
- [ ] No duplicate validation calls for same symbol
- [ ] Cache persists between application restarts
- [ ] Cache TTL respects 30-day expiration like IB cache

### Testing Scenarios:
- [ ] **First validation**: Symbol JEPI → cache miss → host service call → backend cache updated
- [ ] **Second validation**: Symbol JEPI → cache hit → no host service call
- [ ] **Cache expiry**: After TTL, symbol requires re-validation
- [ ] **Multiple symbols**: GOOG, AAPL, JEPI all cached independently
- [ ] **Application restart**: Cache loaded from file correctly

## 🔧 FILES TO CREATE/MODIFY

### New Files:
- `/ktrdr/data/components/symbol_cache.py` - Cache implementation
- `/data/backend_symbol_cache.json` - Cache storage file

### Modified Files:
- `/ktrdr/data/data_loading_orchestrator.py` - Add cache integration
- `/ktrdr/data/data_manager.py` - Add cache management methods

## ⚠️ CONSTRAINTS & CONSIDERATIONS

### What We're NOT Changing:
- Host service endpoints (can keep their cache)
- IbDataAdapter validation logic  
- IB connection or retry logic
- ValidationResult data structure

### What We ARE Adding:
- Backend-managed symbol cache
- Cache at the intelligent layer (DataLoadingOrchestrator)
- Cache management via DataManager
- Persistent cache storage

### Cache File Location:
- Backend cache: `/data/backend_symbol_cache.json`
- Host service cache: `/ib-host-service/data/symbol_discovery_cache.json` (unchanged)
- **Both can coexist - no conflict**

## 📈 IMMEDIATE BENEFITS

- **Reduced host service calls**: Cached symbols skip network requests
- **Faster data loading**: Cache hits avoid validation latency  
- **Better debugging**: Backend cache hit/miss visibility
- **Foundation for intelligence**: Cache managed by smart layer, not IB layer
- **Minimal risk**: Additive changes only, no existing logic modified

## 🎯 NEXT STEPS AFTER IMPLEMENTATION

1. **Monitor cache performance**: Track hit/miss ratios
2. **Consider cache warming**: Pre-populate common symbols
3. **Long-term**: Move toward full architectural refactor (separate plan)