# Data Module Guidelines

## 🚨 IB GATEWAY CRITICAL REQUIREMENTS

**MUST READ**: `docs/ib-connection-lessons-learned.md` before ANY IB changes

### Connection Rules:
1. **Wait for "Synchronization complete"** (minimum 2 seconds after connect)
2. **Max 3 client ID retry attempts** to avoid corrupting IB Gateway
3. **1-2 second delays** between connection attempts
4. **Conservative health checks** - no heavy API calls during validation

**⚠️ WARNING**: Ignoring these WILL corrupt IB Gateway's socket state

## 📊 DATA MODULE PATTERNS

### DataManager is the ONLY Entry Point
```python
# ❌ Bad - Direct IB access
ib_client = IBClient()
data = ib_client.get_data()

# ✅ Good - Through DataManager
data_manager = DataManager()
data = data_manager.load_data(symbol, timeframe)
```

### Timezone-Aware Timestamps
```python
# ❌ Bad - Naive timestamp
timestamp = pd.Timestamp.now()

# ✅ Good - UTC aware
timestamp = pd.Timestamp.now(tz='UTC')
```

## 🚫 DATA MODULE ANTI-PATTERNS

❌ Assuming IB connection is instant
✅ Wait for synchronization complete

❌ Unlimited connection retries
✅ Max 3 attempts with delays

❌ Direct CSV file manipulation
✅ Use DataManager methods

❌ Mixing naive and aware timestamps
✅ Always use UTC-aware timestamps

## 📁 FILE STRUCTURE

CSV files location: `data/{timeframe}/{symbol}_{timeframe}.csv`

Format:
- Index: UTC timestamps
- Columns: open, high, low, close, volume
- No missing values in saved data

## 🔧 COMMON DATA TASKS

### Loading with gap detection:
```python
data = data_manager.load_data(
    symbol="AAPL",
    timeframe="1h", 
    mode="tail"  # or "backfill", "full"
)
```

### Handling IB errors:
- Pace violations: Automatic backoff
- Connection lost: Reconnect with new client ID
- No data: Return empty with proper error

## ⚠️ PERFORMANCE NOTES

- Cache loaded data in memory
- Use vectorized pandas operations
- Batch IB requests when possible
- Monitor memory usage for large datasets