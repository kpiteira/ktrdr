# M5 Status Observability Handoff

## Task 5.1 Complete: Update get_status() for Multi-Research Response

### Key Changes

The `get_status()` method now returns a comprehensive status with:
- `active_researches`: List of all active research operations with details
- `workers`: Worker utilization by type (busy/total)
- `budget`: Remaining budget and daily limit
- `capacity`: Active count vs limit

### Breaking Change: Response Structure

**Old format** (single research at top level):
```python
{
    "status": "active",
    "operation_id": "op_xxx",
    "phase": "training",
    "strategy_name": "...",
    "child_operation_id": "op_yyy",
}
```

**New format** (list of researches):
```python
{
    "status": "active",
    "active_researches": [
        {
            "operation_id": "op_xxx",
            "phase": "training",
            "strategy_name": "...",
            "child_operation_id": "op_yyy",
            "duration_seconds": 123,
        }
    ],
    "workers": {"training": {"busy": 1, "total": 2}, "backtesting": {"busy": 0, "total": 1}},
    "budget": {"remaining": 3.42, "daily_limit": 5.0},
    "capacity": {"active": 1, "limit": 6},
}
```

### Gotchas

- **Worker registry import**: Must import `get_worker_registry` from `ktrdr.api.endpoints.workers`, not from agent_service module (affects test mocking)
- **duration_seconds**: Calculated from `started_at` or `created_at` (fallback), requires timezone-aware datetime
- Tests must set `started_at` on mock operations for duration calculation

## Task 5.2 Complete: Update CLI Status Display

### Key Changes

Created new `ktrdr agent status` command that displays multi-research status:
- New `ktrdr/cli/commands/agent.py` module with `agent_app` Typer group
- Registered in `app.py` as a subcommand group
- Calls `/agent/status` API endpoint

### Output Format

```
Active researches: 2

  op_abc123  training     strategy: rsi_variant_7      (2m 15s)
  op_def456  designing    strategy: -                  (0m 30s)

Workers: training 2/3, backtest 1/2
Budget: $3.42 remaining today
Capacity: 2/6 researches
```

### Gotchas

- **Patch location for tests**: Patch `ktrdr.cli.client.AsyncCLIClient`, not the module where it's used (lazy imports inside function body)
- **Duration format**: Uses `format_duration(seconds)` helper → "Xm Ys" with zero-padded seconds
- **Strategy name**: Shows "-" when None (no strategy designed yet)

### Next Task Notes (5.3: Unit and Integration Tests)

- Unit tests already exist in `tests/unit/cli/test_agent_status.py`
- Need integration test that calls real API with test data
- Test existing patterns in `tests/unit/cli/commands/` for mock patterns
