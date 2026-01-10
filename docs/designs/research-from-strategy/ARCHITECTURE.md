# Research from Strategy: Architecture

## Overview

This feature extends the research command to accept a strategy name instead of a goal. The CLI detects mode automatically, and the backend agent skips the design phase when given an existing strategy.

## Changes Required

### CLI (ktrdr/cli/commands/research.py)

- Add strategy detection: check if argument exists as strategy via `GET /strategies/{name}`
- Add `--strategy` and `--goal` flags for explicit mode selection
- Add `--start` and `--end` date flags (required for strategy mode, optional override for goal mode)
- Validate strategy is v3 format before starting
- Reuse existing `_monitor_agent_cycle()` for follow mode — no changes to UX

### Backend Agent

- Modify research entry point to accept `mode: "strategy" | "goal"`
- When `mode: "strategy"`:
  - Load strategy by name
  - Skip design phase (emit progress: `phase=design, status=skipped`)
  - Proceed directly to training phase
- Rest of pipeline unchanged: train → backtest → assess → learn

### Backend API

- Modify `POST /agent/trigger` to accept:
  ```json
  {
    "mode": "strategy",
    "strategy_name": "momentum",
    "start_date": "2024-01-01",
    "end_date": "2024-06-01"
  }
  ```
- Existing goal mode unchanged:
  ```json
  {
    "mode": "goal",
    "goal": "build a momentum strategy"
  }
  ```

## Detection Logic

```
Input: "momentum"
  → GET /strategies/momentum
  → 200 OK → mode = strategy
  → 404 Not Found → mode = goal
```

Explicit flags (`--strategy`, `--goal`) override detection.

## Dependencies

- Requires CLI Restructure to be complete (strategy names, operation runner pattern)
- Backend agent changes are isolated to entry point and phase orchestration
