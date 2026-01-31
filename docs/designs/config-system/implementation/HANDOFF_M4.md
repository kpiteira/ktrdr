# M4 Handoff: Worker Settings

## Task 4.1 Complete: Create `WorkerSettings` Class

### Gotchas

**Port default is 5003 (not 5002 or 5004)**: The original bug had two different defaults — 5002 in `training_worker.py` and 5004 in `worker_registration.py`. The canonical default is now 5003, which matches the most common usage (first backtest worker port in docker-compose). All workers should use `get_worker_settings().port` as the single source of truth.

**No backend_url field**: Per design, `WorkerSettings` does NOT include a `backend_url` field. Workers should use `get_api_client_settings().base_url` from M5's `APIClientSettings` for backend connection. This ensures a single source of truth for the backend URL.

**worker_id defaults to None, not auto-generated**: Unlike the old code that generated worker IDs inline with `uuid.uuid4().hex[:8]`, the settings class defaults to `None`. The ID generation should happen at runtime in the worker startup code (Task 4.5 will handle this migration).

### Emergent Patterns

**Optional fields use `str | None` with `deprecated_field()`**: For fields like `endpoint_url` and `public_base_url` that are optional and auto-detected at runtime, use `str | None` type with `None` default.

### Next Task Notes (4.2: Align CheckpointSettings)

- `CheckpointSettings` already exists with `CHECKPOINT_*` prefix
- Need to change prefix to `KTRDR_CHECKPOINT_*`
- Add `deprecated_field()` for old names like `CHECKPOINT_EPOCH_INTERVAL` → `KTRDR_CHECKPOINT_EPOCH_INTERVAL`
- Keep all existing functionality

---
