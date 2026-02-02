# Handoff: M3 - Slot Pool Infrastructure

## Task 3.1 Complete: Update registry to v2 schema

**Implementation Notes:**
- SlotInfo dataclass stores: slot_id, infrastructure_path, profile, workers, ports, claimed_by, claimed_at, status
- Registry now has `slots` dict (str -> SlotInfo) for slot pool
- PROFILE_ORDER = ["light", "standard", "heavy"] for slot selection logic
- `get_available_slot(min_profile)` returns first unclaimed slot >= min profile, preferring lighter slots
- v1 registries auto-migrate on load (preserves instances and local_prod, adds empty slots dict)

**Testing Notes:**
- Tests use `mock_registry_path` fixture to patch REGISTRY_DIR and REGISTRY_FILE
- Import SlotInfo from sandbox_registry, not from a separate module

**Next Task Notes:**
- Task 3.2 creates `kinfra sandbox provision` command
- Use SLOT_PROFILES dict pattern from milestone plan
- Port allocation: slot N uses 8000+N for API, 5432+N for DB, etc.

## Task 3.2 Complete: Create slot provisioning command

**Implementation Notes:**
- SANDBOXES_DIR = `~/.ktrdr/sandboxes/` (module-level constant for easy mocking)
- SLOT_PROFILES dict defines profile and workers per slot
- `_get_slot_ports(slot_id)` returns port dict for any slot
- Provision creates placeholder docker-compose.yml (actual template in Task 3.3)
- Idempotent: checks `slot_path.exists()` before creating

**Testing Notes:**
- Tests use `monkeypatch.setattr()` to redirect SANDBOXES_DIR and REGISTRY_FILE to tmp_path
- Must patch both kinfra/sandbox.py and sandbox_registry.py paths

**Next Task Notes:**
- Task 3.3 creates compose templates in `ktrdr/cli/kinfra/templates/`
- Replace placeholder compose file with proper template
- Template uses `${VARIABLE}` placeholders for ports, worker counts
