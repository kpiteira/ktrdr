# Configuration System: Validation Results

**Date:** 2026-01-27
**Status:** Validated. All scenarios traced, gaps resolved, interface contracts defined.
**Branch:** `doc/config-system-design-v2`

---

## Validation Summary

Ran full `/kdesign-validate` on the config system design. Enumerated 17 scenarios, traced each through the architecture, identified 9 gaps (3 critical), resolved all gaps, defined interface contracts, and proposed milestone structure.

Additionally performed a comprehensive codebase audit that expanded scope from ~40 env vars to ~90 env vars plus 14 YAML files, 6 duplications, 1 bug, and 5 Python modules to delete.

---

## Scenarios Traced

### Happy Paths

| # | Scenario | Result |
|---|----------|--------|
| H1 | Backend startup with all `KTRDR_*` env vars set | `validate_all("backend")` instantiates all Settings classes, all pass, no warnings |
| H2 | Backend startup with insecure defaults (dev mode) | Settings load with defaults, `detect_insecure_defaults()` emits BIG WARNING, app starts |
| H3 | Hot reload during development | uvicorn restarts Python process, `lru_cache` clears naturally, new Settings instances created, container env vars persist |
| H4 | Worker startup with valid config | `validate_all("worker")` checks DB + logging + worker + checkpoint settings, passes |
| H5 | CLI command (e.g., `ktrdr --help`) | No validation called — import doesn't trigger validation. Works without any env vars |
| H6 | Local-prod startup | `ktrdr local-prod up` sets `KTRDR_ENV=production`, passes compose env to Docker, backend validates strictly |

### Error Paths

| # | Scenario | Result |
|---|----------|--------|
| E1 | Missing required setting (no default) | `validate_all()` collects error, prints formatted message with env var name, raises `ConfigurationError` |
| E2 | Invalid type (`KTRDR_API_PORT=abc`) | Pydantic validation error collected, message includes field name, expected type, and actual value |
| E3 | Multiple errors at once | All errors collected (not just first), displayed together in one block |
| E4 | Insecure defaults in production mode | `KTRDR_ENV=production` + default password → **hard failure**, not just warning |

### Edge Cases

| # | Scenario | Result |
|---|----------|--------|
| EC1 | Deprecated env var (`DB_PASSWORD` instead of `KTRDR_DB_PASSWORD`) | `AliasChoices` accepts old name, `warn_deprecated_env_vars()` emits `DeprecationWarning` |
| EC2 | Both old and new name set | Pydantic `AliasChoices` prefers first match = new name wins (listed first). Warning still emitted for old name presence |
| EC3 | `validation_alias` overrides `env_prefix` | **Critical finding.** Solved by `deprecated_field()` helper that explicitly includes prefixed name in `AliasChoices` |
| EC4 | Settings read at import time | Only `lru_cache` getters read settings. Import of settings module does NOT trigger env var reads |

### Integration Boundaries

| # | Scenario | Result |
|---|----------|--------|
| I1 | Worker validates subset only | `validate_all("worker")` only instantiates worker-relevant Settings classes |
| I2 | Test isolation | `clear_settings_cache()` resets `lru_cache`, `monkeypatch.setenv()` + cache clear gives test isolation |
| I3 | Docker compose passes env vars | `ktrdr sandbox up` calls `fetch_sandbox_secrets()` → merges into `compose_env` → `subprocess.run(cmd, env=compose_env)` → container inherits |

---

## Gaps Found and Resolved

### Critical Gaps

#### GAP-D: `validation_alias` Overrides `env_prefix` (Pydantic v2 Behavior)

**Problem:** When `validation_alias=AliasChoices(...)` is set on a field, Pydantic v2 completely ignores `env_prefix` for that field. This means `KTRDR_DB_HOST` would NOT work if the `AliasChoices` only lists `DB_HOST`.

**Verified:** Ran actual Python test confirming this behavior.

**Resolution:** Decision 9 — `deprecated_field()` helper that always includes the prefixed name as the FIRST alias:
```python
def deprecated_field(default, new_env: str, old_env: str, **kwargs) -> Field:
    return Field(
        default=default,
        validation_alias=AliasChoices(new_env, old_env),
        **kwargs,
    )

# Usage:
password: str = deprecated_field("localdev", "KTRDR_DB_PASSWORD", "DB_PASSWORD")
```

#### GAP-I: Import-Time Validation Breaks CLI

**Problem:** Decision 7 originally said settings validate at import time. But `ktrdr --help` imports the config module — it would fail without `KTRDR_DB_PASSWORD` set.

**Resolution:** Decision 7 rewritten — validation is an **explicit startup call**. Only `ktrdr/api/main.py` and worker entrypoints call `validate_all()`. CLI commands never trigger validation.

#### GAP-C: `KTRDR_ENV` Has No Home

