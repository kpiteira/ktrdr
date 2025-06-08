# KTRDR Timezone and Data Synchronization Analysis

## Executive Summary

Analysis of MSFT 1h data timing issues (May 31 - June 6, 2025) reveals multiple systemic problems:

1. **Symbol Validation Cache Flaws** - Aggressive TTL and permanent failed symbol marking
2. **Fallback Data Path Issues** - Different timezone handling when IB validation fails
3. **Chart Synchronization Bug** - Different data transformation paths causing time range mismatches
4. **Missing Trading Hours Metadata** - No timezone/session info stored for symbols

## Critical Finding: Failed Symbol Fallback Causes Wrong Timestamps

**Root Cause**: MSFT is in `failed_symbols` cache → triggers fallback data path → different timezone logic → wrong timestamps (15:00 UTC instead of 13:30 UTC)

## Detailed Analysis

### Issue 1: Symbol Cache Logic Flaws

**Problem**: Symbol validation cache has two critical design flaws:

1. **Too Aggressive TTL**: 1-hour cache expiration for stable symbols
```python
# ktrdr/data/ib_symbol_validator.py:65
self._cache_ttl = 3600  # 1 hour - TOO SHORT for stable symbols!
```

2. **Permanent Failed Symbol Marking**: Once a symbol fails (e.g., due to IB disconnect), it's marked as failed permanently
```python
# ktrdr/data/ib_symbol_validator.py:354-357
self._failed_symbols.add(normalized)
# No TTL or retry logic for failed symbols!
```

**Impact**: 
- Stable symbols like MSFT get re-validated every hour
- Temporary IB disconnects cause permanent symbol failures
- Failed symbols trigger fallback data paths with wrong timezone logic

**Evidence**: 
- All major symbols (MSFT, AAPL, GOOGL, etc.) are in failed_symbols list
- Cache is empty despite these being common, stable symbols

### Issue 2: Fallback Data Path Timezone Issues

**Problem**: When symbols are in `failed_symbols`, the system uses fallback logic with different timestamp handling

**Flow**:
1. MSFT lookup → found in `failed_symbols` → skip IB validation
2. Fallback to format-based classification: "MSFT" → 'stock'
3. Different data loading path → different timezone conversion
4. Results in 15:00 UTC (11:00 AM EDT) instead of proper 13:30 UTC (9:30 AM EDT)

**Proper IB Path**:
```python
# ib_data_fetcher_sync.py:357-361
if df.index.tz is None:
    df.index = df.index.tz_localize("UTC")
else:
    df.index = df.index.tz_convert("UTC")
```

**Fallback Path**: Uses different timezone logic (needs investigation)

### Issue 3: Chart Time Range Synchronization

**Problem**: Different charts show different time ranges after operations

**Evidence from Screenshots**:
- Main chart: 5/31 6:00 to 6/2 15:00
- Fuzzy chart: 5/30 23:00 to 6/2 8:00

**Root Cause**: Multiple data transformation paths:
- Main OHLCV data (via `/api/v1/data/load`)
- Fuzzy overlay data (via `/api/v1/fuzzy/data`) 
- Indicator calculations (separate API calls)

Each path may apply different timestamp transformations.

### Issue 4: Missing Trading Hours Metadata

**Problem**: No storage of exchange timezone or trading session information

**Current Symbol Cache**:
```typescript
interface ContractInfo {
  symbol: string
  asset_type: string
  exchange: string
  currency: string
  description: string
  validated_at: float
  // Missing: timezone, trading_hours, session_times
}
```

**Impact**: Cannot display data in exchange local time or validate trading sessions

## Comprehensive Solutions

### Solution 1: Fix Symbol Cache Logic

**A. Never Mark Previously Validated Symbols as Failed**:
```python
# ktrdr/data/ib_symbol_validator.py
class IbSymbolValidator:
    def __init__(self, ...):
        self._cache_ttl = 86400 * 30  # 30 days for re-validation
        self._validated_symbols: Set[str] = set()  # Permanently validated symbols
        # Remove _failed_symbols logic for previously validated symbols
```

