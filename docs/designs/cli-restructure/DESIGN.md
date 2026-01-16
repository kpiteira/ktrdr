# CLI Restructure: Design

## Problem Statement

The KTRDR CLI has grown organically with inconsistencies that hurt usability: duplicate entry points (two backtest commands), object-oriented command structure that doesn't match user mental models ("I want to train" vs "I want to work with models"), CLI-side strategy parsing that duplicates backend logic, slow startup (~1s for `--help`), and file paths passed to a remote backend that can't read them. The CLI should be a thin, fast UX layer over the API—not a local processing tool.

## Goals

1. **Workflow-oriented commands** — Top-level verbs (`train`, `backtest`, `research`) that match how users think
2. **Fast startup** — `ktrdr --help` in <100ms (currently ~1000ms)
3. **Strategy names, not paths** — CLI passes names; backend resolves to files
4. **Fire-and-follow pattern** — Default: start operation, return ID. Optional `--follow` to poll
5. **Machine-readable output** — Global `--json` flag for scripting/automation
6. **Unified operation handling** — Same code path for train, backtest, research
7. **Clean break** — Remove deprecated/duplicate commands, update all documentation

## Constraints: Preserving Existing Experience

**This restructure changes command STRUCTURE, not command BEHAVIOR.**

The following must be preserved exactly from existing commands:

1. **All command-line options** — If `ktrdr models train` has `--verbose`, `--dry-run`, `--models-dir`, then `ktrdr train` must have them too (unless explicitly deprecated in "Removed Commands")
2. **Ctrl+C behavior** — Operations started with `--follow` must cancel on Ctrl+C (not just detach)
3. **Results display** — Training shows epochs/loss/model path on completion; backtest shows sharpe/drawdown/trades
4. **Error messages** — Same error handling and user-facing messages
5. **Telemetry** — `@trace_cli_command` decorators preserved
6. **Option shorthands** — If `-c` was shorthand for `--capital`, keep it

**Implementation note:** When implementing new commands, the implementer MUST:
1. Read the existing command being replaced
2. Document all options, behaviors, and outputs from the existing command
3. Implement the new command with ALL existing functionality
4. Only add new functionality (like fire-and-forget mode) on top

**The UX examples in this document show the EXPECTED output. Implementations must match.**

## Non-Goals (Out of Scope)

1. **`research <strategy>` feature** — Skipping design phase requires backend agent changes (separate design)
2. **Desktop notifications** — Nice-to-have, can add later without design changes
3. **Shell completion** — Can add incrementally after restructure
4. **Interactive wizard mode** — Future enhancement

## User Experience

### Training a Model

```bash
# Start training, get operation ID immediately
$ ktrdr train momentum --start 2024-01-01 --end 2024-06-01
Started training: op_abc123
  Track progress: ktrdr status op_abc123
  Follow live:    ktrdr follow op_abc123

# Or follow progress inline
$ ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --follow
Started training: op_abc123
[████████████████░░░░] 80% - Epoch 80/100
...
Training complete! Model saved: momentum_20240601.pt
```

### Running a Backtest

```bash
$ ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
Started backtest: op_def456
  Track progress: ktrdr status op_def456

$ ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01 -f
Started backtest: op_def456
[████████████████████] 100% - Bar 5000/5000
Backtest complete! Sharpe: 1.42, Max DD: -12.3%
```

### Research Agent

The research command (`ktrdr research`) preserves the existing agent UX which works well:

```bash
# Fire-and-forget (default)
$ ktrdr research "build a momentum strategy for AAPL"
Research cycle started!
  Operation ID: op_ghi789
  Model: claude-opus-4-20250514
Use ktrdr status to monitor progress.

# Follow mode (existing nested progress bar UX - unchanged)
$ ktrdr research "analyze volatility patterns" --follow
Research cycle started!
  Operation ID: op_ghi789
[Research Cycle] Design: Analyzing requirements  [████████░░] 40%  0:02:30
   └─ Training: Epoch 45/100                     [████░░░░░░] 45%
```

**Note:** The `--follow` mode preserves the existing nested progress display with parent/child operations, Ctrl+C handling, and completion summaries. This UX is not changing.

### Monitoring Operations

