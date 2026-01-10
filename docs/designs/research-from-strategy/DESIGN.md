# Research from Strategy: Design

## Problem Statement

Currently, the research agent always starts from a natural language goal and goes through the full pipeline: design → train → backtest → assess → learn. When a user already has a valid v3 strategy, they must either manually run train + backtest (losing the assess/learn phases) or describe the strategy in natural language and hope the agent recreates it. There's no way to say "I have this strategy, run the full research pipeline on it."

## Goals

1. **Skip design phase** — When given an existing strategy, jump directly to training
2. **Full pipeline** — Still execute train → backtest → assess → create memory/learning
3. **Same UX** — Works with `--follow`, `--json`, same progress reporting
4. **Strategy validation** — Verify strategy is valid v3 before starting pipeline

## Non-Goals (Out of Scope)

1. **Strategy modification** — Agent doesn't modify the provided strategy
2. **Design feedback** — No design phase means no design critique/iteration
3. **Multi-strategy comparison** — Running multiple strategies in parallel for comparison
4. **Automatic strategy improvement** — Agent suggesting changes based on results (future feature)

## User Experience

### Research with Existing Strategy

```bash
# Goal-based research (current behavior)
$ ktrdr research "build a momentum strategy for AAPL"
Started research: op_abc123
  Phase: Design

# Strategy-based research (new behavior)
$ ktrdr research momentum
Started research: op_def456
  Phase: Training (design skipped - using existing strategy)

$ ktrdr research momentum --follow
Started research: op_def456
[Design] Skipped - using existing strategy 'momentum'
[Train] Epoch 50/100...
[Train] Complete! Model: momentum_20240601.pt
[Backtest] Bar 2500/5000...
[Backtest] Complete! Sharpe: 1.42
[Assess] Analyzing results...
[Assess] Performance: Good (Sharpe > 1.0, Max DD < 15%)
[Learn] Recording insights...
[Learn] Memory created: momentum performs well in trending markets
Research complete!
```

### Automatic Detection

The CLI detects whether the argument is a strategy name or a goal:

```bash
# Looks like a strategy name (exists in backend)
ktrdr research momentum                    # → Strategy mode

# Looks like a goal (natural language, doesn't exist as strategy)
ktrdr research "analyze AAPL volatility"   # → Goal mode

# Explicit disambiguation (if needed)
ktrdr research --strategy momentum         # → Strategy mode
ktrdr research --goal "momentum analysis"  # → Goal mode
```

### JSON Output

```bash
$ ktrdr research momentum --json
{"operation_id": "op_def456", "status": "started", "mode": "strategy", "strategy": "momentum"}

$ ktrdr research momentum --json --follow
{"event": "started", "operation_id": "op_def456", "mode": "strategy"}
{"event": "phase", "phase": "design", "status": "skipped", "reason": "using existing strategy"}
{"event": "phase", "phase": "training", "status": "started"}
{"event": "progress", "phase": "training", "percent": 50, "epoch": 50}
{"event": "phase", "phase": "training", "status": "completed", "model": "momentum_20240601.pt"}
{"event": "phase", "phase": "backtest", "status": "started"}
...
{"event": "completed", "operation_id": "op_def456", "result": {...}}
```

### Error Cases

```bash
# Strategy doesn't exist
$ ktrdr research nonexistent_strategy
Error: 'nonexistent_strategy' not found as strategy or recognized as research goal.
  Did you mean to run goal-based research? Use: ktrdr research --goal "nonexistent_strategy"

# Strategy is v2 (not supported)
$ ktrdr research old_v2_strategy
Error: Strategy 'old_v2_strategy' is v2 format. Research requires v3 strategies.
  Migrate with: ktrdr migrate ./strategies/old_v2_strategy.yaml

# Strategy validation fails
$ ktrdr research broken_strategy
Error: Strategy 'broken_strategy' has validation errors:
  - Missing required field: nn_inputs
  - Invalid indicator reference: rsi_20
```

## Key Decisions

### 1. Detection by Existence Check

**Choice:** Check if argument exists as a strategy name in backend. If yes, strategy mode. If no, goal mode.

**Alternatives considered:**
- Require explicit `--strategy` or `--goal` flags
- Heuristic detection (quotes, length, etc.)

**Rationale:** Most intuitive UX. Strategy names are short identifiers; goals are natural language. Explicit flags available for edge cases.

### 2. Strategy Mode Skips Only Design

**Choice:** Strategy mode skips design phase but runs full train → backtest → assess → learn pipeline.

**Alternatives considered:**
- Skip design and assess (just train + backtest)
- Make phases configurable

**Rationale:** The value of the agent is the full pipeline including assessment and learning. If user just wants train + backtest, they can run those commands directly.

### 3. V3 Strategies Only

**Choice:** Research-from-strategy requires v3 format.

**Alternatives considered:**
- Support v2 with auto-migration
- Support both formats

**Rationale:** V3 is the target format. Auto-migration adds complexity and may produce unexpected results. Better to require explicit migration.

### 4. Same Operation Type

**Choice:** Strategy-mode research creates same "research" operation type, with metadata indicating strategy mode.

**Alternatives considered:**
- New operation type "strategy_research"
- Separate tracking

**Rationale:** It's still research, just with a different starting point. Same progress tracking, same cancellation, same result format.

## Command Structure

```bash
ktrdr research <goal-or-strategy> [options]

Arguments:
  goal-or-strategy    Research goal (natural language) or strategy name

Options:
  --strategy NAME     Explicitly specify strategy (skip design)
  --goal TEXT         Explicitly specify goal (full pipeline)
  --start DATE        Training start date (required for strategy mode)
  --end DATE          Training end date (required for strategy mode)
  -f, --follow        Follow progress until completion
  --json              Machine-readable output
```

**Note:** `--start` and `--end` are required for strategy mode because the strategy defines *what* to train but not *when*. Goal mode doesn't require them because the design phase determines appropriate date ranges.

## Open Questions

1. ~~**Date range for goal mode**~~ — **Resolved:** Yes, allow `--start` and `--end` override for goal mode too.
2. **Budget handling** — Does strategy mode use same budget system as goal mode?
3. **Memory/learning scope** — Are learnings from strategy mode associated with that strategy specifically? (Note: Many existing strategies have no learnings — this feature helps populate them.)
4. ~~**Re-running with same strategy**~~ — **Resolved:** User's choice, but show a warning. The main value is creating memory/learnings for strategies that don't have any.

## Dependencies

- **CLI Restructure** — This feature builds on the restructured CLI (strategy names, operation runner)
- **Backend Agent Changes** — Agent needs entry point that accepts strategy name and skips design
- **Strategy Validation API** — `GET /api/v1/strategies/{name}/validate` to check before starting
