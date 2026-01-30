# M1 Handoff: Database Settings

## Task 1.1 Complete: Create `deprecated_field()` Helper and `DatabaseSettings` Class

### Gotchas

**`deprecated_field()` uses TypeVar for proper typing**: The function returns `FieldInfo` at runtime but uses `TypeVar("T")` so mypy understands the return type matches the default's type. The Pydantic mypy plugin recognizes `Field()` and handles this pattern correctly. No type ignores needed on the function itself.

**`@computed_field` with `@property` requires type ignore**: Mypy doesn't support decorators stacked on top of `@property`. Use `@computed_field  # type: ignore[prop-decorator]` when you need computed fields that serialize.

**`validation_alias` completely overrides `env_prefix`**: This is the reason `deprecated_field()` exists. When you set `validation_alias` on a field, Pydantic ignores `env_prefix` for that field entirely. The helper enforces that you pass the full env var name (e.g., `KTRDR_DB_HOST`) not just the suffix.

### Emergent Patterns

**AliasChoices order matters**: The first name in `AliasChoices` takes precedence. `deprecated_field()` lists the new name first so `KTRDR_DB_HOST` wins when both `KTRDR_DB_HOST` and `DB_HOST` are set.

### Next Task Notes (1.2: Validation Module)

- Import `DatabaseSettings` via `from ktrdr.config.settings import DatabaseSettings`
- `INSECURE_DEFAULTS` dict should include `"KTRDR_DB_PASSWORD": "localdev"`
- Validation module reads `KTRDR_ENV` via `os.getenv()` (not from a Settings class)

## Task 1.2 Complete: Create Validation Module

### Gotchas

**Lazy initialization of BACKEND_SETTINGS/WORKER_SETTINGS lists**: The lists are initialized lazily via `_init_settings_lists()` to avoid circular imports. Call this function before accessing the lists, or call `validate_all()` which does it automatically.

**Use `details` dict for error context**: The `ConfigurationError` class stores structured data in `details`, not in the main message. Tests should check `exc.details.get("insecure_settings", [])` for the list of insecure env vars, not `str(exc)`.

**Pydantic validation errors need conversion**: When `settings_class()` raises `PydanticValidationError`, extract error details from `e.errors()` and format them into user-friendly messages. The raw error format is not readable.

### Emergent Patterns

**Warning format matches ARCHITECTURE.md**: The boxed warning format with `========` borders is specified in ARCHITECTURE.md. Use `logger.warning()` (not `print()`) for the warning output.

**Validation errors collected before raising**: All settings classes are validated and errors are collected into a single list before raising `ConfigurationError`. This ensures users see all issues at once.

### Next Task Notes (1.3: Deprecation Module)

- Import pattern: `from ktrdr.config.validation import validate_all, detect_insecure_defaults`
- `DEPRECATED_NAMES` dict maps old → new names: `{"DB_HOST": "KTRDR_DB_HOST", ...}`
- Use `warnings.warn()` with `DeprecationWarning` category
- Check `os.environ` directly for deprecated names (fast lookup)

## Task 1.3 Complete: Create Deprecation Module

### Gotchas

**`warnings.warn()` stacklevel matters**: Use `stacklevel=2` so the warning points to the caller of `warn_deprecated_env_vars()`, not the function itself. This makes the warning more useful for users.

**Test with `warnings.catch_warnings(record=True)`**: When testing warning emission, use this context manager with `warnings.simplefilter("always")` to capture all warnings. Filter the captured list for `DeprecationWarning` category since other warnings may be emitted.

### Emergent Patterns

**Dict iteration order is stable**: Python 3.7+ guarantees dict iteration order matches insertion order. The returned list of deprecated vars will always be in the same order as `DEPRECATED_NAMES` keys.

### Next Task Notes (1.4: Update `__init__.py` Public API)

- Export `warn_deprecated_env_vars` and `DEPRECATED_NAMES` from `ktrdr.config`
- Import from: `from ktrdr.config.deprecation import warn_deprecated_env_vars, DEPRECATED_NAMES`
- Keep existing exports for backward compatibility

## Task 1.4 Complete: Update `__init__.py` Public API

### Gotchas

**Import order matters for circular dependencies**: The deprecation module has no internal dependencies, so it can be imported early. The validation module imports from settings, so keep that import after settings.

### Emergent Patterns

**Group exports by milestone/feature**: The `__all__` list is organized with comments grouping related exports (# New config system (M1), # Validation (M1.2), # Deprecation (M1.3)).

### Next Task Notes (1.5: Migrate database.py)

- Replace `os.getenv("DB_*")` calls with `get_db_settings().field`
- Use `get_db_settings().url` for async connection string
- Use `get_db_settings().sync_url` for sync connection string
- Import: `from ktrdr.config import get_db_settings`

## Task 1.5 Complete: Migrate database.py to Use get_db_settings()

### Gotchas

**Reset `_engine` global when testing**: The database module uses global `_engine` and `_session_factory` for lazy initialization. In tests, reset these to `None` before each test to ensure clean state.

**Use settings.url directly**: The `get_database_url()` function is now a thin wrapper around `get_db_settings().url`. Could be removed in a future cleanup, but kept for backward compatibility.

### Emergent Patterns

**Single settings call for multiple fields**: In `get_engine()`, call `settings = get_db_settings()` once and access multiple fields (url, echo, host, port, name) from the cached instance. This is more efficient than calling `get_db_settings()` multiple times.

### Next Task Notes (1.6: Add Startup Validation to main.py)

- Import: `from ktrdr.config import warn_deprecated_env_vars, validate_all`
- Call `warn_deprecated_env_vars()` first (emit deprecation warnings)
- Call `validate_all("backend")` second (fail fast if invalid)
- These must run BEFORE `app = FastAPI(...)` creation

## Task 1.6 Complete: Add Startup Validation to main.py

### Gotchas

**Import order matters for ruff**: When adding new imports, keep them alphabetically sorted within the `ktrdr.*` block. `ktrdr.config` comes before `ktrdr.errors`.

**Validation runs at module import**: The `warn_deprecated_env_vars()` and `validate_all("backend")` calls run when main.py is imported, not when `create_application()` is called. This is intentional - fail fast before any other initialization.

### Emergent Patterns

**Section comment for visibility**: Added a clear section header `# Startup Validation (M1: Config System)` with explanation of the two-step process. This makes the validation calls visible and documents their purpose.

### Next Task Notes (1.7: Write Unit Tests)

- Most unit tests were written alongside each task (TDD)
- Task 1.7 is mainly verification that all tests from 1.1-1.4 are implemented
- Run `make test-unit` to verify all pass
