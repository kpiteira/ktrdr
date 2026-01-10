# CLI Restructure: Validation

**Date:** 2025-01-10
**Documents Validated:**
- [DESIGN.md](DESIGN.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)

## Validation Summary

**Scenarios Validated:** 6 core scenarios traced
**Critical Gaps Found:** 0 (all resolved via clarification)
**Backend API:** Verified ready

## Scenarios Validated

### Happy Paths
1. **Train with follow**: `ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --follow` — progress bar, completion message
2. **Fire-and-forget backtest**: `ktrdr backtest momentum ...` without `--follow` — operation ID returned immediately
3. **Research cycle**: `ktrdr research "build a momentum strategy" --follow` — nested progress with child operations

### Error Paths
4. **Strategy not found**: `ktrdr train nonexistent ...` — clear error message
5. **Backend unavailable**: Any command when backend is down — helpful error (not stack trace)

### Edge Cases
6. **Validate local vs deployed**: `ktrdr validate ./my_strategy.yaml` (local) vs `ktrdr validate momentum` (API)

## Key Decisions

1. **Local validation is an intentional exception**
   - Context: Design says "CLI should be thin API client" but also supports `validate ./path`
   - Decision: This is explicitly documented as an exception for development workflows
   - Trade-off: Small amount of validation logic in CLI, but enables pre-deployment testing

2. **Strategy resolution uses convention**
   - Context: Backend needs to find strategies by name
   - Decision: `{shared_data}/strategies/{name}.yaml`
   - Trade-off: Simple and predictable; matches existing directory structure

3. **Existing UX preserved with --follow**
   - Context: Current training/backtest/agent progress display works well
   - Decision: Keep it exactly as-is; `--follow` enables the existing UX
   - Trade-off: None — this is purely additive (fire-and-forget becomes the default)

4. **Operation runner method named `start()`**
   - Context: Interface design for unified operation handling
   - Decision: Simple name `start()` with `follow` parameter, not `start_and_follow()`

## Backend API Verification

Verified against live API at `http://localhost:8001/api/v1/docs`:

| Endpoint | Method | CLI Command | Status |
|----------|--------|-------------|--------|
| `/api/v1/trainings/start` | POST | `train` | Ready — accepts `strategy_name` |
| `/api/v1/backtests/start` | POST | `backtest` | Ready — accepts `strategy_name` |
| `/api/v1/agent/trigger` | POST | `research` | Ready — accepts `brief` |
| `/api/v1/strategies/` | GET | `list strategies` | Exists — verify v3 format |
| `/api/v1/strategies/{name}` | GET | `show features` | Exists — verify v3 format |
| `/api/v1/strategies/validate/{name}` | POST | `validate <name>` | Exists |
| `/api/v1/operations` | GET | `ops` | Ready |
| `/api/v1/operations/{id}` | GET | `status`, `follow` | Ready |
| `/api/v1/operations/{id}` | DELETE | `cancel` | Ready |
| `/api/v1/models` | GET | `list models` | Ready |
| `/api/v1/checkpoints` | GET | `list checkpoints` | Ready |

**To verify during implementation:** `/api/v1/strategies/` v3 format support

## Implementation Note

**This is a CLI restructure, not a rewrite.**

The current UX for training, backtest, and agent progress display is good and should be preserved exactly as-is when `--follow` is specified. The changes are:

1. Making progress display opt-in (`--follow`) rather than default
2. Introducing fire-and-forget as the new default
3. Reorganizing commands from object-oriented (`ktrdr models train`) to workflow-oriented (`ktrdr train`)

## Interface Contracts

### CLI State

```python
@dataclass
class CLIState:
    json_mode: bool = False
    verbose: bool = False
    api_url: str = "http://localhost:8000"
```

### Operation Runner

```python
class OperationRunner:
    """Unified start/follow for all operation types."""

    def start(
        self,
        operation_type: Literal["training", "backtest", "research"],
        params: dict,
        follow: bool,
        json_mode: bool,
    ) -> None:
        """
        Start operation via API.
        If follow=False: print operation ID and return.
        If follow=True: use existing polling/progress UX (unchanged).
        If json_mode=True: output JSON/NDJSON instead of human text.
        """
```

### Command Signatures

```
train <strategy> --start DATE --end DATE [--validation-split FLOAT] [-f/--follow] [--json]
backtest <strategy> --start DATE --end DATE [--capital FLOAT] [-f/--follow] [--json]
research <goal> [-f/--follow] [--json]
validate <name|./path>
status [op-id]
follow <op-id> [--json]
ops [--json]
cancel <op-id>
list strategies|models|checkpoints [--json]
show <symbol> [timeframe]
show features <strategy>
migrate <./path>
```

## Milestone Structure

### Milestone 1: Core Infrastructure + One Command

**User Story:** User can run `ktrdr train momentum --start 2024-01-01 --end 2024-06-01` and see an operation start.

**Scope:**
- `app.py`: New entry point with global flags (`--json`, `--verbose`)
- `state.py`: CLIState dataclass
- `output.py`: Human/JSON output helpers
- `operation_runner.py`: Start operation, poll with `--follow`
- `commands/train.py`: First command implementation

**E2E Test:**
```
Given: Backend running, strategy "momentum" exists
When: User runs `ktrdr train momentum --start 2024-01-01 --end 2024-06-01`
Then: Operation ID printed, operation visible in backend
```

### Milestone 2: Remaining Operation Commands

**User Story:** User can run all operation-based commands (`backtest`, `research`, `status`, `follow`, `ops`, `cancel`).

**Scope:**
- `commands/backtest.py`
- `commands/research.py` (reuses existing agent monitoring code)
- `commands/status.py`
- `commands/follow.py`
- `commands/ops.py`
- `commands/cancel.py`

**E2E Test:**
```
Given: Running operation from Milestone 1
When: User runs `ktrdr follow <op-id>`
Then: Progress bar displays, updates until completion
```

### Milestone 3: Information Commands

**User Story:** User can list strategies, models, checkpoints, and show data.

**Scope:**
- `commands/list_cmd.py`
- `commands/show.py`
- `commands/validate.py`
- `commands/migrate.py`

**E2E Test:**
```
Given: Strategies exist in backend
When: User runs `ktrdr list strategies`
Then: Table of strategies with version, symbols, timeframes
```

### Milestone 4: Lazy Imports + Performance

**User Story:** `ktrdr --help` responds in <100ms.

**Scope:**
- Refactor imports in `app.py` to be lazy
- Move telemetry init to first command execution
- Profile and optimize import chain

**E2E Test:**
```
Given: Cold start (no cached bytecode)
When: User runs `ktrdr --help`
Then: Response in <100ms (measured)
```

**Baseline:** Currently ~1000ms

### Milestone 5: Cleanup + Documentation

**User Story:** Old commands removed, all documentation updated.

**Scope:**
- Remove old `commands.py` and object-oriented command structure
- Update entry point in `pyproject.toml`
- Audit and update: CLI references in prompts, slash commands, docs
- Update CLAUDE.md examples if needed

**E2E Test:**
```
Given: User familiar with old CLI
When: User runs `ktrdr models train`
Then: Command not found (clean error, not crash)
```
