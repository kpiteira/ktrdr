# Parallel Coding Workflow: Architecture

## Overview

This architecture separates **sandbox infrastructure** (expensive, persistent) from **code worktrees** (cheap, transient). Sandbox slots are pooled resources that worktrees claim temporarily for E2E testing. Session management is handled by Agent Deck, an external tool.

The system has three main components:
1. **Agent Deck** — External session manager (sourced, not built)
2. **Sandbox Slot Pool** — Pre-created infrastructure slots
3. **kinfra CLI** — Infrastructure tooling commands (worktrees, sandboxes, deploy)

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Agent Deck                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Session 1│  │ Session 2│  │ Session 3│  │ Session 4│            │
│  │ genome-M1│  │ config-M3│  │ spec-work│  │  (idle)  │            │
│  │ [waiting]│  │ [running]│  │  [idle]  │  │          │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┘            │
│       │             │             │                                  │
│  tmux status: ⚡ [1] genome-M1 [2] config-M3                        │
└───────┼─────────────┼─────────────┼─────────────────────────────────┘
        │             │             │
        ▼             ▼             ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Worktree    │ │   Worktree    │ │   Worktree    │
│ ktrdr-impl-   │ │ ktrdr-impl-   │ │ ktrdr-spec-   │
│ genome-M1     │ │ config-M3     │ │ new-feature   │
│               │ │               │ │               │
│ Claims slot 1 │ │ Claims slot 2 │ │ (no sandbox)  │
└───────┬───────┘ └───────┬───────┘ └───────────────┘
        │                 │
        ▼                 ▼
┌─────────────────────────────────────────────────────┐
│              Sandbox Slot Pool                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Slot 1    │  │   Slot 2    │  │   Slot 3    │  │
│  │ ports 8001  │  │ ports 8002  │  │ ports 8003  │  │
│  │ claimed by: │  │ claimed by: │  │ (available) │  │
│  │ genome-M1   │  │ config-M3   │  │             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Component Relationships (Structured Summary)

| Component | Type | Depends On | Used By |
|-----------|------|------------|---------|
| Agent Deck | External tool | tmux | User (terminal management) |
| Worktree | Git worktree | Git repo | Claude Code sessions |
| Sandbox Slot | Docker infrastructure | Docker, ports | Worktrees (E2E testing) |
| Slot Registry | JSON file | Filesystem | kinfra commands |

---

## Components

### Component 1: Agent Deck (External)

**Location:** Installed via `curl` or Homebrew
**Purpose:** Manage multiple Claude Code sessions with state detection and notifications

**Key behaviors:**
- Detects session state (running/waiting/idle/error)
- Shows waiting sessions in tmux status bar
- Allows jumping between sessions with `Ctrl+b N`
- Supports session forking with conversation history

**Configuration:** `~/.agent-deck/config.toml`

```toml
[general]
auto_update = true

[worktree]
location = "sibling"  # ../ktrdr-impl-<name>
```

**Integration:** Agent Deck manages tmux sessions; Claude Code runs inside them.

---

### Component 2: Sandbox Slot Pool

**Location:** `~/.ktrdr/sandboxes/slot-{1..6}/`
**Purpose:** Pre-created Docker infrastructure for E2E testing

**Each slot contains:**
```
~/.ktrdr/sandboxes/slot-1/
├── docker-compose.yml           # Base infrastructure
├── docker-compose.override.yml  # Generated: code mounts (when claimed)
├── .env.sandbox                 # Port allocation, secrets ref
└── volumes/                     # Persistent data (DB, etc.)
```

**Slot profiles:**

| Slot | Profile | Workers | Memory |
|------|---------|---------|--------|
| 1 | light | 1 backtest, 1 training | ~1.5GB |
| 2 | light | 1 backtest, 1 training | ~1.5GB |
| 3 | light | 1 backtest, 1 training | ~1.5GB |
| 4 | light | 1 backtest, 1 training | ~1.5GB |
| 5 | standard | 2 backtest, 2 training | ~2.5GB |
| 6 | heavy | 4 backtest, 4 training | ~4GB |

**Key behaviors:**
- Slots are pre-created with allocated ports and profile
- **Unclaimed slots are stopped** (no memory usage)
- Claiming generates `docker-compose.override.yml` and starts containers (~1 min)
- Releasing stops containers and removes override file
- DB volumes persist across claims (data survives release/re-claim)