**Problem:** `KTRDR_ENV` controls validation strictness but can't live in a Settings class (circular: you need to know the env to know how strictly to validate settings).

**Resolution:** `KTRDR_ENV` is read via plain `os.getenv("KTRDR_ENV", "development")` inside the validation module. Not a Settings field. Injected by CLI commands:
- `ktrdr local-prod up` → `KTRDR_ENV=production`
- `ktrdr sandbox up` → `KTRDR_ENV=development`

### Important Gaps

#### GAP-A: Complete Consumer Audit Missing

**Problem:** Design referenced "~40 env vars" but actual count was unknown.

**Resolution:** Comprehensive audit found ~90 unique env var names across ~30 files. Full mapping now in ARCHITECTURE.md.

#### GAP-G: metadata.py Removal Impact

**Problem:** `metadata.get()` is called in ~35 places. Removing metadata.py affects many files.

**Resolution:** Each `metadata.get()` call maps to a specific Settings class field. Migration plan Phase 2 covers all consumers. Phase 3 explicitly verifies zero remaining `metadata.get()` calls.

#### GAP-H: Docker Compose Env Var Update

**Problem:** Two docker-compose files use old env var names throughout.

**Resolution:** Phase 2 step 11 handles docker-compose migration. Deprecated names ensure backward compatibility during transition.

#### GAP-F: `.env.local` Loading

**Problem:** Design mentions `.env.local` but Pydantic needs explicit `env_file` config.

**Resolution:** Settings base class includes `env_file=".env.local"` in `model_config`. File is optional (Pydantic handles missing file gracefully).

### Minor Gaps

#### GAP-B: Config Loader Fate

**Problem:** Should `ktrdr/config/loader.py` be deleted entirely?

**Resolution:** Keep for domain config loading (indicator specs, strategy YAML). Remove system config loading. "Modify" not "Delete".

#### GAP-E: Version Source

**Problem:** `APP_VERSION` env var is set in docker-compose, also read from metadata YAML.

**Resolution:** Use `importlib.metadata.version("ktrdr")` for runtime version (reads from pyproject.toml). Remove `APP_VERSION` env var. No Settings field needed.

---

## Codebase Audit Summary

### By the Numbers

| Category | Count |
|----------|-------|
| Unique env var names found | ~90 |
| Files with `os.getenv()` calls | ~30 |
| Files with `metadata.get()` calls | ~15 |
| Duplicated config concepts | 6 |
| Bugs found | 1 |
| Settings classes needed | 16 |
| Deprecated name mappings | ~50 |
| YAML files to delete | 10 |
| Python modules to delete | 5 (metadata.py, ib_config.py, host_services.py, api/config.py, and YAML files) |

### Duplications Found

1. **`APIConfig` vs `APISettings`** — Two classes, same `KTRDR_API_` prefix, overlapping fields. `APIConfig` in `ktrdr/api/config.py` duplicates `APISettings` in `ktrdr/config/settings.py`.
2. **Environment concept** — Three different env var names: `KTRDR_ENVIRONMENT`, `ENVIRONMENT`, `KTRDR_API_ENVIRONMENT`. All mean the same thing.
3. **`USE_IB_HOST_SERVICE`** — Read in 4 separate places with different defaults (`"false"` vs `"true"` vs no default).
4. **`WORKER_PORT`** — Defaults to 5002 in `training_worker.py` but 5004 in `worker_registration.py`. **Bug: worker could register with wrong port.**
5. **`KTRDR_API_URL` vs `KTRDR_API_CLIENT_BASE_URL`** — Same concept (backend URL for workers/CLI), different names.
6. **metadata YAML → Settings → YAML loop** — Some values exist in metadata YAML, are loaded into Settings, and the Settings default reads from YAML. Three layers for one value.

### Config Patterns Found (All to Consolidate)

| Pattern | Location | Count | Migration Target |
|---------|----------|-------|-----------------|
| `os.getenv()` direct reads | Scattered across codebase | ~80 calls | Settings class getters |
| `metadata.get()` calls | Various modules | ~35 calls | Settings class defaults |
| `IbConfig` dataclass | `ktrdr/config/ib_config.py` | 1 class, ~15 fields | `IBSettings` |
| `HostServiceSettings` dataclass | `ktrdr/config/host_services.py` | 2 classes | `IBHostServiceSettings`, `TrainingHostServiceSettings` |
| `APIConfig(BaseSettings)` | `ktrdr/api/config.py` | 1 class | Merge into `APISettings` |
| Existing `BaseSettings` | `ktrdr/config/settings.py` | 4 classes | Expand to 16 classes |
| YAML system config | `config/*.yaml` | 10 files | Settings class defaults, then delete |
| YAML domain config | `config/indicators/*.yaml`, etc. | ~4 files | **Keep** (domain data, not system config) |

---

## Interface Contracts

### Settings Module API

