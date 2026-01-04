# Isolated Development Sandbox: Design

## Problem Statement

KTRDR development is constrained to a single execution environment per developer machine. When working on multiple features in parallel (human-led or agent-led), there's no way to run isolated, complete KTRDR stacks side-by-side. The current sandbox provides a container with tools but not a full running KTRDR environment with database, workers, and observability.

This creates friction for:
- Parallel branch work (agent A and agent B collide)
- Automated E2E runs (agent needs a runnable environment per branch)
- Safe autonomy (agent needs broad permissions but you want minimal risk)

## Goals

What we're trying to achieve:

1. **One command to full environment** — Clone KTRDR, run a single command, get a complete working stack
2. **Parallel isolation** — 2-3 feature streams running simultaneously without collision
3. **Hot reload per instance** — Each instance's source code changes reflect in its own stack
4. **Autonomous agent capability** — Agents can run full test loops including E2E within their instance
5. **Predictable lifecycle** — Create, start, test, collect evidence, teardown — all reliable
6. **Startability Gate** — Every instance proves it can start cleanly before work begins

## Non-Goals (Out of Scope)

What we're explicitly not doing:

- **Host services in sandbox** — IB Gateway and GPU training run natively; sandboxes skip these (stub mode if needed)
- **Resource limits** — We'll document requirements but not enforce hard limits per instance
- **Production deployment** — This is for local development only
- **Perfect security** — We minimize blast radius but trust the developer's machine
- **Shared observability** — Each instance gets its own Grafana/Jaeger/Prometheus (simpler isolation)
- **Replacing existing tooling** — `make test-unit`, `uv run pytest`, etc. continue to work as-is

## User Experience

### Mental Model: Persistent Development Environments

Sandboxes are **persistent development environments**, not ephemeral per-feature containers:

- You create a sandbox once (e.g., `ktrdr--feature-work`)
- You work in it over days/weeks with hot reload
- You switch branches, run tests, develop features — all within the same sandbox
- Multiple sandboxes can run in parallel for different workstreams
- You destroy a sandbox when you're done with that workstream (or never)

This is exactly how `../ktrdr2` works today — a persistent environment with hot reload. The sandbox system lets you have 2-3 of these running simultaneously without port conflicts.

**Worktrees vs. Clones:**
- **Worktrees** share git objects (faster, less disk), separate working directories
- **Clones** are fully independent (simpler mental model, more disk)
- Both work equally well with the sandbox system

### Creating a New Instance

```bash
# From any directory
ktrdr sandbox create feat-operation-metrics

# What happens:
# 1. Creates git worktree at ../ktrdr--feat-operation-metrics
# 2. Allocates port slot (e.g., slot 2 → ports 8002, 5434, 3002, etc.)
# 3. Generates .env.sandbox with instance-specific config
# 4. Reports instance details
```

Output:
```
Created instance: feat-operation-metrics
  Location: /Users/karl/Documents/dev/ktrdr--feat-operation-metrics
  Port slot: 2
  API: http://localhost:8002
  Grafana: http://localhost:3002
  Jaeger: http://localhost:16688

Run 'cd ../ktrdr--feat-operation-metrics && ktrdr sandbox up' to start
```

### Starting an Instance

```bash
cd ../ktrdr--feat-operation-metrics
ktrdr sandbox up

# What happens:
# 1. Validates .env.sandbox exists
# 2. Sets COMPOSE_PROJECT_NAME from instance_id
# 3. Runs docker compose up -d
# 4. Waits for health checks (Startability Gate)
# 5. Reports status
```

Output:
```
Starting instance: feat-operation-metrics (slot 2)
  ✓ Database ready
  ✓ Backend healthy
  ✓ Workers registered (2 backtest, 2 training)
  ✓ Observability stack ready

Startability Gate: PASSED

Instance ready:
  API: http://localhost:8002/api/v1/docs
  Grafana: http://localhost:3002
```

