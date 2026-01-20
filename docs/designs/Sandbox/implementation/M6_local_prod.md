---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Local-Prod Environment

**Goal:** Create a production-like execution environment using the sandbox infrastructure, replacing the ad-hoc `../ktrdr2` setup.

**Branch:** `feature/sandbox-m6-local-prod`

**Builds on:** M1-M5 (sandbox infrastructure)

---

## Overview

Local-prod is where you run KTRDR for real work - connecting to IB Gateway, running GPU training, using the MCP server with Claude. It's not for testing (that's what sandboxes are for).

**Why not just keep ktrdr2?**
- ktrdr2 grew organically as a "special snowflake"
- The sandbox system works beautifully
- Local-prod brings that same reliability to the main execution environment

**Key Differences from Sandbox:**

| Aspect | Sandbox | Local-Prod |
|--------|---------|------------|
| Purpose | E2E testing | Real execution |
| Git setup | Worktree | Clone |
| Slot | 1-10 | 0 (standard ports) |
| Count | Up to 10 | Singleton |
| Host services | No | Yes (IB, GPU) |
| MCP server | No | Yes |
| Creation | `create` (automated) | `init` (manual clone first) |

---

## Setup Instructions

Local-prod requires a manual clone because of a chicken-and-egg problem: you need the CLI to run `create`, but you need a clone to have the CLI.

### First-Time Setup

```bash
# 1. Clone the repository
git clone https://github.com/kpiteira/ktrdr.git ~/Documents/dev/ktrdr-prod
cd ~/Documents/dev/ktrdr-prod

# 2. Install dependencies
uv sync

# 3. Initialize as local-prod
uv run ktrdr local-prod init

# 4. Initialize shared data (if not already done)
uv run ktrdr sandbox init-shared --from ~/Documents/dev/ktrdr2  # or --minimal

# 5. Start the environment
uv run ktrdr local-prod up
```

### After Setup

```bash
cd ~/Documents/dev/ktrdr-prod
ktrdr local-prod up      # Start
ktrdr local-prod status  # Check health
ktrdr local-prod down    # Stop
```

---

## E2E Test Scenario

**Purpose:** Prove local-prod works as the primary execution environment.

**Prerequisites:**
- M1-M5 complete (sandbox infrastructure working)
- At least one sandbox tested
- Shared data initialized (`~/.ktrdr/shared/`)

```bash
# 1. Clone and initialize
git clone https://github.com/kpiteira/ktrdr.git /tmp/test-ktrdr-prod
cd /tmp/test-ktrdr-prod
uv sync
uv run ktrdr local-prod init

# 2. Verify initialization
cat .env.sandbox | grep SLOT_NUMBER  # Should be 0
cat .env.sandbox | grep KTRDR_API_PORT  # Should be 8000

# 3. Start local-prod
uv run ktrdr local-prod up --no-secrets  # Skip 1Password for test

# 4. Verify services on standard ports
curl -f http://localhost:8000/api/v1/health  # Backend
curl -f http://localhost:3000/api/health     # Grafana
curl -f http://localhost:16686               # Jaeger UI

# 5. Verify workers registered
curl -s http://localhost:8000/api/v1/workers | jq '.workers | length'  # Should be 4

# 6. Verify MCP server container exists
docker compose ps | grep mcp-local  # Should show running

# 7. Test status command
uv run ktrdr local-prod status  # Should show all services

# 8. Stop and verify
uv run ktrdr local-prod down
curl http://localhost:8000/api/v1/health  # Should fail (connection refused)

# 9. Test destroy (unregister only, keeps clone)
uv run ktrdr local-prod up --no-secrets
uv run ktrdr local-prod destroy --force
ls .env.sandbox  # Should NOT exist (unregistered)
ls ktrdr/        # Should exist (clone kept)

# 10. Verify registry cleared
cat ~/.ktrdr/sandbox/instances.json | jq '.local_prod'  # Should be null

# Cleanup
cd /
rm -rf /tmp/test-ktrdr-prod
```

