# IB Connector Host Service

A lightweight FastAPI service that runs directly on the host machine to provide reliable IB Gateway connectivity, bypassing Docker networking issues that cause frequent disconnections.

## Overview

This service wraps the existing `ktrdr.ib` modules with HTTP endpoints that the containerized backend can call. It solves the critical Docker networking problems with IB Gateway while reusing all existing IB integration code.

## Quick Start

1. **Ensure IB Gateway is running** on your machine
2. **Start the service**:
   ```bash
   ./start.sh
   ```
3. **Test the service**:
   ```bash
   curl http://localhost:5001/health
   ```

## API Endpoints

### Health & Status
- `GET /` - Service information
- `GET /health` - Basic health check  
- `GET /health/detailed` - Detailed connection status

### Data Operations
- `POST /data/historical` - Fetch historical OHLCV data
- `POST /data/validate` - Validate symbol and get metadata
- `GET /data/head-timestamp` - Get earliest available timestamp

## Integration with Backend

The containerized backend uses these endpoints through the modified `IbDataAdapter` when `USE_IB_HOST_SERVICE=true` is set.

## Architecture

```
Docker Backend → HTTP → Host Service → IB Gateway
               (5001)  (localhost)     (4002)
```

**Benefits:**
- ✅ Direct host network connection to IB Gateway
- ✅ No Docker socket/networking layer interference  
- ✅ Reuses existing `ktrdr.ib` code (no duplication)
- ✅ Easy rollback via environment variable

## Configuration

The service uses YAML-based configuration consistent with KTRDR patterns:

- **IB Settings**: Uses existing `ktrdr.config.ib_config` for IB Gateway connection
- **Host Service Settings**: Configured via `config/ib_host_service.yaml`

### Configuration File

Create or modify `config/ib_host_service.yaml`:

```yaml
host_service:
  host: "127.0.0.1"  # Localhost only for security
  port: 5001         # Service port
  log_level: "INFO"  # Logging level
```

If no config file exists, sensible defaults are used.

## Logging

Logs to console with INFO level by default. Compatible with existing ktrdr logging patterns.