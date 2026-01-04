# Isolated Development Sandbox: Architecture

## Overview

The sandbox system consists of four main parts:

1. **`ktrdr sandbox` CLI** — A Python Click subcommand that manages instance lifecycle (create, up, down, destroy)
2. **Modified Docker Compose** — The existing compose file updated for multi-instance support (no container names, parameterized ports, shared data mounts)
3. **Instance State** — A simple registry tracking active instances and their port slots
4. **Shared Data Package** — A standardized way to initialize `~/.ktrdr/shared/` with required data

The CLI wraps standard Docker Compose operations, adding instance identity, port allocation, port conflict detection, and the Startability Gate. Testing uses existing `make test-*` commands.

## Components

### Component: `ktrdr sandbox` CLI

**Responsibility:** Manages the full lifecycle of sandbox instances — creation, startup, shutdown, and cleanup. Does NOT handle test execution (use existing `make test-*` commands).

**Location:** `ktrdr/cli/sandbox.py` (new file), exposed as `ktrdr sandbox` subcommand

**Dependencies:**

- Click (already used by `ktrdr` CLI)
- Docker SDK for Python (container inspection, health checks)
- Git (worktree management via subprocess)
- Existing compose file

**Key Functions:**

```python
# Instance lifecycle
def create(name: str, branch: str | None, slot: int | None) -> Instance
def init(slot: int | None) -> Instance  # Initialize existing directory as instance
def up(wait: bool = True, build: bool = False) -> None  # Start stack, run Startability Gate
def down(remove_volumes: bool = False) -> None
def destroy(keep_worktree: bool = False) -> None

# Status and inspection
def list_instances() -> list[Instance]
def status() -> InstanceStatus
def logs(service: str | None, follow: bool) -> None

# Utilities
def allocate_slot() -> int
def check_port_conflicts(slot: int) -> list[int]  # Returns conflicting ports
def derive_instance_id(path: Path) -> str
def generate_env(instance: Instance) -> None
```

### Component: Port Allocator

**Responsibility:** Assigns and tracks port slots for instances. Detects port conflicts and blacklists unavailable slots.

**Location:** `ktrdr/cli/sandbox_ports.py` (new file)

**Dependencies:** `socket` (for port checking)

**Port Mapping:**

```python
BASE_PORTS = {
    "backend": 8000,
    "db": 5432,
    "grafana": 3000,
    "jaeger_ui": 16686,
    "jaeger_otlp": 4317,
    "prometheus": 9090,
    "worker_base": 5000,
}

def get_ports(slot: int) -> dict[str, int]:
    """
    Slot 0: reserved for main dev (uses base ports)
    Slot 1-10: sandbox instances
    """
    if slot == 0:
        return BASE_PORTS

    return {
        "backend": 8000 + slot,        # 8001, 8002, ...
        "db": 5432 + slot,             # 5433, 5434, ...
        "grafana": 3000 + slot,        # 3001, 3002, ...
        "jaeger_ui": 16686 + slot,     # 16687, 16688, ...
        "jaeger_otlp": 4317 + slot,    # 4318, 4319, ...
        "prometheus": 9090 + slot,     # 9091, 9092, ...
        "worker_base": 5000 + (slot * 10),  # 5010, 5020, ...
    }

def check_ports_available(slot: int) -> list[int]:
    """
    Returns list of ports that are already in use.
    Empty list means all ports are available.
    """
    ports = get_ports(slot)
    in_use = []
    for port in ports.values():
        if not is_port_free(port):
            in_use.append(port)
    return in_use

def is_port_free(port: int) -> bool:
    """Check if a port is available for binding."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
```

**Conflict Handling:** If any port in a slot is in use by something external, the entire slot is blacklisted. The CLI refuses to start and suggests picking a different slot.

### Component: Instance Registry

**Responsibility:** Tracks which instances exist and their allocated slots.

**Location:** `~/.ktrdr/sandbox/instances.json`

**Dependencies:** Filesystem

**Schema:**