**Success Criteria:**
- [ ] `init` works on fresh clone, creates `.env.sandbox` with slot 0
- [ ] `init` fails if local-prod already exists (singleton)
- [ ] `init` fails on worktree (must be clone)
- [ ] `up` starts all services on standard ports (8000, 5432, 3000, etc.)
- [ ] `up` fetches secrets from `ktrdr-local-prod` 1Password item
- [ ] `status` shows all services and URLs
- [ ] `down` stops containers
- [ ] `destroy` unregisters + stops + removes volumes, but keeps clone directory
- [ ] `destroy` works from ANY directory (uses registry, not cwd)
- [ ] MCP server (`mcp-local`) is running and accessible
- [ ] 4 workers registered (not 8)

---

## Tasks

### Task 6.1: Update Registry for Local-Prod

**File:** `ktrdr/cli/sandbox_registry.py` (exists, minor updates)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
The registry already has `local_prod` field and helper functions. Verify they work correctly for the init-only flow (no create).

**Implementation Notes:**
- `local_prod_exists()` - already implemented
- `get_local_prod()` - already implemented
- `set_local_prod()` - already implemented
- `clear_local_prod()` - already implemented
- Verify `is_worktree` field is correctly set to `False` for clones

**Testing Requirements:**

*Unit Test:*
```python
def test_local_prod_registry_crud():
    """Test local-prod singleton CRUD operations."""
    # Clear any existing
    clear_local_prod()
    assert not local_prod_exists()

    # Set local-prod
    info = InstanceInfo(
        instance_id="ktrdr-prod",
        slot=0,
        path="/tmp/test-ktrdr-prod",
        created_at="2024-01-01T00:00:00Z",
        is_worktree=False,  # Clone, not worktree
        parent_repo=None,
    )
    set_local_prod(info)

    # Verify
    assert local_prod_exists()
    retrieved = get_local_prod()
    assert retrieved.instance_id == "ktrdr-prod"
    assert retrieved.slot == 0
    assert not retrieved.is_worktree

    # Clear
    clear_local_prod()
    assert not local_prod_exists()
```

**Acceptance Criteria:**
- [ ] Local-prod CRUD functions work correctly
- [ ] `is_worktree=False` for clones
- [ ] Singleton enforcement (only one local-prod)

---

### Task 6.2: Implement Local-Prod CLI Commands

**File:** `ktrdr/cli/local_prod.py` (exists, needs modification)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** CLI, Configuration

---

## ⚠️ CRITICAL: DO NOT RE-IMPLEMENT - REUSE EXISTING CODE ⚠️

**Local-prod commands are THIN WRAPPERS over `instance_core.py`.**

The sandbox system already has all the functionality we need:
- `instance_core.start_instance()` - starts Docker Compose
- `instance_core.stop_instance()` - stops Docker Compose
- `instance_core.generate_env_file()` - creates `.env.sandbox`
- `instance_core.load_env_file()` - reads `.env.sandbox`
- `instance_core.find_compose_file()` - locates compose file
- `instance_core.show_instance_logs()` - shows logs

**Your job is NOT to write new Docker/Compose logic.** Your job is to:
1. Add local-prod-specific validation (clone check, singleton check)
2. Call the existing `instance_core` functions with the right parameters
3. Use local-prod-specific constants (slot 0, different 1Password item)

---

**Description:**
Modify `local_prod.py` to implement the init-only flow. Remove the `create` command (it creates worktrees, but local-prod must be a clone).

**Commands to implement (as thin wrappers):**

