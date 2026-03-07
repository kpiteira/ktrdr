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
- Task 2.2 (Gates) needs to branch on `output_format`. The gate config is a dataclass in `ktrdr/agents/gates.py`.
- Metric key names from this task: `directional_accuracy`, `r_squared`, `mse`, `mae`, `mean_predicted_return`, `std_predicted_return`