```bash
# System dashboard
$ ktrdr status
Operations: 2 running, 5 completed today
Workers: 3 available (1 GPU, 2 CPU)
IB: Connected (paper account)

# Specific operation
$ ktrdr status op_abc123
Operation: op_abc123
Type: training
Status: running (45%)
Started: 2024-06-01 10:30:00
Strategy: momentum

# Follow any operation
$ ktrdr follow op_abc123
[████████░░░░░░░░░░░░] 45% - Epoch 45/100
```

### Listing and Inspection

```bash
$ ktrdr list strategies
NAME                  VERSION  SYMBOLS      TIMEFRAMES
momentum              3.0      AAPL,MSFT    1h
mean_reversion        3.0      EURUSD       1h,4h
volatility_breakout   3.0      SPY          1d

$ ktrdr list models
NAME                  STRATEGY      CREATED      PERFORMANCE
momentum_20240601     momentum      2024-06-01   Sharpe: 1.42

$ ktrdr ops
ID           TYPE       STATUS     PROGRESS  STARTED
op_abc123    training   running    45%       10:30:00
op_def456    backtest   completed  100%      10:15:00

$ ktrdr show AAPL 1h
[Table of recent OHLCV data]

$ ktrdr show features momentum
[Table of resolved NN input features for strategy]
```

### Validation and Migration

```bash
# Validate deployed strategy (via API)
$ ktrdr validate momentum
Strategy 'momentum' is valid (v3 format)
Resolved features: 12

# Validate local file (for development)
$ ktrdr validate ./my_new_strategy.yaml
Strategy is valid (v3 format)
Resolved features: 8

# Migrate local v2 to v3
$ ktrdr migrate ./old_strategy.yaml
Migrated: ./old_strategy.yaml -> ./old_strategy_v3.yaml
```

### Machine-Readable Output

```bash
# Single JSON response
$ ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --json
{"operation_id": "op_abc123", "status": "started", "type": "training"}

# Streaming NDJSON with --follow
$ ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --json --follow
{"event": "started", "operation_id": "op_abc123", "timestamp": "2024-06-01T10:30:00Z"}
{"event": "progress", "operation_id": "op_abc123", "percent": 10, "epoch": 10, "total_epochs": 100}
{"event": "progress", "operation_id": "op_abc123", "percent": 20, "epoch": 20, "total_epochs": 100}
{"event": "completed", "operation_id": "op_abc123", "result": {"model_path": "models/momentum_20240601.pt"}}

# List operations as JSON
$ ktrdr ops --json
[{"id": "op_abc123", "type": "training", "status": "running", "progress": 0.45}]
```

## Key Decisions

### 1. Workflow-Oriented Commands (Verbs First)

**Choice:** Top-level verbs like `ktrdr train`, `ktrdr backtest`, `ktrdr research`

**Alternatives considered:**
- Object-oriented: `ktrdr models train`, `ktrdr strategies backtest`
- Task-based groups: `ktrdr develop`, `ktrdr monitor`

**Rationale:** Users think in terms of what they want to do ("I want to train"), not what objects they're manipulating. Verbs-first is faster to type and matches mental models. Discoverability is maintained via `--help` with grouped command listings.

### 2. Fire-and-Follow Pattern

**Choice:** Default behavior starts operation and returns immediately with operation ID. Use `--follow` or `-f` to poll until completion.

**Alternatives considered:**
- Always poll (current behavior)
- Separate `start` and `watch` commands

**Rationale:** Matches the agent command pattern (which already works this way). Enables scripting, parallel operations, and "fire and forget" workflows. Users who want to watch can add `--follow`.

### 3. Strategy Names, Not Paths

**Choice:** CLI accepts strategy names (e.g., `momentum`). Backend resolves to file path.

**Alternatives considered:**
- File paths (current behavior)
- Both names and paths with detection

**Rationale:** CLI is an API client; it cannot assume the backend's filesystem matches the local filesystem. Names are portable across environments. Backend already knows where strategies live.

**Exception:** `validate` and `migrate` support local paths (prefixed with `./` or `/`) for development workflows before strategies are deployed.

### 4. Unified Operation Executor

**Choice:** Single code path handles all long-running operations (train, backtest, research).

