# Handoff: M2 — Migrate Sync Commands

## Task 2.1 Complete: Migrate indicator_commands.py

### Migration Pattern Applied

Commands used async helpers wrapped in `asyncio.run()`. Simplified to sync:

```python
# Before
asyncio.run(_compute_indicator_async(...))

# After
with SyncCLIClient() as client:
    result = client.get("/indicators/")
```

### Gotchas

**health_check() replaces check_api_connection()**: The old `check_api_connection()` was async and required a separate import. Now use `client.health_check()` directly on the client instance.

**Error URL display**: Access `client.config.base_url` to show the URL in error messages (was `get_effective_api_url()` before).

**CLIClientError for client errors**: Import and catch `CLIClientError` to handle connection/timeout/API errors consistently.

### Next Task Notes

Task 2.2 (checkpoints_commands.py) follows the same pattern. Look for:
- `from ktrdr.cli.api_client import` → replace with `from ktrdr.cli.client import`
- `asyncio.run(_xxx_async(...))` → inline the logic in sync with SyncCLIClient
- `await check_api_connection()` → `client.health_check()`
- `await api_client.get/post(...)` → `client.get/post(...)`