**B. Protected Re-validation Logic**:
```python
def get_contract_details(self, symbol: str) -> Optional[ContractInfo]:
    normalized = self._normalize_symbol(symbol)
    
    # Check if symbol was ever validated successfully
    if normalized in self._validated_symbols:
        # Previously validated - NEVER mark as failed, only re-validate on TTL
        if self._is_cache_valid(normalized):
            return self._cache[normalized]
        else:
            # Cache expired - re-validate but don't fail on connection issues
            try:
                contract_info = self._attempt_validation(normalized)
                if contract_info:
                    self._cache[normalized] = contract_info
                    return contract_info
                else:
                    # Connection issue - return None but DON'T mark as failed
                    logger.warning(f"Re-validation failed for {normalized} (connection issue), keeping as valid")
                    return None
            except Exception as e:
                logger.warning(f"Re-validation error for {normalized}: {e}")
                return None
    else:
        # Never validated - normal validation with failure tracking
        return self._normal_validation(normalized)

def _mark_symbol_validated(self, symbol: str, contract_info: ContractInfo):
    """Mark symbol as permanently validated."""
    self._validated_symbols.add(symbol)
    self._cache[symbol] = contract_info
    # Remove from failed symbols if it was there
    self._failed_symbols.discard(symbol)
```

**C. Only New Symbols Can Fail**:
```python
def _normal_validation(self, symbol: str) -> Optional[ContractInfo]:
    """Normal validation for never-before-validated symbols."""
    # Check failed symbols cache (only for new symbols)
    if symbol in self._failed_symbols:
        return None
    
    # Attempt validation...
    contract_info = self._attempt_validation(symbol)
    if contract_info:
        self._mark_symbol_validated(symbol, contract_info)
        return contract_info
    else:
        # Mark as failed (only for new symbols)
        self._failed_symbols.add(symbol)
        return None
```

### Solution 2: Enhanced Symbol Cache with Trading Hours

**Expand ContractInfo Structure**:
```python
@dataclass
class ContractInfo:
    symbol: str
    contract: Contract
    asset_type: str
    exchange: str
    currency: str
    description: str
    validated_at: float
    # New fields:
    timezone: str  # e.g., "America/New_York"
    trading_hours: Dict[str, str]  # e.g., {"regular": "09:30-16:00"}
    market_calendar: Optional[str]  # Holiday calendar reference
```

**Fetch Trading Hours During Validation**:
```python
def _lookup_contract(self, contract: Contract) -> Optional[ContractInfo]:
    # ... existing contract lookup ...
    
    # Get trading hours if available
    trading_hours = self._get_trading_hours(contract)
    timezone = self._get_exchange_timezone(contract.primaryExchange)
    
    return ContractInfo(
        # ... existing fields ...
        timezone=timezone,
        trading_hours=trading_hours,
        market_calendar=self._get_market_calendar(contract.primaryExchange)
    )
```

### Solution 3: Unified Timestamp Handling - "Always UTC Internally, Display Locally"

**Core Principle**: All internal data manipulation uses UTC timestamps. Only endpoints (CLI/UI) convert to local timezone for display.

**Create Centralized Timezone Utility**:
```python
# ktrdr/utils/timezone_utils.py
class TimestampManager:
    """Centralized timestamp handling - always UTC internally."""
    
    @staticmethod
    def to_utc(dt: Union[datetime, pd.Timestamp, str]) -> pd.Timestamp:
        """Convert any datetime to UTC timezone-aware timestamp."""
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        if isinstance(dt, datetime):
            dt = pd.Timestamp(dt)
        
        if dt.tz is None:
            # Assume UTC if no timezone info
            return dt.tz_localize('UTC')
        else:
            return dt.tz_convert('UTC')
    
    @staticmethod
    def to_exchange_time(utc_timestamp: pd.Timestamp, exchange_tz: str) -> pd.Timestamp:
        """Convert UTC timestamp to exchange timezone (for display only)."""
        return utc_timestamp.tz_convert(exchange_tz)
    
    @staticmethod
    def format_for_display(utc_timestamp: pd.Timestamp, display_tz: str = 'UTC') -> str:
        """Format UTC timestamp for display in specified timezone."""
        if display_tz == 'UTC':
            return utc_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            local_time = utc_timestamp.tz_convert(display_tz)
            return local_time.strftime('%Y-%m-%d %H:%M:%S %Z')
```

**Apply Consistently Across ALL Data Paths**:
1. **IB data fetcher** ✓ (already implemented)
2. **Fallback data loader** - Use TimestampManager.to_utc()
3. **API data transformations** - Always return UTC, add display_timezone option
4. **Frontend chart data** - Receive UTC, convert for display only
5. **Database storage** - Always store UTC
6. **CSV files** - Always save/load UTC

**CRITICAL: DataManager and Data Acquisition Systems**

The DataManager and all data acquisition/saving systems are the most critical chokepoints for timezone consistency. These must be meticulously clean:

