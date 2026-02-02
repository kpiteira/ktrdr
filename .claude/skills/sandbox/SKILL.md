---
name: sandbox
description: Use when working with sandbox environments, port mappings, docker compose in sandboxes, .env.sandbox files, sandbox CLI commands, local-prod, host service connectivity, shared data directories, or 1Password secrets integration.
---

# Sandbox System

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL sandbox loaded!`

Load this skill when working on:

- Sandbox or local-prod CLI commands (via `kinfra`)
- Port allocation or conflict resolution
- Docker compose in multi-instance contexts
- `.env.sandbox` files or auto-detection
- Shared data directories (`~/.ktrdr/shared/`)
- 1Password secrets integration
- Host services (IB Gateway, GPU training) in sandbox context
- Startability gate health checks
- Worktree-based parallel development workflow

---

## What Sandboxes Are

Sandboxes are **persistent, isolated development environments** running the full KTRDR stack (backend, workers, DB, Grafana, Jaeger) on unique port sets. They enable parallel development — multiple feature branches running simultaneously without collision.

Sandboxes are NOT ephemeral. You create one, work in it for days/weeks with hot reload, switch branches, run tests — all within the same sandbox.

### Worktree Workflow (Recommended)

The recommended workflow uses **kinfra** commands with pre-provisioned sandbox slots:

1. **`uv run kinfra spec <feature>`** — Create spec worktree for design (no sandbox)
2. **`uv run kinfra impl <feature/milestone>`** — Create impl worktree with sandbox slot
3. Work on implementation with full E2E testing capability
4. **`uv run kinfra done <name>`** — Clean up after PR merge (releases sandbox slot)

This workflow uses a **slot pool** — pre-provisioned sandbox configurations (slots 1 and 2) that are claimed on-demand by impl worktrees. No manual slot allocation needed.

**Naming conventions:**
- Spec worktrees: `ktrdr-spec-<feature>` (no Docker containers)
- Impl worktrees: `ktrdr-impl-<feature>` (has sandbox slot)
- Long-lived clones: `ktrdr--<purpose>` (e.g., `ktrdr--stream-b`)

### Legacy Workflow (Still Supported)

For long-lived development environments, clones are still supported:

1. Clone the repo: `git clone ... ../ktrdr--feature-name`
2. Register as sandbox: `cd ../ktrdr--feature-name && uv run kinfra sandbox init`
3. Work in it for days/weeks
4. Clean up: `uv run kinfra sandbox destroy`

### Two Flavors

| | Sandbox | Local-Prod |
|---|---------|------------|
| Purpose | Feature development, E2E testing | Real execution with host services |
| Git setup | Worktree (via kinfra impl) or clone | Clone (required) |
| Slot | 1-2 (slot pool) or 3-10 (manual) | 0 (standard ports) |
| Count | Up to 10 | Singleton |
| Host services | No (IB/GPU skipped) | Yes (IB Gateway, GPU training) |
| 1Password item | `ktrdr-sandbox-dev` | `ktrdr-local-prod` |
| Create command | `kinfra impl` (auto slot) or `kinfra sandbox init` | `kinfra local-prod init` |

---

## Slot Pool

The slot pool provides pre-provisioned sandbox configurations for impl worktrees:

- **Slots 1-2** are in the pool, available for `kinfra impl` to claim automatically
- **Slot 0** is reserved for local-prod
- **Slots 3-10** available for manual allocation via `kinfra sandbox init --slot N`

When you run `kinfra impl`, it:
1. Finds the first available slot in the pool
2. Creates the worktree and `.env.sandbox`
3. Starts containers on that slot's ports
4. Records the claim in `~/.ktrdr/sandbox/slots.json`

When you run `kinfra done`, it:
1. Stops containers
2. Releases the slot back to the pool
3. Removes the worktree

---

## Port Allocation

Every sandbox gets a **slot** (0-10) that deterministically maps to ports:

```
Slot 0 (local-prod):  API=8000  DB=5432  Grafana=3000  Jaeger=16686  Workers=5003-5006
Slot 1:               API=8001  DB=5433  Grafana=3001  Jaeger=16687  Workers=5007-5010
Slot 2:               API=8002  DB=5434  Grafana=3002  Jaeger=16688  Workers=5017-5020
Slot N:               API=8000+N DB=5432+N Grafana=3000+N Jaeger=16686+N
```

Worker port formula for slots 1-10: `5007 + (slot-1)*10` through `5010 + (slot-1)*10`

**Only external (host) ports vary.** Internal container ports are always fixed (8000, 5432, etc.). Docker Compose maps `${KTRDR_API_PORT}:8000`.

### Key File: `ktrdr/cli/sandbox_ports.py`

```python
from ktrdr.cli.sandbox_ports import get_ports, check_ports_available, PortAllocation

