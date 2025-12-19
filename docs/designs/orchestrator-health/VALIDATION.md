# Design Validation: Orchestrator Health Check

**Date:** 2024-12-18
**Documents Validated:**

- Design: [DESIGN.md](DESIGN.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## Validation Summary

**Scenarios Validated:** 8/8 traced
**Critical Gaps Found:** 1 (resolved)
**Interface Contracts:** Defined

## Key Decisions Made

### 1. Dependency-ordered checks with skip on failure (GAP-1)

**Decision:** Run checks in dependency order. If sandbox fails, skip dependent checks (claude_auth, github_token) with status "skipped".

**Context:** Without this, a stopped sandbox causes 3 failures (sandbox, claude_auth, github_token) which obscures the root cause.

**Trade-off accepted:** Slightly more complex implementation in exchange for clearer error messages.

### 2. Unified output format for single check

**Decision:** `--check X` returns the same JSON shape as full check, just with one entry in `checks`.

**Context:** Original design had two different output shapes, complicating scripting.

**Trade-off accepted:** None — strictly simpler.

### 3. Claude auth via file check

**Decision:** Check for `~/.claude/credentials.json` existence instead of a CLI command.

**Context:** `claude auth status` doesn't exist as a subcommand. The sandbox-init.sh script already uses file existence check.

### 4. 5 second timeout per check

**Decision:** Each check has independent 5s timeout. If one times out, others still run.

## Scenarios Validated

### Happy Paths

1. **All Checks Pass** — Full health check returns healthy, exit 0
2. **Single Check Mode** — `--check sandbox` returns same shape with one entry
3. **Working State** — Orchestrator reports "working on task X.Y"

### Error Paths

4. **Sandbox Not Running** — Sandbox fails, dependent checks skipped, orchestrator still runs
5. **Claude Not Logged In** — Sandbox ok, claude_auth fails, others continue
6. **Check Timeout** — 5s timeout, returns failed with timeout message

### Edge Cases

7. **Docker Daemon Not Running** — All docker-dependent checks fail, orchestrator check passes
8. **Partial Failure** — Any single failure = unhealthy overall

## Interface Contracts

### Check Status Values

```python
status: Literal["ok", "failed", "skipped"]
```

### Check Dependencies

```python
CHECK_DEPENDENCIES = {
    "sandbox": [],              # No dependencies
    "claude_auth": ["sandbox"], # Requires sandbox
    "github_token": ["sandbox"], # Requires sandbox
    "orchestrator": [],         # No dependencies
}
```

### Output Format (unified)

```json
{
  "status": "healthy|unhealthy",
  "timestamp": "ISO8601",
  "checks": {
    "<check_name>": {
      "status": "ok|failed|skipped",
      "message": "human-readable message"
    }
  }
}
```

## Implementation Milestone

Single milestone — this is a small feature:

**Milestone 1: Health Check Command**

- `orchestrator/health.py`: CheckResult, HealthReport, all check functions, get_health()
- `orchestrator/cli.py`: Add `health` subcommand with `--check` option
- Tests for all checks (mocked docker calls)

**E2E Test:**

```bash
# With everything healthy:
orchestrator health  # exit 0, status "healthy"

# With sandbox stopped:
orchestrator health  # exit 1, sandbox failed, others skipped
```

## Files Changed

| File | Change |
|------|--------|
| `orchestrator/health.py` | New file — all health check logic |
| `orchestrator/cli.py` | Add `health` subcommand |