| Command | What it does | Reuses from |
|---------|--------------|-------------|
| `init` | Validate clone + call `generate_env_file(slot=0)` + register | `instance_core.generate_env_file()` |
| `up` | Call `start_instance(profile="local-prod")` | `instance_core.start_instance()` |
| `down` | Call `stop_instance(profile="local-prod")` | `instance_core.stop_instance()` |
| `destroy` | Registry lookup + `stop_instance()` + unregister | `instance_core.stop_instance()` |
| `status` | Load env + show URLs (similar to sandbox) | `instance_core.load_env_file()` |
| `logs` | Call `show_instance_logs()` | `instance_core.show_instance_logs()` |

**Local-prod-specific constants:**

```python
LOCAL_PROD_NAME = "ktrdr-prod"
LOCAL_PROD_SLOT = 0
LOCAL_PROD_SECRETS_ITEM = "ktrdr-local-prod"  # Different from sandbox!
```

**The only new logic needed:**

1. **Clone validation** (for `init`):
```python
def _is_clone_not_worktree(path: Path) -> bool:
    """Worktrees have .git as a FILE. Clones have .git as a DIRECTORY."""
    git_path = path / ".git"
    return git_path.is_dir()
```

2. **Different secrets item** (for `up`):
```python
# In instance_core.py, the secrets item is configurable
# Pass LOCAL_PROD_SECRETS_ITEM instead of SANDBOX_SECRETS_ITEM
```

3. **Destroy uses registry lookup** (NOT cwd):
```python
@local_prod_app.command()
def destroy(...):
    # CORRECT: Look up from registry
    info = get_local_prod()
    local_prod_path = Path(info.path)  # <-- Registry path, NOT cwd!
```

**What to DELETE from current `local_prod.py`:**
- The `create` command (local-prod uses `init`, not `create`)
- Any code that duplicates `instance_core.py` functionality

**Testing Requirements:**

*Unit Tests:*
```python
def test_init_fails_on_worktree(tmp_path, monkeypatch):
    """init should reject worktrees."""
    (tmp_path / ".git").write_text("gitdir: /some/path")  # Worktree marker
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(local_prod_app, ["init"])
    assert result.exit_code != 0
    assert "must be a clone" in result.output.lower()

def test_init_fails_if_already_exists():
    """init should reject if local-prod already registered."""
    set_local_prod(InstanceInfo(...))  # Pre-register
    result = runner.invoke(local_prod_app, ["init"])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()

def test_destroy_uses_registry_not_cwd(tmp_path, monkeypatch):
    """destroy must use registry path, not current directory."""
    set_local_prod(InstanceInfo(path="/path/a", ...))
    monkeypatch.chdir(tmp_path)  # Different directory!
    # Should destroy /path/a, NOT tmp_path
```

**Acceptance Criteria:**
- [ ] `create` command REMOVED (use `init` instead)
- [ ] `init` validates clone (not worktree)
- [ ] `init` enforces singleton
- [ ] `init` calls `instance_core.generate_env_file(slot=0)`
- [ ] `up` calls `instance_core.start_instance(profile="local-prod")`
- [ ] `up` uses `ktrdr-local-prod` 1Password item
- [ ] `down` calls `instance_core.stop_instance(profile="local-prod")`
- [ ] `destroy` uses registry path (not cwd)
- [ ] `destroy` keeps clone directory, only unregisters
- [ ] No duplicated Docker/Compose logic - all via `instance_core`

---

### Task 6.3: Create Bootstrap Setup Script

**File:** `scripts/setup-local-prod.sh` (new)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration, Documentation

**Description:**
Create an interactive setup script that guides users through local-prod installation. This solves the chicken-and-egg problem (need CLI to setup, need clone to have CLI).

**What the script does:**

1. **Check prerequisites** and report what's missing:
   - Git installed
   - Docker Desktop installed and running
   - `uv` installed
   - 1Password CLI (`op`) installed
   - `op` authenticated (`op signin`)

2. **Explain 1Password requirements:**
   - Item name: `ktrdr-local-prod`
   - Required fields: `db_password`, `jwt_secret`, `anthropic_api_key`, `grafana_password`
   - Offer to continue without (will use insecure defaults)

