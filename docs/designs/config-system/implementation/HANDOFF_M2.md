# M2 Handoff: API, Auth & Logging Settings

## Task 2.1 Complete: Create `APISettings` Class

### Gotchas

**CORS list fields use JSON arrays in env vars**: pydantic-settings expects `list[str]` fields to be provided as JSON arrays in environment variables, NOT comma-separated strings. Example: `KTRDR_API_CORS_ORIGINS='["http://localhost:3000","http://localhost:8080"]'`

**Validators for environment and log_level normalize case**: The `environment` validator converts to lowercase, `log_level` validator converts to uppercase. This means `PRODUCTION` → `production` and `debug` → `DEBUG`.

**Removed metadata.get() for direct defaults**: The old `APISettings` used `metadata.get("api.host", "127.0.0.1")` for defaults. The new version uses direct defaults (`default="127.0.0.1"`) for clarity. Environment variables override these anyway.

### Emergent Patterns

**No custom CORS parsing needed**: The original `APIConfig` had `@field_validator("cors_origins", mode="before")` to parse comma-separated strings. With pydantic-settings, JSON arrays work out of the box, so no custom parsing is needed.

**Merged fields from APIConfig**: The new `APISettings` includes all CORS fields from `ktrdr/api/config.py::APIConfig`:
- `cors_allow_credentials` (bool)
- `cors_allow_methods` (list[str])
- `cors_allow_headers` (list[str])
- `cors_max_age` (int)

### Next Task Notes (2.2: Create AuthSettings)

- Add `AuthSettings` class with `env_prefix="KTRDR_AUTH_"`
- Include `jwt_secret` field (will need insecure default detection later)
- Include `jwt_algorithm`, `token_expire_minutes`
- Follow same pattern: `@lru_cache` getter, add to `clear_settings_cache()`

---

## Task 2.2 Complete: Create `AuthSettings` Class

### Gotchas

**Insecure default for jwt_secret**: The default `"insecure-dev-secret"` is intentionally insecure. Task 2.9 will add validation to reject this in production mode.

### Emergent Patterns

**Minimal validation, explicit defaults**: Unlike `APISettings` which has validators for `environment` and `log_level`, `AuthSettings` keeps it simple. The `jwt_algorithm` is a plain string (no validation for valid algorithms like HS256/HS512/RS256) — if an invalid algorithm is used, it will fail at JWT sign/verify time, which is clear enough. YAGNI applies.

### Next Task Notes (2.3: Create LoggingSettings)

- `LoggingSettings` already exists (skeleton from earlier) but may need enhancement
- Check if it needs `env_file=".env.local"` and `extra="ignore"` for consistency
- Fields: `level`, `format`, maybe `json_output`
- Verify it's already in `clear_settings_cache()` and `__all__`

---

## Task 2.3 Complete: Create `LoggingSettings` Class

### Gotchas

**Changed env prefix from `KTRDR_LOGGING_` to `KTRDR_LOG_`**: The original skeleton used `KTRDR_LOGGING_` but the task description (and other settings) use shorter prefixes. Changed to `KTRDR_LOG_` for consistency (e.g., `KTRDR_LOG_LEVEL` not `KTRDR_LOGGING_LEVEL`).

**Removed `metadata.get()` for defaults**: The skeleton used `metadata.get("logging.level", "INFO")` which was reading from metadata.yaml. Changed to direct defaults for consistency with other settings classes. Environment variables override these anyway.

### Emergent Patterns

**Level validation pattern reused**: Copied the level validation pattern from `APISettings.validate_log_level()` to `LoggingSettings.validate_level()` — same allowed values, same case normalization to uppercase.

### Next Task Notes (2.4: Create ObservabilitySettings)

- Add `ObservabilitySettings` class with `env_prefix="KTRDR_OTEL_"`
- Fields: `jaeger_host`, `jaeger_port`, `service_name`, `enabled`
- Check existing Jaeger env vars in the codebase (grep for `JAEGER_*`, `OTEL_*`)
- Follow same pattern: `@lru_cache` getter, add to `clear_settings_cache()`, add to `__all__`

---

## Task 2.4 Complete: Create `ObservabilitySettings` Class

### Gotchas

**Used `otlp_endpoint` instead of separate host/port**: The codebase uses `OTLP_ENDPOINT` as a full URL (`http://jaeger:4317`), not separate host/port. Kept this pattern for compatibility.

**Deprecated name for `OTLP_ENDPOINT`**: Added `deprecated_field()` support so existing `OTLP_ENDPOINT` env var continues to work while new code can use `KTRDR_OTEL_OTLP_ENDPOINT`.

### Emergent Patterns

**Full URL better than separate host/port**: For OTLP endpoints, a full URL is more flexible (can include path, protocol) than separate host/port fields. The monitoring code already uses this pattern.

### Next Task Notes (2.5: Migrate API Consumers)

- Replace all `os.getenv("KTRDR_API_*")` and `os.getenv("API_*")` calls in `ktrdr/api/`
- Replace `APIConfig()` usages with `get_api_settings()`
- Delete `ktrdr/api/config.py` after migration
- Check `ktrdr/api/main.py`, `ktrdr/api/server.py`, and CORS setup code

---

## Task 2.5 Complete: Migrate API Consumers and Delete `ktrdr/api/config.py`

### Gotchas

**`ktrdr/config/__init__.py` needed updating**: The new settings classes and getters weren't exported from `ktrdr.config`. Added all M2 settings to the package exports so `from ktrdr.config import get_api_settings` works.

