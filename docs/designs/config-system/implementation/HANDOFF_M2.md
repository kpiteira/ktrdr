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
