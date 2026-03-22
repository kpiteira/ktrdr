# M3: Comparison Experiment

## Goal
Direct MLP vs LSTM comparison on identical features/labels/splits to answer hypothesis H_003: do temporal patterns in standard indicators carry predictive signal that point-in-time values don't?

## Dependencies
- M2 complete (LSTM models can be backtested)

## Tasks

### Task 3.1: LSTM Strategy Template + Training

**What:** Create LSTM strategy YAML and train models for comparison.

**Key implementation:**
- Create `strategies/trend_tb_lstm_signal_v1.yaml` — LSTM version of existing TB signal strategy
- Same indicators, fuzzy sets, nn_inputs as `trend_tb_gaussian_signal_v1.yaml`
- Only difference: `model.type: lstm` with `sequence_length: 20`, `hidden_size: 64`, `num_layers: 2`
- Train both MLP and LSTM on identical data window (2020-2023)
- Record training metrics for both

**Tests:**
- `tests/unit/config/test_lstm_strategy.py`
  - Strategy YAML loads and validates correctly
  - model.type == "lstm" parsed correctly
  - sequence_length present in architecture config

**Files:** `strategies/trend_tb_lstm_signal_v1.yaml` (new)

### Task 3.2: MLP vs LSTM Backtest Comparison

**What:** Run identical backtests with MLP and LSTM models, compare metrics.

**Key implementation:**
- Backtest both models on identical test window (2024-01-01 to 2024-12-31)
- Compare: win rate, trade count, total PnL, Sharpe ratio
- Document results in HANDOFF_M3.md
- If LSTM > MLP by >5pp win rate: temporal signal confirmed → proceed to autoresearch
- If similar: features uninformative regardless of architecture → pivot

**This is an experiment task, not a code task.** Results documented, not automated.

**Files:** `docs/designs/temporal-signal-models/implementation/HANDOFF_M3.md` (new)

## E2E Validation
- Both models trained on 2020-2023 with identical features
- Both backtested on 2024 with identical configuration
- Results compared in table format
- Go/no-go decision documented

## Completion Checklist
- [ ] LSTM strategy YAML created and validated
- [ ] LSTM model trained successfully
- [ ] MLP model trained on identical data for comparison
- [ ] Both backtested on same test window
- [ ] Results compared and documented
- [ ] H_003 status updated in hypotheses.yaml
