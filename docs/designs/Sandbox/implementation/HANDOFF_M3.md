# Handoff: M3 Startability Gate + Status

## Gotchas

### Mocking httpx Responses in Tests

**Problem:** AsyncMock makes all methods return coroutines, but `resp.json()` in httpx is synchronous.

**Symptom:** Tests fail with `'coroutine' object has no attribute 'get'`.

**Solution:** Use `MagicMock` for the response object, not `AsyncMock`:

```python
# Correct
mock_response = MagicMock()
mock_response.status_code = 200
mock_response.json.return_value = {"workers": [...]}

# Wrong - json() returns coroutine
mock_response = AsyncMock()
mock_response.json.return_value = {"workers": [...]}
```

## Patterns Established

### Startability Gate API

Task 3.1 created `ktrdr/cli/sandbox_gate.py` with:

```python
from ktrdr.cli.sandbox_gate import (
    CheckStatus,
    CheckResult,
    GateResult,
    StartabilityGate,
    run_gate,
)

# Synchronous usage (for CLI)
result = run_gate(api_port=8001, db_port=5433, timeout=60)
print(f"Passed: {result.passed}, Duration: {result.duration_seconds:.1f}s")
for check in result.checks:
    print(f"  {check.name}: {check.status.value} - {check.message}")

# Check results
result.passed      # True if all non-skipped checks passed
result.checks      # List[CheckResult] with individual check results
result.duration_seconds  # Total time spent checking
```

### Jaeger Port Calculation

Jaeger UI port is derived from API port offset:

```python
jaeger_port = 16686 + (api_port - 8000)
# API 8001 → Jaeger 16687
# API 8002 → Jaeger 16688
```

### Check Dependencies

Checks run sequentially with dependencies:

1. Database (independent)
2. Backend (depends on database being up)
3. Workers (SKIPPED if backend fails)
4. Observability (independent)

### Gate Integration in `up` Command

Task 3.2 integrated the gate into `sandbox.py`:

```python
from ktrdr.cli.sandbox_gate import CheckStatus, run_gate

# In up command, after docker compose up:
if no_wait:
    console.print("Instance starting...")
    return

result = run_gate(api_port, db_port, timeout=float(timeout))
# Display results with ✓/✗ symbols
# Exit with code 2 on failure
```

### Status Command Output Format

Task 3.3 implemented the `status` command with this output structure:

```text
Instance: ktrdr--<name> (slot N)
Status: running|stopped|partial|not started
Containers: X/Y healthy

Services:
  Backend:    http://localhost:<api_port>
  API Docs:   http://localhost:<api_port>/api/v1/docs
  Database:   localhost:<db_port>
  Grafana:    http://localhost:<grafana_port>
  Jaeger:     http://localhost:<jaeger_port>
  Prometheus: http://localhost:<prometheus_port>

Workers:
  Worker 1:   http://localhost:<worker_port_1>
  Worker 2:   http://localhost:<worker_port_2>
  Worker 3:   http://localhost:<worker_port_3>
  Worker 4:   http://localhost:<worker_port_4>
```

### Port Conflict Detection Exit Codes

Task 3.4 added port conflict detection with exit code 3:

```python
# Exit codes for `sandbox up`:
# 1 = Not in sandbox directory / no compose file / docker compose failure
# 2 = Startability Gate failed
# 3 = Port conflict detected
```

The check happens before docker compose starts, using `check_ports_available(slot)`.

### Logs Command

Task 3.5 implemented `logs` command with options:

```bash
ktrdr sandbox logs              # All services, last 100 lines
ktrdr sandbox logs backend      # Single service
ktrdr sandbox logs -f           # Follow mode (Ctrl+C to exit)
ktrdr sandbox logs --tail 50    # Control line count
```

## M3 Progress

- [x] Task 3.1: Create Startability Gate Module
- [x] Task 3.2: Integrate Gate into `sandbox up`
- [x] Task 3.3: Implement `ktrdr sandbox status` Command
- [x] Task 3.4: Add Port Conflict Detection to `up`
- [x] Task 3.5: Implement `ktrdr sandbox logs` Command

**M3 COMPLETE** — All 5 tasks done. Ready for M4: CLI Auto-Detection.
