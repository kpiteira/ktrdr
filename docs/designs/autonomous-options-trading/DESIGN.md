# ktrdr Autonomous Options Trading System — Design Document

> **Author**: Claude (Opus 4.6), commissioned by Karl Piteira
> **Date**: 2026-04-18
> **Status**: Draft v4 — fixes applied for problem statement accuracy (ktrdr as research system on forex, not profitable trading system on stocks), equity options (SPY) as target instrument, SPY model training hardened into M1
> **Grounded in**: ktrdr codebase analysis (`KTRDR_REALITY_MAP.md`), Kronos integration spec (`spec.md`)

---

## 1. Problem Statement

### What Problem Does This Solve?

ktrdr is a **strategy research system** — not a live trading system. It explores and validates directional trading strategies on **forex pairs** (EUR/USD, GBP/USD, etc.) using a pipeline of technical indicators, fuzzy membership functions, and neural networks (MLP/LSTM/GRU) to produce BUY/SELL/HOLD signals. The pipeline: OHLCV → IndicatorEngine → FuzzyEngine → FuzzyNeuralProcessor → neural network → softmax over {BUY, HOLD, SELL}. ktrdr has **no live trading history** and is **not profitable** — internal validation runs show a Sharpe of approximately 0.181 (from training-period validation, not an independent out-of-sample backtest), a research-grade result that demonstrates directional signal content but not a deployable edge on linear instruments.

**The opportunity**: ktrdr's backtested directional signals can be extended to **equity options trading**, where options provide asymmetric payoff profiles that can amplify edge even with modest directional accuracy. A correct BUY signal that triggers buying a call spread pays 2-5x the risk, while an incorrect signal loses only the premium paid. Combined with a vol regime signal (from Kronos) that informs *which* options structure to use, the system can match structure to market conditions rather than applying one-size-fits-all directional bets.

**The gap being filled**: ktrdr generates research-grade directional signals but cannot execute or capitalize on them. This system bridges that gap by:

1. Training a new ktrdr model on **SPY** equity data using the same fuzzy-neural pipeline (M1) — transferring the signal methodology from forex to equities
2. Adding Kronos vol regime classification to determine whether implied volatility is rich or cheap (M1)
3. Building a Black-Scholes options pricing engine for synthetic backtesting (M2)
4. Backtesting the full system on SPY options using the decision matrix (M3)
5. Adding Opus 4.7 reasoning for live trade structure selection and portfolio construction (M4)
6. Paper trading via IBKR to validate the end-to-end system with real options chains (M5)

**Why equity options, not forex options**: ktrdr's existing models are trained on forex, but the target instrument for this system is **equity options** (SPY as primary underlying). Forex options are OTC, illiquid, and have limited IBKR support — they are explicitly out of scope. Equity options (SPY, etc.) are exchange-traded, liquid, and fully supported by IBKR's API. ktrdr's directional signal methodology transfers to SPY via a new model trained on SPY/equity OHLCV data using the same pipeline.

### What Does Success Look Like?

| Milestone | Metric | Timeline |
|-----------|--------|----------|
| M1: SPY model + Vol regime signal validates | ktrdr SPY model trained; Kronos classifier AUC > 0.60 on held-out IV data | Phase 1 (weeks 1-2) |
| M2: Synthetic backtest shows edge | Combined system Sharpe > 0.50 on 2-year synthetic options backtest | Phase 2 (weeks 3-5) |
| M3: Paper trading confirms | Paper Sharpe > 0.40 over 60+ trading days with > 30 trades | Phase 3 (months 2-4) |
| M4: Live deployment | Sharpe > 0.35 on real capital, max drawdown < 15% | Phase 4 (month 5+) |

**The Sharpe targets are deliberately conservative**. A Sharpe of 0.50 on synthetic backtest with Black-Scholes reconstruction has known approximation errors (see Section 5); paper trading at 0.40 accounts for real-world slippage. If these targets are met, the system has genuine edge.

### Non-Goals

- **High-frequency options trading**: ktrdr operates at bar-level granularity (1h-1d). This system targets swing options (5-45 DTE), not intraday scalping.
- **Exotic options**: No barriers, digitals, or path-dependent exotics. Vanilla calls, puts, and standard multi-leg structures only.
- **Market making / delta-neutral strategies**: This system is directional-first. Vol regime informs structure selection, not standalone vol trading.
- **Fully automated execution without human oversight**: Lux recommends trades and can paper-trade autonomously, but live execution requires Karl's approval until paper trading validates the system.
- **Multi-asset portfolio optimization**: Single-name options on one ticker at a time. Portfolio-level correlation management is out of scope.
- **Replacing ktrdr's core ML pipeline**: The options layer sits *on top of* ktrdr's existing signal. Phase 1 of Kronos integration (replacing fuzzy features) is specced separately.
- **Forex options**: OTC, illiquid, limited IBKR support. This system targets exchange-traded equity options only.

---

## 2. System Overview

### High-Level Architecture

```
                    +-----------------+
                    |   Lux (24/7)    |
                    |  Orchestrator   |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
    +------------------+  +--------+  +------------------+
    | ktrdr REST API   |  | Kronos |  | Options Data     |
    | POST /api/v1/    |  | Vol    |  | (yfinance/CBOE/  |
    | models/predict   |  | Regime |  |  IBKR chain)     |
    +--------+---------+  +---+----+  +--------+---------+
             |                |                |
             v                v                v
    +--------------------------------------------------+
    |           Signal Aggregation Layer                |
    |  ktrdr signal + Kronos regime + IV percentile    |
    +------------------------+-------------------------+
                             |
                             v
    +--------------------------------------------------+
    |              Opus 4.7 Reasoning                  |
    |  Input: structured JSON (signals + chain data)   |
    |  Output: structure + strikes + expiry + size     |
    +------------------------+-------------------------+
                             |
                             v
    +--------------------------------------------------+
    |            Position Management                    |
    |  Track open positions, Greeks, P&L               |
    |  Managed by Lux in local state                   |
    +------------------------+-------------------------+
                             |
                             v
    +--------------------------------------------------+
    |              Execution Target                     |
    |  Backtest (synthetic) -> Paper (IBKR) -> Live    |
    +--------------------------------------------------+
```

### Component List

| Component | Responsibility |
|-----------|---------------|
| **Lux** | Orchestrates the entire flow: polls ktrdr, runs Kronos, calls Opus 4.7, manages positions, reports via Telegram |
| **ktrdr REST API** | Produces directional signal (BUY/SELL/HOLD + probability distribution) from trained models. ktrdr is a strategy research system; its signals are backtested research outputs, not live-validated production signals. |
| **Kronos Vol Regime Classifier** | Classifies current market as SELL_VOL / BUY_VOL / NEUTRAL based on frozen Kronos embeddings + trained linear head |
| **Options Data Provider** | Supplies IV percentile, options chain data, and historical IV for backtesting |
| **Signal Aggregation** | Combines ktrdr directional signal, Kronos vol regime, and IV context into a structured decision input |
| **Opus 4.7 Reasoning** | Selects optimal options structure, strikes, expiry, and position size given the aggregated signal |
| **Position Manager** | Tracks open options positions, monitors Greeks, triggers exit conditions |
| **Backtest Engine (Options)** | Reconstructs historical options P&L via Black-Scholes for strategy validation |

### Data Flow: "Lux Triggers Analysis" to "Recommendation Produced"

1. **Trigger**: Lux runs on a schedule (e.g., every hour for 1h bars, every day for 1d bars) or on demand via Telegram command.

2. **Fetch ktrdr signal**: Lux sends `POST /api/v1/models/predict` to ktrdr server with `{model_name, symbol, timeframe}`. Receives `{signal, confidence, signal_strength}` plus `input_features`. Note: ktrdr's signals are research-grade outputs (validation Sharpe ~0.181 on forex, from training runs); the SPY model trained in M1 will have its own validation performance characteristics.

