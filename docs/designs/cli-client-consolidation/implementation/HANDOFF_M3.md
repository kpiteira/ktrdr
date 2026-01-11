# Handoff: M3 — Migrate Async Commands

## Task 3.1 Complete: Migrate agent_commands.py

### Migration Pattern Applied

Old pattern using `_make_request`:
```python
from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError

async with AsyncCLIClient() as client:
    result = await client._make_request("GET", "/agent/status")
```

New pattern using convenience methods:
```python
from ktrdr.cli.client import AsyncCLIClient, CLIClientError

async with AsyncCLIClient() as client:
    result = await client.get("/agent/status")
```

### Gotcha: Error Code Checking

Old client had `e.error_code` attribute. New client uses string matching:
```python
# Old
if e.error_code == "CLI-ConnectionError":

# New
error_str = str(e)
if "Connection" in error_str:
```

---

## Task 3.2 Complete: Migrate async_data_commands.py

Same pattern. Also replaced health check:
```python
# Old
await cli._make_request("GET", "/health")

# New
await cli.health_check()
```

---

## Task 3.3 Complete: Migrate data_commands.py (async parts)

Only async portions migrated. File still has `from ktrdr.cli.api_client import` for other sync code.

---

## Task 3.4 Complete: Migrate model_commands.py

Most complex migration - training operation polling uses many API calls.

### Method Name Changes

| Old | New |
|-----|-----|
| `client._make_request("GET", path)` | `client.get(path)` |
| `client._make_request("POST", path, json_data={...})` | `client.post(path, json={...})` |
| `client._make_request("DELETE", path)` | `client.delete(path)` |

Note: Parameter name changed from `json_data` to `json`.

---

## M3 Complete

All 4 async command files migrated from old `AsyncCLIClient` pattern to new module:
1. agent_commands.py
2. async_data_commands.py
3. data_commands.py (async parts only)
4. model_commands.py

### E2E Verification
- `ktrdr agent status` works
- `ktrdr data show AAPL --timeframe 1d` works
- `ktrdr data load AAPL --timeframe 1h` - async polling works (failed at IB layer)
- `ktrdr agent trigger --model haiku` - POST and status works (failed at API key layer)
- No imports from old `async_cli_client.py`

---

## IMPORTANT: Final Milestone E2E Requirement

**At the end of M5 (final milestone), run FULL E2E tests for ALL commands with SUCCESS criteria:**

Commands that must succeed:
- `ktrdr data load` - requires IB host service running
- `ktrdr agent trigger --monitor` - requires Anthropic API key
- `ktrdr models train` - requires training infrastructure
- All other migrated commands

**Process:**
1. Ask user to start IB host service and add Anthropic API key before final E2E
2. Run each command and verify it completes successfully
3. If infrastructure fails, ask user to fix before proceeding
4. Tests may take hours - that's expected
