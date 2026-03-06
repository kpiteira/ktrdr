# Handoff: M1 Regression Substrate

## Status
All tasks (1.1-1.8) complete.

## Files Created
- `ktrdr/training/forward_return_labeler.py` — ForwardReturnLabeler class
- `tests/unit/training/test_forward_return_labeler.py` — 14 tests
- `tests/unit/neural/test_mlp_regression.py` — 9 tests
- `tests/unit/training/test_model_trainer_regression.py` — 6 tests
- `tests/unit/training/test_training_pipeline_regression.py` — 11 tests
- `tests/unit/backtesting/test_decision_function_regression.py` — 20 tests
- `tests/unit/config/test_strategy_validator_regression.py` — 10 tests
- `strategies/regression_example_v3.yaml` — Example regression strategy
- `tests/integration/test_regression_pipeline.py` — 5 integration tests
- `.claude/skills/e2e-testing/tests/regression/full-cycle.md` — E2E test recipe

## Files Modified
- `ktrdr/neural/models/mlp.py` — build_model() output_dim=1 for regression, train() Huber/MSE loss
- `ktrdr/training/model_trainer.py` — train() regression branch (loss, squeeze, directional accuracy, val_predicted fix)
- `ktrdr/training/training_pipeline.py` — create_labels() forward_return source branch, evaluate_model() regression path
- `ktrdr/api/services/training/local_orchestrator.py` — training_config from correct section, weight_decay=0.0 for regression, output_format passthrough, feature truncation
- `ktrdr/backtesting/decision_function.py` — regression predict path, trade_threshold, cosmetic confidence, SELL-from-FLAT allowed for regression
- `ktrdr/backtesting/position_manager.py` — short-selling support (SELL from FLAT opens SHORT, BUY from SHORT closes it, force_close handles SHORT, portfolio value for SHORT)
- `ktrdr/config/strategy_validator.py` — regression decisions/training validation
- `tests/unit/agents/test_worker_queuing.py` — fixed 7 pre-existing test failures (mock _load_strategy_config + budget tracker)

## Key Patterns

### Config Flow
`output_format` flows: strategy YAML decisions section -> training config -> model config -> build_model -> trainer -> saved config.json -> ModelBundle load -> DecisionFunction

### Feature-Label Alignment
Forward return labels are shorter by `horizon` bars. Features truncated from front: `features[:len(labels)]`.

### Mode Branching
`output_format == "regression"` checked at ~12 branch points. No abstract interfaces — simple if/else.

### Cosmetic Confidence
`min(abs(predicted_return) / (3 * threshold), 1.0)` — backward compatible [0,1] range.

### training_config Routing
Strategy YAML has top-level `training` section with epochs/learning_rate/batch_size. The `model` section does NOT contain a `training` sub-key. `local_orchestrator._execute_v3_training()` builds training_config explicitly from the top-level training section, not from `model_config.get("training", {})`.

## Gotchas
- `MLPTradingModel.build_model()` returns the model but doesn't store it. Must do `mlp.model = mlp.build_model(input_size=N)`.
- `ModelTrainer.train()` gets epochs/learning_rate from `self.config`, not kwargs.
- Only `train()` was modified for regression, NOT `train_multi_symbol()` — that still uses CrossEntropyLoss.
- V3 Pydantic models require nested structure (`symbols: {mode: "single", symbol: "EURUSD"}`), not flat dicts.
- `StrategyConfigurationLoader` calls validator internally — construct `StrategyConfigurationV3` directly to test validation errors in isolation.
- `evaluate_model()` was hardcoded to CrossEntropyLoss — fixed to dispatch on output_format. E2E caught this.
- **weight_decay=0.0001 kills regression models**: Default L2 regularization in Adam pushes all weights to zero when Huber loss gradients are tiny (forward returns ~0.003 magnitude). Fix: `training_config["weight_decay"] = 0.0` for regression mode in local_orchestrator.
- **val_predicted unbound in regression**: The regression validation branch didn't set `val_predicted`, causing silent analytics failures. Fixed by adding `val_predicted = val_pred_sign.long()`.
- Model collapse to near-constant prediction is expected when features are uninformative. The trade_threshold correctly produces 0 trades in this case. Future milestones should address label normalization and feature quality.
- **SELL-from-FLAT was blocked at TWO layers**: (1) `decision_function.py:277` "no short positions in MVP" filter blocked SELL signals from FLAT. Fixed: only block for classification mode. (2) `position_manager.py:221` `can_execute_trade()` only allowed SELL when LONG. Fixed: added full short-selling support (`_execute_short_entry`, `_execute_short_exit`, updated `force_close_position`, updated `get_portfolio_value` for SHORT).

## Bugs Found and Fixed (beyond M1 scope)
- 7 pre-existing test failures in `test_worker_queuing.py` — 5 from `CycleError: Strategy config not found` (fixed by mocking `_load_strategy_config`), 2 from corrupted budget JSON (fixed by mocking `get_budget_tracker`).
- 24 lint errors (21 in M1 test files, 3 pre-existing) — E402/F401 from `pytest.importorskip("torch")` pattern. All fixed.
- 5 mypy type errors in M1 code — `criterion` type narrowing and tensor type mismatches. All fixed.

## Test Count
75 tests total (all passing): 20 + 9 + 6 + 11 + 14 + 10 + 5
Plus 7 pre-existing test fixes in test_worker_queuing.py

## E2E Validation
Train → save → load → backtest pipeline validated end-to-end:
- Training: 50 epochs Huber loss, model saved with regression config
- Backtest: 2 trades (SHORT entry + force-close), -0.15% return, 50% win rate
- Short-selling: SELL from FLAT opens SHORT, force-closed at backtest end
- Model collapses to near-constant prediction with 4 fuzzy features — expected, not a code bug
