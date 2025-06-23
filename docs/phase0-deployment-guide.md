# Phase 0 Deployment Guide: IB Host Service

## Overview

Phase 0 solves the critical Docker networking issues with IB Gateway by moving the IB connector to run directly on the host machine. This provides stable, direct network connectivity while keeping the rest of the system in Docker containers.

## Architecture

```
┌─────────────────── Host Machine ───────────────────┐
│                                                     │
│  ┌─────────────────┐     ┌─────────────────────┐   │
│  │  IB Gateway     │◄────┤ IB Host Service     │   │
│  │  (Port 4002)    │     │ (Port 5001)        │   │  
│  └─────────────────┘     └─────────────────────┘   │
│                               ▲                     │
└───────────────────────────────┼─────────────────────┘
                                │ HTTP
                                │
┌─────────────── Docker ────────┼─────────────────────┐
│                               ▼                     │
│  ┌─────────────────┐     ┌─────────────────────┐   │
│  │    Frontend     │◄────┤     Backend         │   │
│  │  (React)        │     │   (FastAPI)        │   │
│  └─────────────────┘     └─────────────────────┘   │
│                                                     │
│  ┌─────────────────┐     ┌─────────────────────┐   │
│  │   PostgreSQL    │     │      Redis          │   │
│  └─────────────────┘     └─────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start IB Host Service

```bash
# From project root
cd ib-host-service
./start.sh
```

The service will start on `http://localhost:5001` and show available endpoints.

### 2. Enable Host Service Mode

**Option A: Environment Variable (Temporary)**
```bash
# In docker/ directory
USE_IB_HOST_SERVICE=true docker-compose up backend -d
```

**Option B: Configuration File (Persistent)**
```bash
# Edit config/settings.yaml
ib_host_service:
  enabled: true
  url: "http://localhost:5001"
```

### 3. Verify Integration

**Check backend logs:**
```bash
docker logs ktrdr-backend | grep "host service"
```

Should show: `"IB integration enabled using host service at http://host.docker.internal:5001"`

**Test IB status endpoint:**
```bash
curl http://localhost:8000/api/v1/ib/status
```

Should show `"host": "http://host.docker.internal:5001"` and `"port": 5001`.

## Configuration Methods

### Method 1: YAML Configuration (Recommended)

**File:** `config/settings.yaml`
```yaml
ib_host_service:
  enabled: true  # Enable host service mode
  url: "http://localhost:5001"  # Host service URL
```

### Method 2: Environment Variables

**For Docker:**
```bash
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://host.docker.internal:5001
```

**For development:**
```bash
export USE_IB_HOST_SERVICE=true
export IB_HOST_SERVICE_URL=http://localhost:5001
```

### Method 3: Environment Override Files

**Create:** `config/environment/ib_host_service_enabled.yaml`
```yaml
ib_host_service:
  enabled: true
  url: "http://localhost:5001"
```

**Use:**
```bash
IB_HOST_SERVICE_CONFIG=ib_host_service_enabled docker-compose up -d
```

## Service Management

### Starting/Stopping Host Service

**Manual start:**
```bash
cd ib-host-service
uv run python main.py
```

**Background start (macOS/Linux):**
```bash
cd ib-host-service
nohup ./start.sh > service.log 2>&1 &
```

**Stop service:**
```bash
# Find and kill the process
ps aux | grep "main.py"
kill <PID>
```

### Health Monitoring

**Basic health check:**
```bash
curl http://localhost:5001/health
```

**Detailed status:**
```bash
curl http://localhost:5001/health/detailed
```

**Service info:**
```bash
curl http://localhost:5001/
```

## Troubleshooting

### Common Issues

**1. "Host service request failed"**
- **Cause**: Host service not running or network connectivity issue
- **Solution**: Check if service is running on port 5001
- **Test**: `curl http://localhost:5001/health`

**2. "Connection refused to host.docker.internal:5001"**
- **Cause**: Docker can't reach host service
- **Solution**: Ensure Docker has host.docker.internal configured
- **Test**: `docker exec ktrdr-backend curl http://host.docker.internal:5001/health`