**Additional files outside `ktrdr/api/` also used `APIConfig`**:
- `tests/api/test_api_setup.py` - updated to use `get_api_settings()`
- `scripts/run_api_server.py` - updated, removed `APIConfig.from_env()` call (was no-op anyway)
- `tests/unit/api/test_config.py` - **deleted** (tested old `APIConfig`, replaced by `tests/unit/config/test_api_settings.py`)

**`from_env()` method was deleted**: The old `APIConfig.from_env()` method doesn't exist in `APISettings`. Environment variables are read automatically by pydantic-settings. The script that used it was updated.

### Emergent Patterns

**Re-export from package `__init__.py`**: Updated `ktrdr/config/__init__.py` to export all M2 settings classes and getters, making imports cleaner: `from ktrdr.config import get_api_settings`.

**Backward compatibility export**: `ktrdr/api/__init__.py` now re-exports `APISettings` (not `APIConfig`) for any external code that imports from there.

### Files Deleted

- `ktrdr/api/config.py` — duplicate `APIConfig` class (resolves duplication #1 from audit)
- `tests/unit/api/test_config.py` — tests for deleted `APIConfig`

### Next Task Notes (2.6: Migrate Auth Consumers)

- No auth code exists yet (no `ktrdr/api/auth/` directory)
- Task may be a no-op if there are no auth consumers to migrate
- Check for any `os.getenv("JWT_*")` calls in the codebase

---

## Task 2.6 Complete: Migrate Auth Consumers

### Summary

**No-op task** — No auth consumers exist to migrate. The `ktrdr/api/auth/` directory does not exist, and there are no `os.getenv()` calls for JWT, AUTH, SECRET, or TOKEN in the `ktrdr/` codebase (the `AGENT_*` env vars in `ktrdr/agents/invoker.py` are for LLM token limits, not authentication).

### Acceptance Criteria Met

- Zero direct auth env var reads — confirmed via grep
- Auth functionality unchanged — no auth functionality exists

### Next Task Notes (2.7: Migrate Logging Consumers)

- Check `ktrdr/logging/` directory for `os.getenv("LOG_LEVEL")` calls
- Replace with `get_logging_settings().level`
- Check existing logging setup code (likely in `__init__.py` or similar)

---

## Task 2.7 Complete: Migrate Logging Consumers

### What Was Done

The logging module (`ktrdr/logging/*.py`) already had zero direct `os.getenv()` calls — it's configured via parameters to `configure_logging()`. The wiring needed was in `ktrdr/__init__.py` where logging is initialized.

**Changes made:**
1. Added `get_log_level_int()` method to `LoggingSettings` to convert string level to Python logging constant
2. Updated `ktrdr/__init__.py` to use `get_logging_settings()` when calling `configure_logging()`
3. Wired `LoggingSettings.level` → `console_level` parameter
4. Wired `LoggingSettings.format` → `config["console_format"]` parameter

### Gotchas

**Import timing matters**: The `get_logging_settings()` import is done inside the `if not _is_testing:` block, after `load_dotenv()` is called. This ensures environment variables are loaded before settings are read.

### Emergent Patterns

**Settings provide the values, modules stay decoupled**: Rather than having `ktrdr/logging/config.py` import from settings (which could cause circular imports), the wiring happens at the application entry point (`ktrdr/__init__.py`). The logging module remains a pure utility that takes parameters.

### Next Task Notes (2.8: Migrate Observability/Tracing Consumers)

- Check `ktrdr/monitoring/` for Jaeger/OTEL env var reads
- Look for `OTLP_ENDPOINT`, `JAEGER_*`, `OTEL_*` patterns
- Replace with `get_observability_settings().field`
- May need to add helper methods similar to `get_log_level_int()`

---

## Task 2.8 Complete: Migrate Observability/Tracing Consumers

### What Was Done

Migrated 4 files from `os.getenv("OTLP_ENDPOINT")` to `get_observability_settings()`:

1. **ktrdr/api/main.py** — API monitoring setup now uses `otel_settings.otlp_endpoint` and `otel_settings.console_output`
2. **ktrdr/cli/__init__.py** — CLI endpoint derivation compares against settings default to detect explicit user setting
3. **ktrdr/training/training_worker.py** — Training worker uses settings for OTLP endpoint and console output
4. **ktrdr/backtesting/backtest_worker.py** — Backtest worker uses settings (same pattern as training)

### Gotchas

**CLI endpoint derivation has special logic**: The CLI needs to detect "did user explicitly set OTLP endpoint?" vs "using default". Solution: compare `settings.otlp_endpoint` to known default `"http://jaeger:4317"`. If different, user explicitly set it.

**`enabled` flag controls endpoint**: When `otel_settings.enabled` is False, pass `None` to `setup_monitoring()` instead of the endpoint. This disables OTLP export.

**APP_VERSION and ENVIRONMENT are not observability settings**: These env vars in `ktrdr/monitoring/setup.py` are deployment metadata used in trace resources, not observability configuration. They were left as-is.

### Next Task Notes (2.9: Update Validation Module for M2 Settings)

- Add `APISettings`, `AuthSettings`, `LoggingSettings`, `ObservabilitySettings` to `BACKEND_SETTINGS` in `validation.py`
- Add `AuthSettings.jwt_secret` to `INSECURE_DEFAULTS` (detect insecure "insecure-dev-secret" in production)
