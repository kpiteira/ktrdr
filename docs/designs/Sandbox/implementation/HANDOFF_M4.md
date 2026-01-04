# Handoff: M4 CLI Auto-Detection + Init

## Gotchas

### File-Based Detection vs Environment Variables

**Problem:** Using `os.environ.get("KTRDR_API_PORT")` causes "env var pollution" between terminal sessions.

**Symptom:** CLI in one terminal targets the wrong backend because another terminal exported different env vars.

**Solution:** Always read from `.env.sandbox` FILE directly using `parse_dotenv_file()`:

```python
# Correct - reads file
from ktrdr.cli.sandbox_detect import resolve_api_url
url = resolve_api_url(cwd=Path.cwd())

# Wrong - reads env vars (polluted across shells)
port = os.environ.get("KTRDR_API_PORT", "8000")
```

## Patterns Established

### URL Resolution API

Task 4.1 created `ktrdr/cli/sandbox_detect.py` with:

```python
from ktrdr.cli.sandbox_detect import (
    parse_dotenv_file,    # Parse .env file to dict
    find_env_sandbox,     # Walk up tree to find .env.sandbox
    resolve_api_url,      # Full priority-based resolution
    get_sandbox_context,  # Get all sandbox env vars or None
)

# Priority order (highest to lowest):
# 1. explicit_url: --url flag
# 2. explicit_port: --port flag
# 3. .env.sandbox file: Auto-detect from directory tree
# 4. Default: http://localhost:8000

url = resolve_api_url(
    explicit_url=None,      # From --url flag
    explicit_port=8001,     # From --port flag
    cwd=Path.cwd(),         # Starting directory for auto-detect
)
# Returns: "http://localhost:8001"
```

### Directory Tree Walk

`find_env_sandbox()` walks up from cwd looking for `.env.sandbox`:

- Max 10 levels (safety limit)
- Returns `Path` to file or `None`
- Used by both `resolve_api_url()` and `get_sandbox_context()`

### CLI Callback Integration

Task 4.2 modified `ktrdr/cli/commands.py` to integrate auto-detection:

```python
from ktrdr.cli.sandbox_detect import resolve_api_url

@cli_app.callback()
def main(
    url: Optional[str] = typer.Option(...),
    port: Optional[int] = typer.Option(...),
):
    resolved_url = resolve_api_url(
        explicit_url=url,
        explicit_port=port,
    )
    if resolved_url != "http://localhost:8000":
        # Reconfigure telemetry, set _cli_state
        ...
```

The key insight: only reconfigure when URL differs from default to avoid unnecessary overhead.

### Repository Validation

Task 4.3 added `is_ktrdr_repo()` in `ktrdr/cli/sandbox.py`:

```python
from ktrdr.cli.sandbox import is_ktrdr_repo

# Returns True if git remote contains 'ktrdr' (case-insensitive)
if not is_ktrdr_repo(cwd):
    # Not a KTRDR repo - exit code 2
```

### Worktree Detection

Task 4.3 detects worktree vs clone:

```python
# Worktrees have .git as file, clones have .git as directory
is_worktree = (cwd / ".git").is_file()

if is_worktree:
    # Parse gitdir path from .git file
    with open(cwd / ".git") as f:
        content = f.read()
        # Format: gitdir: /path/to/.git/worktrees/name
        gitdir = content.split("gitdir:")[1].strip()
        parent_repo = str(Path(gitdir).parent.parent.parent)
```

### Init Command Exit Codes

- Exit 1: Already initialized (`.env.sandbox` exists) or ID collision
- Exit 2: Not a KTRDR repository
- Exit 3: Port conflicts

## M4 Progress

- [x] Task 4.1: Implement URL Resolution Logic
- [x] Task 4.2: Add `--port` Flag to Main CLI
- [x] Task 4.3: Implement `ktrdr sandbox init` Command
- [ ] Task 4.4: Update CLI Help Text
