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

## For Next Tasks

- **Task 2.2 (Registry):** Use `get_ports(slot).to_env_dict()` when generating `.env.sandbox`
- **Task 2.3 (CLI Module):** Register sandbox_app in `ktrdr/cli/__init__.py`
- **Task 2.4 (Create):** Import from `ktrdr.cli.sandbox_ports` for port allocation
- **Task 2.5 (Up/Down):** Load port info from `.env.sandbox`, not from `get_ports()`
