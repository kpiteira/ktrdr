# Sandbox Shell Command: Architecture

## Overview

Add a `shell` subcommand to the existing `ktrdr sandbox` command group. The command wraps `docker compose exec` with the correct environment and compose file, providing a convenient way to access container shells.

## Components

### Component 1: Shell Command

**Responsibility:** Parse arguments and execute `docker compose exec` with interactive flags.

**Location:** `ktrdr/cli/sandbox.py` (add to existing file)

**Dependencies:**
- `load_env_sandbox()` — existing function
- `find_compose_file()` — existing function

## Data Flow

```
User runs: ktrdr sandbox shell [service]
    │
    ▼
Load .env.sandbox from current directory
    │
    ▼
Find compose file (sandbox or main)
    │
    ▼
Build environment (merge os.environ + .env.sandbox)
    │
    ▼
Execute: docker compose exec <service> bash
    │
    ▼
Interactive shell session
```

## Error Handling

| Error | Detection | User Message |
|-------|-----------|--------------|
| Not in sandbox | `.env.sandbox` missing | "Not in a sandbox directory" |
| No compose file | `find_compose_file()` raises | "No docker-compose file found" |
| Service not running | Non-zero exit from docker | Exit code passed through |
| No shell in container | Exit code 126 | "No shell available in {service}" |

## Verification Strategy

### Unit Tests

**File:** `tests/unit/cli/test_sandbox_shell.py`

| Test | Purpose |
|------|---------|
| `test_shell_default_service` | Verify default is "backend" |
| `test_shell_custom_service` | Verify service argument passed correctly |
| `test_shell_not_in_sandbox` | Verify error when no .env.sandbox |

### E2E Test

**File:** `.claude/skills/e2e-testing/tests/sandbox/shell.md`

**Scenario:** Shell into running sandbox

**Prerequisites:**
- Sandbox instance running

**Steps:**
1. Navigate to sandbox directory
2. Run `ktrdr sandbox shell`
3. Execute `echo $HOSTNAME` in shell
4. Exit shell
5. Verify exit code 0

**Success Criteria:**
- Shell prompt appears
- Commands execute inside container
- Clean exit