3. **Clone the repository:**
   - Ask for destination path (suggest `~/Documents/dev/ktrdr-prod`)
   - Clone from `https://github.com/kpiteira/ktrdr.git`

4. **Install dependencies:**
   - Run `uv sync`

5. **Initialize local-prod:**
   - Run `uv run ktrdr local-prod init`

6. **Initialize shared data (optional):**
   - Ask if user has existing ktrdr environment to copy from
   - Run `uv run ktrdr sandbox init-shared --from <path>` or `--minimal`

7. **Offer to start:**
   - Ask if user wants to start local-prod now
   - Run `uv run ktrdr local-prod up`

**Implementation Notes:**

```bash
#!/bin/bash
# scripts/setup-local-prod.sh
# Interactive setup for KTRDR local-prod environment

set -e

echo "=== KTRDR Local-Prod Setup ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_prereq() {
    local name="$1"
    local cmd="$2"

    if command -v "$cmd" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (not found)"
        return 1
    fi
}

echo "Checking prerequisites..."
MISSING=0
check_prereq "Git" "git" || MISSING=1
check_prereq "Docker" "docker" || MISSING=1
check_prereq "uv" "uv" || MISSING=1
check_prereq "1Password CLI" "op" || MISSING=1

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Some prerequisites are missing.${NC}"
    echo "Install them before continuing."
    exit 1
fi

# Check Docker is running
if ! docker info &> /dev/null; then
    echo -e "  ${RED}✗${NC} Docker Desktop is not running"
    exit 1
fi

# Check 1Password auth
echo ""
echo "Checking 1Password authentication..."
if op account get &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} 1Password authenticated"
else
    echo -e "  ${YELLOW}!${NC} 1Password not authenticated"
    echo ""
    echo "For full functionality, create a 1Password item:"
    echo "  Item name: ktrdr-local-prod"
    echo "  Fields: db_password, jwt_secret, anthropic_api_key, grafana_password"
    echo ""
    read -p "Continue without 1Password? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Run 'op signin' and try again."
        exit 1
    fi
fi

# Get destination path
echo ""
DEFAULT_PATH="$HOME/Documents/dev/ktrdr-prod"
read -p "Installation path [$DEFAULT_PATH]: " DEST_PATH
DEST_PATH="${DEST_PATH:-$DEFAULT_PATH}"

if [ -d "$DEST_PATH" ]; then
    echo -e "${RED}Error:${NC} Directory already exists: $DEST_PATH"
    exit 1
fi

# Clone
echo ""
echo "Cloning repository..."
git clone https://github.com/kpiteira/ktrdr.git "$DEST_PATH"
cd "$DEST_PATH"

# Install dependencies
echo ""
echo "Installing dependencies..."
uv sync

# Initialize
echo ""
echo "Initializing local-prod..."
uv run ktrdr local-prod init

# Shared data
echo ""
read -p "Initialize shared data? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    read -p "Copy from existing environment? (path or 'minimal'): " SHARED_SOURCE
    if [ "$SHARED_SOURCE" = "minimal" ]; then
        uv run ktrdr sandbox init-shared --minimal
    elif [ -n "$SHARED_SOURCE" ]; then
        uv run ktrdr sandbox init-shared --from "$SHARED_SOURCE"
    fi
fi

# Done
echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "To start local-prod:"
echo "  cd $DEST_PATH"
echo "  ktrdr local-prod up"
echo ""
```

**Testing Requirements:**

*Smoke Test:*
```bash
# Test prerequisite checking (should pass on dev machine)
./scripts/setup-local-prod.sh --check-only  # Add this flag for testing

# Full test (in CI or clean environment)
./scripts/setup-local-prod.sh <<EOF
/tmp/test-local-prod
minimal
n
EOF
```