ports: PortAllocation = get_ports(slot=2)
ports.backend        # 8002
ports.db              # 5434
ports.grafana         # 3002
ports.jaeger_ui       # 16688
ports.worker_ports    # [5017, 5018, 5019, 5020]

# Check for conflicts before startup
conflicts = check_ports_available(slot=2)
if conflicts:
    print(f"Ports in use: {conflicts}")
```

---

## .env.sandbox File

Every sandbox has a `.env.sandbox` in its root directory. This is the source of truth for the instance.

```bash
# Instance Identity
INSTANCE_ID=ktrdr--stream-b
COMPOSE_PROJECT_NAME=ktrdr--stream-b
SLOT_NUMBER=2

# Ports
KTRDR_API_PORT=8002
KTRDR_DB_PORT=5434
KTRDR_GRAFANA_PORT=3002
KTRDR_JAEGER_UI_PORT=16688
KTRDR_JAEGER_OTLP_GRPC_PORT=4337
KTRDR_JAEGER_OTLP_HTTP_PORT=4338
KTRDR_PROMETHEUS_PORT=9092
KTRDR_WORKER_PORT_1=5017  # 5007 + (slot-1)*10
KTRDR_WORKER_PORT_2=5018
KTRDR_WORKER_PORT_3=5019
KTRDR_WORKER_PORT_4=5020

# Shared Data
KTRDR_SHARED_DIR=/Users/karl/.ktrdr/shared
KTRDR_DATA_DIR=/Users/karl/.ktrdr/shared/data
KTRDR_MODELS_DIR=/Users/karl/.ktrdr/shared/models
KTRDR_STRATEGIES_DIR=/Users/karl/.ktrdr/shared/strategies
```

### Auto-Detection

The CLI resolves the API URL with this priority:
1. `--url` flag (explicit full URL)
2. `--port` flag (shorthand, assumes localhost)
3. `.env.sandbox` file found in current/parent directories
4. Default: `http://localhost:8000`

**Key file:** `ktrdr/cli/sandbox_detect.py`

**Important:** Detection reads the `.env.sandbox` FILE, not environment variables. This prevents cross-contamination between terminal sessions.

---

## Docker Compose

**File:** `docker-compose.sandbox.yml` (repo root)

Key design choices:
- **No `container_name:` fields** — Docker Compose uses `<project>_<service>_<index>` naming, enabling parallel instances
- **`COMPOSE_PROJECT_NAME`** set from `.env.sandbox` — all resources (containers, volumes, networks) scoped to project
- **Parameterized host ports** with defaults: `${KTRDR_API_PORT:-8000}:8000`
- **Shared data mounts** with backward compatibility: `${KTRDR_DATA_DIR:-./data}:/app/data`

### Container Naming

Containers follow Docker Compose convention:
```
ktrdr--stream-b-backend-1
ktrdr--stream-b-db-1
ktrdr--stream-b-grafana-1
```

To target a specific sandbox's containers:
```bash
# Always use -p or COMPOSE_PROJECT_NAME
docker compose -p ktrdr--stream-b -f docker-compose.sandbox.yml logs backend
```

---

## Instance Registry

**Location:** `~/.ktrdr/sandbox/instances.json`

