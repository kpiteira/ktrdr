# Handoff: M2 CLI Core Commands

## Gotchas

### Port Allocation Import
**Problem:** The module logs on import due to KTRDR's logging setup.

**Symptom:** Running `from ktrdr.cli.sandbox_ports import get_ports` produces log output.

**Solution:** This is expected behavior and doesn't affect functionality. For quiet scripts, use logging configuration or redirect stderr.

## Patterns Established

### Port Allocation API
Task 2.1 created `ktrdr/cli/sandbox_ports.py` with:

```python
from ktrdr.cli.sandbox_ports import get_ports, check_ports_available, is_port_free

# Get all ports for a slot
ports = get_ports(1)  # Returns PortAllocation dataclass
ports.backend  # 8001
ports.db       # 5433
ports.worker_ports  # [5010, 5011, 5012, 5013]

# Generate .env.sandbox content
env_dict = ports.to_env_dict()  # Dict[str, str] with KTRDR_* keys

# Check for port conflicts
conflicts = check_ports_available(1)  # Returns list of ports in use
```

### Testing Port Conflicts
For tests that need to simulate port conflicts, mock `is_port_free`:

```python
from unittest.mock import patch
from ktrdr.cli.sandbox_ports import check_ports_available, get_ports

ports = get_ports(3)

def mock_is_port_free(port):
    return port != ports.backend  # Simulate backend port in use

with patch("ktrdr.cli.sandbox_ports.is_port_free", side_effect=mock_is_port_free):
    conflicts = check_ports_available(3)
    # conflicts will contain ports.backend
```

### Instance Registry API

Task 2.2 created `ktrdr/cli/sandbox_registry.py` with:

```python
from ktrdr.cli.sandbox_registry import (
    add_instance, get_instance, remove_instance,
    allocate_next_slot, get_allocated_slots, clean_stale_entries,
    load_registry, InstanceInfo
)

# Allocate next available slot (fills gaps)
slot = allocate_next_slot()  # Returns 1-10, raises if exhausted

# Create and register an instance
info = InstanceInfo(
    instance_id="ktrdr--my-feature",
    slot=slot,
    path="/path/to/ktrdr--my-feature",
    created_at="2024-01-15T10:30:00Z",
    is_worktree=True,
    parent_repo="/path/to/ktrdr"
)
add_instance(info)

# Query instances
instance = get_instance("ktrdr--my-feature")
allocated = get_allocated_slots()  # Returns set[int]

# Cleanup
remove_instance("ktrdr--my-feature")
stale = clean_stale_entries()  # Removes entries with missing directories
```

### Testing Registry Operations

For tests, mock the registry path to use a temp directory:

```python
@pytest.fixture
def mock_registry_path(tmp_path):
    registry_dir = tmp_path / ".ktrdr" / "sandbox"
    registry_dir.mkdir(parents=True)
    registry_file = registry_dir / "instances.json"
    with patch("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir):
        with patch("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_file):
            yield registry_file
```

### CLI Module Pattern

Task 2.3 created `ktrdr/cli/sandbox.py` with the Typer app structure:

```python
from ktrdr.cli.sandbox import sandbox_app, console, error_console
```

Add commands using the `@sandbox_app.command()` decorator. Use `console` for output and `error_console` for errors with Rich formatting.

## For Next Tasks

- **Task 2.4 (Create):** Import from `ktrdr.cli.sandbox_ports` for port allocation
- **Task 2.5 (Up/Down):** Load port info from `.env.sandbox`, not from `get_ports()`
