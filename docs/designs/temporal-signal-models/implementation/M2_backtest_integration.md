# M2: Backtest Integration

## Goal
Run a trained LSTM/GRU model through the ensemble backtest pipeline and produce trade results.

## Dependencies
- M1 complete (LSTM models can be trained and saved)

## Tasks

### Task 2.1: FeatureCache.get_feature_window()

**What:** Add method to FeatureCache that returns last N rows of features for a given timestamp.

**Key implementation:**
- `get_feature_window(timestamp, sequence_length) -> pd.DataFrame | None`
- Uses index position to slice cached features DataFrame
- Returns None if insufficient history (first seq_len-1 bars)
- Returned DataFrame has columns in exact feature order

**Tests (RED first):**
- `tests/unit/backtesting/test_feature_cache_window.py`
  - Returns correct window size
  - Returns None for early timestamps with insufficient history
  - Column order matches expected_features
  - Values match the cached data exactly
  - Edge case: exact seq_len bars available returns valid window

**Files:** `ktrdr/backtesting/feature_cache.py` (modified)

### Task 2.2: DecisionFunction Sequence-Aware Inference

**What:** Modify DecisionFunction._predict() to handle both dict (MLP) and DataFrame (LSTM/GRU) inputs.

**Key implementation:**
- Detect input type: dict → MLP path (unchanged), DataFrame → sequence path
- Sequence path: convert DataFrame to (1, seq_len, features) tensor
- Add `sequence_length` and `model_type` to DecisionFunction.__init__() (from ModelBundle metadata)
- Caller (ensemble_runner or backtest service) passes window instead of dict when model is temporal

**Tests (RED first):**
- `tests/unit/backtesting/test_decision_function_sequence.py`
  - MLP path unchanged: dict input → (1, F) tensor
  - LSTM path: DataFrame input → (1, S, F) tensor
  - Output format identical for both paths (signal, confidence, raw_outputs)
  - Feature ordering preserved in sequence tensor

**Files:** `ktrdr/backtesting/decision_function.py` (modified)

### Task 2.3: ModelBundle.load() for Temporal Models

**What:** Update ModelBundle to load LSTM/GRU model architectures and expose sequence_length.

**Key implementation:**
- Read model_type from metadata (default "mlp")
- Dispatch to LSTMTradingModel/GRUTradingModel for architecture reconstruction
- Read architecture config from config.json (hidden_size, num_layers, etc.)
- Expose sequence_length on ModelBundle for callers
- Update EnsembleBacktestRunner to pass windows for temporal models

**Tests (RED first):**
- `tests/unit/backtesting/test_model_bundle_temporal.py`
  - Loads LSTM model from saved artifacts
  - Correct architecture reconstructed (hidden_size, num_layers match)
  - sequence_length exposed on ModelBundle
  - MLP loading unchanged (regression test)

**Files:** `ktrdr/backtesting/model_bundle.py` (modified), `ktrdr/backtesting/ensemble_runner.py` (modified)

## E2E Validation
- Train LSTM model (from M1)
- Backtest via CLI: `uv run ktrdr backtest run trend_tb_lstm_signal_v1 EURUSD 1h --start-date 2024-07-01 --end-date 2024-12-31`
- Verify: trades produced, PnL calculated, no crashes
- Verify: first ~20 bars have no trades (insufficient sequence history)

## Completion Checklist
- [ ] FeatureCache returns correct windows for temporal models
- [ ] DecisionFunction handles both dict and DataFrame inputs
- [ ] ModelBundle loads LSTM/GRU models correctly
- [ ] EnsembleBacktestRunner passes windows for temporal models
- [ ] End-to-end backtest produces trade results
- [ ] All unit tests pass
- [ ] `make quality` passes