Tracks all sandbox instances and their slots. Managed by `ktrdr/cli/sandbox_registry.py`.

```json
{
  "version": 1,
  "local_prod": {
    "instance_id": "ktrdr-prod",
    "slot": 0,
    "path": "/Users/karl/Documents/dev/ktrdr-prod"
  },
  "instances": {
    "ktrdr--stream-b": {
      "instance_id": "ktrdr--stream-b",
      "slot": 2,
      "path": "/Users/karl/Documents/dev/ktrdr--stream-b",
      "is_worktree": false,
      "parent_repo": null
    }
  },
  "allocated_slots": [2]
}
```

Key functions:
```python
from ktrdr.cli.sandbox_registry import (
    load_registry,
    add_instance,
    remove_instance,
    get_allocated_slots,
    allocate_next_slot,
    clean_stale_entries,   # Remove entries where directory no longer exists
    get_local_prod,
    set_local_prod,
)
```

---

## CLI Commands

### kinfra Worktree Commands (Recommended)

```bash
uv run kinfra spec <feature>
    # Create spec worktree for design work (no sandbox)
    # Creates ../ktrdr-spec-<feature> with branch spec/<feature>

uv run kinfra impl <feature/milestone>
    # Create impl worktree with sandbox slot
    # Claims slot from pool, starts containers automatically
    # Creates ../ktrdr-impl-<feature> with branch impl/<feature>

uv run kinfra done <name> [--force]
    # Complete worktree, release sandbox slot, remove worktree
    # Checks for uncommitted/unpushed changes (use --force to bypass)
    # Aliases: kinfra finish, kinfra complete

uv run kinfra worktrees
    # List active worktrees with sandbox status
```

### kinfra Sandbox Commands

```bash
uv run kinfra sandbox slots
    # List sandbox slot pool with claimed/available status

uv run kinfra sandbox up [--no-wait] [--build] [--timeout <s>] [--no-secrets]
    # Start stack + run startability gate

uv run kinfra sandbox down [--volumes]
    # Stop containers

uv run kinfra sandbox init [--slot <n>] [--name <name>]
    # Register existing clone/worktree as sandbox (legacy)

uv run kinfra sandbox status
    # Current instance details

uv run kinfra sandbox logs [service] [--follow] [--tail <n>]
```

### kinfra Local-Prod Commands

```bash
uv run kinfra local-prod init
    # Must be a clone (not worktree), enforces singleton, uses slot 0

uv run kinfra local-prod up [--no-wait] [--build] [--timeout <s>] [--no-secrets]
uv run kinfra local-prod down [--volumes]
uv run kinfra local-prod status
```

### Key Files

| File | Purpose |
|------|---------|
| `ktrdr/cli/sandbox.py` | Sandbox CLI commands |
| `ktrdr/cli/local_prod.py` | Local-prod CLI commands |
| `ktrdr/cli/sandbox_ports.py` | Port allocation |
| `ktrdr/cli/sandbox_registry.py` | Instance registry |
| `ktrdr/cli/sandbox_gate.py` | Startability gate health checks |
| `ktrdr/cli/sandbox_detect.py` | API URL auto-detection |
| `ktrdr/cli/instance_core.py` | Shared lifecycle logic |
| `ktrdr/cli/helpers/secrets.py` | 1Password integration |

---

## Startability Gate

After `docker compose up`, the gate validates the stack is healthy before declaring success.

**Checks (sequential):**
1. **Database** — TCP connection to DB port
2. **Backend** — `GET /api/v1/health` returns 200
3. **Workers** — `GET /api/v1/workers` returns 4+ registered workers (skipped if backend fails)
4. **Observability** — Jaeger UI responds

**Implementation:** `ktrdr/cli/sandbox_gate.py` — `StartabilityGate` class

Polling: 2-second intervals, configurable timeout (default 120s).

```bash
ktrdr sandbox up              # Runs gate (default)
ktrdr sandbox up --no-wait    # Skip gate
ktrdr sandbox up --timeout 60 # Custom timeout
```

---

## Secrets (1Password)

