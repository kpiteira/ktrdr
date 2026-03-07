# Handoff: M3 Execution Realism

## Task 3.1 Complete: BacktestEngine Next-Bar Execution

Changed the main simulation loop in `engine.py` to use `pending_signal`/`pending_metadata` pattern:
1. Execute any pending signal from previous bar at THIS bar's open price
2. Decide based on current bar's features (at close)
3. Store non-HOLD decisions as pending for next bar

**Implementation notes:**
- Mark-to-market tracking still uses `close_price` (unchanged)
- `pending_signal` and `pending_metadata` are local variables in `run()`, reset to None after execution
- Last bar with a pending signal: pending is simply dropped (force-close handles end-of-backtest)
- No mode branching — same execution path for regression and classification

**Gotchas:**
- Existing `test_engine_rewrite.py` tests all pass unchanged because they use constant prices (open=close=1.1) or don't assert execution prices
- Pre-existing uncommitted changes in `memory/hypotheses.yaml` and `test_prompts_regression.py` — not part of M3

**Next task notes:**
- Task 3.3: slippage defaults in `backtest_worker.py` and API endpoint

## Task 3.2 Complete: Update Affected Tests

No existing tests broke from next-bar execution because they either:
- Used constant prices (open=close=1.1), making same-bar vs next-bar indistinguishable
- Tested components directly (PositionManager, DecisionFunction), not through the engine loop

**Changes made:**
- `test_engine_rewrite.py` `TestSimulationLoopTradeExecution` fixture: updated to use distinct open/close prices
- Added `test_trade_uses_next_bar_open_price` — verifies execution at bar 51's open, not bar 50's close
- Added `test_trade_timestamp_is_next_bar` — verifies timestamp matches execution bar

**Hand-verified:** Both new tests confirmed by computing expected values from fixture data:
- Bar 51 open = 1.1000 + 51*0.0001 = 1.1051 (not bar 50 close = 1.1050 + 50*0.0001 = 1.1100)
- Timestamp = 2024-01-01 + 51h (not +50h)

## Task 3.3 Complete: Slippage Defaults Standardization

Standardized slippage default from inconsistent values (0.0, 0.001) to 0.0005 (0.05%) across all entry points:
- `backtest_worker.py` BacktestStartRequest: 0.0 → 0.0005
- `backtest_worker.py` resume fallback: 0.0 → 0.0005
- `api/models/backtesting.py` BacktestStartRequest: 0.001 → 0.0005
- `backtesting_service.py` run_backtest + run_backtest_on_worker: 0.001 → 0.0005
- `backtesting_service.py` context fallback: 0.001 → 0.0005
- `cli/commands/backtest.py` typer option: 0.001 → 0.0005
- `cli/operation_adapters.py`: 0.001 → 0.0005
- `engine.py` BacktestConfig was already correct (0.0005)

## Task 3.4 Complete: E2E Validation

**E2E test:** `backtest/execution-realism` — PASSED (5 steps)

**Key evidence:**
- Slippage default 0.0005 confirmed through full API→worker→engine pipeline
- 97 trades produced, total_return=-7630.29, execution_time=2.2s
- Commission (0.001) and slippage (0.0005) correctly distinct

**Gotchas:**
- Sandbox Jaeger port: `.env.sandbox` needs `KTRDR_JAEGER_OTLP_GRPC_PORT` (compose uses this, not `KTRDR_OTLP_GRPC_PORT`)
- Sandbox agent ports: need `KTRDR_DESIGN_AGENT_PORT=5061` and `KTRDR_ASSESSMENT_AGENT_PORT=5062` to avoid conflicts
- Operation metadata stores slippage at `metadata.parameters.slippage` (not `metadata.slippage`)
