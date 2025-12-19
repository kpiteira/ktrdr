# Orchestrator Health Check: Architecture

## Overview

Health checking is implemented as independent check functions in `orchestrator/health.py`, composed by the CLI layer. Each check returns a `CheckResult` dataclass. Telemetry (metrics + traces) wraps each check execution.

## Components

### CheckResult Dataclass
**Responsibility:** Standardized return type for all health checks
**Location:** `orchestrator/health.py`

```python
@dataclass
class CheckResult:
    status: Literal["ok", "failed", "skipped"]
    message: str
    check_name: str
```

### Individual Check Functions
**Responsibility:** Perform one specific health check
**Location:** `orchestrator/health.py`

| Function | What it checks | How |
|----------|---------------|-----|
| `check_sandbox()` | Container running | `docker inspect` exit code |
| `check_claude_auth()` | Claude logged in | `docker exec sandbox test -f ~/.claude/credentials.json` |
| `check_github_token()` | GH_TOKEN present | `docker exec sandbox test -n "$GH_TOKEN"` |
| `check_orchestrator()` | Orchestrator state | Read state file, return idle/working |

### Health Aggregator
**Responsibility:** Run all checks, aggregate results
**Location:** `orchestrator/health.py`

```python
def get_health(checks: list[str] | None = None) -> HealthReport:
    """Run specified checks (or all) and return aggregated report."""
```

### CLI Command
**Responsibility:** Parse args, call health module, format output
**Location:** `orchestrator/cli.py`

```
orchestrator health [--check NAME] [--format json|text]
```

### Check Dependencies
**Responsibility:** Define which checks depend on others
**Location:** `orchestrator/health.py`

```python
CHECK_DEPENDENCIES = {
    "sandbox": [],              # No dependencies
    "claude_auth": ["sandbox"], # Requires sandbox running
    "github_token": ["sandbox"], # Requires sandbox running
    "orchestrator": [],         # No dependencies (local state)
}

CHECK_ORDER = ["sandbox", "claude_auth", "github_token", "orchestrator"]
```

## Data Flow

```
CLI invocation
     │
     ▼
┌─────────────────┐
│  get_health()   │
│  (aggregator)   │
└────────┬────────┘
         │
         ▼
    check_sandbox ──────────────────┐
         │                          │
         ├─[ok]──────────┐          │
         │               ▼          │
         │        check_claude      │
         │               │          │
         │        check_github      │
         │               │          │
         ├─[failed]─► skip both ────┤
         │                          │
         └──────────────────────────┤
                                    │
    check_orchestrator (always) ◄───┘
         │
         ▼
   HealthReport
         │
         ▼
   JSON output + exit code
```

Dependency logic:
- Sandbox check runs first
- If sandbox fails, claude_auth and github_token are skipped (status: "skipped")
- Orchestrator check always runs (reads local state, no docker dependency)

Each check is wrapped with:
- Trace span (`orchestrator.health.{check_name}`)
- Counter increment (`orchestrator_health_checks_total`)
- Gauge update (`orchestrator_health_check_status`)

## API Contracts

### get_health()

```python
def get_health(checks: list[str] | None = None, timeout: float = 5.0) -> HealthReport:
    """
    Run health checks and return aggregated report.

    Args:
        checks: Specific checks to run, or None for all
        timeout: Max seconds per check (default 5.0)

    Returns:
        HealthReport with overall status and individual check results
    """
```

### HealthReport

```python
@dataclass
class HealthReport:
    status: Literal["healthy", "unhealthy"]
    timestamp: datetime
    checks: dict[str, CheckResult]

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
```

### CLI Output

**Success (exit 0):**
```json
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
```

**Failure (exit 1) - Claude not logged in:**
```json
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
```

**Failure (exit 1) - Sandbox not running (dependent checks skipped):**
```json
{
  "status": "unhealthy",
  "timestamp": "2024-12-18T10:30:00Z",
  "checks": {
    "sandbox": {"status": "failed", "message": "container not running - run 'sandbox-init.sh'"},
    "claude_auth": {"status": "skipped", "message": "sandbox not running"},
    "github_token": {"status": "skipped", "message": "sandbox not running"},
    "orchestrator": {"status": "ok", "message": "idle"}
  }
}
```

## Check Implementation Details

### check_sandbox()

```python
def check_sandbox() -> CheckResult:
    """Check if sandbox container is running."""
    # docker inspect --format '{{.State.Running}}' ktrdr-sandbox
    # Returns "true" or "false"
```

**Success:** Container exists and State.Running == true
**Failure:** Container doesn't exist or not running
**Message on failure:** "container not running - run 'sandbox-init.sh'"

### check_claude_auth()

```python
def check_claude_auth() -> CheckResult:
    """Check if Claude is authenticated in sandbox."""
    # docker exec ktrdr-sandbox test -f /home/ubuntu/.claude/credentials.json
    # Also check /root/.claude/credentials.json as fallback
```

**Success:** credentials.json exists in either location
**Failure:** File not found in either location
**Message on failure:** "not logged in - run 'claude login' in sandbox"

### check_github_token()

```python
def check_github_token() -> CheckResult:
    """Check if GH_TOKEN is present in sandbox."""
    # docker exec ktrdr-sandbox sh -c 'test -n "$GH_TOKEN"'
```

**Success:** Exit code 0 (variable is set and non-empty)
**Failure:** Exit code 1 (variable missing or empty)
**Message on failure:** "GH_TOKEN not set - check sandbox environment"

### check_orchestrator()

```python
def check_orchestrator() -> CheckResult:
    """Check orchestrator state."""
    # Read state file if exists, otherwise "idle"
```

**Success:** Always (reports current state)
**Message:** "idle" | "working on task X.Y" | "paused"

## Telemetry

### Trace Spans

Each check creates a span:
```
orchestrator.health (parent)
├── orchestrator.health.sandbox
├── orchestrator.health.claude_auth
├── orchestrator.health.github_token
└── orchestrator.health.orchestrator
```

Span attributes:
- `check.name`: Name of the check
- `check.status`: "ok" or "failed"
- `check.message`: Result message

### Metrics

```python
# Counter - incremented on each check
health_checks_total = Counter(
    "orchestrator_health_checks_total",
    "Total health checks performed",
    ["check"]
)

# Gauge - current status (1=ok, 0=failed)
health_check_status = Gauge(
    "orchestrator_health_check_status",
    "Health check status",
    ["check"]
)
```

## Error Handling

### Check Timeout

If a check takes longer than `timeout` seconds (default 5s):
- Kill the subprocess
- Return `CheckResult(status="failed", message="check timed out after 5s")`
- Log warning with check name

### Docker Not Available

If docker commands fail (daemon not running):
- Sandbox check fails with "docker not available"
- Other docker-dependent checks also fail
- Orchestrator check still works (reads local state)

### Subprocess Errors

If `docker exec` returns unexpected output:
- Parse what we can
- Default to failed with the raw error message
- Log the full error for debugging

## Integration Points

- **Existing telemetry:** Uses `orchestrator/telemetry.py` for tracing/metrics
- **State file:** Reads from `OrchestratorState` for orchestrator status
- **Sandbox container:** Assumes container name is `ktrdr-sandbox` (from compose)

## File Changes

| File | Change |
|------|--------|
| `orchestrator/health.py` | New file - all health check logic |
| `orchestrator/cli.py` | Add `health` subcommand |