### Running Tests

Once in an instance directory, use the existing tooling:

```bash
make test-unit        # Unit tests (fast, no stack needed)
make test-integration # Integration tests (needs DB)
make test-e2e         # E2E tests (needs full stack)
make quality          # Lint + format + typecheck
```

The instance's `.env.sandbox` sets environment variables so tests automatically target the correct ports (e.g., `localhost:8002` instead of `localhost:8000`).

For E2E tests specifically, the stack must be running. The tests hit the instance's API at its allocated port.

### Checking Status

```bash
ktrdr sandbox list

# Output:
# INSTANCE                    SLOT  STATUS   API PORT  CREATED
# feat-operation-metrics      2     running  8002      2h ago
# feat-training-improvements  1     stopped  8001      1d ago
# fix-worker-registration     3     running  8003      30m ago
```

```bash
ktrdr sandbox status  # From within an instance directory

# Output:
# Instance: feat-operation-metrics (slot 2)
# Status: running
# Containers: 8/8 healthy
# API: http://localhost:8002 (responding)
# Workers: 4 registered
```

### Stopping and Cleanup

```bash
ktrdr sandbox down           # Stop containers, keep volumes
ktrdr sandbox destroy        # Stop containers, remove volumes, delete worktree
ktrdr sandbox destroy --all  # Clean up all instances
```

### Working with an Existing Clone

If you already have a clone (not a worktree):

```bash
cd /path/to/my-ktrdr-clone
ktrdr sandbox init           # Initialize as sandbox instance
ktrdr sandbox up
```

## Key Decisions

### Decision 1: Instance Identity from Directory Name

**Choice:** `instance_id` is derived from the directory basename, slugified.

