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

---

## Task 7.3 Complete: Simplify `loader.py`

**Removed (dead code):**
- `load_fuzzy_defaults()` - never called from anywhere
- `load_multi_timeframe_indicators()` - never called
- `validate_multi_timeframe_config()` - never called
- `create_sample_multi_timeframe_config()` - never called

These methods were created for multi-timeframe indicator features but were never integrated.

**Kept (still used):**
- `load()` - Used by `local_data_loader.py`, `ib_service.py`, `data.py` endpoints
- `load_from_env()` - Used by `ib_service.py`, `data.py` endpoints

**Note:** The remaining methods load `KtrdrConfig` from `settings.yaml` which contains
a mix of domain config (data.directory) and some legacy system-ish config (ib_host_service).
Full migration would require updating all callers to use Settings classes, which is a
larger scope change.

---

## Task 7.4 Complete: Move Version to `importlib.metadata`

**Changed:**
- `ktrdr/version.py` - Now uses `importlib.metadata.version("ktrdr")` instead of
  parsing pyproject.toml with tomli. Removes ~50 lines of path-finding code.
- `ktrdr/monitoring/setup.py` - Replaced `os.getenv("APP_VERSION", "dev")` with
  `__version__` from ktrdr.version (2 occurrences)

**Note:** APP_VERSION was not in docker-compose files, so no compose changes needed.

**Gotcha:** The import order matters - `ktrdr.version` import must come after
third-party imports (opentelemetry, prometheus_client) to satisfy ruff.

---

## Task 7.5 Complete: Verify Zero Scattered Config Reads

**Results:**
- ✅ Zero `metadata.get()` calls - Complete success
- ⚠️ Some `os.getenv()` calls remain but categorized as legitimate or future-migrate

**Documented Legitimate Exceptions:**
1. OpenTelemetry metadata (`ENVIRONMENT`) - deployment info for traces
2. Agent quality gates (`TRAINING_GATE_*`, `BACKTEST_GATE_*`) - agent thresholds
3. Testing stubs (`STUB_WORKER_*`, `USE_STUB_WORKERS`) - debug/test flags
4. Dynamic host service detection (service_orchestrator.py) - runtime pattern
5. Docs config path (`KTRDR_DOCS_CONFIG_PATH`) - override for config file

**Future Migration (not blocking):**
Some code still uses deprecated env var names (USE_TRAINING_HOST_SERVICE, USE_IB_HOST_SERVICE,
DB_HOST). These work via deprecation warnings and can be migrated incrementally.

**Next Task Notes:**
- Task 7.6 is DOCUMENTATION - generate configuration reference

---

## Task 7.6 Complete: Generate Configuration Reference Documentation

**Created:**
- `docs/configuration.md` - Complete configuration reference

**Documentation covers:**
- All 16 Settings classes with env var tables
- Environment variable naming convention (KTRDR_* prefixes)
- Type, default, and description for each setting
- Usage examples with Python code snippets
- Full deprecated names migration table (45+ deprecated → new mappings)
- Best practices section

**Next Task Notes:**
- Task 7.7 is VALIDATION - E2E test of config system
- Task 7.8 is VALIDATION - Full distributed system integration test