```python
# ktrdr/config/settings.py

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "ktrdr"
    user: str = "ktrdr"
    password: str = deprecated_field("localdev", "KTRDR_DB_PASSWORD", "DB_PASSWORD")
    echo: bool = False

    @computed_field
    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()

# ... 15 more Settings classes with getters ...

def clear_settings_cache() -> None:
    """Clear all cached settings. Call in tests."""
    get_db_settings.cache_clear()
    get_api_settings.cache_clear()
    # ... all getters ...
```

### Validation Module API

```python
# ktrdr/config/validation.py

def validate_all(component: str = "all") -> None:
    """Validate all settings for the given component.

    Args:
        component: "backend", "worker", or "all"

    Raises:
        ConfigurationError: If any settings are invalid or
            insecure defaults are used in production mode.
    """

def detect_insecure_defaults() -> dict[str, str]:
    """Check which secrets are still at their insecure default values.

    Returns:
        Dict of {env_var_name: default_value} for secrets at defaults.
    """
```

### Deprecation Module API

```python
# ktrdr/config/deprecation.py

DEPRECATED_NAMES: dict[str, str] = {
    "DB_HOST": "KTRDR_DB_HOST",
    "DB_PASSWORD": "KTRDR_DB_PASSWORD",
    # ... ~50 entries (see ARCHITECTURE.md for complete map)
}

def warn_deprecated_env_vars() -> list[str]:
    """Check environment for deprecated var names, emit warnings.

    Returns:
        List of deprecated names that were found set.
    """
```

### Startup Integration

```python
# In ktrdr/api/main.py (backend startup):
from ktrdr.config import validate_all, warn_deprecated_env_vars

deprecated = warn_deprecated_env_vars()  # Warnings first
validate_all(component="backend")         # Then validate

# In worker entrypoints:
from ktrdr.config import validate_all, warn_deprecated_env_vars

deprecated = warn_deprecated_env_vars()
validate_all(component="worker")
```

---

## Proposed Milestone Structure

### Milestone 1: Foundation Settings Classes
- Create/expand all 16 Settings classes with `deprecated_field()` support
- Implement `deprecated_field()` helper
- Write unit tests for all classes (defaults, overrides, aliases, validation)
- No existing code changes

### Milestone 2: Validation & Deprecation Infrastructure
- Rewrite `validation.py` with `KTRDR_ENV`-aware startup validation
- Create `deprecation.py` with complete old→new mapping
- Update `__init__.py` public API
- Write unit tests for validation and deprecation
- Integrate validation into backend startup (`main.py`)

### Milestone 3: Consumer Migration (Core)
- Migrate database, API, auth, logging, observability consumers
- Delete `ktrdr/api/config.py` (resolves duplication #1)
- Update docker-compose files with new env var names
- Each domain in a separate commit

### Milestone 4: Consumer Migration (Workers & Agent)
- Migrate IB, host services, workers, agent, data consumers
- Delete `ktrdr/config/ib_config.py`, `ktrdr/config/host_services.py`
- Fix WORKER_PORT bug
- Each domain in a separate commit

### Milestone 5: Cleanup & Documentation
- Delete `ktrdr/metadata.py` and all `metadata.get()` calls
- Delete unused YAML files
- Simplify `loader.py`
- Move version to `importlib.metadata`
- Generate config reference docs from Pydantic schemas
- Verify zero remaining scattered config reads

### Future: Phase 4 — Deprecation Removal
- Remove `AliasChoices` support for old names
- Remove `deprecation.py`
- All systems use only `KTRDR_*` names

---

## Key Decisions Made During Validation

| Decision | Rationale |
|----------|-----------|
| Explicit startup validation, NOT import-time | CLI commands (`ktrdr --help`) must work without config |
| `KTRDR_ENV` via `os.getenv()`, not in Settings | Avoids circular dependency (need env to know validation strictness) |
| Local-prod IS production (`KTRDR_ENV=production`) | Insecure defaults must fail in local-prod, not just warn |
| `deprecated_field()` helper is mandatory for aliases | Pydantic v2's `validation_alias` overrides `env_prefix` — easy to get wrong |
| Keep `loader.py` for domain config | Indicator/strategy YAML is domain data, not system config |
| Delete `metadata.py` entirely | Three-layer config (YAML→metadata→env) is the root cause of complexity |
| Fix all duplications, not just env vars | User explicitly expanded scope: "ANYTHING that smells like a config" |

---

## Files in This Design

| File | Purpose |
|------|---------|
| `DESIGN.md` | Problem, goals, decisions, user scenarios |
| `ARCHITECTURE.md` | Components, data flow, file changes, migration plan, testing strategy |
| `SCENARIOS.md` | This file — validation results, gaps, audit, interface contracts, milestones |
| `VALIDATION_NOTES.md` | Earlier session notes (2026-01-18, pre-validation) |
