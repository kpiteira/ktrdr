---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 7: Cleanup

**Goal:** Zero `metadata.get()` calls. Zero scattered `os.getenv()` calls for config. Unused files deleted. Documentation complete.

**Why M7:** Final cleanup after all migrations complete. This is the "Definition of Done" for the entire config system redesign.

**Branch:** `feature/config-m7-cleanup`

**Depends on:** M6 (Docker Compose & CLI)

---

## Task 7.1: Delete `ktrdr/metadata.py` and Remove All `metadata.get()` Calls

**Files:** `ktrdr/metadata.py` (delete), various consumers
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Delete the metadata module and remove all `metadata.get()` calls throughout the codebase. This resolves duplication #6 from audit (YAML→metadata→Settings three-layer config).

**Implementation Notes:**
- First, grep for all `metadata.get()` calls
- Each call should already have a Settings equivalent (from M1-M5)
- Replace any remaining calls with appropriate Settings getter
- Then delete `ktrdr/metadata.py`
- Update any imports that reference metadata

**Verification:**
```bash
# Should return zero results after cleanup
grep -r "metadata.get" ktrdr/
grep -r "from ktrdr.metadata" ktrdr/
grep -r "from ktrdr import metadata" ktrdr/
```

**Acceptance Criteria:**
- [ ] Zero `metadata.get()` calls in codebase
- [ ] `ktrdr/metadata.py` deleted
- [ ] No import errors after deletion
- [ ] All tests pass

---

## Task 7.2: Delete Unused YAML Config Files

**Files:** `config/*.yaml` (system config files only)
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Delete the YAML system config files that are now replaced by Settings classes. Keep domain config files (indicators, strategies).

**Implementation Notes:**
- Delete system config YAML files (approximately 10 files per audit)
- Keep domain config files:
  - `config/indicators/*.yaml` — indicator definitions (domain data)
  - `config/strategies/*.yaml` — strategy definitions (domain data)
- Update `loader.py` if it references deleted files

**Files to delete (verify each before deleting):**
- System metadata YAML files
- Any YAML files that only contained env var defaults

**Files to KEEP:**
- Indicator definition files
- Strategy definition files
- Any YAML that contains domain data (not system config)

**Acceptance Criteria:**
- [ ] System config YAML files deleted
- [ ] Domain config YAML files preserved
- [ ] No references to deleted files remain

---

## Task 7.3: Simplify `ktrdr/config/loader.py`

**Files:** `ktrdr/config/loader.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Remove system config loading from `loader.py`. Keep only domain config loading (indicators, strategies).

**Implementation Notes:**
- The `ConfigLoader` class may have methods for loading system config — remove them
- Keep methods for loading indicator specs, strategy definitions, etc.
- If the entire class becomes trivial, consider simplifying further

**Acceptance Criteria:**
- [ ] `loader.py` only handles domain config
- [ ] No system config loading remains
- [ ] Domain config loading still works

---

## Task 7.4: Move Version to `importlib.metadata`

**Files:** Various (wherever version is read)
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace any `APP_VERSION` env var or metadata YAML reads with `importlib.metadata.version("ktrdr")`. This reads the version from the installed package metadata (generated from `pyproject.toml` at build/install time), not from `pyproject.toml` directly. Works correctly in both editable installs and production containers.

**Implementation Notes:**
- Find all places that read version (env var, metadata, hardcoded)
- Replace with:
  ```python
  from importlib.metadata import version
  app_version = version("ktrdr")
  ```
- Remove `APP_VERSION` from docker-compose files
- No Settings field needed for version

**Acceptance Criteria:**
- [ ] Version read from `pyproject.toml` via `importlib.metadata`
- [ ] `APP_VERSION` env var removed from compose files
- [ ] Version displays correctly in API and CLI

---

## Task 7.5: Verify Zero Scattered Config Reads

**Type:** VALIDATION

**Description:**
Comprehensive verification that all config reads go through Settings classes.

**Verification commands:**
```bash
# Check for direct os.getenv calls (should only be in settings.py and validation.py)
grep -rn "os.getenv" ktrdr/ --include="*.py" | grep -v "config/settings.py" | grep -v "config/validation.py" | grep -v "test"

# Check for metadata.get calls (should be zero)
grep -rn "metadata.get" ktrdr/ --include="*.py"

# Check for direct env var reads by pattern (should be zero outside config/)
grep -rn "getenv.*DB_" ktrdr/ --include="*.py" | grep -v "config/"
grep -rn "getenv.*API_" ktrdr/ --include="*.py" | grep -v "config/"
grep -rn "getenv.*WORKER_" ktrdr/ --include="*.py" | grep -v "config/"
```

**Acceptance Criteria:**
- [ ] All verification commands return expected results
- [ ] Any legitimate exceptions documented

---

## Task 7.6: Generate Configuration Reference Documentation

**Files:** `docs/configuration.md` (create/update)
**Type:** DOCUMENTATION

**Description:**
Generate documentation from Pydantic schemas showing all available env vars, their types, defaults, and descriptions.

**Implementation Notes:**
- Can generate from Settings classes using Pydantic's `model_json_schema()`
- Include:
  - All env var names (new names)
  - Deprecated names (with migration guidance)
  - Types and default values
  - Description of each setting
  - Which component uses each setting

**Documentation structure:**
```markdown
# Configuration Reference

