# Temporal Signal Models: LSTM/GRU Architecture

## Status: Intent (pre-design)
## Date: 2026-03-21
## Contributors: Karl + Lux

---

## What We're Building

Add LSTM/GRU temporal model architecture alongside the existing MLP in ktrdr's model zoo. Instead of seeing a single bar's fuzzy features (point-in-time), the model sees a sequence of N bars, allowing it to learn temporal patterns like "RSI rising from oversold" vs "RSI falling into oversold."

## Why

### The Evidence

Signal model evolution (M1-M5) proved that the training pipeline, labeling, and fuzzy encoding all work correctly. But MLP models produce uniform ~33/33/34% predictions when class-weighted — they genuinely cannot distinguish outcomes from point-in-time indicator values.

Key finding (H_INV_004): models capture ~1 pip edge pre-cost, destroyed by ~15 pip round-trip costs. The signal is too weak.

### The Untested Hypothesis (H_003, filed Dec 2025)

An MLP sees "RSI = 30" but cannot tell if RSI is falling into oversold or rising from oversold. These are fundamentally different market situations with different predictive value. LSTM/GRU architectures can learn these temporal patterns.

Multi-timeframe features with MAs were expected to provide temporal context through feature engineering (e.g., 1h MA slope alongside 5m RSI level). This didn't work — possibly because fuzzy discretization erases magnitude and trajectory information. An LSTM on sequences of fuzzy features may recover what's being lost in the point-in-time encoding.

### Why This First

This is the simplest untested hypothesis with the highest expected information value:
- If temporal models break through → we know the features carry signal that MLP can't extract, and investment in autoresearch/evolution becomes meaningful
- If temporal models don't help → we know standard indicators genuinely carry zero predictive information regardless of architecture, and need fundamentally different features
- Either answer redirects all future work

## What It Involves

1. **New model class** — LSTM/GRU alongside existing MLP in `ktrdr/neural/models/`
2. **Sequence data preparation** — training pipeline builds (sequence_length, feature_dim) tensors instead of (feature_dim,) vectors
3. **Sequence inference** — backtest/decision pipeline maintains rolling window for inference
4. **Strategy grammar extension** — model config supports `architecture: lstm` with `sequence_length`, `hidden_size`, `num_layers`
5. **Comparison experiments** — same indicators, same labels, MLP vs LSTM on identical train/val/test splits

## What It Does NOT Involve

- Changing the fuzzy encoding (Gaussian MFs stay as-is)
- Changing the labeling approach (triple barrier stays)
- Building new indicators
- Autoresearch or evolution infrastructure
- Brain region composition

## Success Criteria

- LSTM model trains and backtests end-to-end through existing pipeline
- Comparison: LSTM vs MLP on identical features/labels/splits
- If LSTM shows >5pp improvement in backtest win rate over MLP → strong signal
- If LSTM shows similar performance → features genuinely uninformative, pivot needed

## Connection to Broader Plan

This is Phase 0 of a 4-phase path:
- **Phase 0** (this): Temporal model — answers "do these features carry temporal signal?"
- **Phase 1**: Autoresearch — automated strategy space exploration
- **Phase 2**: Primordial soup — population-based evolution (conditional on Phase 0/1 showing signal)
- **Phase 3**: Brain region composition — combine regime + temporal signal + context
