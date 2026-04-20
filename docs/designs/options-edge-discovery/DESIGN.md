# Options Edge Discovery — Design Document

> **Status:** Draft v1 — replaces PR #404 (`autonomous-options-trading`)
> **Author:** Claude (Opus 4.7, 1M context), in collaboration with Karl Piteira
> **Date:** 2026-04-19
> **Relationship to prior work:** Supersedes `docs/designs/autonomous-options-trading/` (PR #404). That design assumed ktrdr had directional edge and focused on building a 45-day options amplification stack on top. This design inverts the premise: we test whether edge exists before building the amplifier.

---

## 0. Reading Guide

This document is structured so that a future implementer with no context can pick it up from cold. The key claim of the doc is:

> **We do not yet know whether ktrdr's signals contain tradeable directional information.** Previous evaluations conflated "signal quality" with "stock-trading P&L after friction," which are different. Before committing to any options trading program, we need to measure signal quality the right way. Separately, options markets contain edges (like vol-premium harvesting) that do not require any ktrdr signal at all.

The program is structured as three sequential stages on the ktrdr-signal track (Track A), plus one independent non-ML track (Track B). Each stage has a pre-registered pass/fail gate. Any stage failing terminates that track cleanly — no sunk-cost escalation.

Sections 1-3 frame the problem and hypotheses. Sections 4-6 specify the three stages of Track A. Section 7 specifies Track B. Section 8 covers gates, kill criteria, and relationship to existing work. Section 9 lists open decisions.

---

## 1. Problem Statement

### What went wrong with the previous design

PR #404 (`autonomous-options-trading`) proposed a 45-day program to build an options trading system on top of ktrdr's directional signals, with Kronos-based vol regime classification and Opus 4.7 as a live-trading advisor. The structural flaw was in §1 of the design itself:

> "ktrdr is a strategy research system — not a live trading system… it is **not profitable** — internal validation runs show a Sharpe of approximately 0.181 (from training-period validation, not an independent out-of-sample backtest)"

That sentence acknowledges no edge exists, and the rest of the doc proceeds as if edge exists anyway. The central thesis — "asymmetric payoff amplifies modest edge" — is only arithmetically valid when net-of-cost edge is positive. Convex options structures on a zero-or-negative-expectancy signal bleed theta and cross the bid/ask; they do not amplify nothing into something.

Supporting evidence from squad-v2:
- `HANDOFF_M4.md`: "C402 fuzzy granularity probe… NULL — fuzzy granularity is not a lever (10th null against 0.733 floor)" — ten consecutive null results against a cost floor of approximately -$65/trade.
- `impl/predictive-features-M8`: context gate discovered to adjust `confidence_threshold` on classification models while regression models use `trade_threshold`. Prior evaluation runs on regression models evaluated a gate that never fired — an unknown quantity of "positive" results were biased by a silent bug.

### The question that should have been asked first

**Does ktrdr produce directional information that can be economically exploited?**

This is not a yes/no binary. There are three separable sub-questions:

1. **Does the signal contain directional information?** Measurable by Information Coefficient, decile analysis of realized forward returns, and hold-to-horizon P&L. Independent of trade structure and friction.
2. **If yes, what trade structure realizes it after costs?** Bar-wise stock trading is the structure ktrdr's backtest engine currently tests. That is one choice among many. Longer holding periods, position concentration, asymmetric payoff instruments (options), and pair trading are other choices.
3. **If the signal has information but is uneconomical under the current trade structure, can an alternative structure (like options) realize it?**

The previous design skipped (1) and (2), assumed "yes" to (3), and specified an implementation. This design restarts from (1).

### The friction-dominance hypothesis

A specific sub-hypothesis worth naming, because it reframes the historical null results:

> **ktrdr's per-trade P&L is dominated by transaction costs, not by signal quality. The signal may carry real directional information that is being destroyed at the trade-structure layer of the current backtest engine.**

Observable evidence for this hypothesis:
- Per-trade P&L across different ktrdr strategies clusters tightly around the cost floor (-$60 to -$65/trade). If strategies had genuinely different signal quality, variance around the cost floor would be wider.
- Squad-v2 has produced 10+ NULL experiments where different feature sets, labelers, and architectures all converge on similar P&L outcomes. That pattern is consistent with a shared friction drag dominating strategy-specific variation.
- ktrdr's backtest engine re-trades on signal changes (bar-wise). A fuzzy-neural classifier on 1h bars produces ~6 signals per day; a 20-bar label horizon implies a 20-hour holding period. The engine as configured may be trading at a higher frequency than the label was trained to imply, amortizing entry costs across too few bars of signal value.

This hypothesis is the central testable claim of Stage 0. If it holds, the signal may be fine and the backtest engine is the problem. If it fails (signal has no information even under ideal trade structure), no options overlay or NN architecture change will rescue it.

### What this document proposes

A three-stage research program on Track A (ktrdr-signal → options), plus an independent Track B (vol-premium harvesting, no ktrdr involvement):

| Track | Stages | Dependency | Effort if all pass |
|---|---|---|---|
| Track A: ktrdr signal → options | Stage 0 → Stage 1 → Stage 2 | Each stage gates the next | 30-50 dev-days |
| Track B: vol-premium harvesting | Stage B0 → Stage B1 | Independent of Track A | 10-15 dev-days |

The tracks are independent. Track B can run in parallel with any Track A stage. Track A failure at any stage does not invalidate Track B.

### Non-goals

- **Full options trading system in one PR.** That was PR #404. It is explicitly not the goal of this document.
- **Changes to ktrdr's core pipeline before Stage 0 completes.** Stage 0 uses existing models and data; no architectural changes to ktrdr.
- **Forex options, exotic options, naked short options, market making.** Same exclusions as PR #404.
- **Replacement of squad-v2.** Squad-v2 is the research vehicle for Track A and may continue running in parallel. This document does not prescribe changes to squad-v2, though Section 8 discusses how the two relate.
- **A specific trading P&L target.** The Stage 0 gate is signal quality, not P&L. The Stage 2 gate is P&L, but that is far downstream. Setting a P&L target before Stage 0 completes would repeat PR #404's error.

---

## 2. The Two Hypotheses

Frame the entire program as two independent empirical claims:

### H1 — ktrdr directional signal hypothesis

> ktrdr's neural network output, when trained on appropriate labels and evaluated without the friction of per-bar stock-style trading, contains directional information with Information Coefficient ≥ 0.03 out-of-sample on at least one trading instrument.

IC ≥ 0.03 is the conventional threshold in equity quant research for "marginal but real" signal. IC ≥ 0.05 is "strong." Below 0.03 is noise or near-noise.

If H1 is true, options may be a structurally appropriate wrapper because options have natural holding periods that amortize entry costs (see Stage 1). If H1 is false, the entire Track A program — ktrdr signal → any tradeable form — is dead, and the options overlay is irrelevant.

**This is the single most important empirical claim in the ktrdr program.** It has not been directly tested. Prior evaluation has tested the composite: `signal × bar-wise-trading-engine × friction × execution-path`. That composite has been NULL for many cycles, but the individual components have not been decomposed.

### H2 — Vol-premium harvesting hypothesis

> On SPX/SPY index options, selling defined-risk short-vol structures (iron condors, short iron butterflies) when IV percentile is elevated produces positive risk-adjusted returns, independent of any directional signal.

This is a well-documented market structure effect: implied volatility on liquid index options has historically run above realized volatility (the "volatility risk premium"). Selling premium systematically when IV percentile is high has produced positive expectancy over multiple decades. The edge is not a ktrdr edge — it is a market-structural edge that exists whether ktrdr exists or not.

If H2 is true, there is a tradeable options strategy that does not require solving the ktrdr-direction problem. If H2 is false (the premium has compressed, or the strategy was mis-specified), Track B is dead but Track A is unaffected.

### Why frame as two hypotheses

The previous design conflated these. Its decision matrix has 9 cells; one of them (HOLD + SELL_VOL → iron condor) is a vol-premium trade that does not need ktrdr. Seven cells are directional trades that require a ktrdr edge. One is NO_TRADE. The design treated all cells as a unified system gated by ktrdr signal quality.

Separating them means:
- Vol-premium harvesting can be tested and run independently. Its failure mode is isolated.
- ktrdr-directional options trades can only proceed if H1 is confirmed. Their failure mode does not pollute the vol strategy.
- When combined later (if both work), the combination is a weighted portfolio of two independently validated strategies, not a monolithic "options system."

---

## 3. Three-Stage Program (Track A) + Track B Overview

### Track A: ktrdr signal → options

```
  Stage 0: Signal Quality Diagnostic
        │
        │  Gate: IC >= 0.03 on at least one model/timeframe/label
        │        combination out-of-sample. Friction-dominance
        │        hypothesis tested via per-trade P&L decomposition.
        │
        ├──> Stage 1: Options-Native Output Redesign
        │    │
        │    │  Gate: Quantile-output ktrdr + minimal options
        │    │        overlay shows per-trade P&L lift over naive
        │    │        long-flat baseline on held-out data,
        │    │        pre-registered parameters, no tuning sweeps.
        │    │
        │    └──> Stage 2: Full Options System
        │         │
        │         │  Gate: Walk-forward validated Sharpe > 0.4
        │         │        over 3 years OOS with pre-registered
        │         │        parameters. Paper trading validates.
        │         │
        │         └──> PRODUCTION
```

### Track B: Vol-premium harvesting

```
  Stage B0: Historical Diagnostic
        │
        │  Gate: Iron condor strategy shows positive expectancy
        │        over 2016-2024 SPX data with realistic
        │        transaction costs, pre-registered parameters.
        │
        └──> Stage B1: Paper Trading
             │
             │  Gate: 60 days live paper, Sharpe > 0.3
             │
             └──> PRODUCTION
```

Each gate is binary and pre-registered. Failure ends the track.

---

## 4. Stage 0 — Signal Quality Diagnostic

**Goal:** Decide whether H1 is true. Answer: does any ktrdr model/timeframe/label combination produce directional information with IC ≥ 0.03 out-of-sample?

**Effort:** 5-8 dev-days.

**Critical property:** No new models are trained in Stage 0. No new features, no new architectures. Stage 0 is a pure evaluation pass against existing trained models. This is what makes it cheap, fast, and resistant to implementation bias — we are auditing historical results, not running a new experiment.

### 4.1 Scope

Evaluate every trained ktrdr model currently stored under `models/` that meets all of the following:
- Has documented training-period Sharpe > 0.10 (the above-noise threshold)
- Has a held-out evaluation period distinct from the training period (at least 3 months continuous)
- Uses one of: ZigZag labeler, Triple Barrier labeler, or Forward Return labeler (these are the three labelers whose forward-horizon interpretation is well-defined)

**Exclusion:** Context-gated models are excluded until the context-gate architectural mismatch is resolved (see `impl/predictive-features-M8` issue). Their prior evaluations were biased.

**Implementation note for future-me:** The list of models meeting the criteria should be generated by a script that walks `models/` and reads each model's metadata. Budget 0.5 days for this discovery step. If the list is empty or <5 models qualify, first task is retrain a small set of reference models using only the three approved labelers on EUR/USD, GBP/USD, SPY, and QQQ on 1d and 4h timeframes.

### 4.2 Metrics (all computed on out-of-sample data only)

#### 4.2.1 Information Coefficient (IC)

Spearman rank correlation between (a) the model's output and (b) the realized forward return over the label's native horizon.

- For classification models (ZigZag, Triple Barrier): output is `P(BUY) − P(SELL)` (net directional probability); realized is `(close[t+horizon] − close[t]) / close[t]` where `horizon` matches the label's lookahead/max_holding_period.
- For regression models (Forward Return): output is the predicted return; realized is the actual forward return.

Report: IC, IC t-statistic (Newey-West HAC standard errors, 5-bar lag for autocorrelation), IC by year (stability), IC by volatility regime (robustness).

**Gate:** Model passes if **OOS IC ≥ 0.03 AND IC t-statistic ≥ 2.0 AND IC in at least 2 of 3 annual sub-periods ≥ 0.02**. This guards against a single period driving the result.

#### 4.2.2 Decile analysis

At each prediction, rank the model's output into 10 equal-population deciles. Compute mean realized forward return per decile on OOS data.

- If signal contains directional information: top decile should have positive mean realized return, bottom decile negative, monotonic or near-monotonic in between.
- If signal is noise: all deciles cluster around zero or show non-monotonic patterns.

**Gate:** Model passes if **(top-decile mean realized return) − (bottom-decile mean realized return) > 0.5%** on OOS data for the label's native horizon, and the pattern is directionally consistent (top 3 deciles > bottom 3 deciles in mean realized return).

#### 4.2.3 Hold-to-horizon backtest

Unlike ktrdr's current stock backtest (which closes on signal reversal), this backtest holds every signal for the FULL label horizon regardless of subsequent signals. This is the trade structure the label was trained to predict.

- At each bar where the model outputs a confident directional signal (top or bottom decile from 4.2.2), open a position in the predicted direction.
- Hold the position for exactly `horizon` bars. Close.
- Compute per-trade gross return (no costs), transaction costs (using realistic assumptions: 5bps one-way for SPY, 10bps for other equities, 2bps for FX), and net return.
- Report: gross Sharpe, net Sharpe, win rate, per-trade P&L breakdown.

**Gate:** Model passes if **gross per-trade P&L is positive AND gross Sharpe > 0.3** on OOS data. Net Sharpe is NOT gated here — this metric isolates signal quality from friction.

**Diagnostic purpose:** The delta between gross and net Sharpe measures friction drag. If gross Sharpe > 0.3 but net Sharpe < 0.1, this is direct evidence for the friction-dominance hypothesis — the signal has information, the current trade structure can't realize it.

#### 4.2.4 Per-trade P&L decomposition

On the current ktrdr backtest results (not hold-to-horizon — the standard bar-wise backtest), decompose per-trade P&L into:

- **Gross directional P&L:** the move from entry to exit if costs were zero
- **Commissions:** sum of per-trade commission charges
- **Spread cost:** bid/ask crossing cost at entry and exit
- **Slippage:** difference between signal bar close and actual fill price
- **Holding drag:** if any (financing, dividends)

Report these as dollar-per-trade averages across the evaluation period.

**Diagnostic purpose:** This is purely explanatory, not a gate. If the NULL results from squad-v2 decompose as "gross P&L +$15/trade, costs -$75/trade, net -$60/trade," that is conclusive evidence for friction dominance. If they decompose as "gross P&L -$55/trade, costs -$5/trade, net -$60/trade," the signal genuinely has no edge under any trade structure.

### 4.3 Data splits

All metrics computed on **out-of-sample data only**. For each model:
- **In-sample period:** the original training period, used only to verify training-time metrics match what's documented
- **OOS Period A:** first 50% of post-training data (used for development of the diagnostic pipeline itself, e.g., validating that the IC computation is correct by spot-checking against hand calculations)
- **OOS Period B:** second 50% of post-training data (used for final reporting; this is the actual gate evaluation period)

Period A exists to prevent the diagnostic pipeline from itself being overfit to the final test. Do not report Period B results until the pipeline is frozen.

### 4.4 Stage 0 deliverables

1. A `stage_0_report.md` document containing, per model:
   - Model metadata (name, training config, labeler, horizon)
   - All metrics from 4.2 with confidence intervals
   - Gate pass/fail determination
   - Diagnostic commentary on friction-dominance

2. A `stage_0_summary.md` containing:
   - Count of models passing each gate
   - Cross-model patterns (e.g., "all 1d models pass IC gate, all 1h models fail" or "all ZigZag models pass decile, all Triple Barrier fail")
   - Friction-dominance determination: for how many models does hold-to-horizon gross Sharpe substantially exceed current backtest net Sharpe?
   - **Explicit decision:** pass to Stage 1, or kill Track A.

3. Code committed to `ktrdr/diagnostics/` (new module):
   - `ic.py` — Information Coefficient computation with Newey-West SE
   - `decile.py` — decile analysis
   - `hold_to_horizon.py` — hold-to-horizon backtester (NEW, distinct from existing BacktestingEngine)
   - `pnl_decomposition.py` — per-trade P&L breakdown from existing backtest results
   - `stage_0_report.py` — orchestrates all diagnostics, produces reports

### 4.5 Stage 0 gate (the big one)

Track A proceeds to Stage 1 only if **at least one model** passes all three gates (IC, decile, hold-to-horizon gross Sharpe) on OOS Period B.

If no model passes:
- If friction-dominance evidence is strong (gross Sharpe consistently > net Sharpe by 2x+ across models, but no model clears the gross-Sharpe gate), Track A is marginal. Document findings, pause Track A, consider whether a different label horizon or instrument class (via targeted retraining) might produce a signal that passes. This is a judgment call.
- If friction-dominance is weak (gross and net Sharpe both near zero), Track A is dead. ktrdr's current pipeline does not produce directional information on tested instruments. Write a `stage_0_conclusion.md` documenting the kill decision. Redirect effort to Track B or to a different research question entirely.

### 4.6 Stage 0 does NOT do

- Train new models (except the minimum retrain in 4.1 if the model pool is empty)
- Change ktrdr's core pipeline
- Test options strategies
- Evaluate vol-regime classifiers
- Touch anything in the PR #404 design

Stage 0 is a pure evaluation pass with one gate. Keep it narrow.

---

## 5. Stage 1 — Options-Native Output Redesign (sketched, gated on Stage 0 pass)

**Goal:** If Stage 0 confirms signal exists, adapt ktrdr's output shape so it can inform options structure selection economically.

**Effort estimate:** 10-15 dev-days, confirmed after Stage 0 reveals which model(s) passed.

**This section is a sketch, not an implementation plan.** The implementation plan will be written after Stage 0 completes and tells us which model family to target.

### 5.1 Why the current output shape is wrong for options

ktrdr's current classification head outputs a softmax over {BUY, HOLD, SELL}. For options:
- **The output is a categorical prediction, not a probability distribution over underlying returns.** Options pricing requires `P(S_T > K)` for any strike K. The categorical output does not support this query.
- **The probabilities are uncalibrated.** Softmax outputs of a classifier trained with cross-entropy and class weights do not represent calibrated probabilities. `P(BUY) = 0.65` does not mean 65% chance of up-move.
- **The decision thresholds (0.45, 0.60, 0.75 in PR #404's decision matrix) were chosen without calibration evidence.** They are arbitrary cuts on uncalibrated outputs.

### 5.2 Proposed redesign

Two changes, both tractable with existing ktrdr infrastructure:

**A. Quantile regression head.** Replace the classification head with a regression head that predicts multiple quantiles of the forward return distribution (e.g., 10th, 25th, 50th, 75th, 90th percentiles). Implementation: swap `ForwardReturnLabeler`'s MSE loss for quantile (pinball) loss with multi-output head. The loss function is standard and small (≈20 lines). The existing regression infrastructure supports this.

Output shape changes from:
```
{BUY: 0.65, HOLD: 0.25, SELL: 0.10}    # classification
```
to:
```
{q10: -0.028, q25: -0.012, q50: 0.003, q75: 0.019, q90: 0.041}    # quantile regression
```

The quantile output gives a full (empirical) distribution over forward returns, from which `P(S_T > K)` can be computed directly for any strike K by interpolating between quantiles.

**B. Post-hoc calibration layer.** After training, apply isotonic regression on a held-out calibration set to ensure that when the model predicts `P(return > X) = p`, the realized rate is actually `p`. This is a standard step (~30 lines) and makes the outputs directly usable for options pricing.

### 5.3 Minimal options overlay for Stage 1

Build the minimum viable options backtest to validate that the new output shape actually improves options-trade economics. No Kronos, no Opus advisor, no 9-cell decision matrix, no IBKR.

**Specification:**
- **Underlying:** one instrument, chosen based on which ktrdr model passed Stage 0 (if SPY model passes, use SPY; if a forex model passes, use a currency ETF with options like FXE)
- **Structure:** one structure type only — OTM debit call spread (for long-signal trades) or OTM debit put spread (for short-signal trades). Defined risk, standard pricing, well-documented liquidity.
- **Entry rule:** open when the model's q75 > +threshold (bullish expected) or q25 < −threshold (bearish expected). Threshold chosen pre-registered from Stage 0 decile results — not swept.
- **Strike selection:** short strike at the model's predicted q50 (50th percentile) of the forward return distribution, mapped to the underlying price. Long strike one width OTM. Width is pre-registered (suggest 1 strike or 1% of underlying, whichever is smaller).
- **Holding:** to expiry or to 50% of max profit, whichever first. DTE matches the model's label horizon (e.g., 20-bar horizon on 1d = 20 DTE).
- **P&L:** Black-Scholes reconstruction with 15% flat cost haircut (no tuning).
- **Baseline:** underlying-only long-flat strategy on same bars (same entry signal, flat if no signal, long underlying if bullish signal, flat if bearish — do not short). This is the "no options overlay" comparison.

**Stage 1 gate:** Options overlay shows **per-trade P&L lift over the underlying-long-flat baseline** on OOS data, with pre-registered parameters and no sweeps. Specifically: `(options strategy per-trade P&L) − (baseline per-trade P&L) > 0` with bootstrap 90% CI excluding zero.

If the gate passes, Stage 2 is justified. If it fails, the signal has information (Stage 0) but the options structure does not realize it economically — a smaller but still important result. Write conclusion, consider alternative trade structures (concentrated underlying positions, pair trades), or park.

### 5.4 Stage 1 deliverables (draft)

1. New output head implementation in `ktrdr/neural/models/` (quantile regression)
2. Calibration module in `ktrdr/neural/calibration/`
3. Minimum options backtest in `ktrdr/options/` (new package, kept minimal)
4. Stage 1 report documenting gate result and per-trade economics
5. Decision: proceed to Stage 2 or park

### 5.5 Stage 1 does NOT do

- Support multiple structure types (that is Stage 2)
- Include Kronos vol regime (that is deferred)
- Include Opus advisor (that is deferred)
- Connect to IBKR (that is Stage 2 or later)
- Use live data (all historical)

---

## 6. Stage 2 — Full Options System (sketched further, gated on Stage 1 pass)

**Goal:** If Stage 1 shows per-trade lift, build a production-ready options trading system that can be paper-traded.

**Effort estimate:** 20-30 dev-days (re-estimated after Stage 1 completes).

**This section is a shape, not a spec.** The full implementation plan will be written after Stage 1 confirms the minimal overlay works. Much of the scaffolding from PR #404 may be salvageable at that point — the new output shape makes it actually workable.

### 6.1 Expected scope

- Multiple options structures (not just debit spreads): bull/bear vertical spreads, iron condors, calendars if justified
- Vol-regime context as a separate input (may or may not use Kronos; a simpler IV-percentile-based classifier may suffice)
- Position management: tracking open positions, Greeks, exit rules, risk limits
- IBKR integration for paper trading
- Telegram notifications via Lux
- Calibration monitoring in live operation

### 6.2 Critical guardrails (these were missing from PR #404)

- **Walk-forward validation.** Each parameter choice evaluated on rolling OOS windows. No in-sample tuning followed by single OOS evaluation.
- **Pre-registered parameters.** The parameter set is frozen before the final evaluation. Any sweep happens on Stage 1 data, not Stage 2 evaluation data.
- **Held-out period untouched.** Reserve the most recent 12 months of data for the final pre-paper validation. Do not look at it during development.
- **Gross vs. net reporting.** Every P&L figure reports gross, net-of-cost, and the cost breakdown. Same decomposition as Stage 0.
- **Paper trading as actual validation.** Synthetic backtest Sharpe is a necessary but not sufficient condition. Paper trading with real chain data for a statistically meaningful period (60+ trading days, 30+ trades) is the real gate.

### 6.3 Stage 2 gate (placeholder, to refine after Stage 1)

Paper trading Sharpe > 0.4 over 60+ trading days with 30+ trades, matching the Sharpe range of synthetic backtest within one standard error. If paper diverges materially from backtest, investigate — do not deploy.

### 6.4 Stage 2 does NOT do (yet)

- Trade live capital (that is post-Stage-2 subject to separate decision)
- Trade multiple underlyings (start with one, add after validation)
- Use Opus 4.7 in the backtest hot path (reserve as live advisor, and stage-validate via shadow mode on backtest bars first)

---

## 7. Track B — Vol-Premium Harvesting (independent of Track A)

**Goal:** Test whether systematic short-volatility on SPX/SPY index options produces positive risk-adjusted returns.

**Effort:** 10-15 dev-days total (Stage B0: 5-7 days; Stage B1: 5-8 days setup + 60 days paper trading).

**Independent of Track A.** This track uses no ktrdr signal, no fuzzy-neural pipeline, no Kronos. It tests a market-structural edge that exists regardless of whether ktrdr works.

### 7.1 Why this is worth doing in parallel

- It does not depend on Stage 0 resolution. If Stage 0 kills Track A, Track B may still succeed — two shots on goal.
- The implementation is mostly standard. The vol-risk-premium literature is decades deep. We are not inventing anything.
- Effort per-unit-EV is favorable compared to Track A's uncertainty cascade.
- If it works, it provides cash flow while Track A is being developed or re-thought.

### 7.2 Strategy specification (Stage B0)

**Core thesis:** Sell defined-risk vol structures when IV percentile is elevated; stay flat when it is not.

**Instrument:** SPX options (European, cash-settled, large notional per contract) preferred for tax efficiency and no early-assignment risk. SPY options as alternative if SPX minimum capital requirement is too high.

**Structure:** Iron condor only. Four legs per position:
- Sell OTM put at ~0.16 delta
- Buy further OTM put at ~0.10 delta (wing width = 1-2 strikes)
- Sell OTM call at ~0.16 delta
- Buy further OTM call at ~0.10 delta (wing width = 1-2 strikes)

Delta targets are pre-registered and do not sweep.

**Entry rule:**
- IV percentile (252-day lookback on VIX) > 60 → enter position
- IV percentile ≤ 60 → stay flat, do not open new positions
- DTE: 30-45 days at entry

**Exit rule:**
- Close at 50% of maximum profit OR at 21 DTE, whichever first
- Hard stop: close if loss exceeds 200% of credit received

**Sizing:** Risk no more than 2% of account per position. Maximum 2 concurrent positions.

**No tuning. No sweeps.** The parameters above are pre-registered. The only degree of freedom in Stage B0 is whether to use SPX or SPY (choose once, document).

### 7.3 Stage B0 — Historical diagnostic

**Period:** 2016-01-01 through 2024-12-31 (covers multiple regimes: low-vol 2017, 2018 vol-crush, COVID 2020, 2022 bear market).

**Method:** For each trading day in the period:
1. Compute IV percentile from VIX rolling 252-day window
2. If > 60 and no open positions: select strikes from historical option chain (OptionsDX data if budget permits, Black-Scholes reconstruction from VIX if not), enter position
3. Track position mark-to-market daily, apply exit rules
4. Record all fills with realistic cost assumptions (SPX options: $0.50 per contract commission, 5bps spread; or B-S reconstruction + 15% cost haircut)

**Metrics:** Total return, annualized Sharpe, maximum drawdown, win rate, average P&L per position, trade frequency.

**Gate:** Track B proceeds to Stage B1 only if:
- **Annualized Sharpe > 0.5 gross** AND **> 0.3 net of costs** over the full period
- **Maximum drawdown < 30%** (iron condors are defined-risk, so drawdowns come from sequencing losses — reasonable cap)
- **No single year contributes > 50% of total return** (stability check)
- **At least 40 trades over the period** (statistical power)

### 7.4 Stage B1 — Paper trading

If Stage B0 passes, implement in Lux as a scheduled capability:
- Daily IV-percentile check
- Entry/exit logic per 7.2
- IBKR paper trading via existing IBKR integration
- Telegram notifications for fills

**Gate:** 60+ trading days of paper operation, 5+ positions taken, realized Sharpe > 0.3 net-of-cost, behaves qualitatively like Stage B0 backtest.

### 7.5 Track B deliverables

- **Stage B0:** `docs/designs/options-edge-discovery/stage_b0_report.md`, backtest code in `ktrdr-options/vol_premium/` or similar independent module, results
- **Stage B1:** paper trading running in Lux, 60-day review document

### 7.6 Track B interaction with Track A

None by design in Stages B0 and B1. Both tracks may succeed independently. If Track A Stage 2 completes successfully, a future (unscoped) combined design could blend the two — e.g., Track A's directional signal could inform iron condor strike placement. That is a later problem.

---

## 8. Decision Gates, Kill Criteria, Relationship to Existing Work

### 8.1 Decision gates (consolidated)

| Gate | Stage | Criterion | If fail |
|---|---|---|---|
| G0 | Stage 0 | At least one model: OOS IC ≥ 0.03 AND decile spread > 0.5% AND hold-to-horizon gross Sharpe > 0.3 | Kill Track A; write conclusion; redirect squad-v2 research question or deprecate |
| G1 | Stage 1 | Options overlay per-trade P&L lift over underlying-only baseline, pre-registered, OOS | Park Track A at Stage 2; signal has information but options are not the right wrapper |
| G2 | Stage 2 | Walk-forward Sharpe > 0.4 on held-out 12 months, pre-registered params | Refine or park; do not paper-trade |
| G2-paper | Stage 2 | Paper Sharpe > 0.4 over 60+ days, matches backtest within one SE | Refine or park; do not go live |
| GB0 | Stage B0 | Net-of-cost Sharpe > 0.3 over 2016-2024, max DD < 30%, ≥40 trades | Kill Track B |
| GB1 | Stage B1 | Paper Sharpe > 0.3 over 60 days | Refine parameters or kill |

### 8.2 Kill criteria for the whole program

Both tracks killed at first gate → deprecate the autonomous-options-trading thesis for ktrdr. Document conclusions in `docs/designs/options-edge-discovery/program_outcome.md`. Redirect squad-v2's research question (see 8.4).

Stage 0 kills → Track A dead, Track B continues. Do not re-attempt Track A without a materially new hypothesis (different model family, different instrument class, or a new feature set that was not available during Stage 0).

### 8.3 Pre-registration principle

Every parameter that appears in any gate computation must be specified in writing BEFORE the gate is evaluated. "Pre-registered" means:
- Written down in a dated markdown file (e.g., `stage_0_params.md`) committed to the repo
- Git hash recorded
- The evaluation code reads parameters from that file; it does not take command-line overrides at evaluation time

This is the only defense against the "knobs were turned until Sharpe exceeded 0.5" failure mode that made PR #404's M3 gate meaningless.

### 8.4 Relationship to squad-v2

Squad-v2 is ktrdr's research platform for discovering directional strategies. It has produced 10+ consecutive NULL experiments on 1h forex. This design takes no position on whether squad-v2 should continue running during Stage 0 — that is a separate decision based on the Stage 0 outcome.

Three possible relationships:

1. **If Stage 0 passes on a model squad-v2 has trained:** squad-v2's research is vindicated. The previous null results reflected evaluation methodology, not model quality. Continue squad-v2 with updated evaluation (IC, decile, hold-to-horizon) as primary metrics.
2. **If Stage 0 passes on a model that pre-dates squad-v2 (e.g., an older manually-trained model):** squad-v2 has been exploring in the wrong direction. Revise its research question or deprecate.
3. **If Stage 0 fails entirely:** ktrdr's current pipeline does not produce directional information on tested instruments. Squad-v2 cannot fix this by training more variations. The research question needs to change — possibly to "what does produce information on these instruments?" which may imply different features, different instruments, or a different prediction target (volatility, autocorrelation, order-flow proxies) rather than next-horizon direction.

### 8.5 Relationship to Lux / agent-memory

Lux is the orchestration runtime (agent-memory-based). Stage B1 paper trading specifically runs as a Lux capability: dialogue tick loop executes the daily IV-percentile check, Telegram channel delivers notifications, beliefs capture lessons learned from each closed position, cost intelligence bounds any API spend.

Stage 2 of Track A (if reached) also runs on Lux. The design here makes no changes to Lux itself — it uses Lux's existing primitives. Any Lux-layer changes (new skills, new MCP tools) are scoped in separate Lux design documents.

Important operational concern: **Lux is already the user's coding partner and runs squad-v2 as a capability.** Adding trading-operator responsibilities is a different reliability mode. Before Track B or Track A Stage 2 runs with any real money (not just paper), Lux must demonstrate it can *not* execute under bad signals — specifically, the stale-nudge incident from squad-v2 HANDOFF_M4 (where the Director force-ran an experiment the Critic flagged as pointless) must be resolved. Paper trading is lower risk and can proceed in parallel with that fix.

### 8.6 Relationship to PR #404

PR #404 is superseded by this document and should be closed. Reasons:
- Its core premise (ktrdr edge exists) is what this document is testing, not assuming
- Its M1 gate ("any directional signal content") is unfalsifiable
- Its M3 gate (synthetic B-S Sharpe > 0.5 after parameter sweep) cannot distinguish edge from tuning

Material PR #404 may salvage:
- The Kronos vol-regime classifier concept (usable in Stage 2 or Track B as a richer IV-context signal, if it clears AUC > baseline IV-percentile heuristic — which is a separate diagnostic not scoped here)
- The Black-Scholes engine specification (usable in Stages 1 and B0 for P&L reconstruction)
- The IBKR MCP investigation ([DECISION NEEDED] in PR #404 Task 5.1 — this work is still needed before Stage B1)
- The per-component architecture specs (useful as a reference if Stage 2 proceeds, not as a commitment)

---

## 9. Open Decisions and Pre-Registered Parameters

### 9.1 Decisions required before Stage 0 begins

1. **Options data budget for Stage B0:** $0 (B-S reconstruction from VIX), ~$200 (OptionsDX for SPY/SPX historical), $1000+ (CBOE DataShop full surface). Recommendation: start $0 for Stage B0 feasibility, spend $200 if results look promising before Stage B1.
2. **Squad-v2 during Stage 0:** Continue, pause, or redirect? Recommendation: pause active cycles for the duration of Stage 0 (5-8 days). Stage 0's outcome will inform squad-v2's research question.
3. **Parallel or sequential tracks:** Run Track A Stage 0 and Track B Stage B0 in parallel (different people / different time slices), or sequential (Stage 0 first, then Stage B0)? Recommendation: parallel. They are truly independent and share no code paths.
4. **Who runs what:** Stage 0 is a data-analysis task (mostly pandas, matplotlib, scipy.stats). Stage B0 is a backtest engineering task. They have different skill profiles. Assign accordingly.

### 9.2 Pre-registered parameters (Stage 0)

These must be committed to `docs/designs/options-edge-discovery/stage_0_params.md` before Stage 0 evaluation runs. Initial values:

- IC gate: OOS IC ≥ 0.03, t-stat ≥ 2.0, 2-of-3 annual periods ≥ 0.02
- Decile gate: top-minus-bottom mean realized return > 0.5%, top-3 > bottom-3
- Hold-to-horizon gross Sharpe gate: > 0.3
- OOS split: 50% Period A (pipeline development), 50% Period B (final evaluation)
- Newey-West lag: 5 bars
- Transaction cost model: SPY/major ETFs 5bps one-way, other equities 10bps, FX 2bps
- Slippage model: 1 bar of bid/ask crossing, approximated as 50% of bar's H-L range for equities, 1 pip for FX

### 9.3 Pre-registered parameters (Stage B0)

To commit before Stage B0 runs:

- Instrument: SPX preferred, SPY if capital constraint
- Structure: iron condor, 0.16Δ short strikes, 0.10Δ long strikes
- DTE: 30-45 at entry, close at 21 DTE or 50% profit
- IV percentile threshold: 60 (above = enter)
- Lookback for IV percentile: 252 trading days of VIX
- Max concurrent positions: 2
- Position size: 2% of account at risk
- Hard stop: 200% of credit received
- Cost model: SPX $0.50/contract commission + 5bps spread, OR B-S reconstruction + 15% haircut
- Backtest period: 2016-01-01 through 2024-12-31

### 9.4 Items that may surface later and should be flagged when they do

- If Stage 0 reveals a specific labeler is dominant (e.g., all passing models use ZigZag), Stage 1's quantile-regression redesign should use the analogous labeler for the new output shape.
- If Stage 0 reveals timeframe matters strongly (e.g., 1d passes, 1h does not), Stage 2 should restrict to the passing timeframe even if it means fewer trade opportunities.
- If Track B Stage B0 fails on the full 2016-2024 period but passes on a sub-period, investigate regime dependence before concluding. The vol-risk-premium has been observed to compress and expand over decades; if compression is the cause, that is a different kind of failure than "strategy never worked."

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **IC (Information Coefficient)** | Spearman rank correlation between predicted and realized forward returns. Standard quant-finance signal quality metric. IC > 0.03 is meaningful, > 0.05 is strong. |
| **Decile analysis** | Ranking predictions into 10 equal-population buckets and measuring mean realized outcome per bucket. Tests whether high-confidence predictions actually outperform. |
| **Hold-to-horizon backtest** | Backtest that holds every entered position for exactly the label horizon, regardless of subsequent signals. Tests the trade structure the label was trained to predict. |
| **Friction-dominance hypothesis** | The claim that per-trade P&L is dominated by transaction costs, not signal quality. Testable via gross-vs-net Sharpe decomposition. |
| **Pre-registration** | Committing all parameters of a gate evaluation to a dated markdown file before the evaluation runs. Prevents post-hoc parameter selection. |
| **Vol-risk-premium (VRP)** | Historical observation that implied volatility on index options has exceeded subsequent realized volatility. Basis of Track B. |
| **Iron condor** | Four-leg defined-risk options position: sell OTM put + buy further OTM put + sell OTM call + buy further OTM call. Profits if underlying stays within a range and IV contracts. |
| **Quantile regression** | Regression that predicts specified quantiles of the output distribution rather than the mean. Pinball loss function. Produces a distribution, not a point estimate. |
| **Calibration (probabilistic)** | Property that predicted probabilities match observed frequencies. Isotonic regression on a held-out set is the standard post-hoc calibration method. |

## Appendix B: What This Doc Does NOT Cover

- Implementation-ready specifications for Stages 1 and 2 (deferred until Stage 0 outcome is known)
- Kronos vol-regime classifier details (may be revived in Stage 2 or Track B if useful, with its own AUC-vs-heuristic gate)
- Opus 4.7 live advisor role (deferred to Stage 2; must be validated via shadow mode on backtest before live use)
- IBKR MCP options order capabilities ([DECISION NEEDED] — needed before Stage B1 paper trading)
- Full component specs (see PR #404 for reference; not the commitment here)
- Squad-v2 operational fixes (stale nudges, Inventor ordering, double cycle_complete — tracked in squad-v2 design, not here)
- Lux capability interface for trading (uses existing primitives; no new Lux-layer design required)

## Appendix C: Change Log

| Date | Version | Author | Summary |
|---|---|---|---|
| 2026-04-19 | Draft v1 | Claude + Karl | Initial replacement for PR #404. Three-stage Track A + independent Track B. Stage 0 implementation-ready; Stages 1/2 sketched; Track B implementation-ready. |