**Alternatives considered:**
- Separate implementations per operation type

**Rationale:** Reduces code duplication, ensures consistent UX (progress display, cancellation, `--json` output). The existing `AsyncCLIClient.execute_operation()` pattern can be extended.

### 5. Hard Deprecation (No Aliases)

**Choice:** Old commands are removed entirely, not aliased with warnings.

**Alternatives considered:**
- Aliases with deprecation warnings
- Version flag for old behavior

**Rationale:** Clean break is simpler to maintain. Aliases create confusion about "which is right." Documentation update task ensures all references are fixed.

### 6. Lazy Imports for Startup Performance

**Choice:** Heavy dependencies (pandas, OpenTelemetry) are imported only when needed, not at module load time.

**Alternatives considered:**
- Keeping eager imports
- Separate "lite" CLI entry point

**Rationale:** `ktrdr --help` should be instant. Users pay import cost only for commands that need heavy dependencies. This is standard practice for responsive CLIs.

## Command Structure

```
ktrdr
├── train <strategy> [-f/--follow] [--json]      # Train model
│     --start DATE (required)
│     --end DATE (required)
│     --validation-split FLOAT (default: 0.2)
│
├── backtest <strategy> [-f/--follow] [--json]   # Run backtest
│     --start DATE (required)
│     --end DATE (required)
│     --capital FLOAT (default: 100000)
│
├── research <goal> [-f/--follow] [--json]       # Agent pipeline
│
├── validate <name|./path>                        # Validate strategy
│
├── show <symbol> [timeframe]                     # Show market data
├── show features <strategy>                      # Show strategy features
│
├── status [op-id]                               # Dashboard or op status
├── follow <op-id> [--json]                      # Follow/tail operation
├── ops [--json]                                 # List operations
├── cancel <op-id>                               # Cancel any operation
│
├── list strategies [--json]                     # List strategies
├── list models [--json]                         # List models
├── list checkpoints [--json]                    # List checkpoints
│
├── checkpoint restore <id>                      # Restore checkpoint
├── migrate <./path>                             # v2 -> v3 migration
│
├── sandbox ...                                  # (subgroup, unchanged)
├── ib ...                                       # (subgroup, unchanged)
└── deploy ...                                   # (subgroup, unchanged)

Global flags (all commands):
  --json           Machine-readable JSON output
  --verbose/-v     Debug output, show startup logs
  --url/-u URL     Target API URL
  --port/-p PORT   Target API port on localhost
```

## Removed Commands

| Old Command | Replacement |
|-------------|-------------|
| `ktrdr models train` | `ktrdr train` |
| `ktrdr backtest run` | `ktrdr backtest` |
| `ktrdr strategies backtest` | `ktrdr backtest` |
| `ktrdr strategies validate` | `ktrdr validate` |
| `ktrdr strategies features` | `ktrdr show features` |
| `ktrdr strategies list` | `ktrdr list strategies` |
| `ktrdr strategies migrate` | `ktrdr migrate` |
| `ktrdr operations list` | `ktrdr ops` |
| `ktrdr operations status` | `ktrdr status` |
| `ktrdr operations cancel` | `ktrdr cancel` |
| `ktrdr agent trigger` | `ktrdr research` |
| `ktrdr agent status` | `ktrdr status` |
| `ktrdr agent cancel` | `ktrdr cancel` |
| `ktrdr indicators compute` | Removed (unused) |
| `ktrdr fuzzy compute` | Removed (unused) |
| `ktrdr dummy *` | Removed (demo only) |

## Open Questions

1. **Strategy API v3 support** — `GET /strategies/` exists but is designed for v1/v2 format (uses `data.symbols`). Needs update to support v3 `training_data.symbols` format.
2. **MCP alignment** — MCP tools should use strategy names (not paths), consistent with CLI and API. Verify and update if needed.
3. **Checkpoint restore UX** — What does restoring a checkpoint actually do? Need to understand before finalizing command.

## Dependencies

- **Backend: Strategy listing API** — `GET /api/v1/strategies` to list available strategies
- **Backend: Strategy resolution** — Training/backtest endpoints accept strategy name, resolve internally
- **Documentation audit** — Find all CLI references in prompts, slash commands, docs