Secrets are fetched at CLI time and injected into Docker as environment variables.

**1Password items:**
- `ktrdr-sandbox-dev` — for sandbox instances
- `ktrdr-local-prod` — for local-prod

**Fields fetched:** `db_password`, `jwt_secret`, `anthropic_api_key`, `grafana_password`

**Mapping to env vars:**
```python
SANDBOX_SECRETS_MAPPING = {
    "db_password": "DB_PASSWORD",
    "jwt_secret": "JWT_SECRET",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "grafana_password": "GF_ADMIN_PASSWORD",
}
```

**Flow:**
```
1Password → ktrdr sandbox up → compose_env dict → docker compose → container env
```

**Fallbacks:**
- 1Password not installed or not authenticated: insecure defaults used
- `--no-secrets` flag: explicitly skip 1Password
- Secrets don't need re-fetching on hot reload (container env persists, only Python process restarts)

---

## Shared Data

**Location:** `~/.ktrdr/shared/`

```
~/.ktrdr/shared/
├── data/         # Symbol data (OHLCV CSVs)
├── models/       # Trained models
└── strategies/   # Strategy configurations
```

All sandboxes mount the same shared directory, avoiding gigabytes of duplicated data. Docker compose mounts:
```yaml
- ${KTRDR_DATA_DIR:-./data}:/app/data
- ${KTRDR_MODELS_DIR:-./models}:/app/models
- ${KTRDR_STRATEGIES_DIR:-./strategies}:/app/strategies
```

If `KTRDR_DATA_DIR` is unset, falls back to local `./data` for backward compatibility.

---

## Host Services (Local-Prod Only)

Host services run natively on the host machine (not in Docker). Only local-prod connects to them because it uses slot 0 (standard ports).

| Service | Port | Purpose |
|---------|------|---------|
| IB Host Service | 5001 | IB Gateway TCP proxy |
| Training Host Service | 5002 | GPU-accelerated training |

**Enable via environment variables:**
```bash
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://localhost:5001
```

**Docker containers connect via:** `host.docker.internal` (Docker Desktop feature)

Sandboxes (slots 1-10) do NOT connect to host services. They use containerized workers only.

---

## Common Gotchas

### Never kill port 8000 with lsof

`lsof -ti:8000 | xargs kill` destroys Docker containers. If something is wrong, use `docker compose down` or `ktrdr sandbox down`.

### Container names are project-scoped

Don't hardcode container names. Use `docker compose -p <project> ...` or rely on `COMPOSE_PROJECT_NAME` from `.env.sandbox`.

### API URL detection

When writing code or tests that call the API, never hardcode `localhost:8000`. Use:
```python
from ktrdr.cli.sandbox_detect import get_effective_api_url
url = get_effective_api_url()  # Reads .env.sandbox automatically
```

Or in shell:
```bash
source .env.sandbox
curl http://localhost:${KTRDR_API_PORT}/api/v1/health
```

### Clone vs Worktree detection

```python
def _is_clone_not_worktree(path):
    git_path = path / ".git"
    return git_path.is_dir()  # Clone = directory, Worktree = file
```

Local-prod requires a clone. Sandboxes work with either but clones are the norm.

### Destroy uses registry path, not cwd

`local-prod destroy` MUST look up the path from the registry, not use the current working directory. Using cwd caused data loss in the M6 implementation.

---

## Checking Current Environment

```bash
# Am I in a sandbox?
ls .env.sandbox 2>/dev/null && echo "SANDBOX" || echo "NOT A SANDBOX"

# What slot/ports?
cat .env.sandbox

# Full status
uv run kinfra sandbox status

# List all worktrees
uv run kinfra worktrees

# List sandbox slots
uv run kinfra sandbox slots
```

---

## Documentation

- Design: `docs/designs/Sandbox/DESIGN.md`
- Usage Guide: `docs/designs/Sandbox/USAGE_GUIDE.md`
- Validation: `docs/designs/Sandbox/VALIDATION.md`
- Implementation milestones: `docs/designs/Sandbox/implementation/M1-M7`
