# Phase 0 Troubleshooting Checklist

## Quick Diagnostic Commands

Run these commands in order to diagnose Phase 0 issues:

### 1. Host Service Status
```bash
# Check if host service is running
curl -s http://localhost:5001/health || echo "❌ Host service not running"

# Get detailed service status  
curl -s http://localhost:5001/health/detailed | jq .
```

### 2. Docker Backend Configuration
```bash
# Check environment variables
docker exec ktrdr-backend env | grep -E "(USE_IB|IB_HOST)"

# Expected output:
# USE_IB_HOST_SERVICE=true
# IB_HOST_SERVICE_URL=http://host.docker.internal:5001
```

### 3. Network Connectivity
```bash
# Test Docker-to-host communication
docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health

# Expected: {"healthy":true,"service":"ib-connector",...}
```

### 4. Backend Integration Status
```bash
# Check backend logs for host service mode
docker logs ktrdr-backend | grep -E "(host service|IB integration)"

# Expected: "IB integration enabled using host service at http://host.docker.internal:5001"
```

### 5. API Endpoint Validation
```bash
# Check IB status shows host service
curl -s http://localhost:8000/api/v1/ib/status | jq .data.connection

# Expected: 
# {
#   "host": "http://host.docker.internal:5001",
#   "port": 5001
# }
```

## Common Issues & Solutions

### Issue 1: Host Service Not Starting

**Symptoms:**
- `curl: (7) Failed to connect to localhost port 5001`
- No response from host service endpoints

**Diagnostic:**
```bash
cd ib-host-service
lsof -i :5001  # Check if port is in use
```

**Solutions:**
1. **Port conflict**: Kill process using port 5001
2. **Missing dependencies**: Run `uv install` in ib-host-service/
3. **Python path issues**: Check PYTHONPATH includes parent directory

### Issue 2: Backend Still Using Direct Connection

**Symptoms:**
- IB status shows `"host": "172.17.0.1"`
- Backend logs show "direct connection"

**Diagnostic:**
```bash
# Check Docker environment
docker exec ktrdr-backend env | grep USE_IB_HOST_SERVICE

# Check backend configuration loading
docker logs ktrdr-backend | grep "host_service.enabled"
```

**Solutions:**
1. **Environment not set**: Use `USE_IB_HOST_SERVICE=true docker-compose up`
2. **Config cache**: Restart backend after config changes
3. **YAML syntax**: Validate config/settings.yaml syntax

### Issue 3: Network Communication Failure

**Symptoms:**
- "Connection refused to host.docker.internal:5001"
- Timeout errors from Docker backend

**Diagnostic:**
```bash
# Test host resolution
docker exec ktrdr-backend nslookup host.docker.internal

# Test direct IP access
docker exec ktrdr-backend curl -s http://host-gateway:5001/health
```

**Solutions:**
1. **Docker Desktop issue**: Restart Docker Desktop
2. **Firewall blocking**: Check macOS/Linux firewall settings
3. **Network mode**: Ensure backend uses bridge network (not host)

### Issue 4: IB Gateway Connection Issues

**Symptoms:**
- Host service timeouts on IB operations
- "Connection to IB Gateway failed"

**Diagnostic:**
```bash
# Check IB Gateway is running
lsof -i :4002

# Test direct IB connection
telnet localhost 4002
```

**Solutions:**
1. **IB Gateway not running**: Start IB Gateway/TWS
2. **Wrong port**: Check IB Gateway is on port 4002 (paper trading)
3. **Client ID conflict**: Ensure no other connections using same client ID

### Issue 5: Configuration Not Loading

**Symptoms:**
- Default configuration used despite changes
- "Failed to load configuration" in logs

**Diagnostic:**
```bash
# Check config file exists and is readable
ls -la config/settings.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/settings.yaml'))"
```

**Solutions:**
1. **YAML syntax error**: Fix indentation/syntax in config file
2. **File permissions**: Ensure config files are readable
3. **Path issues**: Check working directory when starting services

## Health Check Matrix

| Component | Check | Expected | Command |
|-----------|-------|----------|---------|
| Host Service | Running | `{"healthy":true}` | `curl localhost:5001/health` |
| Docker Backend | Host Service Mode | `USE_IB_HOST_SERVICE=true` | `docker exec ktrdr-backend env \| grep USE_IB` |
| Network | Docker→Host | `{"healthy":true}` | `docker exec ktrdr-backend curl host.docker.internal:5001/health` |
| IB Status | Host Service URL | `"host": "http://host.docker.internal:5001"` | `curl localhost:8000/api/v1/ib/status` |
| IB Gateway | Port Open | Connection accepted | `telnet localhost 4002` |

## Emergency Rollback

If Phase 0 has issues, immediately rollback:

```bash
# 1. Stop backend
docker-compose down backend

# 2. Disable host service
USE_IB_HOST_SERVICE=false docker-compose up backend -d

# 3. Verify rollback
curl -s http://localhost:8000/api/v1/ib/status | jq .data.connection.host
# Should show: "172.17.0.1" (direct connection)
```

**Rollback time: < 30 seconds**

## Success Validation

Run all these checks - all should pass:

```bash
#!/bin/bash
echo "=== Phase 0 Validation ==="

# 1. Host service health
echo -n "Host service: "
curl -s http://localhost:5001/health | jq -r .healthy && echo "✅" || echo "❌"

# 2. Backend environment
echo -n "Backend config: "
docker exec ktrdr-backend env | grep -q "USE_IB_HOST_SERVICE=true" && echo "✅" || echo "❌"

# 3. Network connectivity  
echo -n "Network: "
docker exec ktrdr-backend curl -s http://host.docker.internal:5001/health | jq -r .healthy && echo "✅" || echo "❌"

# 4. IB status endpoint
echo -n "IB status: "
curl -s http://localhost:8000/api/v1/ib/status | jq -r .data.connection.host | grep -q "host.docker.internal" && echo "✅" || echo "❌"

echo "=== Validation Complete ==="
```

Save as `validate-phase0.sh` and run to verify deployment.