**3. "IB Gateway connection timeout"**
- **Cause**: IB Gateway not running or incorrect configuration
- **Solution**: Start IB Gateway and check port 4002
- **Test**: Direct connection to IB Gateway

**4. Backend still showing direct connection**
- **Cause**: Environment variables not properly set
- **Solution**: Check `docker exec ktrdr-backend env | grep IB`
- **Expected**: `USE_IB_HOST_SERVICE=true`

### Validation Steps

**1. Check host service is running:**
```bash
curl -s http://localhost:5001/ | jq .service
# Expected: "IB Connector Host Service"
```

**2. Verify Docker backend configuration:**
```bash
docker exec ktrdr-backend env | grep IB
# Expected: USE_IB_HOST_SERVICE=true
```

**3. Test backend-to-host communication:**
```bash
docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health
# Expected: {"healthy":true,"service":"ib-connector",...}
```

**4. Verify backend uses host service:**
```bash
curl -s http://localhost:8000/api/v1/ib/status | jq .data.connection.host
# Expected: "http://host.docker.internal:5001"
```

## Performance Monitoring

### Key Metrics to Monitor

**Host Service Health:**
- Service uptime and responsiveness
- HTTP request/response times
- Connection pool status

**IB Gateway Connectivity:**
- Connection stability over time
- Reconnection frequency
- Request success rates

**Backend Integration:**
- HTTP communication latency
- Fallback behavior testing
- Error handling verification

### Monitoring Commands

**Check service metrics:**
```bash
curl -s http://localhost:5001/health/detailed | jq .
```

**Monitor backend logs:**
```bash
docker logs -f ktrdr-backend | grep -E "(host service|IB|error)"
```

**Watch IB status:**
```bash
watch -n 10 'curl -s http://localhost:8000/api/v1/ib/status | jq .data.connection'
```

## Rollback Procedure

**Emergency rollback to direct IB connection:**

1. **Stop backend:**
   ```bash
   docker-compose down backend
   ```

2. **Disable host service:**
   ```bash
   USE_IB_HOST_SERVICE=false docker-compose up backend -d
   ```

3. **Verify direct connection:**
   ```bash
   curl -s http://localhost:8000/api/v1/ib/status | jq .data.connection.host
   # Expected: "172.17.0.1" (Docker bridge IP)
   ```

**Rollback time:** Under 30 seconds

## Success Criteria

Phase 0 is considered successful when:

- ✅ **Host service starts and responds**: All endpoints operational
- ✅ **Backend detects host service**: Logs show host service mode enabled  
- ✅ **Network communication works**: Docker can reach host service
- ✅ **System consistency**: Both DataManager and IbService use same connection method
- ✅ **API compatibility maintained**: Existing endpoints work unchanged
- ✅ **Easy rollback**: Can disable host service in under 30 seconds

## Next Steps

After Phase 0 deployment:

1. **Monitor stability** for 24+ hours
2. **Test with real IB Gateway** connection
3. **Validate sleep/wake resilience** (macOS)
4. **Performance comparison** vs. Docker-only setup
5. **Plan Phase 1** enhancements (Training service extraction)

---

## Appendix: Technical Details

### HTTP API Endpoints

**Host Service (localhost:5001):**
- `GET /` - Service information
- `GET /health` - Basic health check
- `GET /health/detailed` - Comprehensive status
- `POST /data/historical` - Fetch historical data
- `POST /data/validate` - Symbol validation
- `GET /data/head-timestamp` - Earliest data timestamp

### Configuration Priority

1. **Environment variables** (highest priority)
2. **Environment override files** 
3. **Main settings.yaml**
4. **Default values** (lowest priority)

### Network Requirements

- **Host service**: Port 5001 available on host
- **IB Gateway**: Port 4002 accessible from host
- **Docker networking**: `host.docker.internal` resolution working
- **Firewall**: Allow HTTP traffic on port 5001 (localhost only)