```json
{
  "instances": {
    "ktrdr--feat-operation-metrics": {
      "slot": 2,
      "path": "/Users/karl/Documents/dev/ktrdr--feat-operation-metrics",
      "created_at": "2024-01-15T10:30:00Z",
      "is_worktree": true,
      "parent_repo": "/Users/karl/Documents/dev/ktrdr2"
    }
  },
  "allocated_slots": [1, 2, 3]
}
```

**Note:** The registry is a convenience for `list` and slot tracking. Instance state is also derivable from:
- Scanning for directories matching `ktrdr--*` pattern
- Checking for `.env.sandbox` marker file
- Querying Docker for running containers with matching project names

### Component: Modified Docker Compose

**Responsibility:** Define services in a way that supports multiple concurrent instances with shared data.

**Location:** `deploy/environments/local/docker-compose.yml` (modified)

**Changes Required:**

1. **Remove all `container_name:` fields** — Enables Compose project isolation
2. **Parameterize all published ports** — `${KTRDR_API_PORT:-8000}:8000`
3. **Use project-scoped volumes** — No `external: true`, let Compose namespace them
4. **Add instance_id to environment variables** — For telemetry labeling
5. **Mount shared data directory** — `~/.ktrdr/shared/` for data, models, strategies

**Shared Data Mounts:**

```yaml
services:
  backend:
    volumes:
      # Shared across all instances (read-mostly)
      - ${KTRDR_SHARED_DIR:-~/.ktrdr/shared}/data:/app/data
      - ${KTRDR_SHARED_DIR:-~/.ktrdr/shared}/models:/app/models
      - ${KTRDR_SHARED_DIR:-~/.ktrdr/shared}/strategies:/app/strategies
      # Instance-specific (hot reload)
      - ./ktrdr:/app/ktrdr
      - ./tests:/app/tests
```

### Component: Shared Data Package

**Responsibility:** Provides a standardized way to initialize `~/.ktrdr/shared/` with required symbol data, models, and strategies.

**Location:** `scripts/init-shared-data.sh` or `ktrdr sandbox init-shared`

**Contents of `~/.ktrdr/shared/`:**

```
~/.ktrdr/shared/
├── data/           # Symbol data (flat CSVs: AAPL_1d.csv, EURUSD_1h.csv, etc.)
├── models/         # Trained models
└── strategies/     # Strategy configurations
```

**Initialization Options:**

1. **Copy from existing dev environment:**
   ```bash
   ktrdr sandbox init-shared --from ~/Documents/dev/ktrdr2
   ```
   This copies `data/`, `models/`, and `strategies/` from an existing working environment.

2. **Manual setup:** Copy files directly to `~/.ktrdr/shared/` from a backup or another machine.

**New Dev Machine Workflow:**

```bash
# 1. Clone KTRDR
git clone git@github.com:kpiteira/ktrdr.git

# 2. Initialize shared data
ktrdr sandbox init-shared --minimal  # Or copy from backup

# 3. Create first sandbox
ktrdr sandbox create my-feature
ktrdr sandbox up
```

### Component: Startability Gate

**Responsibility:** Validates that an instance starts correctly before declaring it ready.

**Location:** Part of `ktrdr-sandbox up` command

**Dependencies:** Docker SDK, HTTP client

**Checks:**

```python
class StartabilityGate:
    async def check(self, instance: Instance) -> GateResult:
        checks = [
            self.check_containers_running(),
            self.check_database_ready(),
            self.check_backend_healthy(),
            self.check_workers_registered(),
            self.check_observability_ready(),
        ]
        results = await asyncio.gather(*checks)
        return GateResult(passed=all(r.passed for r in results), checks=results)

    async def check_backend_healthy(self) -> CheckResult:
        """GET /health returns 200"""

    async def check_workers_registered(self) -> CheckResult:
        """GET /api/v1/workers returns expected worker count"""

    async def check_database_ready(self) -> CheckResult:
        """pg_isready or SELECT 1 succeeds"""
```

### Component: CLI Port Flag Extension

**Responsibility:** Adds `--port` / `-p` flag to the existing `ktrdr` CLI for easy instance targeting.

**Location:** `ktrdr/cli/main.py` (modified)

**Implementation:**

