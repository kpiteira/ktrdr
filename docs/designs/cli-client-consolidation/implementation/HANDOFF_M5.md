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