**Interface (illustrative):**
```python
class SandboxSlot:
    slot_id: int
    infrastructure_path: Path
    claimed_by: Optional[Path]  # Worktree path

    def claim(self, worktree_path: Path) -> None: ...
    def release(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

---

### Component 3: kinfra CLI

**Location:** `ktrdr/cli/kinfra/` (new package)
**Purpose:** Infrastructure tooling CLI, separate from product `ktrdr` CLI

**Commands:**
```bash
# Worktree management
kinfra spec <feature>                    # Create spec worktree
kinfra impl <feature/milestone>          # Create impl worktree + claim sandbox
kinfra impl <feature/milestone> --profile standard  # Request specific profile
kinfra done <name>                       # Complete worktree (aliases: finish, complete)
kinfra done <name> --force               # Force cleanup even with uncommitted changes
kinfra worktrees                         # List active worktrees

# Sandbox management (moved from ktrdr sandbox)
kinfra sandbox up/down/status
kinfra sandbox slots                     # List all slots
kinfra sandbox provision                 # Create new slots

# Local-prod (moved from ktrdr local-prod)
kinfra local-prod up/down/status/logs/shell

# Deployments (moved from ktrdr deploy)
kinfra deploy homelab/canary/status
```

**Key behaviors:**
- `spec` creates worktree only (no sandbox), creates design folder if needed
- `impl` checks slot availability FIRST (fails fast), then creates worktree and claims slot
- `impl` uses existing branch if `impl/<feature>-<milestone>` exists, otherwise creates new
- `done` checks for uncommitted/unpushed changes, aborts unless `--force`
- `done`/`finish`/`complete` are aliases, all release sandbox and remove worktree

**Entry point:** `kinfra` command registered in `pyproject.toml`:
```toml
[project.scripts]
ktrdr = "ktrdr.cli.main:app"
kinfra = "ktrdr.cli.kinfra.main:app"
```

**Interface (illustrative):**
```python
def spec(feature: str) -> Path:
    """Create spec worktree for a feature."""
    ...

def impl(feature_milestone: str, profile: str = "light") -> Path:
    """Create impl worktree and claim sandbox slot.

    Order of operations (GAP-6 resolution):
    1. Check slot availability FIRST (fail fast)
    2. Create git worktree
    3. Claim slot, generate override, start containers

    On Docker failure (GAP-7 resolution):
    - Release slot
    - Keep worktree (user can fix and retry with `kinfra sandbox up`)
    """
    ...

def done(name: str, force: bool = False) -> None:
    """Complete worktree, release sandbox.

    Checks for uncommitted/unpushed changes unless force=True.
    """
    ...
```

---

### Component 4: Slot Registry

**Location:** `~/.ktrdr/sandboxes/registry.json`
**Purpose:** Track slot allocation, profiles, and claims

**Structure:**
```json
{
  "version": 2,
  "slots": {
    "1": {
      "infrastructure_path": "/Users/karl/.ktrdr/sandboxes/slot-1",
      "profile": "light",
      "workers": {"backtest": 1, "training": 1},
      "ports": {
        "api": 8001,
        "db": 5433,
        "grafana": 3001,
        "jaeger_ui": 16687
      },
      "claimed_by": "/Users/karl/Documents/dev/ktrdr-impl-genome-M1",
      "claimed_at": "2026-02-01T12:00:00Z",
      "status": "running"
    },
    "2": {
      "infrastructure_path": "/Users/karl/.ktrdr/sandboxes/slot-2",
      "profile": "light",
      "workers": {"backtest": 1, "training": 1},
      "ports": { "api": 8002, "..." },
      "claimed_by": null,
      "status": "stopped"
    },
    "3": { "profile": "light", "..." },
    "4": { "profile": "light", "..." },
    "5": {
      "infrastructure_path": "/Users/karl/.ktrdr/sandboxes/slot-5",
      "profile": "standard",
      "workers": {"backtest": 2, "training": 2},
      "ports": { "api": 8005, "..." },
      "claimed_by": null,
      "status": "stopped"
    },
    "6": {
      "infrastructure_path": "/Users/karl/.ktrdr/sandboxes/slot-6",
      "profile": "heavy",
      "workers": {"backtest": 4, "training": 4},
      "ports": { "api": 8006, "..." },
      "claimed_by": null,
      "status": "stopped"
    }
  }
}
```

---

## Data Flow

### Creating an Implementation Worktree

```
User                kinfra                 Git              Slot Pool
  │                  │                      │                   │
  │ kinfra impl      │                      │                   │
  │ genome/M1        │                      │                   │
  │─────────────────>│                      │                   │
  │                  │                      │                   │
  │                  │ auto-detect milestone│                   │
  │                  │ docs/designs/genome/ │                   │
  │                  │ implementation/M1_*  │                   │
  │                  │                      │                   │
  │                  │ find_available_slot()│                   │
  │                  │ (CHECK FIRST!)       │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │     slot 1        │
  │                  │<─────────────────────────────────────────│
  │                  │                      │                   │
  │                  │ git worktree add     │                   │
  │                  │ ../ktrdr-impl-       │                   │
  │                  │ genome-M1            │                   │
  │                  │─────────────────────>│                   │
  │                  │                      │                   │
  │                  │ claim slot, generate │                   │
  │                  │ override.yml         │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │                   │
  │                  │ prompt for secrets   │                   │
  │                  │ docker compose up    │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │                   │
  │ Success: slot 1  │                      │                   │
  │ claimed          │                      │                   │
  │<─────────────────│                      │                   │
