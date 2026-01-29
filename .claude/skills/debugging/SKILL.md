---
name: debugging
description: Use when troubleshooting host service connectivity, debugging data loading issues, investigating progress tracking problems, diagnosing environment or configuration issues, or checking Grafana dashboards.
---

# Debugging Common Issues

Load this skill when:
- Troubleshooting host service connectivity
- Debugging data loading issues
- Investigating progress tracking problems
- Diagnosing environment or configuration issues

For distributed tracing and Jaeger queries, use the `observability` skill instead.

---

## Debugging Priority

1. **Check Grafana dashboards** — Quick visual diagnostics
2. **Query Jaeger** — For operation-specific issues (see `observability` skill)
3. **Check logs** — Only if observability doesn't have the answer

---

## Grafana Dashboards (First Stop)

**URL**: http://localhost:3000

| Dashboard | Path | Use Case |
|-----------|------|----------|
| System Overview | `/d/ktrdr-system-overview` | Service health, error rates, latency |
| Worker Status | `/d/ktrdr-worker-status` | Worker capacity, resource usage |
| Operations | `/d/ktrdr-operations` | Operation counts, success rates |

### Quick Checks

- **"Is it working?"** → System Overview: Healthy Services count
- **"Why is it slow?"** → System Overview: P95 Latency panel
- **"Workers missing?"** → Worker Status: Healthy Workers and Health Matrix
- **"Operations failing?"** → Operations: Success Rate and Status Distribution

**Dashboard files**: `deploy/shared/grafana/dashboards/`

---

## Host Services Not Working

### Check if services are running

```bash
lsof -i :5001  # IB Host Service
lsof -i :5002  # Training Host Service
```

### Test connectivity from Docker

```bash
docker exec ktrdr-backend curl http://host.docker.internal:5001/health
docker exec ktrdr-backend curl http://host.docker.internal:5002/health
```

### Check logs

```bash
tail -f ib-host-service/logs/ib-host-service.log
tail -f training-host-service/logs/training-host-service.log
```

### Common issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Connection refused | Service not running | Start the service |
| Timeout | Wrong URL or firewall | Check `host.docker.internal` works |
| 500 errors | Service crashed | Check service logs |

---

## Environment Variable Issues

### Check what's set in Docker container

```bash
docker exec ktrdr-backend env | grep -E "(IB|TRAINING)"
```

### Common problems

- `USE_IB_HOST_SERVICE` not set → Falls back to local (wrong in Docker)
- URL wrong → Connection failures
- Service not started → Timeouts

### Required environment for Docker

```bash
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://host.docker.internal:5001
```

---

## Progress Not Updating

Check in this order:

1. **Is OperationsService being used?**
   - File: `ktrdr/api/services/operations_service.py`
   - The operation must be registered with `register_operation()`

2. **Is progress callback being passed?**
   - ServiceOrchestrator methods need progress callback
   - Check the calling code passes callback

3. **Is GenericProgressManager updating?**
   - Progress updates happen through the manager
   - Check `update_progress()` is being called

4. **Is cancellation token triggered?**
   - Cancelled operations stop updating
   - Check `token.is_cancelled()`

---

## Data Loading Issues

### Common root causes

1. **IB Gateway not running** (port 4002)
   ```bash
   lsof -i :4002
   ```

2. **IB Host Service not started**
   ```bash
   curl http://localhost:5001/health
   ```

3. **Symbol format incorrect**
   - Use IB format: `AAPL` not `AAPL.US`

4. **Date range outside available data**
   - Check IB has data for the requested range

5. **Timeframe not supported**
   - IB supports specific timeframes only

### Debug data flow

```bash
# Check if data exists locally
ktrdr data range AAPL 1d

# Test IB connection
ktrdr ib test

# Check IB status
ktrdr ib status
```

---

## Workers Not Registering

### Check registered workers

```bash
curl http://localhost:8000/api/v1/workers | jq
```

### Common issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Empty worker list | Workers not started | `docker-compose up` |
| Workers show UNAVAILABLE | Workers crashed | Check worker logs |
| Backend not reachable | Network issue | Check Docker network |

### Worker logs

```bash
docker compose logs -f backtest-worker-1 backtest-worker-2
docker compose logs -f training-worker-1 training-worker-2
```

---

## Async/Await Issues

### "Function not working in async context"

**Wrong** — Wrap in try/except and return None:
```python
try:
    result = await something()
except:
    return None  # Hides the real problem
```

**Right** — Ensure proper async/await chain:
```python
# Check the entire call chain is async
async def caller():
    result = await async_function()  # Must be awaited
    return result
```

### Common async mistakes

- Forgetting `await` on async functions
- Mixing sync and async code incorrectly
- Not using `asyncio.to_thread()` for blocking operations

---

## Test Failures

### Unit tests failing

```bash
# Run with verbose output
make test-unit PYTEST_ARGS="-v"

# Run single test
uv run pytest tests/path/to/test.py::test_name -v
```

### Integration tests failing

```bash
# Check services are running
docker-compose ps

# Run with output
make test-integration PYTEST_ARGS="-v -s"
```

### Common test issues

- Missing fixtures → Check `conftest.py`
- Database state → Tests may need isolation
- Async issues → Ensure `@pytest.mark.asyncio` decorator

---

## Quick Diagnostic Commands

```bash
# Check all services
docker-compose ps

# Check backend health
curl http://localhost:8000/api/v1/health | jq

# Check workers
curl http://localhost:8000/api/v1/workers | jq

# Check operations
curl http://localhost:8000/api/v1/operations | jq

# Check recent logs
docker-compose logs --tail=100 backend

# Check resource usage
docker stats --no-stream
```
