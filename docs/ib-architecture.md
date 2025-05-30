# IB Integration Architecture

This document describes the new persistent IB integration architecture that provides:
- Self-managing connections independent of API requests  
- Automatic gap filling for market data
- Host-side port forwarding for Docker container access

## Components

### 1. Host-Side Port Forwarding

**Script**: `scripts/ib_port_forward.sh`

Creates a port forward from host port 4003 to IB Gateway on localhost:4002, allowing Docker containers to access IB Gateway via `host.docker.internal:4003`.

**Usage**:
```bash
# Start port forwarding (run on host before starting containers)
./scripts/ib_port_forward.sh
```

**Requirements**: `socat` (`brew install socat` on macOS)

### 2. Persistent IB Connection Manager

**Module**: `ktrdr.data.ib_connection_manager`

Manages a persistent IB connection that:
- Starts automatically when the API starts
- Uses sequential client IDs (1, 2, 3...) instead of random
- Auto-reconnects on failure with progressive backoff
- Runs independently in background thread
- Provides connection status to other components

**Key Features**:
- Singleton pattern - only one instance per application
- Thread-safe connection management
- Progressive retry delays: 5s, 10s, 30s, 60s, 2m, 5m
- Client ID cycling (1-50, then resets)
- Connection health monitoring

### 3. Automatic Gap Filling Service

**Module**: `ktrdr.data.ib_gap_filler`

Automatically fills gaps in market data by:
- Scanning CSV files every 5 minutes for data gaps
- Fetching missing data when IB connection is available
- Updating local CSV files with new data
- Processing symbols in batches to avoid overwhelming IB

**Configuration**:
- Check interval: 5 minutes
- Max gap age: 30 days
- Batch size: 5 symbols per cycle
- Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d

### 4. Updated DataManager

**Module**: `ktrdr.data.data_manager`

Now uses the persistent connection manager instead of creating its own connections:
- No lazy initialization
- If no IB connection available, returns local data only
- No attempt to connect from API requests
- Simplified connection logic

## Usage

### Starting the System

1. **Start IB Gateway/TWS** on the host
2. **Start port forwarding**:
   ```bash
   ./scripts/ib_port_forward.sh
   ```
3. **Start Docker containers**:
   ```bash
   docker-compose -f docker/docker-compose.yml up
   ```

The persistent IB connection manager and gap filling service will start automatically with the API.

### Monitoring

Monitor services via API endpoints:

- **IB Connection Status**: `GET /api/v1/system/ib-status`
- **Gap Filler Status**: `GET /api/v1/system/gap-filler-status`  
- **Overall System Status**: `GET /api/v1/system/system-status`
- **Force Gap Scan**: `POST /api/v1/system/gap-filler/force-scan`

### Configuration

Environment variables in `docker-compose.yml`:
```yaml
- IB_HOST=host.docker.internal  # Use port forwarding
- IB_PORT=4003                  # Forwarded port
- IB_CLIENT_ID=1               # Starting client ID
```

## Architecture Benefits

1. **Reliability**: Persistent connections with auto-reconnect
2. **Independence**: Background services independent of API requests
3. **Efficiency**: Single shared connection for all operations
4. **Automation**: Automatic gap filling without manual intervention
5. **Monitoring**: Comprehensive status endpoints for observability
6. **Docker-friendly**: Host port forwarding eliminates networking issues

## Troubleshooting

### Connection Issues
- Check if IB Gateway/TWS is running and logged in
- Verify port forwarding script is running
- Check `GET /api/v1/system/ib-status` for connection details
- Look for client ID conflicts (auto-resolved by sequential IDs)

### Gap Filling Issues  
- Monitor `GET /api/v1/system/gap-filler-status` for statistics
- Use `POST /api/v1/system/gap-filler/force-scan` to trigger immediate scan
- Check Docker logs for gap filling service messages

### Docker Issues
- Ensure `host.docker.internal` is available in container
- Verify port forwarding is working: `curl host.docker.internal:4003` from inside container
- Check environment variables are set correctly