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

## Task 2.3 Complete: Assessment Prompt Regression Context

Added regression branch to `get_assessment_prompt()`:
- Shows directional accuracy, R², MSE, MAE instead of classification accuracy
- Includes regression evaluation guidance section
- Includes cost_model details (round_trip_cost, min_edge_multiplier, computed threshold)
- Added `cost_model` optional field to `AssessmentContext` dataclass

Extracted helpers: `_format_regression_training()`, `_format_regression_guidance()`, `_format_classification_training()`.

## Task 2.4 Complete: Design Prompt Regression Guidance

Added "Regression Mode" section to `DESIGN_SYSTEM_PROMPT` with:
- `decisions` config example (output_format, cost_model)
- `training` config example (forward_return labels, horizon, huber loss)
- Design guidance (architecture sizing, horizon selection, selectivity)
- Classification mode documented as legacy alternative

## Task 2.5 Complete: Research Worker Regression Metadata

**Research worker changes:**
- `_start_training()`: Extracts `output_format` and `cost_model` from strategy config, stores in parent op metadata
- `_handle_training_phase()`: Injects `output_format` into training result before `check_training_gate()`
- `_handle_backtesting_phase()`: Injects `output_format` into backtest result before `check_backtest_gate()`, extracts `net_return`/`trade_count`

**Assessment worker changes:**
- `_build_user_prompt()`: Adds regression evaluation guidance section when `output_format == "regression"`
- New `_format_regression_guidance()` static method

**Gotchas:**
- Design prompt line count test updated from 100→150 to accommodate regression docs
- Pre-existing: `test_forward_return_labeler.py` errors on collection (no importorskip guard)

## Task 2.6 Complete: E2E Validation

Full regression research cycle completed via sandbox (slot 6, port 8006).

**E2E results (op_agent_research_20260307_010859_739ad019):**
1. Design agent produced `rsi_macd_regression_eurusd_1h_v1` with `output_format: regression`, `cost_model`, `forward_return` labels, `huber` loss ✅
2. Training completed (60 epochs, 28034 samples, huber loss ~7e-6) with `output_format: "regression"` in result ✅
3. Training gate used regression check: `directional_accuracy_below_threshold (0.0% <= 50%)` — correct gate path ✅
4. Gate rejection routed to assessment (not backtest) — correct behavior for failed gate ✅
5. Assessment agent evaluated with regression context (mentions directional accuracy, cost-aware thresholding, forward returns) ✅
6. Assessment verdict: "poor" with regression-specific strengths/weaknesses/suggestions ✅

**Gotchas:**
- Sandbox agent ports conflict with ktrdr-prod. Added `KTRDR_DESIGN_AGENT_PORT=5061` and `KTRDR_ASSESSMENT_AGENT_PORT=5062` to `.env.sandbox`
- DB volume must be removed when recreating containers (`docker volume rm slot-6_postgres_data`)
- `directional_accuracy` shows 0.0% in gate because training pipeline doesn't yet call `collect_regression_metrics()` — gate correctly defaults to 0 and rejects. This is expected; M1 training pipeline will wire this up.
- Backtest gate not exercised (training gate rejected → routed to assessment). Backtest regression gate path is unit-tested.