## Database Settings (`KTRDR_DB_*`)
| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| KTRDR_DB_HOST | str | localhost | Database host |
...

## API Settings (`KTRDR_API_*`)
...

## Deprecated Names
| Old Name | New Name | Migration |
|----------|----------|-----------|
| DB_HOST | KTRDR_DB_HOST | Change in your env files |
...
```

**Acceptance Criteria:**
- [ ] `docs/configuration.md` exists and is complete
- [ ] All Settings classes documented
- [ ] Deprecated names documented with migration guidance
- [ ] Documentation accurate and helpful

---

## Task 7.7: Execute Final E2E Test

**Type:** VALIDATION

**Description:**
Comprehensive E2E validation of the entire config system.

**E2E Test Scenarios:**

### Scenario 1: Fresh start with only KTRDR_* names
```bash
# Clean environment
docker compose down -v
# Start with only new env var names (no deprecated names)
docker compose up -d
curl http://localhost:8000/health
# Expected: 200 OK, no deprecation warnings in logs
docker compose logs 2>&1 | grep -i "deprecated"
# Expected: no output
docker compose down
```

### Scenario 2: Zero metadata.get calls verified
```bash
grep -r "metadata.get" ktrdr/ --include="*.py"
# Expected: no output
```

### Scenario 3: Version from pyproject.toml
```bash
docker compose up -d backend
curl http://localhost:8000/api/v1/info | jq '.version'
# Expected: version matches pyproject.toml
docker compose down
```

### Scenario 4: Domain config still works
```bash
# Verify indicator loading still works
uv run python -c "from ktrdr.config.loader import ConfigLoader; print(ConfigLoader().load_indicators())"
# Expected: indicators loaded successfully
```

### Scenario 5: Full integration test
```bash
docker compose up -d
# Run full test suite
make test-integration
# Expected: all tests pass
docker compose down
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Zero `metadata.get()` calls
- [ ] Zero scattered `os.getenv()` calls (outside config/)
- [ ] Version from `importlib.metadata`
- [ ] Documentation complete
- [ ] All tests pass

---

## Task 7.8: Full Distributed System Integration Test

**Type:** VALIDATION

**Description:**
Validate the complete config system works across all components: Backend, Workers, and CLI working together. This is the final validation that the entire migration succeeded.

**E2E Test Scenarios:**

### Scenario 1: Full stack startup and operation
```bash
# Start full stack
docker compose up -d

# Verify backend healthy
curl -f http://localhost:8000/health

# Verify workers registered
curl http://localhost:8000/api/v1/workers | jq 'length > 0'
# Expected: true (at least one worker registered)

# CLI can connect and fetch data
uv run ktrdr data show AAPL 1d --start-date 2024-01-01 --limit 5
# Expected: data displayed (proves CLI → API connection)

# Create an operation via CLI (proves Backend → Worker flow)
uv run ktrdr ops list
# Expected: operation list displayed

docker compose down
```

### Scenario 2: All components use new config
```bash
docker compose up -d

# Check no deprecation warnings anywhere
docker compose logs 2>&1 | grep -i "deprecated"
# Expected: no output (all components using KTRDR_* names)

# Check backend validation passed
docker compose logs backend 2>&1 | grep -i "configuration error"
# Expected: no output

# Check workers validated their config
docker compose logs training-worker 2>&1 | grep -i "configuration error"
# Expected: no output

docker compose down
```

**Success Criteria:**
- [ ] Full stack starts with all components
- [ ] Workers register successfully
- [ ] CLI communicates with backend
- [ ] No deprecation warnings in any component logs
- [ ] No configuration errors in any component

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] `ktrdr/metadata.py` deleted
- [ ] `ktrdr/config/credentials.py` deleted (if exists, from M3)
- [ ] System config YAML files deleted
- [ ] `loader.py` simplified
- [ ] Version from `importlib.metadata`
- [ ] Documentation generated
- [ ] Verification commands pass
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] Branch merged to main

---

## Definition of Done (Entire Config System Redesign)

After M7 completion, the following must be true:

1. **All 16 Settings classes exist** with proper KTRDR_* prefixes
2. **Zero `metadata.get()` calls** anywhere in codebase
3. **Zero scattered `os.getenv()` calls** for config (only in `ktrdr/config/`)
4. **All deprecated names work** with deprecation warnings
5. **`KTRDR_ENV` controls validation strictness**
6. **Insecure defaults fail in production**, warn in development
7. **Docker compose files use only KTRDR_* names**
8. **Configuration documentation is complete and accurate**
9. **All tests pass** (unit, integration, E2E)
10. **No regressions** in existing functionality