```python
@click.option(
    "--port", "-p",
    type=int,
    envvar="KTRDR_API_PORT",
    help="Backend port (expands to http://localhost:PORT)"
)
@click.option(
    "--url", "-u",
    envvar="KTRDR_API_URL",
    help="Full backend URL"
)
def cli(port: int | None, url: str | None):
    if url:
        api_url = url
    elif port:
        api_url = f"http://localhost:{port}"
    else:
        api_url = "http://localhost:8000"  # Default
```

**Usage:** When working in a sandbox instance, `.env.sandbox` sets `KTRDR_API_PORT`, so the CLI automatically targets the correct backend without flags.

## Data Flow

### Instance Creation Flow

```
User: ktrdr-sandbox create feat-metrics
                │
                ▼
        ┌───────────────┐
        │ Allocate Slot │ ← Check registry for free slots
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Create Worktree│ ← git worktree add ../ktrdr--feat-metrics
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Generate .env │ ← Write .env.sandbox with ports, instance_id
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Update Registry│ ← Record instance in ~/.ktrdr/sandbox/
        └───────┬───────┘
                │
                ▼
        Report success with URLs
```

### Instance Startup Flow

```
User: ktrdr-sandbox up
        │
        ▼
┌───────────────────┐
│ Load .env.sandbox │ ← Get instance_id, ports, slot
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Set COMPOSE_PROJECT│ ← export COMPOSE_PROJECT_NAME=$instance_id
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ docker compose up │ ← Start all services
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Startability Gate │ ← Wait for health, check workers
└────────┬──────────┘
         │
    ┌────┴────┐
    │         │
  PASS      FAIL
    │         │
    ▼         ▼
 Report    Report errors,
 ready     suggest fixes
```

### Test Execution Flow

Tests use existing `make` commands. The `.env.sandbox` file ensures they target the correct instance.

```
User: make test-e2e  (from instance directory)
        │
        ▼
┌────────────────────────┐
│ Load .env.sandbox      │ ← Sets KTRDR_API_PORT, DB_PORT, etc.
└────────┬───────────────┘
         │
         ▼
┌────────────────────────┐
│ pytest tests/e2e/      │ ← Tests use env vars for endpoints
└────────┬───────────────┘
         │
         ▼
    Report results

Note: E2E tests require the stack to be running (`ktrdr sandbox up`).
The Makefile sources .env.sandbox if present, ensuring tests hit the right ports.
```

## API Contracts

### CLI Interface

```bash
ktrdr sandbox create <name> [--branch <branch>] [--slot <n>]
  Creates a new sandbox instance using git worktree.

  Arguments:
    name        Instance name (will be prefixed with ktrdr--)
    --branch    Git branch to checkout (default: current branch)
    --slot      Force specific port slot (default: auto-allocate)

  Exit codes:
    0   Success
    1   Slot unavailable or port conflict
    2   Git worktree creation failed
    3   Directory already exists

ktrdr sandbox init [--slot <n>]
  Initialize current directory as a sandbox instance (for existing clones).

  Exit codes:
    0   Success
    1   Already initialized
    2   Not a ktrdr repository
    3   Port conflict on allocated slot

ktrdr sandbox up [--no-wait] [--build]
  Start the sandbox stack.

  Arguments:
    --no-wait   Don't wait for Startability Gate
    --build     Force rebuild images

  Exit codes:
    0   Success, Startability Gate passed
    1   Compose up failed
    2   Startability Gate failed (with details)
    3   Port conflict detected

ktrdr sandbox down [--volumes]
  Stop the sandbox stack.

  Arguments:
    --volumes   Also remove volumes (database data, etc.)

ktrdr sandbox destroy [--keep-worktree]
  Completely remove instance.

  Arguments:
    --keep-worktree   Don't delete the git worktree/directory

ktrdr sandbox list
  List all sandbox instances.

  Output format:
    INSTANCE                    SLOT  STATUS   API PORT  CREATED

ktrdr sandbox status
  Show detailed status of current instance.

ktrdr sandbox logs [service] [--follow]
  View logs for instance services.

ktrdr sandbox init-shared [--from <path>] [--minimal]
  Initialize the shared data directory (~/.ktrdr/shared/).

  Arguments:
    --from      Copy data from existing dev environment
    --minimal   Download minimal seed data only
```

