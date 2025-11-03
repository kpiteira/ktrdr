# Data Module Guidelines

## 🚨 IB GATEWAY CRITICAL REQUIREMENTS

**MUST READ**: `docs/architecture/data/IB-IMPORT-PROHIBITION.md` before ANY IB changes

### Connection Rules

1. **Wait for "Synchronization complete"** (minimum 2 seconds after connect)
2. **Max 3 client ID retry attempts** to avoid corrupting IB Gateway
3. **1-2 second delays** between connection attempts
4. **Conservative health checks** - no heavy API calls during validation

**⚠️ WARNING**: Ignoring these WILL corrupt IB Gateway's socket state

## 📊 NEW DATA ARCHITECTURE (Phase 5 Complete)

### Repository + Acquisition Pattern

The data module now uses a clean separation between cached data access and external data downloads:

```python
# ✅ For reading cached data - DataRepository
from ktrdr.data.repository.data_repository import DataRepository

repository = DataRepository()
data = repository.load(symbol="AAPL", timeframe="1d")

# ✅ For downloading new data - DataAcquisitionService
from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService

acquisition_service = DataAcquisitionService()
result = await acquisition_service.download_data(
    symbol="AAPL",
    timeframe="1h",
    mode="tail"
)
```

### ❌ What NOT to Do

```python
# ❌ Bad - DataManager no longer exists (removed in Phase 5)
data_manager = DataManager()  # This will fail!

# ❌ Bad - Direct IB access (violates architecture)
ib_client = IBClient()
data = ib_client.get_data()

# ❌ Bad - Direct CSV manipulation
with open("data/1d/AAPL_1d.csv") as f:
    data = pd.read_csv(f)
```

### ✅ Correct Patterns

```python
# ✅ Reading cached data
repository = DataRepository()
data = repository.load(symbol="AAPL", timeframe="1d")
symbols = repository.list_symbols()
date_range = repository.get_date_range(symbol="AAPL", timeframe="1d")

# ✅ Downloading new data (async)
acquisition_service = DataAcquisitionService()
result = await acquisition_service.download_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-12-31",
    mode="tail"  # or "backfill", "full"
)
```

## 🏗️ ARCHITECTURE COMPONENTS

### DataRepository
- **Purpose**: Access cached OHLCV data
- **Location**: `ktrdr/data/repository/data_repository.py`
- **Operations**: load, save, list_symbols, get_date_range, has_data

### DataAcquisitionService
- **Purpose**: Download data from external providers (IB)
- **Location**: `ktrdr/data/acquisition/acquisition_service.py`
- **Features**: Gap analysis, progress tracking, operation management

### IbDataProvider
- **Purpose**: Interface to IB Gateway (used by DataAcquisitionService)
- **Location**: `ktrdr/data/acquisition/ib_data_provider.py`
- **Note**: Runs in host service for Docker compatibility

## 🚫 DATA MODULE ANTI-PATTERNS

❌ Assuming IB connection is instant
✅ Wait for synchronization complete

❌ Unlimited connection retries
✅ Max 3 attempts with delays

❌ Direct CSV file manipulation
✅ Use DataRepository for all file operations

❌ Mixing naive and aware timestamps
✅ Always use UTC-aware timestamps

❌ Mixing read and write operations
✅ DataRepository for reads, DataAcquisitionService for writes

## 📁 FILE STRUCTURE

CSV files location: `data/{timeframe}/{symbol}_{timeframe}.csv`

Format:
- Index: UTC timestamps
- Columns: open, high, low, close, volume
- No missing values in saved data

## 🔧 COMMON DATA TASKS

### Loading cached data

```python
repository = DataRepository()
data = repository.load(symbol="AAPL", timeframe="1d")
```

### Downloading new data with gap detection

```python
acquisition_service = DataAcquisitionService()
result = await acquisition_service.download_data(
    symbol="AAPL",
    timeframe="1h",
    mode="tail"  # Fill recent gaps
)
```

### Checking data availability

```python
repository = DataRepository()
has_data = repository.has_data(symbol="AAPL", timeframe="1d")
date_range = repository.get_date_range(symbol="AAPL", timeframe="1d")
```

### Handling IB errors

- Pace violations: Automatic backoff via IbDataProvider
- Connection lost: Reconnect with new client ID
- No data: Return empty with proper error

## ⚠️ PERFORMANCE NOTES

- Cache loaded data in memory
- Use vectorized pandas operations
- DataRepository uses local file cache for speed
- DataAcquisitionService batches IB requests
- Monitor memory usage for large datasets

## 🔀 MIGRATION FROM OLD ARCHITECTURE

If you see code referencing DataManager:
1. For data reads → Use DataRepository
2. For data downloads → Use DataAcquisitionService
3. DataManager was deleted in Phase 5

See `docs/architecture/data/03-implementation-plan-v2-revised.md` for complete migration guide.
