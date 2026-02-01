# M7 Handoff - Cleanup

**Branch:** `feature/config-m7-cleanup`
**Started:** 2026-02-01

---

## Context

M7 is the final cleanup phase for the config system redesign. It removes the legacy `metadata` module and ensures all config reads go through Settings classes.

---

## Task 7.1 Complete: Delete `metadata.py` and Remove All `metadata.get()` Calls

**Changes:**
- Deleted `ktrdr/metadata.py` (legacy config loader from YAML)
- Deleted `tests/unit/core/test_metadata.py`
- Updated `ktrdr/config/settings.py`:
  - Changed import from `from .. import metadata` to `from ..version import __version__`
  - Replaced `metadata.VERSION` with `__version__`
  - Replaced `metadata.API_TITLE` with `"KTRDR API"`
  - Replaced `metadata.API_DESCRIPTION` with `"REST API for KTRDR trading system"`
  - Replaced `metadata.API_PREFIX` with `"/api/v1"`
  - Replaced `metadata.get("api.client_*", ...)` with hardcoded defaults
- Updated `ktrdr/config/__init__.py`:
  - Removed `from .. import metadata`
  - Removed `"metadata"` from `__all__`
- Updated `ktrdr/api/endpoints/system.py`:
  - Changed import to use `ktrdr.version.__version__`
- Updated tests:
  - `tests/api/test_api_setup.py` - uses `__version__`
  - `tests/integration/api/test_main.py` - uses `__version__`
  - `tests/unit/config/test_config_exports.py` - removed metadata import test
- Added `tests/unit/config/test_version_source.py` - verifies version access

**Gotchas:**
- Many files have variables named `metadata` (dicts for model info, symbol info, etc.) - these are NOT the `ktrdr.metadata` module
- The health endpoint test needed updating because it now includes `orphan_detector` field

**Next Task Notes:**
- Task 7.2 will delete unused YAML config files
- `config/ktrdr_metadata.yaml` can now be deleted since nothing reads it

---

## Task 7.2 Complete: Delete Unused YAML Config Files

**Deleted:**
- `config/ktrdr_metadata.yaml` - Central metadata, only read by deleted metadata.py
- `config/environment/` directory (5 files) - Environment overrides, only used by metadata.py
- `scripts/update_metadata.py` - Script to sync metadata to other files, now obsolete
- `ktrdr/version.json` - Generated file, nothing references it

**Preserved (still have active references):**
- `config/settings.yaml` - Used by data modules via ConfigLoader
- `config/fuzzy.yaml` - Used by loader.py:load_fuzzy_defaults()
- `config/docs_config.yaml` - Used by docs_config.py
- `config/indicators.yaml` - Indicator definitions (domain data)
- `config/ib_host_service.yaml` - Used by ib-host-service
- `config/training_host_service.yaml` - Used by training-host-service
- `config/workers.dev.yaml` / `config/workers.prod.yaml` - Used by deployment config tests

**Next Task Notes:**
- Task 7.3 will simplify loader.py to remove system config loading
