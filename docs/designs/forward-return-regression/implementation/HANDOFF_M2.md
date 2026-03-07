# Handoff: M2 Assessment + Agent Integration

## Task 2.1 Complete: MetricsCollector Regression Metrics

Added `collect_regression_metrics(y_true, y_pred)` to `MetricsCollector` returning: mse, mae, r_squared, directional_accuracy, mean_predicted_return, std_predicted_return.

**Implementation notes:**
- Method accepts both numpy arrays and torch tensors (auto-converts)
- R-squared handles SS_tot=0 edge case (constant true values) by returning 0.0
- Uses sklearn `mean_squared_error` and `mean_absolute_error` for MSE/MAE
- Directional accuracy uses `np.sign()` comparison

**Gotchas:**
- torch not available in this worktree — all torch-dependent tests skip. Tests will run in CI.
- Pre-existing: `test_forward_return_labeler.py` errors on collection (missing torch, no importorskip guard)

**Next task notes:**
- Metric key names from Task 2.1: `directional_accuracy`, `r_squared`, `mse`, `mae`, `mean_predicted_return`, `std_predicted_return`

## Task 2.2 Complete: Gate System Regression Gates

Both `check_training_gate` and `check_backtest_gate` now branch on `output_format` from metrics dict.

**Training gate regression checks:** directional_accuracy > 50% (strict >), max_loss check preserved.
**Backtest gate regression checks:** net_return >= 0, trade_count >= 5, max_drawdown check preserved.

**Implementation notes:**
- Regression path returns early — skips classification-specific loss_decrease check (not meaningful for Huber loss)
- `output_format` comes from metrics dict, defaults to "classification" if absent
- Gate configs load regression thresholds from env vars (TRAINING_GATE_MIN_DIRECTIONAL_ACCURACY, BACKTEST_GATE_MIN_NET_RETURN, BACKTEST_GATE_MIN_TRADES)

**Next task notes:**
- Task 2.3 modifies `ktrdr/agents/prompts.py` — assessment prompt needs regression context
- Gates pass `output_format` via metrics dict — assessment worker should include it when calling gates