**Alternatives considered:**
- UUID per instance (harder to remember, no semantic meaning)
- Branch name only (doesn't work for multiple worktrees of same branch)
- Manual specification (error-prone)

**Rationale:** Directory name is visible, memorable, and naturally unique per worktree. Slugifying ensures valid Docker resource names.

Example: `/Users/karl/Documents/dev/ktrdr--feat-operation-metrics` → `ktrdr--feat-operation-metrics`

### Decision 2: Pool-Based Port Allocation

**Choice:** Pre-defined port slots (1-10) with deterministic port mapping.

| Slot | Backend | DB | Grafana | Jaeger UI | Workers |
|------|---------|-----|---------|-----------|---------|
| 1 | 8001 | 5433 | 3001 | 16687 | 5010-5019 |
| 2 | 8002 | 5434 | 3002 | 16688 | 5020-5029 |
| 3 | 8003 | 5435 | 3003 | 16689 | 5030-5039 |
| ... | ... | ... | ... | ... | ... |

**Alternatives considered:**
- Dynamic port allocation (find free ports at startup) — unpredictable, hard to bookmark
- Hash-based (hash instance_id to port range) — could collide, hard to predict
- No host ports (everything internal) — loses ability to browse from host

**Rationale:** Predictable ports mean you can bookmark instance URLs. Slots are simple to reason about. 10 slots is plenty for local dev.

### Decision 3: Remove All `container_name:` from Compose

**Choice:** Delete all `container_name:` fields, let Compose generate names as `<project>_<service>_<index>`.

**Alternatives considered:**
- Parameterize container names with instance_id — still hardcoded, just templated
- Keep container names for "main" dev stack — creates inconsistency

**Rationale:** This is the single biggest unlock for parallel stacks. Hardcoded container names prevent multiple instances of the same compose file.

### Decision 4: Separate Observability Per Instance

**Choice:** Each instance runs its own Grafana, Jaeger, and Prometheus.

**Alternatives considered:**
- Shared observability with instance_id labels — cleaner UX but requires careful configuration and filtering
- No observability in sandbox — loses debugging capability

**Rationale:** Simpler isolation. No risk of data mixing. Each instance is fully self-contained. The cost is ~3 extra containers per instance, which is acceptable for 2-3 parallel streams.

### Decision 5: E2E Tests Run Inside the Stack

**Choice:** E2E tests execute in a container that's part of the Compose network, using DNS names (`backend:8000`).

**Alternatives considered:**
- E2E from host using published ports — requires port allocation, more fragile
- E2E in sandbox container connecting to stack — network complexity

**Rationale:** No port conflicts. Tests are reproducible. Same approach works in CI. Container can be `docker compose run --rm e2e-tests`.

### Decision 6: CLI as Subcommand of Existing ktrdr

**Choice:** Implement sandbox commands as a subcommand group of the existing `ktrdr` CLI, not as a separate binary.

**What is Typer?** Typer is the CLI library we already use for the `ktrdr` command (see `ktrdr/cli/main.py`). It handles argument parsing, help text, and subcommands, and is built on top of Click. No new dependency.

**Implementation:**

- New file: `ktrdr/cli/sandbox.py`
- Registered in `ktrdr/cli/__init__.py` via `cli_app.add_typer(sandbox_app)`
- Commands: `ktrdr sandbox create`, `ktrdr sandbox up`, etc.

**Alternatives considered:**

- Separate `ktrdr-sandbox` binary — two entry points, PATH complexity
- Shell scripts — harder to maintain, less portable
- Makefile targets — limited expressiveness

**Rationale:** Single entry point for all KTRDR commands. Shared CLI infrastructure. The `--port` flag naturally applies to all existing commands. No installation complexity.

### Decision 7: Shared Data Directory

**Choice:** All instances share common data via a mounted host directory at `~/.ktrdr/shared/`.

**What's shared:**

- `data/` — Symbol data (OHLCV, etc.)
- `strategies/` — Strategy configurations
- `models/` — Trained models

**How it works:** Docker Compose mounts `~/.ktrdr/shared/data:/app/data` (and similar for strategies/models) for all instances. This mirrors the homelab NFS mount pattern.

**Alternatives considered:**

- Per-instance data copies — wastes disk, slower setup
- Symlinks in each worktree — requires management, fragile
- No sharing — requires re-downloading data for each instance

**Rationale:** Matches homelab pattern. Data is read-mostly. Models and strategies can be shared safely. Avoids duplicating gigabytes of symbol data.

### Decision 8: Real Workers by Default

**Choice:** Sandbox instances run real workers (backtesting, training), not stubs.

**Rationale:** The whole point is running real E2E tests. Stub workers would defeat the purpose. Host services (IB Gateway, GPU training) are skipped since they run natively outside Docker.

### Decision 9: Database Seeding

**Choice:** New instances start with seed data (schema + essential reference data).

**What's seeded:**

- Database schema (migrations applied)
- Essential reference data (if any)

**Note:** Symbol data (OHLCV) lives in the filesystem (`data/` directory), not the database. It's shared via `~/.ktrdr/shared/data/`.

**Rationale:** Instances should be immediately usable with schema ready.

### Decision 10: CLI Instance Targeting via Directory Detection

**Choice:** The `ktrdr` CLI gains a `--port` / `-p` flag and auto-detects the target based on the current directory's `.env.sandbox` file.

**Usage:**

```bash
# Explicit: full URL
ktrdr -u http://localhost:8002 operations list

# Explicit: just the port (assumes localhost)
ktrdr -p 8002 operations list

# Automatic: CLI detects .env.sandbox in current/parent directory
cd ../ktrdr--feat-a
ktrdr operations list  # Auto-targets port 8001
```

**How it works (priority order):**

1. `--url` flag — explicit full URL, always wins
2. `--port` flag — convenience shorthand for localhost
3. `.env.sandbox` file — auto-detect from current directory tree
4. Default — `http://localhost:8000`

**Critical design choice:** The CLI reads the `.env.sandbox` FILE directly, NOT environment variables. This avoids env var pollution between terminal sessions.

```python
# We do this:
config = parse_dotenv_file(".env.sandbox")
port = config.get("KTRDR_API_PORT")

# NOT this (env vars leak between shells):
port = os.environ.get("KTRDR_API_PORT")
```

**Rationale:** Directory-based detection is predictable — behavior depends on where you are in the filesystem, not on shell state. No need for `source .env.sandbox` or manual exports.

### Decision 11: Two-File Development Strategy with Merge

**Choice:** During development, use a separate `docker-compose.sandbox.yml` file. Merge into main `docker-compose.yml` only when confident.

**Why:**

- Protects existing `../ktrdr2` workflow throughout development
- Allows iteration without risk
- Merge only happens when fully tested

**Merge requirements:**

- Git tag before merge (rollback point)
- Backup of original compose file
- Automated verification script
- Rollback script that restores in seconds

**Rationale:** The existing dev environment is critical infrastructure. We don't touch it until the new system is proven.

### Decision 12: Internal Ports Fixed, External Ports Parameterized

**Choice:** Only parameterize the host-side (left) of port mappings. Internal container ports stay fixed.

**Example:**

```yaml
# Correct: external varies, internal fixed
ports:
  - "${KTRDR_API_PORT:-8000}:8000"

# Wrong: unnecessary complexity
ports:
  - "${KTRDR_API_PORT:-8000}:${KTRDR_API_PORT:-8000}"
```

**Rationale:** Each sandbox has its own Docker network, so internal ports don't conflict. Services always listen on their standard ports (backend on 8000, db on 5432). Only the host-published ports need to differ.

## Open Questions

Issues to resolve during implementation:

1. **Compose file location** — `docker-compose.sandbox.yml` at root, or under `deploy/environments/parallel/`? Leaning toward root for simplicity.

2. **Registry cleanup frequency** — Clean stale entries on every `list`, or require explicit command?

3. **Worker count per instance** — Always 4 workers, or make configurable via `.env.sandbox`?

## Resolved Questions

Decisions made during design review:

1. **Worktree vs. Clone** — Support both. `ktrdr sandbox create` uses worktrees by default. `ktrdr sandbox init` initializes an existing clone. Users uncomfortable with worktrees can use regular clones.

2. **Main dev environment** — Slot 0 with standard ports (8000, 5432, 3000). Goal is eventually to not need a special "main" environment, but for now it's practical.

3. **Stub vs. real workers** — Real workers. The whole point is real E2E testing.

4. **Database seeding** — Yes, seed schema and essential data so instances are immediately usable.

5. **Test execution** — Use existing `make test-*` commands. No custom test CLI. The sandbox handles environment isolation, not test execution.

6. **Shared data initialization** — Create a "shared data package" as part of this feature. When setting up a new dev machine, there should be a clear, documented way to initialize `~/.ktrdr/shared/` with the required data (symbol data, strategies, models). This makes onboarding new machines straightforward.

7. **Port conflict detection** — If a slot's ports are in use by something external (not a tracked sandbox), blacklist that slot entirely. The CLI should detect this during `ktrdr sandbox up` and refuse to start, suggesting the user pick a different slot or resolve the conflict.

8. **Slot persistence mechanism** — Use `~/.ktrdr/sandbox/instances.json`. Clean stale entries (instance directory doesn't exist) during `list` command.

9. **Shared data concurrent writes** — Accept the risk. Models and strategies are written infrequently, collision probability is low. The convenience of sharing outweighs the risk.

10. **Repo validation for init** — Check git remote to verify it's a KTRDR repository, not just presence of specific files.

11. **Instance ID collision** — If two directories have the same basename, error with helpful message asking user to rename or use `--name` flag.

12. **Backward compatibility approach** — Use separate `docker-compose.sandbox.yml` during development. Merge only when confident, with rollback script and verification checklist.