```python
# DataManager - The Central Coordinator (MUST enforce UTC everywhere)
class DataManager:
    def load_data(self, symbol: str, timeframe: str, mode: str = "auto", **kwargs):
        """Load data with guaranteed UTC timestamps regardless of source."""
        
        # Route to appropriate loader based on mode
        if mode == "ib" or (mode == "auto" and self._should_use_ib(symbol)):
            df = self._ib_loader.fetch_data(symbol, timeframe, **kwargs)
        else:
            df = self._local_loader.load_data(symbol, timeframe, **kwargs)
        
        # CRITICAL: Guarantee UTC conversion regardless of source
        if df is not None and not df.empty:
            df.index = TimestampManager.to_utc(df.index)
            
            # Validate timezone consistency before returning
            self._validate_timezone_consistency(df)
        
        return df
    
    def save_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Save data with guaranteed UTC timestamps."""
        # CRITICAL: Ensure UTC before saving
        if df.index.tz is None:
            logger.error(f"Attempting to save timezone-naive data for {symbol}!")
            df.index = TimestampManager.to_utc(df.index)
        elif df.index.tz != pytz.UTC:
            logger.warning(f"Converting non-UTC data to UTC before saving {symbol}")
            df.index = df.index.tz_convert('UTC')
        
        # Save with explicit UTC marker in filename/metadata
        self._local_loader.save_data(df, symbol, timeframe, timezone_marker="UTC")

# IB Data Acquisition (Entry point from external source)
class IbDataLoader:
    def fetch_data(self, symbol: str, timeframe: str, **kwargs):
        """Fetch from IB with immediate UTC conversion."""
        raw_df = self._fetch_from_ib(symbol, timeframe, **kwargs)
        
        # CRITICAL: Convert to UTC immediately upon acquisition
        if raw_df is not None and not raw_df.empty:
            raw_df.index = TimestampManager.to_utc(raw_df.index)
            logger.info(f"IB data for {symbol} converted to UTC: {raw_df.index[0]} to {raw_df.index[-1]}")
        
        return raw_df

# Local Data Storage/Loading (File I/O boundary)
class LocalDataLoader:
    def save_data(self, df: pd.DataFrame, symbol: str, timeframe: str, timezone_marker: str = "UTC"):
        """Save with explicit timezone documentation."""
        # CRITICAL: Validate UTC before saving to file
        if not df.index.tz or df.index.tz != pytz.UTC:
            raise ValueError(f"Can only save UTC data! Got: {df.index.tz}")
        
        # Save with timezone metadata
        metadata = {
            "timezone": "UTC",
            "saved_at": pd.Timestamp.now(tz='UTC').isoformat(),
            "symbol": symbol,
            "timeframe": timeframe
        }
        
        # Include timezone info in file format
        self._save_with_metadata(df, symbol, timeframe, metadata)
    
    def load_data(self, symbol: str, timeframe: str):
        """Load with timezone validation."""
        df, metadata = self._load_with_metadata(symbol, timeframe)
        
        if df is not None and not df.empty:
            # CRITICAL: Validate loaded data timezone
            expected_tz = metadata.get("timezone", "UNKNOWN")
            if expected_tz != "UTC":
                logger.error(f"Loaded data for {symbol} has wrong timezone: {expected_tz}")
            
            # Ensure UTC regardless of what was loaded
            df.index = TimestampManager.to_utc(df.index)
        
        return df

# Validation Helper
def _validate_timezone_consistency(self, df: pd.DataFrame):
    """Validate that DataFrame has proper UTC timezone."""
    if df.index.tz is None:
        raise ValueError("DataFrame has timezone-naive index!")
    if df.index.tz != pytz.UTC:
        raise ValueError(f"DataFrame has non-UTC timezone: {df.index.tz}")
    
    # Additional sanity checks
    if len(df) > 0:
        first_ts = df.index[0]
        last_ts = df.index[-1]
        logger.debug(f"Timezone validation passed: {first_ts} to {last_ts} (UTC)")
```

**Key Enforcement Points:**
1. **DataManager.load_data()** - Always returns UTC regardless of source
2. **DataManager.save_data()** - Validates UTC before saving
3. **IbDataLoader.fetch_data()** - Converts to UTC immediately upon acquisition
4. **LocalDataLoader** - Saves/loads with timezone metadata validation
5. **File Format** - Include timezone metadata in saved files

### Solution 4: Fix Chart Synchronization

**Ensure Consistent Time Ranges**:
```python
# In API responses, include time range metadata
{
  "data": [...],
  "metadata": {
    "time_range": {
      "start": "2025-05-31T13:30:00Z",
      "end": "2025-06-06T20:00:00Z",
      "timezone": "UTC"
    },
    "source": "ib_validated"  # vs "fallback"
  }
}
```

