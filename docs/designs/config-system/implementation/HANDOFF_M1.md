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
