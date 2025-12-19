# Orchestrator Health Check: Design

## Problem Statement

The orchestrator needs comprehensive health reporting to verify the system is ready to execute tasks. Operators need to quickly diagnose issues (sandbox down, Claude logged out, GitHub token expired), and monitoring systems need metrics to alert on degraded states.

## Goals

What we're trying to achieve:

1. **Quick diagnosis** — When something's wrong, immediately know what
2. **Monitoring integration** — Prometheus can scrape health metrics
3. **Automation-friendly** — Exit codes and JSON output for scripts
4. **Observable** — Health checks themselves are traced for debugging

## Non-Goals (Out of Scope)

What we're explicitly not doing:

- Auto-remediation (e.g., automatically logging Claude back in)
- Historical health tracking (that's Prometheus's job)
- Health checks for external services (IB Gateway, backend API)
- Liveness/readiness probes for Kubernetes (not our deployment model)
- GitHub token expiry warnings (just check presence)
- Orchestrator "stuck" detection (assume it's doing work)

## User Experience

### Scenario 1: Quick Health Check

Operator wants to verify system is ready:

```bash
$ orchestrator health
{
  "status": "healthy",
  "timestamp": "2024-12-18T10:30:00Z",
  "checks": {
    "sandbox": {"status": "ok", "message": "container running"},
    "claude_auth": {"status": "ok", "message": "authenticated"},
    "github_token": {"status": "ok", "message": "present"},
    "orchestrator": {"status": "ok", "message": "idle"}
  }
}
$ echo $?
0
```

### Scenario 2: Diagnosing a Problem

Something's wrong, operator investigates:

```bash
$ orchestrator health
{
  "status": "unhealthy",
  "timestamp": "2024-12-18T10:30:00Z",
  "checks": {
    "sandbox": {"status": "ok", "message": "container running"},
    "claude_auth": {"status": "failed", "message": "not logged in - run 'claude login' in sandbox"},
    "github_token": {"status": "ok", "message": "present"},
    "orchestrator": {"status": "ok", "message": "idle"}
  }
}
$ echo $?
1
```

### Scenario 3: Single Check

Operator wants to verify just one component:

```bash
$ orchestrator health --check github_token
{
  "status": "healthy",
  "timestamp": "2024-12-18T10:30:00Z",
  "checks": {
    "github_token": {"status": "ok", "message": "present"}
  }
}
```

### Scenario 4: Monitoring Integration

Prometheus scrapes the orchestrator:

```
# HELP orchestrator_health_check_status Health check status (1=ok, 0=failed)
# TYPE orchestrator_health_check_status gauge
orchestrator_health_check_status{check="sandbox"} 1
orchestrator_health_check_status{check="claude_auth"} 1
orchestrator_health_check_status{check="github_token"} 1
orchestrator_health_check_status{check="orchestrator"} 1

# HELP orchestrator_health_checks_total Total health checks performed
# TYPE orchestrator_health_checks_total counter
orchestrator_health_checks_total{check="sandbox"} 142
orchestrator_health_checks_total{check="claude_auth"} 142
```

## Key Decisions

### Decision 1: Individual check functions composed at runtime

**Choice:** Each health check is a separate function; CLI/metrics layer composes them.

**Alternatives considered:**
- Single monolithic `get_health()` function
- Layered quick/deep checks

**Rationale:** Individual functions allow parallel execution, easier testing, and selective checking. Some checks (GitHub API) are slower than others (container status).

### Decision 2: Any failed check = unhealthy + exit code 1

**Choice:** Overall status is "unhealthy" if any check fails. CLI returns exit code 1.

**Alternatives considered:**
- "degraded" status for partial failures
- Different exit codes per failure type

**Rationale:** Simple binary healthy/unhealthy is easier to script and monitor. The detailed check results explain what's wrong.

### Decision 3: Checks include actionable messages

**Choice:** Failed checks include guidance on how to fix.

**Alternatives considered:**
- Just status codes, docs elsewhere

**Rationale:** "not logged in - run 'claude login' in sandbox" is more useful than just "failed". Reduces time to resolution.

### Decision 4: Simple token presence check

**Choice:** GitHub token check just verifies the variable is set, not validity or expiry.

**Alternatives considered:**
- API call to verify token works
- Check token expiry date and warn

**Rationale:** Keep it simple. A present token that doesn't work will fail at task execution time with a clear error.

### Decision 5: 5 second timeout per check

**Choice:** Each check has a 5 second timeout before being marked as failed.

**Rationale:** Long enough for docker exec commands, short enough to not block health polling.

### Decision 6: Dependency-ordered checks with skip on failure

**Choice:** Checks run in dependency order. If sandbox fails, dependent checks (claude_auth, github_token) are skipped with status "skipped".

**Alternatives considered:**
- Let all checks fail independently (cascading failures obscure root cause)
- Stop entirely on first failure

**Rationale:** Shows the root cause clearly (sandbox failed) while still running independent checks (orchestrator). Skipped status makes it obvious these weren't actually checked.

### Decision 7: Unified output format for single check

**Choice:** `--check X` returns the same JSON shape as full check, just with one entry in `checks`.

**Rationale:** Simpler for scripting — `jq '.checks.X.status'` works regardless of whether single or full check.
