# Milestone 2 Handoff

Running notes for M2 CLI restructure implementation.

---

## Task 2.1 Complete: Implement Backtest Command

### Gotchas
- **BacktestingOperationAdapter still requires symbol/timeframe:** Unlike TrainingOperationAdapter (which was updated in M1 Task 1.7 to make symbols/timeframes optional), `BacktestingOperationAdapter` still requires explicit `symbol` and `timeframe` parameters. The implementation uses hardcoded placeholders (`"AAPL"`, `"1h"`) with TODO comments. This should be addressed when the backend supports reading symbol/timeframe from strategy config for backtests.

### Emergent Patterns
- **Follow train.py pattern exactly:** The backtest command closely mirrors train.py structure - state from `ctx.obj`, OperationRunner instantiation, adapter creation, `runner.start(adapter, follow=follow)`, and error handling with `print_error()` followed by `raise typer.Exit(1) from None`.
- **Capital option has `-c` shorthand:** Preserved from old command (`--capital`, `-c`).
- **Test pattern for shorthand options:** Use `mock_adapter.call_args[1]` to verify parameter values when testing shorthand flags like `-c`.

### Next Task Notes
- Task 2.2 (research command) has different async pattern - uses `asyncio.run()` internally rather than OperationRunner since agent trigger has special nested progress UX.
- The command should be wired up in Task 2.8 along with all other M2 commands.
