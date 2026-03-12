# M7 Ensemble + Regime Backtest — Handoff

## Task 7.1 Complete: Build EnsembleConfiguration

**Gotchas:**
- YAML models dict uses keys as logical names — `from_dict()` injects `name` from dict key so YAML doesn't need to repeat the name inside each model block.
- `RouteRule` uses `model_validator(mode="after")` for mutual exclusivity check (both None and both set are errors).

**Next task notes (7.2):**
- `CompositionConfig` has `regime_threshold`, `stability_bars`, `on_regime_transition` — all needed by RegimeRouter.
- `RouteRule.model` is `str | None` (None means forced action like FLAT). `RouteRule.action` is the alternative.
- Architecture doc Section 2.4 defines `RouteDecision` and `TransitionAction` dataclasses.

## Task 7.2 Complete: Build RegimeRouter

**Gotchas:**
- Router is stateful (`_confirmed_regime`, `_pending_regime`, `_regime_counter`). Tests that iterate through regimes need fresh router instances to avoid stability filter interference.
- `previous_regime` param is informational — router tracks its own confirmed regime internally. The param exists for external logging/debugging.

**Next task notes (7.3):**
- `DecisionFunction` at `ktrdr/backtesting/decision_function.py` has `_SIGNAL_MAP = {0: BUY, 1: HOLD, 2: SELL}` hardcoded. Generalize to N-class.
- Regime 4-class map: `{0: TRENDING_UP, 1: TRENDING_DOWN, 2: RANGING, 3: VOLATILE}`.
- Probabilities dict construction (~line 196-219) uses hardcoded BUY/HOLD/SELL keys — must use class names from map.

## Task 7.3 Complete: Generalize DecisionFunction to N-Class

**Gotchas:**
- `_predict()` imports torch at function scope — tests must mock `_predict` entirely (existing pattern) or patch `sys.modules["torch"]` for direct _predict testing.
- Non-signal output types (regime, context) always return `Signal.HOLD` — the ensemble runner reads probabilities from reasoning dict, not the signal.
- `_CLASS_NAMES` dict and `_NON_SIGNAL_OUTPUT_TYPES` set are module-level constants.

**Next task notes (7.4):**
- `DecisionFunction.__init__` now accepts `output_type` param (default "classification"). Pass `output_type="regime_classification"` for regime models.
- Regime probabilities are in `result.reasoning["nn_probabilities"]` with keys `TRENDING_UP/TRENDING_DOWN/RANGING/VOLATILE`.
- EnsembleBacktestRunner needs to extract regime probs from DecisionFunction output and pass to RegimeRouter.

## Task 7.4 Complete: Build EnsembleBacktestRunner

**Gotchas:**
- `_interpret_regime_output()` converts uppercase prob keys (TRENDING_UP) to lowercase (trending_up) for the RegimeRouter. Case mismatch is a silent bug.
- Router state is accessed via `router._confirmed_regime` for the previous_regime param — slightly coupling to internals, but the param is informational only.
- Transition close: LONG→SELL, SHORT→BUY. FLAT positions skip the close trade.

**Next task notes (7.5):**
- CLI command needs to load ensemble config YAML, create BacktestConfig, instantiate EnsembleBacktestRunner, and call `await runner.run()`.
- Follow existing CLI patterns — use Typer app, Rich tables for output.
- `EnsembleBacktestResults.to_dict()` provides serializable output for CLI display.

## Task 7.5 Complete: Wire Ensemble Backtest to CLI

**Gotchas:**
- `raise typer.Exit(code=1)` inside except blocks needs `from None` suffix (B904 lint rule).
- Heavy imports (BacktestConfig, EnsembleBacktestRunner, EnsembleConfiguration, Rich) deferred inside function body per CLI performance conventions.
- Registered via `app.add_typer(ensemble_app)` in `ktrdr/cli/app.py`.

**Next task notes (7.6):**
- Task 7.6 is MIXED — requires training per-regime models, creating ensemble config YAML, running `ktrdr ensemble backtest`, comparing vs baseline.
- CLI command is fully wired; test with a real ensemble YAML config.

## Task 7.6 Complete: Run Full Regime-Routed Backtest

**Gotchas:**
- `ModelBundle.load()` hardcoded `num_classes=3`. Regime models have 4 classes → size mismatch loading state_dict. Fixed by inferring `num_classes` from `metadata.output_type` via `_CLASS_NAMES`.
- `DataRepository` has `load_from_cache()`, not `load_historical_data()`. EnsembleBacktestRunner updated.
- CLI runs locally (no torch). Ensemble backtest must run inside container via `docker exec`.

**Results:**
- Ensemble: 1348 bars, 24 trades, 0 transitions (seed regime classifier classifies everything as "ranging")
- Baseline (same signal model, no routing): identical 24 trades — expected since only one regime active
- Ensemble overhead: 2.5s vs 0.86s baseline (3x, due to loading 3 models + routing per bar)
- Transition costs: $0 (no transitions)
- Conclusion: Infrastructure works end-to-end. Real regime differentiation requires better-trained regime classifier.
