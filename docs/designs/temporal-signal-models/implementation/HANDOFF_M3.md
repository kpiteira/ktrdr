# Handoff — M3: Comparison Experiment (H_003)

## Experiment Design

**Hypothesis H_003** (filed Dec 2025): LSTM/attention architecture might capture RSI trajectories better than MLP.

**Setup:**
- Two identical strategies: same indicators (RSI, ADX, MACD, ROC), same Gaussian fuzzy sets, same hybrid encoding, same triple barrier labels, same training config
- Only difference: `model.type: mlp` vs `model.type: lstm` (sequence_length=20, hidden_size=64, 2 layers)
- Training: EURUSD 5m+1h, 2015-01-01 to 2020-12-31 (6 years)
- Backtest: EURUSD, 2021-01-01 to 2025-01-01 (4 years out-of-sample)
- 300 epochs, batch_size=128, focal loss, gradient clip, LR scheduler, early stopping patience=25

## Training Results

| Metric | MLP (300 epochs) | LSTM (300 epochs) |
|--------|-----------------|------------------|
| Final Train Loss | 0.1133 | **0.1038** (-8.4%) |
| Best Val Loss | 0.1132 | **0.1047** (-7.5%) |
| Best Val Accuracy | ~35% (random) | **~61%** (+26pp) |
| Train Accuracy | ~35% | **~48%** |
| Learning Observed | **No** — flat for 300 epochs | **Yes** — loss decreased continuously |
| Epoch time | 4.5s | 80s |

**MLP behavior:** Loss stuck at 0.1133 from epoch 1 through 300. Val accuracy random-walked between 4% and 57%. The model learned nothing — it could not distinguish TB outcomes from point-in-time indicator values.

**LSTM behavior:** Loss decreased from 0.1127 → 0.1038 over 300 epochs. Val loss improved from 0.1124 → 0.1047. Val accuracy reached 61% at epoch 90. The model learned temporal patterns invisible to MLP.

## Backtest Results (4 years out-of-sample)

| Metric | MLP | LSTM |
|--------|-----|------|
| Total Trades | **0** | **289** |
| Win Rate | N/A | 24.9% (72W / 217L) |
| Total Return | 0.00% | -0.21% |
| Sharpe Ratio | N/A | -0.75 |
| Max Drawdown | 0.00% | 0.21% |
| Profit Factor | N/A | 0.41 |
| Sortino | N/A | -0.80 |

**MLP:** Zero trades. Model predictions never exceeded the 0.5 confidence threshold. Uniform ~33/33/34% class probabilities.

**LSTM:** 289 trades over 4 years (~72/year). Model was selective enough to trade. Win rate 25% with profit factor 0.41 means average winners don't compensate for the higher number of losers.

## H_003 Verdict: CONFIRMED

**Temporal patterns in standard indicators DO carry predictive signal that point-in-time values don't.**

Evidence:
1. LSTM train loss decreased 8.4% while MLP was completely flat
2. LSTM val accuracy reached 61% vs MLP's ~35% (random)
3. LSTM produced 289 trades (non-trivial predictions) vs MLP's 0
4. LSTM found something to learn from; MLP found nothing

**But the signal is insufficient for profitability.** The temporal patterns the LSTM discovers don't overcome transaction costs over 4 years OOS. This is a gap between "better than random on val set" and "profitable in backtest."

## What This Means for the Project

### What we now know
- **Architecture matters.** MLP on these features = dead. LSTM on same features = signal.
- **Standard indicators have temporal information** that fuzzy encoding + MLP destroys. The trajectory of RSI matters more than its current level.
- **The signal-to-cost gap remains.** Even with temporal patterns, standard indicators on EURUSD 1h don't produce enough edge to cover costs.

### What to explore next
1. **Autoresearch with LSTM** — let Claude explore the strategy space with temporal models. The LSTM architecture is now available. Autoresearch can try different indicators, sequence lengths, hidden sizes, timeframe combinations.
2. **Cross-asset features + LSTM** — DXY, yields, VIX provide information not in EURUSD price. Combined with temporal modeling, this could be the combination that works.
3. **Primordial soup with temporal genomes** — population-based evolution where researcher genomes include architecture parameters (MLP vs LSTM, sequence_length, hidden_size).
4. **Longer sequences** — 20 bars of 5m = 100 minutes of context. Try 50 or 100 bars for longer-term temporal patterns.
5. **Attention mechanisms** — if LSTM shows signal, self-attention might capture which parts of the sequence matter most.

### Key insight for the broader KTRDR vision
The "adult brain with specialized regions" architecture becomes more concrete:
- **Regime brain** (works at 69-79% accuracy with MLP — regime classification is easier)
- **Signal brain** now needs LSTM/temporal architecture, not MLP
- **Context brain** (multi-TF daily context) should also benefit from temporal modeling

The evolution framework's competency spectrum makes more sense now: temporal modeling is a capability that enables the jump from Baby (can't distinguish signal from noise) to Toddler (exhibits regime sensitivity).

## Files

- `strategies/experiment_h003_mlp.yaml` — MLP experiment strategy
- `strategies/experiment_h003_lstm.yaml` — LSTM experiment strategy
- Trained models: `~/.ktrdr/shared/models/experiment_h003_mlp/5m_v1/` and `experiment_h003_lstm/5m_v1/`
