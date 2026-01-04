# Isolated Development Sandbox: Design Validation

**Date:** 2026-01-03
**Documents Validated:**
- Design: [DESIGN.md](DESIGN.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## Validation Summary

**Scenarios Validated:** 6 happy path scenarios traced
**Critical Gaps Found:** 8 (all resolved)
**Interface Contracts:** CLI, ports, .env.sandbox, registry

---

## Scenarios Validated

### Happy Paths

| # | Scenario | Description | Verdict |
|---|----------|-------------|---------|
| 11a | Backward Compat (Dev) | ktrdr2 works unchanged during development | SAFE - two-file strategy isolates |
| 11b | Backward Compat (Merge) | ktrdr2 works after merge with defaults | SAFE with verification checklist |
| 3 | Parallel Operation | Two sandboxes run simultaneously | SAFE - networks/volumes isolated |
| 1 | Fresh Sandbox Creation | create → up → verify health | CLEAR |
| 2 | Initialize Existing Clone | existing dir → init → up | CLEAR |
| 4 | CLI Instance Targeting | ktrdr -p 8002 operations list | CLEAR |

### Error Paths (Identified, Not Traced)

| # | Scenario | Notes |
|---|----------|-------|
| 5 | Port Conflict Detection | CLI refuses to start, shows conflicting port |
| 6 | Startability Gate Failure | Shows which checks failed + logs |
| 7 | Worktree Conflict | Helpful error message |

### Edge Cases (Identified, Not Traced)

| # | Scenario | Notes |
|---|----------|-------|
| 8 | Slot Exhaustion | Error with list of instances, suggests cleanup |
| 9 | Stale Registry | Cleaned on `list` command |
| 10 | Destroy Running Instance | Graceful handling |

---

## Key Decisions Made

### Decision 1: Two-File Strategy During Development

**Context:** Need to protect existing ktrdr2 workflow during sandbox feature development.

**Decision:** Create separate `docker-compose.sandbox.yml` during development. Merge into main `docker-compose.yml` only when confident.

**Trade-off accepted:** Temporary duplication, but zero risk to existing workflow.

### Decision 2: CLI as Subcommand of Existing ktrdr

**Context:** Could create separate `ktrdr-sandbox` binary or add subcommand to existing CLI.

**Decision:** Add `sandbox` as subcommand group to existing `ktrdr` CLI.

**Rationale:**
- Single entry point for all KTRDR commands
- Shared CLI infrastructure
- `--port` flag naturally applies to existing commands
- No PATH or installation complexity

**Usage:**
```bash
ktrdr sandbox create feat-a    # New subcommand group
ktrdr sandbox up
ktrdr -p 8002 operations list  # Existing command with new flag
```

### Decision 3: Internal Ports Fixed, External Ports Parameterized

**Context:** Services need different ports to avoid conflicts between instances.

**Decision:**
- Internal ports (container-side): Stay fixed (backend always listens on 8000)
- External ports (host-side): Parameterized per slot

**Rationale:** Each sandbox has its own Docker network, so internal ports don't conflict. Only host-published ports need to differ.

```yaml
# Example for slot 2
ports:
  - "${KTRDR_API_PORT:-8000}:8000"  # Host 8002 → Container 8000
```

### Decision 4: Directory-Based Auto-Detection (Not Env Vars)

**Context:** Want CLI to "just work" in sandbox directories without manual configuration.

**Decision:** CLI reads `.env.sandbox` FILE directly when in a sandbox directory. Does NOT use environment variables.

**Rationale:** Env vars leak between terminal sessions and cause "works on my machine" bugs. File-based detection is predictable based on filesystem location.

**Priority order:**
1. `--url` flag (explicit full URL)
2. `--port` flag (convenience shorthand)
3. `.env.sandbox` file in current/parent directory
4. Default: `http://localhost:8000`

### Decision 5: Worker Ports Use Slot-Based Ranges

**Context:** Workers need published ports for debugging and testing.

**Decision:** Use slot-based port ranges:
- Slot 1: workers on 5010-5019
- Slot 2: workers on 5020-5029
- etc.

**Rationale:** Allows direct worker access for debugging/smoke tests while maintaining predictable allocation.

### Decision 6: Accept Shared Data Write Risk

**Context:** `~/.ktrdr/shared/` contains data/, models/, strategies/. Concurrent writes could conflict.

**Decision:** Accept the risk. Share all three directories.

**Rationale:** Models and strategies are written infrequently. Collision probability is low, and the convenience of sharing outweighs the risk.

### Decision 7: Shared Data Mount with Fallback Default

**Context:** Merged compose file needs to work with or without shared data setup.

**Decision:** Use `${KTRDR_SHARED_DIR:-./data}:/app/data` pattern.

**Rationale:**
- Without env var: uses `./data` (current behavior, backward compatible)
- With env var: uses `~/.ktrdr/shared/data` (sandbox mode)

### Decision 8: Merge Requires Easy Rollback

**Context:** Merging sandbox changes into main compose carries risk.

**Decision:** Milestone 6 includes:
- Git tag before merge
- Backup of original compose file
- Rollback script that restores in seconds
- Automated verification checklist

**Trade-off accepted:** Extra process, but guaranteed 5-minute recovery.

---

## Interface Contracts

### CLI Commands

```bash
# Instance Lifecycle
ktrdr sandbox create <name> [--branch <branch>] [--slot <n>]
ktrdr sandbox init [--slot <n>]
ktrdr sandbox up [--no-wait] [--build]
ktrdr sandbox down [--volumes]
ktrdr sandbox destroy [--keep-worktree]

# Status & Inspection
ktrdr sandbox list
ktrdr sandbox status
ktrdr sandbox logs [service] [--follow]

# Utilities
ktrdr sandbox init-shared [--from <path>] [--minimal]

# Existing commands gain --port flag
ktrdr --port 8002 operations list
ktrdr -p 8002 backtests list
```

### Port Allocation

```
Slot 0 (main dev):
  backend: 8000, db: 5432, grafana: 3000, jaeger: 16686
  workers: 5003, 5004, 5005, 5006

Slot N (1-10):
  backend: 8000+N, db: 5432+N, grafana: 3000+N, jaeger: 16686+N
  workers: 5000 + N*10 + {0,1,2,3}

Example Slot 2:
  backend: 8002, db: 5434, grafana: 3002, jaeger: 16688
  workers: 5020, 5021, 5022, 5023
```

### .env.sandbox Schema

```bash
# Instance Identity
INSTANCE_ID=ktrdr--feat-operation-metrics
COMPOSE_PROJECT_NAME=ktrdr--feat-operation-metrics
SLOT_NUMBER=2

# Published Ports
KTRDR_API_PORT=8002
KTRDR_DB_PORT=5434
KTRDR_GRAFANA_PORT=3002
KTRDR_JAEGER_UI_PORT=16688
KTRDR_JAEGER_OTLP_GRPC_PORT=4319
KTRDR_JAEGER_OTLP_HTTP_PORT=4320
KTRDR_PROMETHEUS_PORT=9092
KTRDR_WORKER_PORT_1=5020
KTRDR_WORKER_PORT_2=5021
KTRDR_WORKER_PORT_3=5022
KTRDR_WORKER_PORT_4=5023

# Shared Data
KTRDR_SHARED_DIR=~/.ktrdr/shared

# Metadata
CREATED_AT=2024-01-15T10:30:00Z
SANDBOX_VERSION=1
```

### Instance Registry

**Location:** `~/.ktrdr/sandbox/instances.json`

```json
{
  "version": 1,
  "instances": {
    "ktrdr--feat-operation-metrics": {
      "slot": 2,
      "path": "/Users/karl/Documents/dev/ktrdr--feat-operation-metrics",
      "created_at": "2024-01-15T10:30:00Z",
      "is_worktree": true,
      "parent_repo": "/Users/karl/Documents/dev/ktrdr2"
    }
  }
}
```

### Startability Gate Checks

1. **Database ready**: `pg_isready` succeeds
2. **Backend healthy**: `GET /api/v1/health` returns 200
3. **Workers registered**: `GET /api/v1/workers` returns expected count
4. **Observability ready**: Jaeger UI responds

### CLI URL Resolution

```python
def resolve_api_url(explicit_url, explicit_port, cwd) -> str:
    """
    Priority:
    1. --url flag (explicit full URL)
    2. --port flag (becomes http://localhost:{port})
    3. .env.sandbox in current/parent directory
    4. Default: http://localhost:8000

    IMPORTANT: Reads .env.sandbox FILE, not environment variables.
    This avoids env var pollution between terminal sessions.
    """
```

---

## Implementation Milestones

### Milestone 1: Compose File + Shared Data Setup

**User Story:** Developer can manually run two KTRDR stacks in parallel with shared data.

**Scope:**
- `docker-compose.sandbox.yml` with parameterized ports
- `~/.ktrdr/shared/` directory structure
- Documentation of manual process

**E2E Test:**
```bash
# Setup shared data
mkdir -p ~/.ktrdr/shared/{data,models,strategies}

# Terminal 1 - Slot 1
COMPOSE_PROJECT_NAME=ktrdr-test-1 KTRDR_API_PORT=8001 ...
docker compose -f docker-compose.sandbox.yml up -d
curl http://localhost:8001/api/v1/health  # ✓

# Terminal 2 - Slot 2
COMPOSE_PROJECT_NAME=ktrdr-test-2 KTRDR_API_PORT=8002 ...
docker compose -f docker-compose.sandbox.yml up -d
curl http://localhost:8002/api/v1/health  # ✓
```

---

### Milestone 2: CLI Core

**User Story:** Developer can create and manage sandbox instances with simple commands.

**Scope:**
- `ktrdr sandbox create/up/down/destroy`
- Port allocator with slot management
- Instance registry

**E2E Test:**
```bash
ktrdr sandbox create feat-test
cd ../ktrdr--feat-test
ktrdr sandbox up
curl http://localhost:8001/api/v1/health  # ✓
ktrdr sandbox destroy
```

---

### Milestone 3: Startability Gate + Status

**User Story:** Developer sees clear feedback when sandbox is ready.

**Scope:**
- Startability Gate health checks
- `ktrdr sandbox status` with URLs
- `ktrdr sandbox list`
- Port conflict detection

**E2E Test:**
```bash
ktrdr sandbox up
# ✓ Database ready
# ✓ Backend healthy
# ✓ Workers registered (4)
# Startability Gate: PASSED

ktrdr sandbox status
# Shows all service URLs
```

---

### Milestone 4: CLI Auto-Detection + Init

**User Story:** CLI automatically targets the right sandbox based on directory.

**Scope:**
- Directory-based `.env.sandbox` detection
- `ktrdr sandbox init` for existing clones
- `ktrdr --port` flag

**E2E Test:**
```bash
cd ../ktrdr--feat-a
ktrdr operations list  # Auto-detects port 8001

cd ../ktrdr2
ktrdr operations list  # Uses default 8000
```

---

### Milestone 5: Shared Data + Init-Shared

**User Story:** New dev machine can be set up with shared data.

**Scope:**
- `ktrdr sandbox init-shared` command
- `--from` and `--minimal` options
- Setup documentation

**E2E Test:**
```bash
ktrdr sandbox init-shared --from /backup/data
ls ~/.ktrdr/shared/  # data/ models/ strategies/
```

---

### Milestone 6: Backward-Compatible Merge

**User Story:** Main compose supports both workflows with guaranteed rollback.

**Scope:**
- Merge changes into main `docker-compose.yml`
- Verification checklist (automated)
- Rollback script
- Git tag for rollback point

**Pre-merge verification:**
```bash
# Must pass before merge is complete
scripts/verify-sandbox-merge.sh

# Tests default ports still work
cd ../ktrdr2
docker compose up -d
curl http://localhost:8000/api/v1/health  # ✓
```

**Rollback:**
```bash
# If anything breaks
scripts/sandbox-rollback.sh
# Restores original compose in seconds
```

---

## Remaining Open Questions

To be resolved during implementation:

1. **Compose file location:** `docker-compose.sandbox.yml` at root, or under `deploy/environments/parallel/`?

2. **Registry cleanup frequency:** Clean stale entries on every `list`, or require explicit command?

3. **Worker count per instance:** Always 4 workers, or configurable?

---

## Appendix: Gap Resolution Summary

| Gap ID | Issue | Resolution |
|--------|-------|------------|
| GAP-11a-1 | Shared mount might not exist | Default to `./data`, override for sandbox |
| GAP-11b-1 | Defaults must match current | Verification checklist |
| GAP-3-1 | Debug access to services | `sandbox status` shows all URLs |
| GAP-3-2 | Worker port strategy | Slot-based ranges |
| GAP-3-3 | Concurrent write safety | Accept risk (low probability) |
| GAP-1-2 | Git branch handling | Default to current, helpful error |
| GAP-1-4 | Compose file location | New file (not autonomous sandbox) |
| GAP-2-1 | Repo validation | Check git remote |
| GAP-2-2 | Instance ID collision | Error with helpful message |
| GAP-4-1 | URL precedence | --url > --port > file > default |
| GAP-4-2 | Auto-loading strategy | Read file directly, not env vars |
