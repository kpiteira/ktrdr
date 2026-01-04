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

## M3 Progress

- [x] Task 3.1: Create Startability Gate Module
- [ ] Task 3.2: Integrate Gate into `sandbox up`
- [ ] Task 3.3: Implement `ktrdr sandbox status` Command
- [ ] Task 3.4: Add Port Conflict Detection to `up`
- [ ] Task 3.5: Implement `ktrdr sandbox logs` Command

Ready for Task 3.2: Integrate gate into `up` command.
