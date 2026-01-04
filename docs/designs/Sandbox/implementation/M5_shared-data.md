---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Shared Data + Init-Shared

**Goal:** New development machine can be set up with shared data easily.

**Branch:** `feature/sandbox-m5-shared-data`

**Builds on:** M2 (CLI Core) — can run in parallel with M3/M4

---

## E2E Test Scenario

**Purpose:** Prove shared data initialization works for new machine setup.

**Prerequisites:**
- M2 complete
- Existing dev environment with data (e.g., `../ktrdr2`)

```bash
# 1. Clean slate - remove any existing shared data
rm -rf ~/.ktrdr/shared

# 2. Initialize from existing environment
ktrdr sandbox init-shared --from ../ktrdr2

# Expected output:
# Initializing shared data directory: ~/.ktrdr/shared
#   Copying data/ ... 1.2 GB
#   Copying models/ ... 450 MB
#   Copying strategies/ ... 12 KB
#
# Shared data initialized:
#   ~/.ktrdr/shared/data/      (1.2 GB, 42 files)
#   ~/.ktrdr/shared/models/    (450 MB, 8 files)
#   ~/.ktrdr/shared/strategies/ (12 KB, 3 files)

# 3. Verify structure
ls -la ~/.ktrdr/shared/
# Should show data/, models/, strategies/

# 4. Create sandbox and verify it uses shared data
ktrdr sandbox create test-shared
cd ../ktrdr--test-shared
ktrdr sandbox up --no-wait
sleep 30

# Verify data is accessible
docker exec ktrdr--test-shared-backend-1 ls /app/data
# Should show same files as ~/.ktrdr/shared/data/

# 5. Test minimal init (for CI or quick setup)
rm -rf ~/.ktrdr/shared
ktrdr sandbox init-shared --minimal

# Expected output:
# Initializing shared data directory: ~/.ktrdr/shared
#   Creating empty structure...
#
# Shared data initialized (minimal):
#   ~/.ktrdr/shared/data/
#   ~/.ktrdr/shared/models/
#   ~/.ktrdr/shared/strategies/
#
# Note: No data copied. Download data with 'ktrdr data download' after starting.

# Cleanup
cd ../ktrdr--test-shared && ktrdr sandbox destroy --force
```

**Success Criteria:**
- [ ] `init-shared --from` copies data from existing environment
- [ ] `init-shared --minimal` creates empty structure
- [ ] Sandbox instances can access shared data
- [ ] Progress shown during copy

---

## Tasks

### Task 5.1: Implement `ktrdr sandbox init-shared` Command

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** API Endpoint (CLI), Configuration

**Description:**
Implement the `init-shared` command that sets up `~/.ktrdr/shared/` directory.

**Implementation Notes:**

```python
import shutil
from pathlib import Path


SHARED_DIR = Path.home() / ".ktrdr" / "shared"
SHARED_SUBDIRS = ["data", "models", "strategies"]


def get_dir_stats(path: Path) -> tuple[int, str]:
    """Get file count and human-readable size for a directory."""
    if not path.exists():
        return 0, "0 B"

    total_size = 0
    file_count = 0

    for f in path.rglob("*"):
        if f.is_file():
            file_count += 1
            total_size += f.stat().st_size

    # Human-readable size
    for unit in ["B", "KB", "MB", "GB"]:
        if total_size < 1024:
            return file_count, f"{total_size:.1f} {unit}"
        total_size /= 1024

    return file_count, f"{total_size:.1f} TB"


def copy_with_progress(src: Path, dst: Path, console) -> None:
    """Copy directory with progress indication."""
    if not src.exists():
        console.print(f"  [dim]Skipping {src.name}/ (not found)[/dim]")
        return

    file_count, size = get_dir_stats(src)
    console.print(f"  Copying {src.name}/ ... {size} ({file_count} files)")

    # Use shutil.copytree for simplicity
    # For very large directories, could use rsync subprocess
    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


@sandbox_app.command("init-shared")
def init_shared(
    from_path: Path = typer.Option(
        None,
        "--from",
        "-f",
        help="Copy data from existing KTRDR environment",
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        "-m",
        help="Create empty structure only (no data copied)",
    ),
):
    """Initialize the shared data directory (~/.ktrdr/shared/)."""
    console.print(f"Initializing shared data directory: {SHARED_DIR}")

    # Create base directory
    SHARED_DIR.mkdir(parents=True, exist_ok=True)

    if minimal:
        # Just create empty directories
        console.print("  Creating empty structure...")
        for subdir in SHARED_SUBDIRS:
            (SHARED_DIR / subdir).mkdir(exist_ok=True)

        console.print(f"\n[green]Shared data initialized (minimal):[/green]")
        for subdir in SHARED_SUBDIRS:
            console.print(f"  {SHARED_DIR / subdir}/")
        console.print("\n[dim]Note: No data copied. Download data after starting sandbox.[/dim]")
        return

    if from_path:
        # Validate source
        if not from_path.exists():
            error_console.print(f"[red]Error:[/red] Source not found: {from_path}")
            raise typer.Exit(1)

        # Copy each subdirectory
        for subdir in SHARED_SUBDIRS:
            src = from_path / subdir
            dst = SHARED_DIR / subdir
            copy_with_progress(src, dst, console)

        console.print(f"\n[green]Shared data initialized:[/green]")
        for subdir in SHARED_SUBDIRS:
            path = SHARED_DIR / subdir
            file_count, size = get_dir_stats(path)
            console.print(f"  {path}/ ({size}, {file_count} files)")
        return

    # No --from and no --minimal: check if shared dir already has content
    existing_content = any((SHARED_DIR / subdir).exists() and
                          list((SHARED_DIR / subdir).iterdir())
                          for subdir in SHARED_SUBDIRS)

    if existing_content:
        console.print(f"\n[yellow]Shared data already exists:[/yellow]")
        for subdir in SHARED_SUBDIRS:
            path = SHARED_DIR / subdir
            if path.exists():
                file_count, size = get_dir_stats(path)
                console.print(f"  {path}/ ({size}, {file_count} files)")
        console.print("\nUse --from to overwrite or --minimal to reset to empty.")
        return

    # Empty and no flags: create minimal structure
    console.print("  Creating empty structure...")
    for subdir in SHARED_SUBDIRS:
        (SHARED_DIR / subdir).mkdir(exist_ok=True)

    console.print(f"\n[green]Shared data initialized (empty):[/green]")
    for subdir in SHARED_SUBDIRS:
        console.print(f"  {SHARED_DIR / subdir}/")
    console.print("\nPopulate with:")
    console.print("  ktrdr sandbox init-shared --from /path/to/existing/ktrdr")
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_init_shared.py`
- [ ] `test_get_dir_stats_empty` — Returns 0, "0 B" for empty dir
- [ ] `test_get_dir_stats_with_files` — Correct count and size

