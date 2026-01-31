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

## Task 3.2 Complete: Create `IBHostServiceSettings` Class

### Gotchas

**Environment has `USE_IB_HOST_SERVICE=true`**: The development environment has this env var set. Tests for default values need to use `patch.dict(os.environ, {}, clear=True)` to ensure a clean slate. This is different from other settings tests that only need `clear=False`.

**Split base_url into host/port**: The existing `IbHostServiceSettings` uses `base_url` as a single field. The new `IBHostServiceSettings` splits this into `host` and `port` (like `IBSettings`) with `base_url` as a computed property. This is more flexible and consistent.

**Naming conflict with host_services.py**: Both `host_services.py` and `settings.py` now have `get_ib_host_service_settings()` functions. They return different classes (`IbHostServiceSettings` vs `IBHostServiceSettings`). The settings.py version is the new canonical one - Task 3.5 will migrate consumers and delete host_services.py.

### Emergent Patterns

**Computed properties for derived values**: Used `@computed_field` for `base_url` which is derived from `host` and `port`. This keeps the URL synchronized with configuration changes.

**Port helper methods from parent class**: Kept `get_health_url()` and `get_detailed_health_url()` for API compatibility with the old class.

### Next Task Notes (3.3: Create TrainingHostServiceSettings)

- Add `TrainingHostServiceSettings` class with `env_prefix="KTRDR_TRAINING_HOST_"`
- Similar structure to `IBHostServiceSettings` (host, port, enabled, timeout, etc.)
- Check if there's a deprecated env var for training host service enabled flag
- Default port is likely 5002 based on the pattern

---

## Task 3.3 Complete: Create `TrainingHostServiceSettings` Class

### Gotchas

**No existing TrainingHostServiceSettings class**: Unlike `IbHostServiceSettings` in `host_services.py`, there was no existing `TrainingHostServiceSettings` class to migrate from. The comment in `host_services.py` states "Training and backtesting now use distributed workers (WorkerRegistry). Workers register themselves on startup - no host service configuration needed." However, the milestone explicitly requires this class for consistency with the config system design.

**Deprecated env var is `USE_TRAINING_HOST_SERVICE`**: Found in multiple places across the codebase (especially in `specification/current/gpu-acceleration-implementation-plan.md` and `docs/training-host-service-fix-plan.md`). The `TRAINING_HOST_SERVICE_URL` env var was also used historically but is now replaced by separate host/port fields.

### Emergent Patterns

**Consistent structure with IBHostServiceSettings**: Used identical structure - same fields (host, port, enabled, timeout, health_check_interval, max_retries, retry_delay), same computed `base_url` property, same helper methods (`get_health_url()`, `get_detailed_health_url()`). The only difference is default port (5002 vs 5001) and env prefix.

### Next Task Notes (3.4: Migrate IB Consumers)

- Find all `IbConfig()` instantiations and replace with `get_ib_settings()`
- Find direct `os.getenv("IB_*")` calls and replace
- Delete `ktrdr/config/ib_config.py` after migration
- Check imports in `ktrdr/services/ib/*.py` and other IB-related files

---