```

**Flow Steps (Structured Summary):**
1. User runs `kinfra impl genome/M1`
2. CLI auto-detects milestone file: `docs/designs/genome/implementation/M1_*.md`
3. **CLI checks slot availability FIRST** (fails fast if none available)
4. CLI creates git worktree at `../ktrdr-impl-genome-M1` (uses existing branch if `impl/genome-M1` exists)
5. CLI claims slot and generates `docker-compose.override.yml` with worktree code mounts
6. CLI prompts for 1Password secrets (required for startup)
7. CLI starts docker compose with base + override (~1 min)
8. CLI updates registry: slot claimed, status = running

**On Docker failure:** Slot is released, worktree is kept. User can fix and retry with `kinfra sandbox up`.

### Completing a Worktree (After PR Merge)

```
User                kinfra                 Git              Slot Pool
  │                  │                      │                   │
  │ kinfra done      │                      │                   │
  │ genome-M1        │                      │                   │
  │─────────────────>│                      │                   │
  │                  │                      │                   │
  │                  │ check for uncommitted│                   │
  │                  │ or unpushed changes  │                   │
  │                  │─────────────────────>│                   │
  │                  │      (clean or dirty)│                   │
  │                  │<─────────────────────│                   │
  │                  │                      │                   │
  │                  │ [if dirty & !force]  │                   │
  │                  │ ABORT with error     │                   │
  │                  │                      │                   │
  │                  │ docker compose down  │                   │
  │                  │ (stops containers,   │                   │
  │                  │  keeps volumes)      │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │                   │
  │                  │ remove override.yml  │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │                   │
  │                  │ update registry      │                   │
  │                  │ (release claim,      │                   │
  │                  │  status=stopped)     │                   │
  │                  │─────────────────────────────────────────>│
  │                  │                      │                   │
  │                  │ git worktree remove  │                   │
  │                  │ ../ktrdr-impl-       │                   │
  │                  │ genome-M1            │                   │
  │                  │─────────────────────>│                   │
  │                  │                      │                   │
  │ Success: slot 1  │                      │                   │
  │ now available    │                      │                   │
  │<─────────────────│                      │                   │