**Frontend Chart Synchronization**:
- Use shared time range context
- Validate all charts use same time bounds
- Add debugging to track time range divergence

### Solution 5: Trading Hours Configuration

**Add API Support for Trading Hours**:
```python
# New endpoint: GET /api/v1/symbols/{symbol}/trading-hours
{
  "symbol": "MSFT",
  "exchange": "NASDAQ",
  "timezone": "America/New_York",
  "sessions": {
    "regular": {"start": "09:30", "end": "16:00"},
    "pre_market": {"start": "04:00", "end": "09:30"},
    "after_hours": {"start": "16:00", "end": "20:00"}
  }
}
```

**Add Data Loading Options**:
```python
# Support session filtering
POST /api/v1/data/load
{
  "symbol": "MSFT",
  "timeframe": "1h",
  "session": "regular",  # "regular" | "extended" | "all"
  "timezone_display": "exchange"  # "utc" | "exchange"
}
```

## Implementation Priority

### Phase 0: Data Cleanup (FIRST!)
**CRITICAL**: Existing data files may be poisoned with wrong timestamps. Before implementing fixes:

1. **Backup existing data** - Move current data files to backup folder
2. **Clear all cached data** - Delete CSV files, cache files, and symbol cache
3. **Reconnect to IB** - Fresh data download after timezone fixes
4. **Verify clean timestamps** - Ensure 9:30 AM market open shows as 13:30 UTC

```bash
# Data cleanup steps
mkdir -p data/backup_$(date +%Y%m%d)
mv data/*.csv data/backup_*/
mv data/symbol_discovery_cache.json data/backup_*/
rm -rf data/cache/  # Clear any other cached data

# After implementing fixes, fresh download:
# Connect to IB and re-download MSFT 1h data for May 31 - June 6, 2025
```

### Phase 1: Critical Fixes (Immediate)
1. **Fix symbol cache logic** - Never mark validated symbols as failed
2. **Implement unified timestamp handling** - TimestampManager for all data paths  
3. **Fix fallback data timezone** - Use same UTC conversion as IB path
4. **Test with clean data** - Verify MSFT timing shows 13:30 UTC market open

### Phase 2: Data Consistency (Short-term)  
1. **Enhanced symbol cache** - Store trading hours metadata
2. **API enhancements** - Trading hours endpoints and display options
3. **Chart synchronization** - Consistent time range handling across all charts
4. **Comprehensive testing** - All symbols, timeframes, and chart types

### Phase 3: User Experience (Medium-term)
1. **Trading session filtering** - Regular vs extended hours options
2. **Exchange timezone display** - Show times in local exchange time  
3. **Market calendar integration** - Handle holidays and special sessions

## Test Plan

### Test 1: Symbol Cache Fix
```bash
# Clear cache and test symbol validation
uv run python -c "
from ktrdr.data.ib_symbol_validator import IbSymbolValidator
validator = IbSymbolValidator()
validator.clear_cache()
result = validator.validate_symbol('MSFT')
print(f'MSFT validation: {result}')
print(f'Cache stats: {validator.get_cache_stats()}')
"
```

### Test 2: Data Timing Verification
```bash
# Test MSFT data timing after cache fix
curl -X POST "http://localhost:8000/api/v1/data/load" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "MSFT",
    "timeframe": "1h", 
    "start_date": "2025-05-31",
    "end_date": "2025-06-06"
  }' | jq '.data.ohlcv[0:3]'  # Check first few timestamps
```

### Test 3: Chart Synchronization
1. Load MSFT data in UI
2. Add indicators and fuzzy overlays  
3. Verify all charts show identical time ranges
4. Check browser console for time range debugging info

## Files Requiring Changes

### Core Symbol Validation
- `ktrdr/data/ib_symbol_validator.py` - Fix cache TTL and failed symbol logic

### Data Loading
- `ktrdr/data/ib_data_loader.py` - Improve fallback timezone handling
- `ktrdr/data/data_manager.py` - Unified timestamp utilities

### API Layer
- `ktrdr/api/endpoints/data.py` - Add trading hours support
- `ktrdr/api/models/data.py` - Enhanced response models
- `ktrdr/api/services/data_service.py` - Trading hours integration

### Frontend
- `frontend/src/api/endpoints/` - Support new API features
- `frontend/src/components/presentation/charts/` - Consistent timestamp handling
- `frontend/src/components/SymbolSelector.tsx` - Display timezone info

This analysis provides a comprehensive plan to fix the timezone and synchronization issues systematically, treating root causes rather than symptoms.