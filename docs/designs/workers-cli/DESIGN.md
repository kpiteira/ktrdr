# Workers CLI Command Design

## Overview

Add `ktrdr workers` command to display registered workers and their status from the CLI.

## Problem

Currently, checking worker status requires:
```bash
curl http://localhost:8000/api/v1/workers | jq
```

This is verbose and doesn't integrate with CLI conveniences (sandbox detection, `--json` flag).

## Solution

New CLI command: `ktrdr workers`

### Output (Default)

```
Workers: 5 registered

TYPE        STATUS     GPU    ENDPOINT                        OPERATION
training    available  MPS    host.docker.internal:5002       -
training    available  -      training-worker-1:5005          -
training    busy       -      training-worker-2:5006          op_abc123
backtesting available  -      backtest-worker-1:5003          -
backtesting available  -      backtest-worker-2:5004          -
```

### Output (--json)

```json
[
  {
    "worker_id": "training-worker-c24df1ef",
    "worker_type": "training",
    "status": "available",
    "capabilities": {"gpu": true, "gpu_type": "MPS"},
    "endpoint_url": "http://host.docker.internal:5002",
    "current_operation_id": null
  },
  ...
]
```

## Non-Goals

- Worker management (start/stop) - out of scope
- Filtering by type - can add later if needed
- Historical worker data - just current state

## API Dependency

Uses existing endpoint: `GET /api/v1/workers`

No backend changes required.