**Acceptance Criteria:**
- [ ] Checks all prerequisites (git, docker, uv, op)
- [ ] Reports missing prerequisites clearly
- [ ] Explains 1Password item requirements
- [ ] Clones to user-specified path
- [ ] Runs `uv sync`
- [ ] Runs `ktrdr local-prod init`
- [ ] Offers shared data initialization
- [ ] Shows next steps at the end

---

### Task 6.4: Update Compose for Local-Prod

**File:** `docker-compose.sandbox.yml` (exists, needs updates)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Update compose file for local-prod requirements:
1. Comment out extra workers (5-8) but keep the profile structure
2. Ensure `mcp-local` service is included and working

**Implementation Notes:**

```yaml
# Comment out extra workers but keep structure for future expansion
# Uncomment these if you need more workers for local-prod

#  backtest-worker-3:
#    profiles: [local-prod]
#    ...

#  backtest-worker-4:
#    profiles: [local-prod]
#    ...

# etc.
```

For MCP server, ensure `mcp-local` is NOT behind a profile (should always start with local-prod).

**Acceptance Criteria:**
- [ ] Extra workers (5-8) commented out
- [ ] Profile structure preserved for future expansion
- [ ] `mcp-local` starts with regular `up` (no profile needed)
- [ ] Compose validates: `docker compose config`

---

### Task 6.5: Create 1Password Item Documentation

**File:** `docs/designs/Sandbox/LOCAL_PROD_SETUP.md` (new)
**Type:** DOCUMENTATION
**Estimated time:** 30 minutes

**Task Categories:** Documentation

**Description:**
Document the complete local-prod setup process, including 1Password item creation.

**Content to include:**

1. **Prerequisites**
   - macOS with Docker Desktop
   - 1Password CLI (`op`) installed and authenticated
   - `uv` installed

2. **1Password Setup**
   - Create item named `ktrdr-local-prod`
   - Required fields: `db_password`, `jwt_secret`, `anthropic_api_key`, `grafana_password`
   - Example values (not real secrets!)

3. **Clone and Initialize**
   - Step-by-step commands
   - Expected output at each step

4. **Daily Usage**
   - Starting/stopping
   - Viewing logs
   - Connecting host services

5. **Host Services**
   - IB Gateway connection
   - GPU training host service
   - How they connect to local-prod

6. **MCP Server Usage**
   - How to use with Claude Code
   - How to use with Claude Desktop

7. **Troubleshooting**
   - Common issues and solutions

**Acceptance Criteria:**
- [ ] Complete setup instructions
- [ ] 1Password item documented
- [ ] Host service connection documented
- [ ] MCP usage documented

---

### Task 6.6: E2E Validation

**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Execute the E2E test scenario from this document and verify all success criteria pass.

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] All success criteria checked off
- [ ] Local-prod usable as primary execution environment

---

## Completion Checklist

- [ ] All 6 tasks complete
- [ ] Registry functions work for local-prod
- [ ] CLI commands are thin wrappers over `instance_core.py`
- [ ] Bootstrap script works end-to-end
- [ ] Compose file updated (extra workers commented out)
- [ ] Documentation complete
- [ ] E2E validation passes
- [ ] Local-prod can replace ktrdr2

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Singleton pattern | Only one local-prod allowed |
| Slot 0 reserved | Local-prod always uses standard ports |
| Shared code | Uses `instance_core.py` like sandbox |
| Registry-based | All operations use registry for state |
| Host service support | Standard ports enable host connections |
| Clone not worktree | Production environment is independent |

---

## CRITICAL: The Destroy Bug

**Read HANDOFF_M6.md for full details.**

The previous implementation of `destroy` used `Path.cwd()` instead of registry lookup. This caused complete loss of the sandbox directory when `destroy` was run from the wrong location.

**The fix:** `local-prod destroy` MUST:
1. Look up the registered local-prod path from registry
2. Operate on that path, NOT the current directory
3. Warn if current directory differs from registered path

This is different from `sandbox destroy` which operates on current directory (because you're "in" a sandbox, but you may not be "in" local-prod when destroying it).
