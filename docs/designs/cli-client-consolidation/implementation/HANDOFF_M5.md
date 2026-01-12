# Handoff: M5 — Cleanup

## Task 5.0 BLOCKED: Pre-Deletion E2E Verification

### Critical Finding: M4.5 Required

Task 5.0 discovered that several command files still use old client imports. M5 cannot proceed until these are migrated.

**Files still using old clients:**

| File | Old Import | Active? |
|------|------------|---------|
| `async_model_commands.py` | `operation_executor.py` | YES - wired to CLI |
| `data_commands.py` | `api_client.py` | YES - `data load` command |
| `dummy_commands.py` | `api_client.py`, `operation_executor.py` | YES |
| `model_commands.py` | `api_client.py` | NO - not wired to CLI |

**Key discovery:** `async_model_commands.py` is the ACTIVE file for `ktrdr models` (via `__init__.py` line 121), not `model_commands.py`. M4 migrated the wrong file.

### M4.5 Created

New milestone `M4.5_remaining_migrations.md` created with:
- Task 4.5.1: Migrate `async_model_commands.py`
- Task 4.5.2: Migrate `data_commands.py` (`data load`)
- Task 4.5.3: Migrate `dummy_commands.py`
- Task 4.5.4: Clean up `model_commands.py` (unused)
- Task 4.5.5: Final verification

### M5 Updated

- Task 5.0 and 5.4 updated with complete API-based command list
- Fixed incorrect command syntax (`--start-date` → `--start`, etc.)
- Added all missing commands (agent, dummy, ib test, indicators compute)
- Clarified infrastructure vs client failures

### Commands That Worked (Current State)

These commands work and use the NEW unified client:
- `data show`, `data range` - SyncCLIClient
- `indicators list` - SyncCLIClient
- `strategies list`, `strategies validate` - local + SyncCLIClient
- `operations list` - SyncCLIClient
- `fuzzy config validate` - SyncCLIClient
- `ib status` - SyncCLIClient
- `checkpoints show` - AsyncCLIClient
- `agent status`, `agent budget` - AsyncCLIClient
- `backtest run` - AsyncCLIClient.execute_operation

### Commands That Use OLD Client (Need M4.5)

- `models train` - uses old `operation_executor.py` via `async_model_commands.py`
- `data load` - uses old `api_client.py`
- `dummy dummy` - uses old `api_client.py` AND `operation_executor.py`

### Next Steps

1. Complete M4.5 (migrate remaining commands)
2. Re-run Task 5.0 verification
3. Proceed with M5 deletion tasks

---

## Task 5.1 Complete: Delete async_cli_client.py

### What Was Done
- Verified no production code imports `async_cli_client.py` (grep confirmed)
- Deleted `ktrdr/cli/async_cli_client.py` (297 lines removed)
- All tests pass (3836 passed)
- Quality checks pass

### Next Task Notes
For Task 5.2 (`api_client.py`):
- Same pattern: grep first, then delete
- Also check for `get_api_client` helper
- File is larger (~500 lines) - more code removed

---

## Task 5.2 Complete: Delete api_client.py

### What Was Done
- Verified no production code imports `api_client.py` (grep confirmed)
- Verified `get_api_client` only existed in the file itself
- Deleted `ktrdr/cli/api_client.py` (870 lines removed)
- All tests pass (3836 passed)
- Quality checks pass

### Next Task Notes
For Task 5.3 (`operation_executor.py`):
- Same pattern: grep first, then delete
- Check for both module import and class import patterns

---

## Task 5.3 Complete: Delete operation_executor.py

### What Was Done
- Verified no production code imports `operation_executor.py` (grep confirmed)
- Deleted `ktrdr/cli/operation_executor.py` (539 lines removed)
- All tests pass (3836 passed)
- Quality checks pass

### Cumulative Code Removed
| Task | File | Lines |
|------|------|-------|
| 5.1 | async_cli_client.py | 297 |
| 5.2 | api_client.py | 870 |
| 5.3 | operation_executor.py | 539 |
| **Total** | | **1,706** |

### Next Task Notes
Task 5.4 is Post-Deletion Verification (E2E testing). This is the FINAL task in M5 and requires:
- Running all CLI commands to verify nothing broke
- Full E2E test with Docker + IB host service