**Note:** Testing uses existing `make test-*` commands, not sandbox CLI.

### Environment File Schema (.env.sandbox)

```bash
# Instance Identity
INSTANCE_ID=ktrdr--feat-operation-metrics
COMPOSE_PROJECT_NAME=ktrdr--feat-operation-metrics
SLOT_NUMBER=2

# Ports (derived from slot)
KTRDR_API_PORT=8002
KTRDR_DB_PORT=5434
KTRDR_GRAFANA_PORT=3002
KTRDR_JAEGER_UI_PORT=16688
KTRDR_JAEGER_OTLP_PORT=4318
KTRDR_PROMETHEUS_PORT=9092
KTRDR_WORKER_BASE_PORT=5020

# Database
DB_HOST=localhost
DB_PORT=5434
DB_NAME=ktrdr
DB_USER=ktrdr
DB_PASSWORD=sandbox-${INSTANCE_ID}

# Workers
USE_STUB_WORKERS=false
WORKER_COUNT_BACKTEST=2
WORKER_COUNT_TRAINING=2

# Observability
OTLP_ENDPOINT=http://jaeger:4317

# Metadata
CREATED_AT=2024-01-15T10:30:00Z
SANDBOX_VERSION=1
```

## State Management

### State 1: Instance Registry

**Where:** `~/.ktrdr/sandbox/instances.json`

**Shape:** See Instance Registry component above