3. **Fetch Kronos vol regime**: Lux calls the Kronos classifier (Python function, not REST — runs in Lux's process or via subprocess). Inputs recent OHLCV bars. Receives `{regime: SELL_VOL|BUY_VOL|NEUTRAL, confidence: float}`.

4. **Fetch options context**: Lux retrieves current IV percentile (from VIX for SPY/indices, or from options chain data for single names) and the relevant options chain (strikes, expiries, bid/ask).

5. **Aggregate and call Opus 4.7**: Lux constructs a structured JSON prompt containing the ktrdr signal, Kronos regime, IV data, and options chain. Sends to Opus 4.7 via Anthropic API with extended thinking enabled.

6. **Opus 4.7 responds**: Returns a structured JSON with selected structure, specific strikes, expiry, position size, and reasoning.

7. **Lux acts**: In backtest mode, logs the synthetic trade. In paper mode, submits order to IBKR paper. In live mode, submits real order (with Karl's approval gate).

---

## 3. The Two ML Signals

### Signal 1: ktrdr Directional Signal

**What it encodes**: The probability that the underlying asset will move up (BUY), down (SELL), or stay flat (HOLD) over the model's prediction horizon. This is a supervised classification output trained on historical price movements using triple barrier, zigzag, or forward return labels. ktrdr is a strategy research system — these signals are research outputs (validation Sharpe ~0.181 on forex pairs, from training runs), not live-validated production signals.

**How it's produced**: 

The signal originates from ktrdr's neural network (`ktrdr/neural/models/base_model.py`, `predict()` method, lines 57-250). The production path for live/external consumption:

1. Raw OHLCV data is loaded from ktrdr's data layer (`ktrdr/data/local_data_loader.py`)
2. `IndicatorEngine` (`ktrdr/indicators/indicator_engine.py`) computes ~28 technical indicators
3. `FuzzyEngine` (`ktrdr/fuzzy/engine.py`) converts indicator values to fuzzy membership degrees (0-1)
4. `FuzzyNeuralProcessor` (`ktrdr/training/fuzzy_neural_processor.py`) assembles features into `torch.FloatTensor`
5. Neural network (MLP/LSTM/GRU) produces softmax probabilities over {BUY, HOLD, SELL}
6. `DecisionOrchestrator` (`ktrdr/decision/orchestrator.py`, lines 216-243) applies position-aware filters

**SPY model (M1 prerequisite)**: ktrdr's existing models are trained on forex pairs (EUR/USD, GBP/USD). M1 must train a new ktrdr model on SPY/equity OHLCV data using the same fuzzy-neural pipeline. This model will produce directional signals for SPY, which gate all downstream milestones (M2 backtest, M3 paper trading). See Section 7 for details.

**How Lux calls it**:

```
POST /api/v1/models/predict
Content-Type: application/json

{
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "timeframe": "1h",
    "test_date": "2026-04-18T14:30:00"   // optional; defaults to latest bar
}
```

Response (from `ktrdr/api/endpoints/models.py`, `PredictionResponse`, lines 194-229):

```json
{
    "success": true,
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "test_date": "2026-04-18T14:30:00",
    "prediction": {
        "signal": "BUY",
        "confidence": 0.756,
        "signal_strength": 0.694
    },
    "input_features": {
        "1h_rsi_momentum_oversold": 0.02,
        "1h_rsi_momentum_overbought": 0.83,
        ...
    }
}
```

**Which output fields matter for options decisions**:

The top-level `signal` and `confidence` are insufficient. The options layer needs the **full probability distribution** — `{"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062}` — because:
- A signal with P(BUY)=0.55, P(HOLD)=0.40, P(SELL)=0.05 suggests a different structure than P(BUY)=0.55, P(HOLD)=0.05, P(SELL)=0.40
- The former is weakly directional; the latter is high-conviction directional with tail risk

**[KARL INPUT NEEDED]**: The current `PredictionResponse` schema returns `signal_strength` but not the full `nn_probabilities` dict. The `reasoning` dict in `TradingDecision` contains `nn_probabilities`, but it's not exposed through the REST API. **Decision needed**: Either (a) extend the `/predict` endpoint to include probabilities, or (b) have Lux call ktrdr as a Python library directly (bypassing REST). Option (a) is cleaner — it's a ~10-line change to the API endpoint.

**Confidence thresholding**:

| Max Probability | Interpretation | Action |
|-----------------|---------------|--------|
| < 0.45 | Model uncertain, probabilities near uniform | HOLD — do not open new positions |
| 0.45 - 0.60 | Weak directional signal | Small position, prefer defined-risk structures |
| 0.60 - 0.75 | Moderate directional signal | Standard position size |
| > 0.75 | Strong directional signal | Allow larger position, consider directional structures |

These thresholds interact with Kronos regime — see Section 4 decision matrix.

**Failure modes**:
- **Model degradation**: ktrdr signal accuracy decays as market regime shifts away from training data. Detectable via running accuracy on recent signals. **Mitigation**: Retrain periodically; Lux monitors win rate.
- **API unavailability**: ktrdr server is down or unreachable. **Mitigation**: Lux retries 3x with exponential backoff; if still down, hold all positions (no new trades).
- **Stale data**: ktrdr's local OHLCV cache hasn't been updated. The prediction uses old bars. **Mitigation**: Check `test_date` in response against current time; alert if > 2 bars stale.
- **All-HOLD degeneration**: Model learns to predict HOLD for everything (high accuracy on imbalanced data). **Detectable**: Track signal distribution over rolling 30-day window.

### Signal 2: Kronos Vol Regime Classifier

**What it encodes**: Whether the current market environment favors being long volatility (BUY_VOL — IV is likely to rise, realized vol will increase), short volatility (SELL_VOL — IV is elevated relative to likely realized vol, premium is rich), or neither (NEUTRAL — no clear vol edge).

**How it's produced**:

This is a **separate trained classifier** on top of **frozen** Kronos embeddings. It is NOT Kronos itself making vol predictions — Kronos is a generative model for K-lines. We use its hidden states as learned representations of market microstructure.

**Architecture**:

```
Recent OHLCV bars (last N bars, N up to 512)
    |
    v
Kronos-mini (frozen, 4.1M params)
    |
    v
Transformer hidden states: (batch, seq_len, 256)
    |
    v
Last hidden state: (batch, 256)     // or mean pool — [VALIDATE EMPIRICALLY]
    |
    v
Linear classifier head (256 -> 3)   // trained on vol regime labels
    |
    v
Softmax -> {SELL_VOL: float, BUY_VOL: float, NEUTRAL: float}
```

**Training the classifier head**:

The classifier is trained on historical data where the label is derived from the relationship between implied volatility (IV) and subsequent realized volatility (RV):

```
Label construction:
  1. For each bar t, compute:
     - IV_percentile_t = percentile rank of current IV over trailing 252 trading days
       (i.e., the fraction of days in the lookback window where IV was lower than today's IV)
     - RV_forward = realized volatility over the next N trading days (N = target holding period, e.g., 20 days)
     - IV_t = current implied volatility (from VIX for indices, or from ATM option IV for single names)
  
  2. Assign label:
     - SELL_VOL:  IV_percentile_t > 70 AND RV_forward < IV_t * 0.85
                  (IV is high relative to its history AND realized vol came in lower — selling premium was correct)
     - BUY_VOL:   IV_percentile_t < 30 AND RV_forward > IV_t * 1.15
                  (IV is low relative to its history AND realized vol expanded — buying options was correct)
     - NEUTRAL:   everything else
```

**Why IV Percentile instead of IV Rank**: This system uses **IV Percentile** (the fraction of trailing days where IV was lower than today) rather than **IV Rank** (min-max normalization: `(current - low) / (high - low)`). IV Percentile is more statistically robust because it is not distorted by outlier spikes. Example: if VIX sat between 15-17 for most of the year but spiked to 35 briefly, IV Rank of 22 would be only 35% (`(22-15)/(35-15)`), while IV Percentile of 22 would correctly reflect that 22 is higher than the vast majority of observed days (likely 90%+). For options structure selection, we care about how unusual today's IV is relative to the distribution of recent IV — that is what IV Percentile measures. The 70/30 percentile thresholds are calibrated to this metric: "IV is higher than 70% of recent days" is a meaningful statement regardless of whether extreme outliers exist in the lookback window.

**[ASSUMPTION]**: The 70th/30th percentile thresholds and the 0.85/1.15 multipliers are starting points. These should be tuned during Phase 1 validation. The label construction must avoid look-ahead bias — labels are based on *future* realized vol but the *features* (Kronos embeddings) use only past bars.

**Training procedure**:

1. Pre-compute Kronos embeddings for the entire training period (cache to disk as `.pt` files)
2. Construct IV/RV labels for each bar (requires historical IV data — see Section 6)
3. Train a linear layer (256 -> 3) with cross-entropy loss, using standard train/val/test split
4. Freeze the linear head after training
5. **No fine-tuning of Kronos itself** in Phase 1 — the hypothesis is that frozen embeddings already encode vol-relevant information

**Output format**:

```python
@dataclass
class VolRegimeSignal:
    regime: str            # "SELL_VOL" | "BUY_VOL" | "NEUTRAL"
    confidence: float      # max probability (0.0-1.0)
    probabilities: dict    # {"SELL_VOL": float, "BUY_VOL": float, "NEUTRAL": float}
    iv_percentile: float   # current IV percentile (0-100) for context
    timestamp: str         # ISO 8601
```

**How it affects structure selection**: See Section 4 decision matrix. In brief:
- SELL_VOL -> favor structures that collect premium (iron condors, credit spreads, short strangles)
- BUY_VOL -> favor structures that pay premium (long straddles, debit spreads, long strangles)
- NEUTRAL -> favor directional structures where theta is minimal relative to delta

**Failure modes**:
- **Kronos model load failure**: Model weights not downloaded or corrupted. **Mitigation**: Verify weights on startup; fall back to IV percentile alone (heuristic: IV percentile > 70 = SELL_VOL, < 30 = BUY_VOL, else NEUTRAL).
- **Embedding quality insufficient**: Kronos hidden states may not encode vol-relevant information. **This is the central empirical risk**. Detectable in Phase 1 via linear probe AUC. If AUC < 0.55, the vol regime classifier adds no value and should be replaced with a simpler IV percentile heuristic.
- **Label noise**: The IV/RV relationship is noisy. SELL_VOL/BUY_VOL labels constructed from VIX may not correspond to single-name IV dynamics. **Mitigation**: Use ticker-specific IV when available (from options data); fall back to VIX only for index ETFs.
- **CPU latency**: Kronos-mini forward pass on CPU is ~100-500ms per prediction [VALIDATE EMPIRICALLY]. This is acceptable for hourly/daily signals but would be a bottleneck for minute-level.

---

## 4. Options Structure Selection Logic

### Target Instrument: Equity Options

This system trades **equity options**, with **SPY** as the primary underlying. The system is designed for equity options generically but is scoped to SPY initially for tractability — SPY has the most liquid options market, VIX is directly applicable as an IV proxy, and it provides a clean single-underlying test case before expanding to other equity options.

**Explicitly NOT in scope**:
- **Forex options**: OTC, illiquid, limited IBKR support. Although ktrdr's existing models are trained on forex pairs, forex options are not viable for this system.
- **Plain stock/equity trading**: The system trades options, not the underlying equities directly.
- **Index options (SPX)**: European-style, cash-settled. SPY options (American-style, share-settled) are preferred for IBKR paper trading compatibility.

### Decision Matrix

The decision matrix maps (ktrdr directional signal, Kronos vol regime, IV percentile) to a specific options structure:

```
                          Kronos Vol Regime
                    SELL_VOL        NEUTRAL         BUY_VOL
                 +---------------+---------------+---------------+
   ktrdr    BUY  | Bull Put      | Bull Call      | Long Call     |
   Signal        | Spread (1)    | Spread (3)     | (5)           |
                 +---------------+---------------+---------------+
            HOLD | Iron           | No Trade       | Long          |
                 | Condor (2)    | (skip)         | Straddle (6)  |
                 +---------------+---------------+---------------+
            SELL | Bear Call      | Bear Put       | Long Put      |
                 | Spread (4)    | Spread (7)     | (8)           |
                 +---------------+---------------+---------------+
```

### Structure Details

**(1) Bull Put Spread** (BUY + SELL_VOL): Directionally bullish, premium is rich.
- Sell OTM put, buy further OTM put (same expiry)
- Collects net credit; profits if underlying stays above short strike
- Max profit: net credit. Max loss: width - credit.
- DTE: 30-45 days. Short strike: ~0.30 delta. Width: 1-2 strikes.

**(2) Iron Condor** (HOLD + SELL_VOL): No directional view, but IV is elevated — sell premium on both sides.
- Sell OTM put + sell OTM call, buy further OTM put + buy further OTM call
- Max profit: net credit. Max loss: width - credit.
- DTE: 30-45 days. Short strikes: ~0.16 delta on each side. Wing width: 1-2 strikes.

**(3) Bull Call Spread** (BUY + NEUTRAL): Directionally bullish, no vol edge — keep it simple.
- Buy ATM/slightly OTM call, sell further OTM call
- Max profit: width - debit. Max loss: debit paid.
- DTE: 21-35 days. Long strike: ~0.45 delta. Width: 2-3 strikes.

**(4) Bear Call Spread** (SELL + SELL_VOL): Directionally bearish, premium is rich.
- Sell OTM call, buy further OTM call
- Mirror of (1) on the put side.

**(5) Long Call** (BUY + BUY_VOL): Directionally bullish AND vol is expected to expand — maximum convexity.
- Buy OTM call
- Unlimited upside, loss limited to premium.
- DTE: 14-30 days. Strike: ~0.35-0.40 delta.
- **Only used when ktrdr confidence > 0.65** — naked long options decay fast.

**(6) Long Straddle** (HOLD + BUY_VOL): No directional view but expecting vol expansion.
- Buy ATM call + ATM put
- Profits from large move in either direction.
- DTE: 14-30 days. Strike: ATM.
- **Only used when Kronos BUY_VOL confidence > 0.70** — straddles are expensive.

**(7) Bear Put Spread** (SELL + NEUTRAL): Directionally bearish, no vol edge.
- Buy ATM/slightly OTM put, sell further OTM put.
- Mirror of (3).

**(8) Long Put** (SELL + BUY_VOL): Directionally bearish AND vol expanding.
- Buy OTM put. Mirror of (5).

### Structures In Scope

- Vertical spreads (bull/bear, call/put)
- Iron condors
- Long calls and puts (single-leg)
- Long straddles

### Structures Explicitly Out of Scope

- **Calendar/diagonal spreads**: Require modeling term structure; too complex for Phase 1.
- **Butterflies**: Narrow max-profit zone; poor risk/reward for a noisy directional signal.
- **Ratio spreads**: Undefined risk on one side; requires precise vol modeling.
- **Naked short options**: Unlimited risk; not appropriate for an automated system.
- **Strangles (short)**: Unlimited risk on both sides. Iron condors are the defined-risk equivalent.
- **Covered calls/puts**: Requires holding underlying; out of scope for pure options system.

### How ktrdr Probabilities Affect Sizing

The probability distribution from ktrdr informs not just direction but position size:

```
position_size_multiplier = f(max_probability, probability_spread)

where:
  max_probability = max(P_BUY, P_HOLD, P_SELL)
  probability_spread = max_probability - second_highest_probability
  
  if probability_spread < 0.10:
      # Model is uncertain between two outcomes
      position_size_multiplier = 0.5
  elif probability_spread < 0.25:
      position_size_multiplier = 0.75
  else:
      position_size_multiplier = 1.0

max_risk_per_trade = account_value * 0.02 * position_size_multiplier
```

**[ASSUMPTION]**: 2% max risk per trade is the base allocation. This is conservative for options (where defined-risk structures have known max loss) but appropriate for an early-stage system. Karl may want to adjust this.

### Confidence Gates

Trades are only opened when signals meet minimum thresholds:

| Condition | Minimum Threshold |
|-----------|------------------|
| ktrdr max probability | 0.45 (for any directional trade) |
| ktrdr max probability (for naked long options: 5, 8) | 0.65 |
| Kronos regime confidence (for vol-specific structures: 2, 6) | 0.70 |
| Kronos regime confidence (for all other structures) | 0.50 |

If thresholds are not met, the system holds (no new position).

These thresholds are empirical starting points derived from common options trading practice, not from optimization on ktrdr's signal distribution. During M3 (backtest), sweep the `min_ktrdr_confidence` gate across [0.40, 0.45, 0.50, 0.55] and report the effect on trade frequency and Sharpe. Use the backtest to select the threshold that maximizes Sharpe while keeping >= 50 trades over 2 years.

---

## 5. The Backtesting Strategy

### Phase 1: Kronos Vol Regime Signal Quality Validation

**Objective**: Determine whether Kronos embeddings contain information about future volatility regimes that a simple classifier can extract.

**Method**:

1. **Data preparation**:
   - Load historical OHLCV for target symbols from ktrdr's data layer (`data/{timeframe}/{Symbol}_{Timeframe}.csv`)
   - Load historical IV data (source: VIX daily from yfinance for SPY/SPX; CBOE DataShop for single names if budget permits — see Section 6)
   - Compute labels for each bar: SELL_VOL / BUY_VOL / NEUTRAL (per Section 3 label construction)
   - Split: 70% train, 15% validation, 15% test, chronological split (no shuffling — this is time series)

2. **Embedding extraction**:
   - Run Kronos-mini on sliding windows of OHLCV data
   - Extract last hidden state: shape `(num_bars, 256)`
   - Cache embeddings to disk as `.pt` files (one per symbol/timeframe)

3. **Classifier training**:
   - Train `nn.Linear(256, 3)` with cross-entropy loss on train set
   - Class weights: `[1.0, 5.0, 8.0]` for [NEUTRAL, SELL_VOL, BUY_VOL] as a starting point (see Section 6 for expected class distribution). Tune based on actual observed label distribution.
   - If NEUTRAL > 80% of labels, consider upsampling minority classes or using focal loss instead of weighted cross-entropy.
   - Early stopping on validation loss
   - No fine-tuning of Kronos weights

4. **Evaluation metrics**:

   | Metric | Threshold for "Useful" | Why This Threshold |
   |--------|----------------------|-------------------|
   | AUC (per-class) | SELL_VOL AUC > 0.58 AND BUY_VOL AUC > 0.55 | Per-class AUC is more informative than macro-average when classes are heavily imbalanced; random = 0.50 |
   | Accuracy | > 0.45 | 3-class, so random = 0.33; but class imbalance matters more than accuracy |
   | Per-class precision | > 0.40 for SELL_VOL and BUY_VOL | We'd rather be right when we predict a regime than catch every regime |
   | Signal-following Sharpe | > 0.20 | Trade: sell straddle on SELL_VOL, buy straddle on BUY_VOL, flat on NEUTRAL |

5. **Baseline comparison**: Compare Kronos classifier against a simple heuristic: IV percentile > 70 = SELL_VOL, IV percentile < 30 = BUY_VOL, else NEUTRAL. If Kronos doesn't beat this heuristic, the complexity isn't justified.

6. **[VALIDATE EMPIRICALLY]**: Does mean pooling of Kronos hidden states outperform last hidden state? Test both.

**Timeline**: ~2 weeks. Most time is in data preparation and embedding extraction.

### Phase 2: Synthetic Options Backtest

**Objective**: Combine ktrdr directional signal + Kronos vol regime -> select structure -> compute P&L using synthetic options pricing -> measure overall system Sharpe.

**Gate**: ktrdr model trained and validated for SPY (completed in M1 — see Section 7).

#### Options Data Availability

| Source | Data | Cost | Quality |
|--------|------|------|---------|
| **yfinance** | Current options chains, VIX history, underlying OHLCV | Free | No historical chains — current snapshot only |
| **CBOE DataShop** | Historical end-of-day options data | ~$200-2000/dataset | Gold standard for US equities |
| **OptionsDX** | Historical EOD options (CSV format) | ~$50-200/symbol/year | Good quality, affordable |
| **VIX (via yfinance)** | Daily VIX close | Free | Available back to 1990 |
| **Treasury rates (FRED)** | Risk-free rate for B-S | Free | Daily, reliable |

**[KARL INPUT NEEDED]**: Budget for historical options data. Options:
- **$0 path**: Use VIX + Black-Scholes reconstruction (lower fidelity, but free). Suitable for Phase 2 proof-of-concept.
- **~$200 path**: OptionsDX data for SPY. Real bid/ask spreads, real IV surface.
- **~$1000+ path**: CBOE DataShop for comprehensive coverage.

Recommendation: Start with $0 path (Black-Scholes reconstruction) for Phase 2. If results are promising, validate with OptionsDX data before paper trading.

#### Black-Scholes Reconstruction Method

For each bar at time $t$ where the system would trade:

```
Given:
  S_t     = underlying price (from ktrdr OHLCV data)
  K       = strike price (selected by the decision matrix based on delta target)
  T       = time to expiry in years (DTE / 365)
  r       = risk-free rate (from FRED Treasury data, daily)
  sigma_t = implied volatility estimate

Option price:
  C(S, K, T, r, sigma) = S * N(d1) - K * e^(-rT) * N(d2)
  P(S, K, T, r, sigma) = K * e^(-rT) * N(-d2) - S * N(-d1)

  where:
    d1 = (ln(S/K) + (r + sigma^2/2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    N(x) = standard normal CDF

Delta (for strike selection):
  delta_call = N(d1)
  delta_put  = N(d1) - 1
```

**IV estimation for historical reconstruction** (the $0 path):

```
sigma_t = VIX_t / 100 * IV_scalar

where:
  VIX_t = VIX close on day t
  IV_scalar = adjustment factor for single-name vs index vol
              (for SPY: IV_scalar = 1.0; for single names: estimate from beta)
              IV_scalar_approx = max(0.8, min(2.0, beta_stock * 0.9 + 0.3))
```

**[ASSUMPTION]**: Using VIX as IV proxy for SPY is a close approximation (VIX is derived from SPX options, and SPY tracks SPX). For single names, this is a significant approximation. This is acceptable for proof-of-concept but NOT for production decisions. Paper trading with real IBKR chain data is the true validation.

**Known approximation errors in Black-Scholes reconstruction**:

1. **Volatility smile/skew ignored**: B-S assumes flat vol across strikes. Real options have higher IV for OTM puts (skew). Impact: underestimates put prices, overestimates bull put spread credit. Magnitude: 5-20% pricing error for OTM options.

2. **Bid/ask spread absent**: B-S gives mid-price. Real options have 5-30% bid/ask spreads for liquid names, wider for illiquid. Impact: overstates realized P&L. **Mitigation**: Apply a flat 10% haircut to all theoretical credits and a 10% markup to all theoretical debits.

3. **Early exercise ignored (European B-S for American options)**: Impact: underprices deep ITM American puts. Magnitude: small for OTM options (which is where most structures in this system operate).

4. **Discrete dividends ignored**: Impact: affects call pricing around ex-dates. **Mitigation**: Exclude bars within 5 days of known ex-dividend dates, or adjust S_t by expected dividend.

5. **No term structure**: Using a single vol number for all expiries. Real IV varies by DTE. Impact: misprices calendar spreads (which are out of scope) but also affects DTE-dependent structures.

**Synthetic backtest loop**:

```python
for each bar t in backtest_period:
    # 1. Get ktrdr signal (from SPY model trained in M1)
    ktrdr_signal = ktrdr_model.predict(features_t)  # from existing BacktestingEngine feature cache
    
    # 2. Get Kronos vol regime
    kronos_regime = kronos_classifier.predict(kronos_embedding_t)  # from pre-computed cache
    
    # 3. Get IV context
    iv_percentile_t = compute_iv_percentile(vix_history, t)
    
    # 4. Decision matrix → structure selection
    structure = decision_matrix(ktrdr_signal, kronos_regime, iv_percentile_t)
    
    # 5. If structure != NO_TRADE and confidence gates pass:
    #    a. Select strikes using B-S delta calculation
    #    b. Compute entry price using B-S
    #    c. Apply bid/ask haircut
    #    d. Record position with entry price, strikes, expiry
    
    # 6. For each open position:
    #    a. Mark to market using B-S at current S_t, updated sigma_t, reduced T
    #    b. Check exit conditions:
    #       - Take profit: P&L > 50% of max profit (for credit spreads)
    #       - Stop loss: P&L < -100% of credit received (i.e., max loss hit)
    #       - Time exit: DTE < 7 (close to avoid gamma risk)
    #       - Signal reversal: ktrdr signal flips direction
    #    c. If exit: compute exit P&L with bid/ask haircut
    
    # 7. Record equity curve, trade log
```

**Sharpe threshold for paper trading**: Sharpe > 0.50 on the synthetic backtest across at least 2 years of data, with > 50 trades. If the system produces < 50 trades in 2 years, the thresholds are too restrictive and should be loosened before concluding the strategy doesn't work.

**[VALIDATE EMPIRICALLY]**: The bid/ask haircut of 10% is a guess. If OptionsDX data is acquired, calibrate the haircut against real bid/ask spreads.

### Interaction with Existing BacktestingEngine

The options backtester is a **separate system** from ktrdr's existing `BacktestingEngine` (`ktrdr/backtesting/engine.py`). It is NOT an extension or wrapper.

**Why not extend the existing engine?**:
- The existing engine tracks stock positions (long/short with linear P&L). Options have nonlinear payoffs, Greeks, time decay, and multi-leg structure management — fundamentally different position semantics.
- The existing engine uses `PositionManager` (`ktrdr/backtesting/position_manager.py`) with commission and slippage models designed for stocks. Options have different cost structures (per-contract fees, different slippage characteristics).
- Modifying the existing engine risks breaking the stock backtesting pipeline, which is production-grade and well-tested (~29 test files).

**What it DOES reuse from ktrdr**:
- **Feature computation**: The options backtester calls ktrdr's feature pipeline (indicators + fuzzy + neural network) to produce directional signals for each bar. It can reuse the same feature cache that the existing `BacktestingEngine` builds.
- **OHLCV data**: Loaded from ktrdr's data layer (`data/{timeframe}/{Symbol}_{Timeframe}.csv`).
- **Signal generation**: Uses `DecisionFunction` (`ktrdr/backtesting/decision_function.py`) to produce `TradingDecision` for each bar, identical to how the existing engine does it.

**What is new**:
- Options position model (tracks each leg: strike, type, DTE, entry price, current Greeks)
- Black-Scholes pricing engine
- Structure-specific entry/exit logic
- Options-specific performance metrics (additional to standard Sharpe/drawdown: average theta, average delta exposure, gamma risk events)

---

## 6. Data Requirements

### Historical OHLCV (already available)

**Source**: ktrdr's data layer at `data/{timeframe}/{Symbol}_{Timeframe}.csv`
**Format**: CSV with DatetimeIndex (UTC, ISO 8601), columns: `[open, high, low, close, volume]`
**Compatibility**: Fully compatible. Kronos also accepts OHLCV DataFrames with the same column names (plus optional `amount`). ktrdr's `LocalDataLoader` (`ktrdr/data/local_data_loader.py`, `load()` method, line 171) returns the exact format needed.

**Required data range**: At least 3 years for meaningful options backtesting:
- 1 year for Kronos classifier training
- 2 years for out-of-sample options backtest
- Additional data for IV percentile computation (252-day lookback)

**SPY OHLCV data**: M1 requires SPY OHLCV data for training the ktrdr SPY model. SPY data is freely available via yfinance and must be loaded into ktrdr's data layer (`data/{timeframe}/SPY_{Timeframe}.csv`) before model training begins.

### Historical Implied Volatility Data

**For SPY/SPX (free path)**:
- VIX daily close from yfinance: `yfinance.download("^VIX", start=..., end=...)`
- Available from 1990 to present
- This IS the implied volatility of SPX options (specifically, 30-day ATM IV)

**For single names (paid path)**:
- OptionsDX: Historical EOD options data includes IV per strike/expiry
- CBOE LiveVol: Provides historical IV surface data
- `[KARL INPUT NEEDED]`: Budget and priority for single-name IV data

**IV percentile computation**:

```python
def compute_iv_percentile(iv_current: float, iv_history_252d: pd.Series) -> float:
    """IV Percentile: fraction of days in the lookback window where IV was lower than today.
    
    This is NOT IV Rank (min-max normalization). IV Percentile is more robust to
    outlier spikes — see Section 3 for the rationale.
    
    Returns 0-100. A value of 80 means current IV is higher than 80% of the
    trailing 252 trading days.
    """
    return scipy.stats.percentileofscore(iv_history_252d, iv_current, kind='rank')
```

**Note**: The same `compute_iv_percentile()` function is used in (a) label construction for the Kronos classifier, (b) signal aggregation for the decision matrix, (c) the `iv_percentile` field in `VolRegimeSignal`, and (d) the config schema thresholds (70/30). There is one metric and one function — no separate "IV Rank" concept in this system.

### Options Chain Data

**For backtesting (Phase 2)**: Not strictly needed if using Black-Scholes reconstruction. The system synthesizes option prices from underlying + VIX + risk-free rate.

**For paper/live trading (Phase 3+)**: Real options chain from IBKR:
- Available strikes and expiries
- Bid/ask for each contract
- Current IV per contract
- Open interest and volume
- Greeks (IBKR provides these)

**[ASSUMPTION]**: IBKR paper trading provides the same options chain data as live. This needs verification but is generally true for IBKR.

### Label Data for Kronos Vol Regime Classifier

**Constructed from**:
1. Historical IV: VIX daily (free) or single-name IV (paid)
2. Historical realized volatility: Computed from ktrdr's OHLCV data

```python
def compute_realized_vol(prices: pd.Series, window: int = 20) -> pd.Series:
    """Annualized realized volatility from close prices."""
    log_returns = np.log(prices / prices.shift(1))
    return log_returns.rolling(window).std() * np.sqrt(252)

def build_vol_regime_labels(
    iv_series: pd.Series,        # daily IV (e.g., VIX/100)
    prices: pd.Series,           # daily close prices
    forward_window: int = 20,    # days to compute forward RV
    iv_pctl_high: float = 70,    # percentile for SELL_VOL
    iv_pctl_low: float = 30,     # percentile for BUY_VOL
    rv_discount: float = 0.85,   # RV < IV * discount = SELL_VOL
    rv_premium: float = 1.15,    # RV > IV * premium = BUY_VOL
) -> pd.Series:
    """Returns labels: 0=NEUTRAL, 1=SELL_VOL, 2=BUY_VOL.
    
    [VALIDATE EMPIRICALLY]: Before training, print the label distribution.
    If SELL_VOL or BUY_VOL < 5% of total labels, the AND thresholds may be 
    too strict — loosen to iv_pctl_high=65 and/or rv_discount=0.90 to 
    generate more training examples.
    """
    iv_percentile = compute_iv_percentile_rolling(iv_series, 252)
    rv_forward = compute_realized_vol(prices, forward_window).shift(-forward_window)
    
    labels = pd.Series(0, index=prices.index)  # default NEUTRAL
    sell_vol_mask = (iv_percentile > iv_pctl_high) & (rv_forward < iv_series * rv_discount)
    buy_vol_mask = (iv_percentile < iv_pctl_low) & (rv_forward > iv_series * rv_premium)
    labels[sell_vol_mask] = 1  # SELL_VOL
    labels[buy_vol_mask] = 2  # BUY_VOL
    
    return labels
```

**[ASSUMPTION]**: Using 20-day forward realized vol. This matches the ~30-day options DTE target. The exact forward window should be tested: 10, 15, 20, 30 days.

**Label distribution estimate**: Expect approximately **10-15% SELL_VOL, 5-10% BUY_VOL, 75-85% NEUTRAL** on typical equity indices (SPY). These estimates account for the joint probability of both AND conditions being satisfied simultaneously — elevated IV alone occurs ~25% of the time, but the additional requirement that realized vol actually comes in lower than IV reduces this to ~10-15%. BUY_VOL is even rarer because low-IV environments that are followed by vol expansion are uncommon (~5-10%). The exact distribution should be computed empirically during M1: run `build_vol_regime_labels()` on the training data and report the actual counts before training.

**Class weights for training**: Use `[1.0, 5.0, 8.0]` for [NEUTRAL, SELL_VOL, BUY_VOL] as a starting point, then tune based on the actual observed label distribution. If NEUTRAL > 80% of labels, consider upsampling the minority classes or using focal loss instead of weighted cross-entropy.

### Risk-Free Rate

**Source**: Federal Reserve (FRED) — 3-month Treasury bill rate
**Access**: Free via `pandas_datareader` or FRED API
**Usage**: Input to Black-Scholes formula; typically 0-5% annualized

---

## 7. Integration Points with ktrdr

### M1 Prerequisite: Train ktrdr Model on SPY

**This is a concrete M1 task, not an optional prerequisite.** M1 must include training a ktrdr model on SPY/equity OHLCV data using the existing fuzzy-neural pipeline. This model gates all downstream milestones — without a trained SPY model, the synthetic backtest (M2), paper trading (M3), and all subsequent phases cannot proceed.

**Why this is needed**: ktrdr's existing models are trained on forex pairs (EUR/USD, GBP/USD, etc.). The system trades SPY equity options, so it needs a directional signal trained on SPY data. The same pipeline (OHLCV → IndicatorEngine → FuzzyEngine → FuzzyNeuralProcessor → MLP/LSTM/GRU) is used — only the training data changes.

**M1 training steps**:

1. **Acquire SPY OHLCV data**: Download SPY historical data (minimum 3 years, preferably 5+) via yfinance or other data provider. Load into ktrdr's data layer at `data/{timeframe}/SPY_{Timeframe}.csv`.

2. **Configure strategy**: Create a ktrdr strategy configuration for SPY using the existing `StrategyConfigurationV3` schema. Select indicators, fuzzy sets, and neural network architecture (recommend starting with LSTM, which has performed best on ktrdr's forex models).

3. **Train model**: Use ktrdr's standard training pipeline to train the model. The model will be saved at `models/{strategy_name}/{timeframe}_v{N}/`.

4. **Validate model**: Run ktrdr's `BacktestingEngine` on held-out SPY data. Record Sharpe ratio, accuracy, and signal distribution. The SPY model does not need to exceed the forex model's Sharpe (0.181) — any directional signal content is sufficient for options amplification. However, if the model degenerates to all-HOLD, it is not usable.

5. **Verify API availability**: Confirm the trained model can be loaded and called via `POST /api/v1/models/predict` with `symbol: "SPY"`.

**The model name referenced in this document (`trend_tb_lstm_signal_v1`) is an example** — the actual model name will be determined during M1 training and should be updated in the system configuration.

### Lux -> ktrdr REST API

**Endpoint**: `POST /api/v1/models/predict`

**Request** (from `ktrdr/api/endpoints/models.py`, `PredictionRequest`):
```json
{
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "timeframe": "1h",
    "test_date": "2026-04-18T14:30:00"
}
```

- `model_name`: Must match a trained model in `models/{strategy_name}/{timeframe}_v{N}/`
- `symbol`: Must have OHLCV data in `data/{timeframe}/`
- `timeframe`: Must be one of ktrdr's supported timeframes (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
- `test_date`: Optional. If omitted, uses the latest available bar.

**Response**:
```json
{
    "success": true,
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "test_date": "2026-04-18T14:30:00",
    "prediction": {
        "signal": "BUY",
        "confidence": 0.756,
        "signal_strength": 0.694
    },
    "input_features": {
        "1h_rsi_momentum_oversold": 0.02,
        "1h_rsi_momentum_neutral": 0.15,
        "1h_rsi_momentum_overbought": 0.83
    }
}
```

**Missing: full probability distribution**. The response currently lacks `nn_probabilities: {"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062}`. This field exists in the internal `TradingDecision.reasoning` dict but is not surfaced through the API.

**Required API change** (small):
- In `ktrdr/api/endpoints/models.py`, extend `PredictionResponse` to include `probabilities: dict[str, float]`
- In the prediction endpoint handler, pass through the `nn_probabilities` from the decision engine's reasoning dict

### ktrdr Server: Running Permanently or On-Demand?

**[KARL INPUT NEEDED]**: Two options:

1. **Persistent** (recommended): ktrdr server runs 24/7 alongside Lux on the same machine. Lux calls `localhost:8000/api/v1/models/predict`. Startup overhead is ~2-5 seconds (model loading), but this is paid once.

2. **On-demand**: Lux starts ktrdr server before each analysis cycle, waits for it to be ready, makes the prediction call, then shuts it down. Adds latency and complexity. Only justified if memory is extremely constrained.

**[ASSUMPTION]**: Using option 1 (persistent server). ktrdr's FastAPI server is lightweight — the main memory cost is the loaded neural network model(s), which are small (MLP: <1MB, LSTM/GRU: <10MB).

### Options Backtester <-> Existing BacktestingEngine

The options backtester is **separate** from the existing `BacktestingEngine`. The interaction is:

```
Shared:
  - OHLCV data (from ktrdr's data layer)
  - Feature computation (reuse IndicatorEngine + FuzzyEngine + FuzzyNeuralProcessor)
  - DecisionFunction (for generating ktrdr directional signals per bar)
  - Model loading (via ModelBundle)

Separate:
  - Position tracking (options vs stocks)
  - P&L computation (Black-Scholes vs linear)
  - Performance metrics (options-specific additions)
  - Exit logic (theta decay, gamma risk vs simple stop-loss)
```

The options backtester imports and uses ktrdr's feature pipeline as a library:

```python
from ktrdr.backtesting.decision_function import DecisionFunction
from ktrdr.backtesting.model_bundle import ModelBundle
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor

# Use ktrdr's pipeline to generate directional signals
# Then apply options-specific logic on top
```

This avoids duplicating ktrdr's feature computation while keeping options logic cleanly separated.

---

## 8. Opus 4.7 Role

### What Input Does Opus 4.7 Receive?

Opus 4.7 receives a structured JSON prompt with all relevant context:

```json
{
    "task": "select_options_structure",
    "timestamp": "2026-04-18T14:30:00Z",
    "underlying": {
        "symbol": "SPY",
        "current_price": 523.45,
        "price_change_1d": -0.82,
        "price_change_5d": 1.23
    },
    "ktrdr_signal": {
        "signal": "BUY",
        "confidence": 0.756,
        "probabilities": {"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062},
        "model": "trend_tb_lstm_signal_v1",
        "timeframe": "1h",
        "signal_source": "ktrdr research system — backtested directional signal (SPY model trained in M1)"
    },
    "kronos_regime": {
        "regime": "SELL_VOL",
        "confidence": 0.68,
        "probabilities": {"SELL_VOL": 0.68, "BUY_VOL": 0.12, "NEUTRAL": 0.20}
    },
    "vol_context": {
        "iv_percentile": 78.5,
        "current_iv": 0.22,
        "vix": 22.4,
        "rv_20d": 0.17
    },
    "options_chain": {
        "expiries_available": ["2026-04-25", "2026-05-02", "2026-05-16", "2026-06-19"],
        "relevant_strikes": {
            "2026-05-16": {
                "puts": [
                    {"strike": 515, "bid": 3.20, "ask": 3.45, "iv": 0.21, "delta": -0.22, "oi": 12500},
                    {"strike": 520, "bid": 5.10, "ask": 5.35, "iv": 0.20, "delta": -0.32, "oi": 18200}
                ],
                "calls": [
                    {"strike": 525, "bid": 4.80, "ask": 5.10, "iv": 0.19, "delta": 0.45, "oi": 15600},
                    {"strike": 530, "bid": 3.10, "ask": 3.35, "iv": 0.20, "delta": 0.33, "oi": 11300}
                ]
            }
        }
    },
    "portfolio_state": {
        "account_value": 100000,
        "buying_power": 85000,
        "open_positions": [],
        "max_risk_per_trade": 2000
    },
    "decision_matrix_suggestion": {
        "structure": "bull_put_spread",
        "reasoning": "BUY signal + SELL_VOL regime -> sell premium with directional bias"
    }
}
```

### What Output Does Opus 4.7 Produce?

```json
{
    "action": "OPEN",
    "structure": "bull_put_spread",
    "source": "opus",
    "matrix_agreed": true,
    "legs": [
        {"type": "SELL", "option_type": "PUT", "strike": 515, "expiry": "2026-05-16", "contracts": 2},
        {"type": "BUY", "option_type": "PUT", "strike": 510, "expiry": "2026-05-16", "contracts": 2}
    ],
    "expected_credit": 1.85,
    "max_risk": 630,
    "max_profit": 370,
    "breakeven": 516.15,
    "exit_plan": {
        "take_profit_pct": 50,
        "stop_loss_pct": 100,
        "time_exit_dte": 7
    },
    "reasoning": "IV percentile at 78.5 with BUY signal. Selling put spread collects elevated premium with directional support. Short 515 put at 0.22 delta gives room for pullback. Width of 5 limits max loss to $630 per spread. Two contracts = $1260 max risk within $2000 budget.",
    "confidence": "HIGH",
    "warnings": []
}
```

The `source` field indicates whether this recommendation came from Opus 4.7 (`"opus"`) or the decision matrix fallback (`"matrix"`). The `matrix_agreed` field indicates whether Opus 4.7's recommendation matches what the decision matrix would have selected — see "Validation Gap" below.

### Is Opus 4.7 in the Backtest Hot Path?

**No.** In backtesting, the decision matrix (Section 4) is applied deterministically — there is no Opus 4.7 call. The decision matrix IS the codified version of what Opus 4.7 would recommend.

Opus 4.7 is used only in **live/paper trading**, where:
- It receives the decision matrix suggestion as a starting point
- It can override or adjust based on chain-specific nuances (e.g., unusually wide bid/ask on the suggested strikes, better liquidity at adjacent strikes)
- It provides human-readable reasoning for Karl's review
- Extended thinking is enabled (latency: 10-30 seconds, which is fine for hourly/daily signals)

**[ASSUMPTION]**: Opus 4.7 is called via the Anthropic API using Lux's existing API key. No separate authentication needed.

### Validation Gap: Backtest vs Live System

The synthetic backtest (Phase 2) validates the **decision matrix only**. The live system adds Opus 4.7, which can **override** the decision matrix. These are different systems, and a Sharpe > 0.50 in synthetic backtest says nothing about what happens when Opus 4.7 makes different choices.

**What "Opus override" means**: Opus 4.7 changes the selected structure (e.g., bull put spread -> iron condor), changes strikes or expiry beyond what the matrix specified, declines to trade when the matrix would trade, or recommends a trade when the matrix would not. Any of these count as a divergence from the matrix path.

**Live tracking protocol** to close the validation gap:

1. **Tag every trade by source**: Every `TradeRecommendation` records `source: "opus" | "matrix"` and `matrix_agreed: bool`. When Opus 4.7 is called and its output matches the matrix suggestion (same structure, similar strikes), `source` is `"opus"` but `matrix_agreed` is `true`. When Opus diverges, `matrix_agreed` is `false`.

2. **Track performance separately**: The `calibration` table tracks P&L, win rate, and per-trade Sharpe contribution separately by source:
   - `matrix_agreed == true`: trades where Opus followed the matrix
   - `matrix_agreed == false`: trades where Opus overrode the matrix
   - This separation reveals whether Opus overrides add or destroy value

3. **Evaluate after sufficient data**: After 30+ live/paper trades with at least 10 Opus-override trades:
   - Compare P&L, Sharpe, and win rate between override and non-override trades
   - If Opus diverges from the matrix on >30% of trades AND Opus-override trades underperform matrix-agreed trades by >15% on P&L, disable Opus reasoning and fall back to matrix-only mode

4. **The paper trading phase (M5) is where the live system is actually validated**, not the synthetic backtest. The synthetic backtest validates the decision matrix as a strategy; paper trading validates the full system including Opus 4.7's judgment, real bid/ask spreads, execution quality, and end-to-end reliability.

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Opus 4.7 API unavailable (outage, rate limit) | Cannot get reasoning for new trades | Fall back to decision matrix output directly; record `source: "matrix"`. Log the fallback. |
| Opus 4.7 returns malformed JSON | Cannot parse trade recommendation | Validate response schema. If invalid after 2 retries, use decision matrix fallback. |
| Opus 4.7 takes > 60 seconds | Blocks the analysis cycle | Set 60-second timeout. Use decision matrix fallback on timeout. |
| Opus 4.7 recommends structure outside scope | Could introduce unwanted risk | Validate `structure` field against allowed list. Reject and retry with explicit constraint. |
| Opus 4.7 sizes position above max risk | Could over-allocate | Validate `max_risk` against `portfolio_state.max_risk_per_trade`. Hard cap enforced by Lux, not by Opus. |

**Critical design principle**: Opus 4.7 is an **advisor**, not a controller. Lux enforces all risk limits. Opus 4.7 cannot bypass position size limits, open disallowed structures, or skip confidence gates. All of its recommendations are validated before execution.

---

## 9. Open Questions / Decisions

### [KARL INPUT NEEDED]

1. **Budget for historical options data?** $0 (VIX + Black-Scholes reconstruction), ~$200 (OptionsDX for SPY), or $1000+ (CBOE DataShop)?

2. **Full probability distribution from ktrdr API**: The current `/predict` endpoint doesn't return `nn_probabilities`. Options: (a) Extend the API endpoint (~10 lines of code), or (b) call ktrdr as a Python library from Lux, bypassing REST. Recommendation: (a).

3. **ktrdr server lifecycle**: Persistent (always running) or on-demand (started per analysis cycle)? Recommendation: persistent.

4. **Max risk per trade**: 2% of account value as default? Karl may have a different risk appetite.

5. **Live trading approval gate**: Should every live trade require Karl's Telegram approval, or only trades above a certain size? Recommendation: require approval for all live trades initially, relax after 30+ successful paper trades.

6. **IBKR MCP options execution API**: I don't know the exact IBKR MCP tool signatures for options order submission. This needs investigation — does the existing IBKR integration in Lux support multi-leg options orders, or only single-leg equity orders?

7. **Additional equity options underlyings**: After SPY is validated, which other equity options to expand to? (e.g., QQQ, IWM, individual large-cap stocks)

### [VALIDATE EMPIRICALLY]

1. **Kronos embedding quality for vol classification**: Does AUC > 0.60? This is the central empirical question. If it fails, fall back to IV percentile heuristic.

2. **Kronos-mini vs Kronos-small**: Which embedding dimension (256 vs 512) produces better vol regime classification? Start with mini for speed.

3. **Mean pool vs last hidden state**: Which pooling strategy extracts more useful information from Kronos?

4. **Bid/ask haircut calibration**: The 10% flat haircut is a guess. Calibrate against real options data if available.

5. **Optimal DTE for each structure**: The design specifies 14-45 days depending on structure. Backtest should test 14, 21, 30, 45 DTE for each structure type.

6. **Label construction thresholds**: The 70/30 IV percentile thresholds and 0.85/1.15 RV/IV multipliers are starting points. Sensitivity analysis needed.

7. **Exit timing**: Take profit at 50% of max profit, or 40%, or 60%? Stop loss at max loss, or earlier at 75%? Backtest should sweep these parameters.

8. **Kronos CPU inference latency**: Expected ~100-500ms on CPU for Kronos-mini. Verify on Karl's Docker stack.

9. **Signal combination method**: The decision matrix is rule-based. An alternative is to train a small model that takes (ktrdr probabilities, Kronos regime probabilities, IV percentile) as input and outputs structure probabilities. Start with rules, test learned combination if rules work.

10. **Label distribution on actual training data**: Run `build_vol_regime_labels()` on the training data before training the classifier. If SELL_VOL < 5% or BUY_VOL < 5%, loosen thresholds (e.g., `iv_pctl_high=65`, `rv_discount=0.90`).

11. **Confidence gate sweep**: During M3, sweep `min_ktrdr_confidence` across [0.40, 0.45, 0.50, 0.55]. Select the threshold that maximizes Sharpe while keeping >= 50 trades over 2 years.

12. **SPY model performance**: What Sharpe ratio and signal distribution does the ktrdr model achieve on SPY data? Compare against forex model performance (Sharpe 0.181) as a reference point, but do not gate on exceeding it.

### [ASSUMPTION]

1. **VIX as IV proxy for SPY**: Using VIX/100 as IV for SPY is a close approximation (VIX is derived from SPX options). For other equity underlyings, this is less accurate. Acceptable for SPY-focused proof-of-concept.

2. **2% max risk per trade**: Conservative baseline. Adjustable.

3. **Opus 4.7 not in backtest hot path**: Decision matrix is applied deterministically in backtests. Opus is only used for live/paper to provide nuanced reasoning. The backtest validates the matrix; paper trading validates the full system including Opus (see Section 8, "Validation Gap").

4. **No position correlation**: Each trade is sized independently. No portfolio-level Greek management in Phase 1.

5. **IBKR paper provides real options chains**: Paper trading account gives the same chain data quality as live. Generally true for IBKR but needs verification.

6. **Kronos frozen embeddings contain vol information**: This is the central hypothesis. If false, the vol regime classifier should be replaced with a simpler approach (e.g., train a small LSTM directly on OHLCV + VIX for vol regime classification, without Kronos).

7. **ktrdr signal methodology transfers from forex to equities**: The same fuzzy-neural pipeline that produces directional signals on forex pairs can produce useful signals on SPY/equity data. This is validated during M1 model training.

8. **Lux can call Python functions directly**: Lux can import and run `KronosFeatureProvider` as a Python module, not just via REST API. This avoids needing a separate Kronos microservice.

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Target Universe** | **SPY equity options** as the primary instrument. The system is designed for equity options generically but scoped to SPY initially for tractability (most liquid options, VIX directly applicable). Other equity options (QQQ, IWM, large-cap single names) may be added after SPY is validated. Forex options are explicitly out of scope (OTC, illiquid). |
| **ktrdr** | A **strategy research system** (not a live trading system) that produces directional signals on forex pairs (EUR/USD, GBP/USD) using a fuzzy-neural pipeline. Sharpe ~0.181 from internal validation runs (training-period validation, not independent backtest); no live trading history. |
| **IV Percentile** | The fraction of days in the trailing 252-day window where IV was lower than today's IV (0-100). A value of 80 means today's IV is higher than 80% of recent days. This is the sole IV-relative metric used in this system — see Section 3 for rationale. |
| **IV Rank** | An alternative metric (NOT used in this system): `(current - 252d_low) / (252d_high - 252d_low) * 100`. Sensitive to outlier spikes; see Section 3 for why IV Percentile was chosen instead. |
| **DTE** | Days to expiry for an options contract |
| **ATM** | At-the-money: strike price equal to current underlying price |
| **OTM** | Out-of-the-money: strike price above (calls) or below (puts) current price |
| **Delta** | Rate of change of option price with respect to underlying price; also approximates probability of expiring ITM |
| **Theta** | Rate of time decay of option value per day |
| **Gamma** | Rate of change of delta; highest near expiry for ATM options |
| **Vega** | Sensitivity of option price to changes in implied volatility |
| **RV** | Realized volatility: historical standard deviation of returns, annualized |
| **B-S** | Black-Scholes option pricing model |

## Appendix B: File References in ktrdr

| Purpose | File | Key Class/Function |
|---------|------|--------------------|
| Signal output | `ktrdr/decision/base.py:26` | `TradingDecision` |
| Signal enum | `ktrdr/decision/base.py:10` | `Signal` |
| Live inference | `ktrdr/decision/orchestrator.py:216` | `DecisionOrchestrator.make_decision()` |
| Backtest inference | `ktrdr/backtesting/decision_function.py:50` | `DecisionFunction.__call__()` |
| Neural network output | `ktrdr/neural/models/base_model.py:57` | `BaseNeuralModel.predict()` |
| REST prediction | `ktrdr/api/endpoints/models.py:194` | `POST /api/v1/models/predict` |
| Backtest engine | `ktrdr/backtesting/engine.py:94` | `BacktestingEngine` |
| Backtest config | `ktrdr/backtesting/engine.py:33` | `BacktestConfig` |
| Performance metrics | `ktrdr/backtesting/performance.py:36` | `PerformanceMetrics` |
| Feature pipeline | `ktrdr/training/fuzzy_neural_processor.py:14` | `FuzzyNeuralProcessor` |
| Feature ordering | `ktrdr/config/feature_resolver.py:35` | `FeatureResolver` |
| Indicator computation | `ktrdr/indicators/indicator_engine.py:20` | `IndicatorEngine` |
| Fuzzy membership | `ktrdr/fuzzy/engine.py:28` | `FuzzyEngine` |
| Data loading | `ktrdr/data/local_data_loader.py:41` | `LocalDataLoader` |
| Model loading | `ktrdr/backtesting/model_bundle.py:230` | `ModelBundle.load()` |
| Strategy config schema | `ktrdr/config/models.py:693` | `StrategyConfigurationV3` |
| Position management | `ktrdr/backtesting/position_manager.py` | `PositionManager` |
