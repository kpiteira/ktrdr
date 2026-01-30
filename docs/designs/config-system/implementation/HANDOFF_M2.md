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