```

**Note:** Aliases `kinfra finish genome-M1` and `kinfra complete genome-M1` do the same thing.

**Dirty worktree handling:** By default, `kinfra done` aborts if there are uncommitted or unpushed changes. Use `--force` to override.

**Key:** `docker compose down` stops containers but preserves volumes. The next claim will reuse the DB data, making startup faster.

---

## State Management

| State | Where | Lifecycle |
|-------|-------|-----------|
| Slot configuration | `~/.ktrdr/sandboxes/slot-N/.env.sandbox` | Created once, persists |
| Slot profile | `registry.json` | Fixed at provisioning |
| Slot claim | `registry.json` | Claimed → Released |
| Containers | Docker | Started on claim, stopped on release |
| Code mounts | `docker-compose.override.yml` | Generated on claim, deleted on release |
| DB volumes | Docker named volumes | Persist across claims (data survives) |
| Worktree | `../ktrdr-impl-<feature>-<milestone>/` or `../ktrdr-spec-<feature>/` | Created → Deleted on done |

**Key invariant:** Unclaimed slots are always stopped. Only claimed slots consume memory.

---

## Error Handling

| Situation | Error Type | Message/Behavior |
|-----------|------------|------------------|
| No slots available | `SlotExhaustedError` | "All 6 slots in use. Run `kinfra worktrees` to see active worktrees." |
| Slot already claimed | `SlotClaimedError` | "Slot 1 is claimed by ktrdr-impl-genome-M1" |
| Milestone file not found | `MilestoneNotFoundError` | "No milestone matching 'M1' found in docs/designs/genome/implementation/" |
| Docker compose fails | `SandboxStartError` | "Failed to start sandbox: [docker error]. Slot released. Worktree kept at ../ktrdr-impl-genome-M1. Fix issue and run `kinfra sandbox up`." |
| Worktree already exists | `WorktreeExistsError` | "Worktree ktrdr-impl-genome-M1 already exists" |
| Uncommitted changes on done | `WorktreeDirtyError` | "Worktree has uncommitted changes. Commit or stash, then retry. Use --force to proceed anyway." |
| Unpushed commits on done | `WorktreeDirtyError` | "Worktree has unpushed commits. Push first, then retry. Use --force to proceed anyway." |
| Done on spec worktree | `InvalidOperationError` | "Spec worktrees don't have sandboxes to release. Just run `git worktree remove`." |

---

## Integration Points

### Commands Moving to kinfra

| Current (`ktrdr`) | New (`kinfra`) | Notes |
|-------------------|----------------|-------|
| `ktrdr sandbox *` | `kinfra sandbox *` | All sandbox commands move |
| `ktrdr local-prod *` | `kinfra local-prod *` | All local-prod commands move |
| `ktrdr deploy *` | `kinfra deploy *` | All deploy commands move |

### kinfra Commands

| Command | Purpose |
|---------|---------|
| `kinfra spec <feature>` | Create spec worktree, create design folder if needed |
| `kinfra impl <feature/milestone>` | Create impl worktree + claim sandbox slot (default: light profile) |
| `kinfra impl <feature/milestone> --profile <profile>` | Request specific profile (light/standard/heavy) |
| `kinfra done <name>` | Release slot, stop containers, delete worktree (aborts if dirty) |
| `kinfra done <name> --force` | Force cleanup even with uncommitted/unpushed changes |
| `kinfra worktrees` | List active worktrees with sandbox status |
| `kinfra sandbox slots` | List all slots with profile and claim status |
| `kinfra sandbox provision` | Create new sandbox slots |
| `kinfra sandbox up/down/status` | Manual sandbox control |
| `kinfra local-prod up/down/status` | Local-prod management |
| `kinfra deploy homelab/canary` | Deployment commands |

### k-command Integration

| Command | Integration |
|---------|-------------|
| `kmilestone` | Works in impl worktree with claimed sandbox |
| `ktask` | Works unchanged (uses claimed sandbox) |
| After PR merge | User (or Claude) runs `kinfra done <name>` to clean up |

### Deprecations in ktrdr

| Command | Status |
|---------|--------|
| `ktrdr sandbox *` | Deprecated, prints "use kinfra sandbox" |
| `ktrdr local-prod *` | Deprecated, prints "use kinfra local-prod" |
| `ktrdr deploy *` | Deprecated, prints "use kinfra deploy" |

---

## Docker Compose Safety

### The Symlink Problem

**Current state:** The repo has a symlink:
```
docker-compose.yml -> deploy/environments/local/docker-compose.yml
```

This causes `docker compose up` (without `-f`) to use port 8000 even when in a sandbox folder. This has caused issues with E2E tests hitting the wrong backend.

### Solution: Remove the Symlink

1. **Delete `docker-compose.yml` symlink** from the repo
2. **Add to `.gitignore`**: `docker-compose.yml` (prevent recreation)
3. **Always use kinfra commands**:
   - Impl worktrees: `kinfra impl` handles sandbox automatically
   - Manual sandbox: `kinfra sandbox up/down`
   - Local-prod: `kinfra local-prod up/down`
   - Never raw `docker compose up`

### Claude Code Awareness

Add to CLAUDE.md and sandbox skill:
```
NEVER run `docker compose up` without explicit -f flag.
ALWAYS use:
- `kinfra sandbox up/down` for sandboxes
- `kinfra local-prod up/down` for local-prod
- `kinfra impl` / `kinfra done` for worktree lifecycle
```

### Worktrees Have No Compose Files

In the new architecture, worktrees contain only code — no compose files. The compose files live in `~/.ktrdr/sandboxes/slot-N/`. This eliminates the confusion entirely for new worktrees.

---

## Docker Compose Override Strategy

**Base file** (`~/.ktrdr/sandboxes/slot-1/docker-compose.yml`):
- Defines all services (backend, workers, DB, etc.)
- Uses `${CODE_DIR}` for volume mounts
- Contains port mappings from `.env.sandbox`

**Override file** (`docker-compose.override.yml`, generated on claim):
```yaml
# Generated by: kinfra impl genome/M1
# Claimed by: /Users/karl/Documents/dev/ktrdr-impl-genome-M1
# Do not edit manually

