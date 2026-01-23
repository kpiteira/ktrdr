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

### Next Task Notes (5.2: CLI Status Display)

- Parse the new `active_researches` list
- Format duration using `format_duration(seconds)` helper
- Workers: show "training X/Y, backtest X/Y"
- Budget: show "$X.XX remaining today"
- Capacity: show "X/Y researches"
