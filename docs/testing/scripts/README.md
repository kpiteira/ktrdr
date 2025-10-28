# Testing Scripts

Helper scripts for running integration tests smoothly.

## Available Scripts

### 1. monitor_progress.sh

Monitor operation progress with automatic polling.

**Usage:**
```bash
./monitor_progress.sh <operation_id> [interval_seconds] [max_polls]
```

**Examples:**
```bash
# Monitor with defaults (5s interval, 20 polls max)
./monitor_progress.sh op_data_load_20251028_123456

# Monitor every 10s, up to 12 polls (2 minutes)
./monitor_progress.sh op_data_load_20251028_123456 10 12

# Monitor training (longer duration)
./monitor_progress.sh op_training_20251028_123456 15 40
```

**Features:**
- Automatic polling with configurable interval
- Stops automatically when operation completes or fails
- Shows status, percentage, current step, and items processed
- Final summary with complete results

### 2. manage_cache.sh

Manage data cache files for testing (backup/restore/delete/clean).

**Usage:**
```bash
./manage_cache.sh <action> <symbol> <timeframe>
```

**Actions:**
- `backup` - Backup existing cache file (moves to .backup)
- `restore` - Restore backed up cache file
- `delete` - Delete cache file (keeps backup if exists)
- `clean` - Remove both cache and backup

**Examples:**
```bash
# Backup before test
./manage_cache.sh backup EURUSD 1h

# Delete cache to force IB download
./manage_cache.sh delete EURUSD 1h

# Restore after test
./manage_cache.sh restore EURUSD 1h

# Clean up everything
./manage_cache.sh clean AAPL 1d
```

## Common Test Workflows

### Data Download Test (D3.1, D3.2, D3.3)

```bash
# 1. Backup existing cache
./docs/testing/scripts/manage_cache.sh backup EURUSD 1h

# 2. Start download
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/data/load \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h","start_date":"2024-01-01","end_date":"2024-12-31","mode":"tail"}')
OPERATION_ID=$(echo "$RESPONSE" | jq -r '.data.operation_id')

# 3. Monitor progress
./docs/testing/scripts/monitor_progress.sh "$OPERATION_ID" 10 12

# 4. Restore original cache
./docs/testing/scripts/manage_cache.sh restore EURUSD 1h
```

### Training Test (1.1, 1.2)

```bash
# Start training
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols":["EURUSD"],"timeframes":["5m"],"strategy_name":"test_e2e_local_pull","start_date":"2023-01-01","end_date":"2025-01-01"}')
TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')

# Monitor progress (5s intervals for faster updates)
./docs/testing/scripts/monitor_progress.sh "$TASK_ID" 5 20
```

## Prerequisites

All scripts require:
- `curl` for API calls
- `jq` for JSON parsing
- Backend running on port 8000
- Proper permissions to read/write in `data/` directory

## Troubleshooting

### Permission Denied
```bash
chmod +x docs/testing/scripts/*.sh
```

### jq not found
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

### Cache file not found
Verify the file exists:
```bash
ls -lh data/EURUSD_1h.csv
```

Check if backup exists:
```bash
ls -lh data/EURUSD_1h.csv.backup
```
