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

## Task 3.3 Complete: Create compose templates

**Implementation Notes:**
- Created `ktrdr/cli/kinfra/templates/` package with `__init__.py` and `docker-compose.base.yml`
- `get_compose_template()` returns template content as string
- Template uses `${KTRDR_*_PORT:-default}` syntax for port substitution
- Simplified from full sandbox compose - workers are single service (can scale with `--scale`)
- Updated provision command to use template instead of placeholder

**Testing Notes:**
- Tests import template module and validate YAML structure
- Use `yaml.safe_load()` to parse and validate template

**Next Task Notes:**
- Task 3.4 creates `kinfra sandbox slots` command to list all slots with status
- Use registry's `get_all_slots()` method for data
- Display in Rich table with profile, ports, claimed status

## Task 3.4 Complete: Create slots listing command

**Implementation Notes:**
- `slots()` command added to sandbox.py
- Uses `registry.slots` dict sorted by slot ID
- Rich Table displays: Slot, Profile, API Port, Claimed By, Status
- Empty registry shows guidance to run `provision`
- Status color-coded: `[green]running[/green]` or `[dim]stopped[/dim]`

**Next Task Notes:**
- Task 3.5 is a VALIDATION task - run E2E test to verify all M3 functionality
- Use E2E agent workflow: e2e-test-designer → e2e-test-architect → e2e-tester

## Task 3.5 Complete: Execute E2E Test (VALIDATION)

**E2E Test Results:** All 10 steps PASSED
- Dry-run mode shows all 6 slots without creating files ✅
- Provision creates 6 slot directories ✅
- Each slot has .env.sandbox and docker-compose.yml ✅
- Port allocations correct (API=8000+slot, DB=5432+slot) ✅
- Profiles correct (1-4 light, 5 standard, 6 heavy) ✅
- Registry v2 schema with version=2 and slots dict ✅
- `kinfra sandbox slots` displays table with all 6 slots ✅
- Idempotency works (second provision skips existing) ✅

**Test Spec:** `.claude/skills/e2e-testing/tests/cli/kinfra-slot-provisioning.md`

**Note:** Registry is stored at `~/.ktrdr/sandbox/instances.json` (without 's'), not `~/.ktrdr/sandboxes/registry.json`. This is correct - the implementation uses the existing registry location for backward compatibility.