**Transitions:**
- `create` → adds entry
- `destroy` → removes entry
- `list` → reads only
- Stale entries cleaned on `list` (if directory doesn't exist)

### State 2: Instance Environment

**Where:** `.env.sandbox` in instance directory

**Shape:** Environment variables (see schema above)

**Transitions:**
- `create`/`init` → generates file
- `destroy` → deletes with worktree
- `up` → reads file, exports to compose

### State 3: Docker Resources

**Where:** Docker daemon

**Shape:** Containers, networks, volumes prefixed with `{instance_id}_`

**Transitions:**
- `up` → creates resources
- `down` → stops containers
- `down --volumes` → removes volumes
- `destroy` → removes all resources

## Error Handling

### Error Category: Slot Exhaustion

**When:** All 10 slots are allocated
**Response:** Error with message listing allocated slots and their instances
**User experience:** "All 10 sandbox slots are in use. Run 'ktrdr-sandbox list' to see instances. Destroy unused instances with 'ktrdr-sandbox destroy'."

### Error Category: Port Conflict

**When:** Allocated ports are already in use by another process
**Response:** Identify which port conflicts, suggest resolution
**User experience:** "Port 8002 is already in use. This could be another sandbox not tracked in the registry. Use 'lsof -i :8002' to identify the process."

### Error Category: Startability Gate Failure

**When:** Stack starts but health checks fail
**Response:** Report which checks failed, container logs for failed services
**User experience:**
```
Startability Gate: FAILED

✓ Database ready
✓ Backend container running
✗ Backend health check failed
  → GET http://localhost:8002/health returned 500
  → Last 10 log lines:
    [logs here]
✗ Workers not registered
  → Expected 4 workers, found 0
  → Worker containers are running but not registering
```

### Error Category: Worktree Conflict

**When:** Git worktree already exists or branch is checked out elsewhere
**Response:** Suggest alternative name or cleanup
**User experience:** "Cannot create worktree: branch 'feat-metrics' is already checked out at '/path/to/other'. Use a different name or checkout a different branch there first."

### Error Category: Not in Instance Directory

**When:** Running `up`, `down`, `status` outside an instance
**Response:** Guide user to correct directory or create instance
**User experience:** "Not in a sandbox instance directory. Run 'ktrdr-sandbox list' to see instances, or 'ktrdr-sandbox create <name>' to create one."

## Integration Points

### Git Integration

- Uses `git worktree add` for creating instances
- Uses `git worktree remove` for cleanup
- Detects parent repo for worktree metadata
- Works with both worktrees and standalone clones

### Docker Compose Integration

- Sets `COMPOSE_PROJECT_NAME` environment variable
- Passes `.env.sandbox` via `--env-file`
- Uses `docker compose ps --format json` for status
- Mounts shared data from `~/.ktrdr/shared/`

### Existing CLI Integration

Exposed as `ktrdr sandbox` subcommand alongside existing commands:

```bash
ktrdr sandbox create my-feature
ktrdr sandbox up
ktrdr sandbox list
```

The existing CLI also gains `--port` / `-p` flag for targeting instances:

```bash
ktrdr -p 8002 operations list
```

## Migration / Rollout

### CRITICAL: Backward Compatibility

**The existing `../ktrdr2` environment MUST continue to work throughout this transition.**

The new sandbox infrastructure is additive, not replacement. We build new capabilities while preserving the working system:

- Existing `docker compose up` in `../ktrdr2` continues to work (uses default ports)
- No breaking changes to compose file — only additions (parameterized ports with defaults)
- Slot 0 (default ports) is reserved for the main dev environment
- New sandbox instances use slots 1-10 with offset ports

**Transition Strategy:**

1. Make compose changes backward-compatible first (test existing workflow still works)
2. Only then add CLI commands
3. Validate each phase before proceeding
4. Keep escape hatch: if sandbox CLI breaks, raw `docker compose up` always works

### Phase 1: Compose Modifications (Backward-Compatible)

1. Remove all `container_name:` fields from compose
2. Parameterize all ports with `${KTRDR_*_PORT:-default}` — **defaults match current values**
3. Add shared data mounts (`~/.ktrdr/shared/`)
4. **Test that existing `docker compose up` still works exactly as before**

### Phase 2: CLI Tool - Core Commands

1. Implement `ktrdr sandbox create` with worktree support
2. Implement `ktrdr sandbox init` for existing clones
3. Implement `ktrdr sandbox up` with Startability Gate
4. Implement `ktrdr sandbox down` and `destroy`
5. Implement port allocator with conflict detection
6. Implement instance registry

### Phase 3: Shared Data & Status

1. Implement `ktrdr sandbox init-shared`
2. Implement `ktrdr sandbox list` and `status`
3. Implement `ktrdr sandbox logs`
4. Add CLI `--port` / `-p` flag

### Phase 4: Documentation & Polish

1. Update README with sandbox workflow
2. Document new dev machine setup
3. Handle edge cases (stale registry, orphaned containers, port conflicts)
4. Update Makefile to source `.env.sandbox` if present

## Verification Strategy

### CLI Commands

**Type:** User-facing CLI
**Unit Test Focus:** Argument parsing, port calculation, env file generation
**Integration Test:** Full create→up→down→destroy cycle with real Docker
**Smoke Test:** `ktrdr sandbox create test-verify && ktrdr sandbox up && ktrdr sandbox destroy`

### Port Allocator

**Type:** Pure logic
**Unit Test Focus:** Port mapping correctness, slot allocation, conflict detection
**Integration Test:** Verify port checking against real sockets
**Smoke Test:** N/A

### Instance Registry

**Type:** Persistence
**Unit Test Focus:** JSON serialization, schema validation
**Integration Test:** Write/read cycle, stale entry cleanup
**Smoke Test:** `cat ~/.ktrdr/sandbox/instances.json | jq`

### Startability Gate

**Type:** Health checking
**Unit Test Focus:** Mock responses, timeout handling
**Integration Test:** Against real running stack
**Smoke Test:** `ktrdr sandbox up --verbose` showing check results

### Compose Modifications

**Type:** Configuration
**Unit Test Focus:** N/A (declarative)
**Integration Test:** Start two instances simultaneously, verify isolation
**Smoke Test:** `COMPOSE_PROJECT_NAME=test1 docker compose up -d && COMPOSE_PROJECT_NAME=test2 docker compose up -d`

### Shared Data Package

**Type:** File system setup
**Unit Test Focus:** Path generation, copy logic
**Integration Test:** Full init-shared flow
**Smoke Test:** `ktrdr sandbox init-shared --minimal && ls ~/.ktrdr/shared/`