*Integration Tests:*
- [ ] `test_init_shared_minimal_creates_dirs` — Empty dirs created
- [ ] `test_init_shared_from_copies_data` — Data copied from source
- [ ] `test_init_shared_from_invalid_path` — Error on missing source
- [ ] `test_init_shared_idempotent` — Safe to run multiple times

*Smoke Test:*
```bash
ktrdr sandbox init-shared --minimal
ls ~/.ktrdr/shared/

ktrdr sandbox init-shared --from ../ktrdr2
ls ~/.ktrdr/shared/data/
```

**Acceptance Criteria:**
- [ ] `--minimal` creates empty structure
- [ ] `--from` copies from existing environment
- [ ] Progress shown during copy
- [ ] Error handling for missing source
- [ ] Idempotent (safe to run multiple times)

---

### Task 5.2: Add Shared Data Verification to Status

**File:** `ktrdr/cli/sandbox.py` (modify)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** API Endpoint (CLI)

**Description:**
Enhance `sandbox status` to show shared data mount status.

**Implementation Notes:**

```python
# Add to status command:

console.print()
console.print("[bold]Shared Data:[/bold]")

shared_dir = Path.home() / ".ktrdr" / "shared"
if shared_dir.exists():
    for subdir in ["data", "models", "strategies"]:
        path = shared_dir / subdir
        if path.exists():
            file_count, size = get_dir_stats(path)
            console.print(f"  {subdir}/: {size} ({file_count} files)")
        else:
            console.print(f"  {subdir}/: [dim]not found[/dim]")
else:
    console.print(f"  [yellow]Not initialized[/yellow]")
    console.print(f"  Run: ktrdr sandbox init-shared")
```

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr sandbox status
# Should show Shared Data section
```

**Acceptance Criteria:**
- [ ] Status shows shared data directory info
- [ ] Shows file counts and sizes per subdirectory
- [ ] Shows helpful message if not initialized

---

### Task 5.3: Document New Machine Setup

**File:** `docs/designs/Sandbox/NEW_MACHINE_SETUP.md` (new)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Document the workflow for setting up KTRDR on a new development machine.

**Implementation Notes:**

Create comprehensive setup documentation:

```markdown
# Setting Up KTRDR on a New Machine

## Prerequisites

- Docker Desktop installed
- Git configured with SSH key
- Python 3.11+ with uv

## Quick Start

1. Clone the repository:
   ```bash
   git clone git@github.com:kpiteira/ktrdr.git
   cd ktrdr
   ```

2. Initialize shared data:
   ```bash
   # If you have a backup or existing machine:
   ktrdr sandbox init-shared --from /path/to/backup

   # Or start with minimal (download data later):
   ktrdr sandbox init-shared --minimal
   ```

3. Create your first sandbox:
   ```bash
   ktrdr sandbox create dev
   cd ../ktrdr--dev
   ktrdr sandbox up
   ```

4. Verify:
   ```bash
   curl http://localhost:8001/api/v1/health
   open http://localhost:3001  # Grafana
   ```

## Transferring Data Between Machines

### From Old Machine

```bash
# Create archive
tar -czvf ktrdr-shared-data.tar.gz ~/.ktrdr/shared/
```

### On New Machine

```bash
# Extract archive
tar -xzvf ktrdr-shared-data.tar.gz -C ~/

# Or copy directly (if same network)
rsync -avz oldmachine:~/.ktrdr/shared/ ~/.ktrdr/shared/
```

## Directory Structure

After setup, you'll have:

```
~/.ktrdr/
  sandbox/
    instances.json    # Registry of sandbox instances
  shared/
    data/             # Symbol data (OHLCV CSVs)
    models/           # Trained ML models
    strategies/       # Strategy configurations
```
```

**Acceptance Criteria:**
- [ ] Clear step-by-step instructions
- [ ] Covers both fresh start and data transfer
- [ ] Copy-pasteable commands

---

## Completion Checklist

- [ ] All 3 tasks complete and committed
- [ ] `init-shared` command works with --from and --minimal
- [ ] Status shows shared data info
- [ ] Setup documentation complete
- [ ] E2E test passes
- [ ] Quality gates pass: `make quality`

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Shared data at `~/.ktrdr/shared/` | `init-shared` creates structure |
| data/, models/, strategies/ subdirs | All three handled |
| Backward compatible mounts | Works with `${KTRDR_SHARED_DIR:-./data}` pattern |