services:
  backend:
    volumes:
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/ktrdr:/app/ktrdr
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/research_agents:/app/research_agents
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/tests:/app/tests
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/config:/app/config:ro
      # Shared data (unchanged from base)
      - ${KTRDR_DATA_DIR}:/app/data
      - ${KTRDR_MODELS_DIR}:/app/models
      - ${KTRDR_STRATEGIES_DIR}:/app/strategies

  backtest-worker-1:
    volumes:
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/ktrdr:/app/ktrdr
      # ... similar

  training-worker-1:
    volumes:
      - /Users/karl/Documents/dev/ktrdr-impl-genome-M1/ktrdr:/app/ktrdr
      # ... similar
```

**Startup command:**
```bash
cd ~/.ktrdr/sandboxes/slot-1
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

---

## Verification Approach

| Component | How to Verify |
|-----------|---------------|
| Agent Deck | Manual: install, create sessions, verify state detection |
| Slot provisioning | Unit test: `kinfra sandbox provision`, verify files created |
| `kinfra spec` | Integration test: create spec worktree, verify design folder created |
| `kinfra impl` | Integration test: `kinfra impl genome/M1`, verify worktree + slot claimed + override file |
| Hot reload | E2E test: modify code in worktree, verify change reflected in container |
| `kinfra done` | Integration test: `kinfra done genome-M1`, verify slot released + worktree removed |

---

## Implementation Planning Summary

### New Components to Create

| Component | Location | Purpose |
|-----------|----------|---------|
| kinfra CLI package | `ktrdr/cli/kinfra/` | New CLI entry point |
| kinfra main | `ktrdr/cli/kinfra/main.py` | Typer app for kinfra |
| Spec command | `ktrdr/cli/kinfra/spec.py` | `kinfra spec` implementation |
| Impl command | `ktrdr/cli/kinfra/impl.py` | `kinfra impl` implementation |
| Done command | `ktrdr/cli/kinfra/done.py` | `kinfra done` implementation |
| Worktrees command | `ktrdr/cli/kinfra/worktrees.py` | `kinfra worktrees` implementation |
| Slot Manager | `ktrdr/cli/kinfra/slots.py` | Slot pool management |
| Override Generator | `ktrdr/cli/kinfra/override.py` | Generate docker-compose.override.yml |

### Existing Components to Move/Modify

| Component | Current Location | New Location | Changes |
|-----------|------------------|--------------|---------|
| Sandbox commands | `ktrdr/cli/sandbox.py` | `ktrdr/cli/kinfra/sandbox.py` | Move + add slot pool |
| Local-prod commands | `ktrdr/cli/local_prod.py` | `ktrdr/cli/kinfra/local_prod.py` | Move |
| Deploy commands | `ktrdr/cli/deploy.py` | `ktrdr/cli/kinfra/deploy.py` | Move |
| Sandbox registry | `ktrdr/cli/sandbox_registry.py` | Keep, update | Add claim tracking, v2 schema |
| Sandbox ports | `ktrdr/cli/sandbox_ports.py` | Keep | No changes |

### Files to Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add `kinfra` entry point |
| `ktrdr/cli/main.py` | Add deprecation warnings for moved commands |
| `docker-compose.yml` (symlink) | Delete |
| `.gitignore` | Add `docker-compose.yml` |

### Compose File Changes

| Profile | File | Workers |
|---------|------|---------|
| light | `docker-compose.light.yml` | 1 backtest, 1 training |
| standard | `docker-compose.standard.yml` | 2 backtest, 2 training |
| heavy | `docker-compose.heavy.yml` | 4 backtest, 4 training |

Or use Docker Compose profiles in a single file.

### External Setup Required

| Step | Command/Action |
|------|----------------|
| Install Agent Deck | `curl -fsSL https://raw.githubusercontent.com/asheshgoplani/agent-deck/main/install.sh \| bash` |
| Configure Agent Deck | Edit `~/.agent-deck/config.toml` |
| Provision initial slots | `kinfra sandbox provision` (creates 6 slots) |
