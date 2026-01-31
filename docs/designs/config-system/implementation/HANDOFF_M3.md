# M3 Handoff: IB & Host Services Settings

## Task 3.1 Complete: Create `IBSettings` Class

### Gotchas

**Static `_chunk_days` dict vs env var**: The `chunk_days` dictionary from `IbConfig` is IB-specific knowledge (historical data request limits per bar size). It's defined as a class attribute `_chunk_days` (with underscore) rather than a Pydantic field. This keeps it static and avoids exposing it as an env var.

**Port validation uses `ge`/`le` not validators**: Used `deprecated_field(..., ge=1, le=65535)` for port validation rather than a custom `@field_validator`. Pydantic's built-in constraints are cleaner and sufficient.

**Old `IB_RETRY_DELAY` → new `KTRDR_IB_RETRY_BASE_DELAY`**: The old env var was `IB_RETRY_DELAY` (without `_BASE_`), but the new canonical name includes `_BASE_` for clarity. The deprecated_field mapping handles this.

### Emergent Patterns

**Keep helper methods on settings class**: Methods like `is_paper_trading()`, `is_live_trading()`, `get_chunk_size()`, `get_connection_config()`, and `to_dict()` are ported to `IBSettings`. This keeps the same API for consumers.

**Use constraints not validators for simple bounds**: For fields with simple numeric bounds (gt=0, ge=1, le=65535), use Pydantic's `Field()` constraints passed through `deprecated_field()`. Only use `@field_validator` for complex validation logic.

### Next Task Notes (3.2: Create IBHostServiceSettings)

- Add `IBHostServiceSettings` class with `env_prefix="KTRDR_IB_HOST_"`
- Check `ktrdr/config/host_services.py` for the existing `HostServiceSettings` fields
- Key field: `enabled` with deprecated name `USE_IB_HOST_SERVICE`
- Include: host, port, enabled, timeout

---
