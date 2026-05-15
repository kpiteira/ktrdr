# Options Edge Discovery — Design Document

> **Status:** Draft v2 — addresses hostile methodology review on PR #405
> **Author:** Claude (Opus 4.7, 1M context), in collaboration with Karl Piteira
> **Date:** 2026-05-15
> **Relationship to prior work:** Supersedes `docs/designs/autonomous-options-trading/` (PR #404). That design assumed ktrdr had directional edge and focused on building a 45-day options amplification stack on top. This design inverts the premise: we test whether edge exists before building the amplifier.
> **v2 changes:** Rewrites Stage 0 to pre-register the model universe and seal a confirmation set (fixing the discovery/confirmation conflation in v1). Splits the IC diagnostic per labeler family with proper event-end alignment and purging. Adds portfolio accounting to the hold-to-horizon engine. Tightens the Stage 1 quantile spec (monotonicity, tail extrapolation, moneyness-stratified calibration). Demotes the $0 B-S/VIX path to plumbing smoke test only — GB0 evaluation requires real option-chain data. Inserts a Bdiag VRP test plus stress windows and parameter-sensitivity sweep into Stage B0. Rewrites Stage B1 as operational validation, not statistical.

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

### 4.1 Scope, pre-registration, and confirmation-set protocol

Stage 0 evaluates a **frozen, pre-registered universe of models** against a **sealed confirmation set**. Screening N models and reporting the best is data mining; we control for it explicitly.

**Step 1 — Enumerate the model universe.** A script walks `models/` and emits every trained model meeting:
- Has documented training-period Sharpe > 0.10
- Uses ZigZag, Triple Barrier, or Forward Return labeler (other labelers excluded — their forward-horizon semantics are not well-defined for this diagnostic)
- Has at least 24 months of data following its training cutoff
- Is not context-gated (the context-gate architectural mismatch in `impl/predictive-features-M8` invalidates prior evaluations)

The full list is committed to `stage_0_model_universe.md` with model name, git hash of training config, labeler family, native horizon, instrument, and post-training data range. **This file is the universe.** No model not in this file is evaluated in Stage 0. No model is added to the file after Step 4 runs.

**Step 2 — Reference retrain if the universe is under-powered.** If fewer than 5 models qualify, train a fixed reference set first: ZigZag-classification, Triple-Barrier-classification, and Forward-Return-regression on EUR/USD, GBP/USD, SPY, and QQQ at 1d and 4h timeframes (up to 24 models). Training cutoff is 24 months before the present. The Period A / Period B split (Step 3) is held out from training entirely. Once trained, the reference set is appended to the universe file and the universe is locked.

**Step 3 — Two-stage data split per model.** Of the model's post-training data:
- **Period A (Discovery)** — first 12 months. Used for diagnostic pipeline validation AND for candidate selection within each labeler family.
- **Period B (Confirmation)** — second 12 months. **Sealed.** No Stage 0 metric is computed on Period B until Step 5. The confirmation script reads Period B from a path that does not exist until Step 5 is unlocked by signed commit of `stage_0_candidates.md`.

**Step 4 — Discovery on Period A.** Run all metrics (§4.2.1–4.2.4) on Period A for every model in the universe. Report. Within each labeler family (ZigZag, Triple Barrier, Forward Return), select **at most one candidate** by the pre-registered rule: highest Period A IC; ties broken by decile spread; further ties broken by gross hold-to-horizon Sharpe. At most 3 candidates total proceed to confirmation. Candidates are committed to `stage_0_candidates.md`. **Selection criteria are pre-registered; the rule is not changed after viewing results.**

**Step 5 — Confirmation on Period B.** Evaluate the (up-to-3) candidates against gates G0a/G0b/G0c (§4.5) on Period B. Apply **Holm-Bonferroni correction** to the IC t-statistic gate over the number of candidates: with 3 candidates, the IC t-stat thresholds become ≈2.39 / 2.13 / 2.00 in rank order of p-value. The decile-spread and gross-Sharpe gates are effect-size gates and use unadjusted thresholds.

**No re-selection after Period B.** If no candidate clears the confirmation gates, Period B is spent. Track A is killed or paused per §4.5. Promoting additional models from the universe into Period B retroactively is forbidden — that path leads back to the data-mining failure mode.

### 4.2 Metrics (all computed on out-of-sample data only)

#### 4.2.1 Information Coefficient (IC) — label-aware

Spearman rank correlation between model output and the **label's own realized outcome**, with event-end alignment, purging, and HAC standard errors matched to the label's overlap structure. A fixed `close[t+H] − close[t]` target is wrong for ZigZag and Triple Barrier — their labels are event-based, not fixed-horizon. Three IC computations, one per labeler family.

**Forward Return labeler (regression).**
- Output: predicted return.
- Realized: `(close[t+H] − close[t]) / close[t]` for fixed horizon H.
- Overlap: consecutive realized returns share H−1 bars of return path → use **Newey-West HAC standard errors with lag = H** (one full horizon). The v1 doc's fixed 5-bar lag was wrong wherever H > 5.

**ZigZag labeler (classification).**
- Output: `P(BUY) − P(SELL)` (net directional probability).
- Realized: signed return from `t` to the next ZigZag pivot — *not* a fixed horizon. For each sample, the event end is the timestamp of the next pivot; the realized outcome is `(close[pivot] − close[t]) / close[t]` with sign matching the direction of the pivot leg.
- Overlap: samples whose `[t, pivot]` intervals overlap share dependence. Use **clustered standard errors with cluster = ZigZag segment index** (all samples falling inside the same up- or down-segment cluster together), or as fallback Newey-West with lag = average event duration in bars over Period A.

**Triple Barrier labeler (classification).**
- Output: `P(UPPER_HIT) − P(LOWER_HIT)`.
- Realized: continuous return at event end, `(close[event_end] − close[t]) / close[t]`, where `event_end` is the bar of first barrier touch, or `t + max_holding_period` for vertical-barrier timeouts.
- Overlap: events have variable duration. Apply **López de Prado purging and embargo**: drop any sample whose event window crosses the Period A / Period B boundary; embargo `ceil(max_holding_period / 10)` bars after each event end before the next sample is admitted to the IC computation. HAC: Newey-West with lag = mean event duration on Period A.

For all three families, report: IC, IC t-statistic (with the HAC/clustering specified above), IC by year, IC by realized-volatility regime (rolling 30-bar return-std bucketed into terciles on Period A and frozen for Period B).

**Gate G0a:** Model passes if **OOS IC ≥ 0.03 AND IC t-statistic ≥ Holm-Bonferroni threshold (2.39/2.13/2.00 for 3 candidates) AND IC ≥ 0.02 in at least 2 of 3 annual sub-periods of Period B**.

#### 4.2.2 Decile analysis

At each prediction, rank the model's output into 10 equal-population deciles. Compute mean realized forward return per decile on OOS data.

- If signal contains directional information: top decile should have positive mean realized return, bottom decile negative, monotonic or near-monotonic in between.
- If signal is noise: all deciles cluster around zero or show non-monotonic patterns.

**Gate:** Model passes if **(top-decile mean realized return) − (bottom-decile mean realized return) > 0.5%** on OOS data for the label's native horizon, and the pattern is directionally consistent (top 3 deciles > bottom 3 deciles in mean realized return).

#### 4.2.3 Hold-to-horizon backtest — with portfolio accounting

Unlike ktrdr's current stock backtest (which closes on signal reversal), this engine holds every entered position for exactly `horizon` bars regardless of subsequent signals — the trade structure the label was trained to predict. But signals fire faster than the holding period, so a naive "open every signal" rule creates overlapping positions and implicit leverage. **Gross per-trade Sharpe under unlimited overlap is not signal quality; it is an exposure-construction artifact.** The engine therefore enforces explicit portfolio accounting.

**Engine spec:**
- Maintain a notional capital pool of $100k (absolute size does not affect Sharpe). Track open positions and remaining capital each bar.
- At each bar where the model outputs a top-decile (long) or bottom-decile (short) signal:
  - If concurrent positions = `N_max`, **skip the signal** (do not enter, do not queue).
  - Else, allocate `1 / N_max` of pool capital to the new position; enter at next-bar open (no in-bar lookahead).
- Hold each position for exactly `horizon` bars; close at that bar's close.

**Pre-registered portfolio cap.** `N_max = clip(ceil(horizon / median_signal_spacing_PeriodA), 1, 10)`, computed per-model from Period A signal frequency and frozen in `stage_0_params.md` before Period B is touched. This keeps expected gross exposure ≤ 100% of capital given the model's signal rate.

**Costs:** 5bps one-way for SPY/major ETFs, 10bps for other equities, 2bps for FX, applied at entry and exit on the allocated-capital fraction.

**Metrics reported:**
- **Gross portfolio Sharpe** (annualized from bar-level capital-weighted returns, cost-free).
- Gross per-trade mean P&L.
- Net portfolio Sharpe (after costs).
- Average concurrent positions; capacity utilization (fraction of signals admitted vs skipped).
- Per-trade P&L distribution.

**Gate G0c:** **Gross *portfolio* Sharpe > 0.3 AND gross per-trade mean P&L > 0** on Period B.

The portfolio metric (not per-trade Sharpe) is gated because per-trade Sharpe under overlapping holds is biased by exposure construction. The gross-vs-net portfolio Sharpe delta still measures friction drag and is reported as the friction-dominance diagnostic. A large *per-trade-vs-portfolio* Sharpe spread is a separate diagnostic that says "the model produces too many signals for its holding period" — the fix in that case is "trade less," not "find a better signal."

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

All metrics on **out-of-sample data only**. For each model:
- **In-sample period:** original training period; consulted only to verify documented training-time metrics.
- **Period A (Discovery):** first 12 months of post-training data. Used for diagnostic pipeline development, threshold spot-checks, and candidate selection within each labeler family (§4.1 Step 4).
- **Period B (Confirmation):** second 12 months of post-training data. **Sealed until Step 5.** Used once, on the (≤3) selected candidates, for the actual gate evaluation.

The 12+12 month structure replaces v1's 50/50 split. Confirmation-set discipline is what gives Stage 0 statistical interpretability: the diagnostic pipeline, parameter choices, and candidate-selection rules are all frozen on Period A; Period B is touched once.

### 4.4 Stage 0 deliverables

1. `stage_0_model_universe.md` — frozen universe (Step 1 / Step 2 output). Committed before Step 4 runs.
2. `stage_0_params.md` — pre-registered parameters: gate thresholds, HAC lag rules per labeler family, portfolio cap per model, candidate-selection rule, Holm-Bonferroni table. Committed before Step 4 runs.
3. `stage_0_period_a_report.md` — Discovery results, per model: all metrics from §4.2 with confidence intervals.
4. `stage_0_candidates.md` — the (≤3) candidates promoted to confirmation, one per labeler family, with the selection trace. Committed before Step 5 runs.
5. `stage_0_period_b_report.md` — Confirmation results for those candidates, with G0a/G0b/G0c pass/fail under Holm-Bonferroni-adjusted thresholds.
6. `stage_0_summary.md` — cross-model patterns, friction-dominance determination, and **explicit decision:** pass to Stage 1, pause Track A, or kill.

Code committed to `ktrdr/diagnostics/` (new module):
- `ic.py` — label-aware IC with the three HAC/clustering modes (§4.2.1)
- `decile.py` — decile analysis
- `hold_to_horizon.py` — portfolio-accounted hold-to-horizon engine (§4.2.3)
- `pnl_decomposition.py` — per-trade P&L breakdown from existing backtest results
- `stage_0_report.py` — orchestrates Period A and Period B runs; refuses to compute Period B metrics unless `stage_0_candidates.md` is committed and signed.

### 4.5 Stage 0 gate (the big one)

Track A proceeds to Stage 1 only if **at least one Step-5 candidate** clears **all three confirmation gates on Period B simultaneously**:
- **G0a (IC):** OOS IC ≥ 0.03 AND IC t-stat ≥ Holm-Bonferroni threshold AND ≥ 2 of 3 annual sub-periods at IC ≥ 0.02.
- **G0b (Decile):** top-minus-bottom mean realized return > 0.5% on Period B, top-3 deciles > bottom-3 deciles in mean realized return.
- **G0c (Hold-to-horizon, portfolio-accounted):** gross portfolio Sharpe > 0.3 AND gross per-trade mean P&L > 0.

If no candidate clears all three:
- **Friction-dominance strong** (across candidates: gross portfolio Sharpe consistently exceeds existing ktrdr-backtest net Sharpe by 2× or more, but no candidate clears the 0.3 gross-Sharpe gate) → Track A is **paused, not killed.** Document. Consider one of: a different label horizon or instrument class for a *separately* pre-registered Stage 0 round (Period B is spent for this universe; a new universe needs new data periods). No silent re-runs against the same Period B.
- **Friction-dominance weak** (gross and net both near zero) → Track A **killed.** Write `stage_0_conclusion.md`. Redirect effort to Track B or a different research question.

The discipline: Period B is single-shot per universe. Promoting more candidates from the universe to Period B retroactively, or re-tuning the diagnostic pipeline after seeing Period B results, would convert Stage 0 back into the data-mining protocol it is designed to avoid.

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

**A. Quantile regression head.** Replace the classification head with a regression head predicting **9 quantiles** of the forward return distribution: q05, q10, q25, q40, q50, q60, q75, q90, q95.

Loss = sum of pinball losses across the 9 levels. **Monotonicity enforced by construction**, not by hope: parametrize as
```
q_05 = base
q_k  = q_{k-1} + softplus(delta_k)    for k in {10, 25, 40, 50, 60, 75, 90, 95}
```
so quantile crossing is impossible. Verified post-hoc on validation that no crossing occurs (a sanity check, since the parametrization makes it structural).

Output shape changes from:
```
{BUY: 0.65, HOLD: 0.25, SELL: 0.10}                  # classification
```
to:
```
{q05, q10, q25, q40, q50, q60, q75, q90, q95}         # quantile regression
```

**Tail extrapolation rule.** Options strikes live in tails that quantile interpolation cannot reach. Beyond q95 and below q05, price strikes under a **Generalized Pareto Distribution (GPD) tail fit**: per-training-fold, fit GPD parameters to empirical exceedances above q95 (and below q05) on the training set; freeze those parameters as part of the model. Between consecutive quantiles, use **piecewise-linear interpolation in (cumulative-probability, return) space**. No tuning at inference.

This is an explicit assumption, not a hidden one — and the GPD parameters are reported with the model so reviewers can evaluate them.

**B. Post-hoc calibration with moneyness stratification.** Isotonic regression on a held-out calibration set, applied per quantile level. Calibration report includes **reliability diagrams stratified by moneyness bucket** (deep-ITM, ITM, ATM, OTM, deep-OTM as defined by `(K - F) / (F * sigma * sqrt(T))`). This catches strike-dependent miscalibration that aggregate reliability hides — the regime where options pricing is most sensitive.

### 5.3 Minimal options overlay for Stage 1

Build the minimum viable options backtest to validate that the new output shape actually improves options-trade economics. No Kronos, no Opus advisor, no 9-cell decision matrix, no IBKR.

**Specification:**
- **Underlying:** one instrument, chosen based on which ktrdr model passed Stage 0 (if SPY model passes, use SPY; if a forex model passes, use a currency ETF with options like FXE)
- **Structure:** one structure type only — OTM debit call spread (for long-signal trades) or OTM debit put spread (for short-signal trades). Defined risk, standard pricing, well-documented liquidity.
- **Entry rule:** open when the model's q75 > +threshold (bullish expected) or q25 < −threshold (bearish expected). Threshold chosen pre-registered from Stage 0 decile results — not swept.
- **Strike selection:** short strike at the model's predicted q50 (50th percentile) of the forward return distribution, mapped to the underlying price. Long strike one width OTM. Width is pre-registered (suggest 1 strike or 1% of underlying, whichever is smaller).
- **Holding:** to expiry or to 50% of max profit, whichever first. DTE matches the model's label horizon (e.g., 20-bar horizon on 1d = 20 DTE).
- **P&L:** Real option-chain data for the chosen underlying (same data feed as Track B Stage B0). If chain data is not yet available at Stage 1 start, B-S reconstruction with 15% flat cost haircut is acceptable *for this minimal overlay only* (debit spreads are less skew-sensitive than iron condors and the gate compares two strategies under the same pricing model), with the limitation flagged in the Stage 1 report. No tuning.
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

#### 7.3.1 Data requirement

The v1 doc offered a $0 path (Black-Scholes reconstruction from VIX) as a fallback. **That path is demoted to plumbing smoke test only and cannot be used to evaluate gate GB0.**

VIX is a 30-day variance index. It provides: no skew, no smile, no strike-specific implied vol, no bid/ask, no realistic iron-condor fill. Iron condor edge depends precisely on the put/call skew shape, short-strike-to-wing premium ratio, and bid/ask costs that VIX cannot reconstruct. A B-S-from-VIX backtest would test a fictional symmetric surface — exactly where short-vol edge and tail risk are most sensitive.

**Two valid uses of the B-S/VIX path remain:**
1. Code plumbing smoke test (engine wiring, position lifecycle, accounting balance) on a synthetic surface.
2. Sanity bound: if even the optimistic symmetric-surface B-S backtest returns a negative Sharpe over the period, the strategy has bigger problems than data quality.

**GB0 evaluation requires real historical option chain data.** Minimum: OptionsDX SPY/SPX daily snapshots (~$200 one-time). Preferred: CBOE DataShop or OptionMetrics for full surface and intraday. **This makes Stage B0 conditional on a data-budget decision (§9.1).**

#### 7.3.2 Bdiag — direct VRP diagnostic (runs before strategy backtest)

A positive iron condor Sharpe bundles vol-risk-premium with IVP timing, strike selection, exit rules, and fill assumptions. Before testing the strategy, test the hypothesis directly.

**Method:** For each trading day 2016–2024, compute:
- `IV30` ≈ VIX (proxy for 30-day implied vol)
- `RV30` = realized 30-day SPX close-to-close annualized std × √252 over the **subsequent** 30 trading days
- `VRP_t = IV30_t − RV30_t`

**Report:**
- Mean, median, IQR of VRP over the full period; mean by year; mean by IV-percentile bucket (low/mid/high).
- Bootstrap 95% CI on mean VRP (block bootstrap with 30-day blocks to respect autocorrelation).
- Fraction of days with VRP > 0.

**Bdiag pass condition:** Mean VRP > 0 with bootstrap 95% CI excluding zero, on the full 2016–2024 period **and** on the subset of days with IV percentile > 60 (the regime the strategy actually trades).

If Bdiag fails, the volatility risk premium has compressed below tradable levels for index-vol-selling. Document and **stop before running the strategy backtest** — the strategy's failure or success would be uninterpretable when the underlying hypothesis is already falsified.

#### 7.3.3 Strategy backtest (only if Bdiag passes)

**Method:** For each trading day in the period:
1. Compute IV percentile from VIX rolling 252-day window.
2. If > 60 and the concurrent-position cap allows, select strikes from the real option chain (OptionsDX or higher tier), enter position.
3. Track position mark-to-market daily on real chain marks; apply exit rules.
4. Record fills with $0.50 per-contract commission and 5bps quote spread (SPX options assumption — to be revised against real spread data if available).

**Stress windows.** Strategy metrics are reported across:
- **Full period 2016–2024.**
- **2018-Q4** (post-vol-mageddon, sustained elevated vol).
- **2020 Feb–Apr** (COVID crash and recovery — most adverse environment for short-vol).
- **2022** (sustained bear market).

The strategy must not blow up max-DD individually in any stress window.

**Parameter sensitivity sweep.** Around the pre-registered parameters, vary one at a time:
- IV-percentile threshold: 48 / 60 / 72 (±20%).
- Short-strike delta: 0.12 / 0.16 / 0.20.
- DTE-at-entry: 25 / 35 / 45.

The full-period net Sharpe must stay within ±0.15 of the pre-registered point across this sweep. A narrow knife-edge optimum is a sign the result is overfit to the chosen parameters.

**Metrics reported:** Total return, gross and net annualized Sharpe (full period and each stress window), maximum drawdown (full period and each stress window), win rate, average P&L per position, trade frequency, **CVaR(5%) of per-position P&L** (left-tail loss sensitivity), and the full sensitivity-sweep surface.

**Gate GB0 (revised):**
- **Bdiag VRP test passes.**
- **Net annualized Sharpe > 0.3 AND gross > 0.5** over the full period.
- **Max DD < 30% full period AND < 50% in each stress window.**
- **No single year > 50% of total return.**
- **≥ 40 trades** over the full period.
- **Sensitivity stable:** net Sharpe within ±0.15 of pre-registered point across the ±20% sweep on every parameter axis.

### 7.4 Stage B1 — Paper trading (operational validation)

Paper trading is **operational validation, not statistical evidence.** Over 60 days a short-vol iron condor strategy may take only 5–10 positions; Sharpe sampling error at that count is enormous, and the strategy's true failure mode (tail losses) may not appear for months or years. The statistical case is made in GB0 against real chain data; B1 confirms the live wiring matches the backtest.

If GB0 passes, implement in Lux as a scheduled capability:
- Daily IV-percentile check.
- Entry/exit logic per §7.2.
- IBKR paper trading via existing IBKR integration.
- Telegram notifications for fills, daily IV-percentile summary, and any control trigger.

**Duration:** 60 trading days minimum (longer if trade count is low).

**Operational gate (GB1):** All of:
1. **Fills match backtest assumptions.** For each closed position, realized entry and exit fill prices land within ±10% of the backtest's modeled mid+haircut. Three consecutive positions filling outside that band → pause and investigate (do not auto-kill).
2. **Slippage stays within the pre-registered cost model.** Per-leg slippage exceedance triggers investigation, not auto-kill.
3. **Controls execute correctly.** Profit-take, 21-DTE close, and 200%-credit hard stop each fire correctly on at least one example (or remain unfired and audited as not-yet-triggered at 60 days).
4. **Alerts work.** Telegram delivers on every fill, daily IV-percentile summary, and any control trigger.
5. **No operational incidents.** No orphaned positions, no double-fills, no auth/connectivity outages > 1 hour without escalation.

**Sharpe is reported, not gated.** The 60-day realized Sharpe is too noisy to confirm the strategy works. If it is wildly inconsistent with GB0 (e.g., net Sharpe < −0.5 with all fills matching), that is a flag to investigate model assumptions, not an automatic kill.

Stage B1 conclusion is an operational sign-off. Going beyond paper to live capital is a separate decision (post-B1) that requires the GB0 statistical evidence, the B1 operational sign-off, and an explicit risk-capital allocation conversation.

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
| G0a | Stage 0 (Period B) | At least one candidate: OOS IC ≥ 0.03 AND IC t-stat ≥ Holm-Bonferroni threshold AND ≥2 of 3 annual sub-periods at IC ≥ 0.02 | Track A killed or paused (see §4.5) |
| G0b | Stage 0 (Period B) | Same candidate: decile spread > 0.5% AND top-3 > bottom-3 deciles | Same as G0a |
| G0c | Stage 0 (Period B) | Same candidate: gross **portfolio** Sharpe > 0.3 AND gross per-trade mean P&L > 0 | Same as G0a |
| G1 | Stage 1 | Options overlay per-trade P&L lift over underlying-only baseline, pre-registered, OOS | Park Track A; signal exists but options are not the right wrapper |
| G2 | Stage 2 | Walk-forward Sharpe > 0.4 on held-out 12 months, pre-registered params | Refine or park; do not paper-trade |
| G2-paper | Stage 2 | Paper Sharpe > 0.4 over 60+ days, matches backtest within one SE | Refine or park; do not go live |
| GB0-diag | Stage B0 (Bdiag) | Mean IV30 − RV30 > 0 with bootstrap 95% CI excluding zero, full period and IV-pct>60 subset | Kill Track B (VRP hypothesis falsified) |
| GB0 | Stage B0 (strategy) | Real-chain data; Net Sharpe > 0.3 and gross > 0.5 full period; max DD < 30% full / < 50% per stress window; ≥40 trades; no single year > 50% of return; sensitivity within ±0.15 Sharpe across ±20% parameter sweep | Kill Track B |
| GB1 | Stage B1 (60-day paper) | **Operational sign-off** — fills/slippage match backtest; controls fire correctly; alerts work; no incidents | Refine plumbing or kill |

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
- The Black-Scholes engine specification (usable as a plumbing/smoke-test fallback only; production evaluation now requires real chain data — see §7.3.1)
- The IBKR MCP investigation ([DECISION NEEDED] in PR #404 Task 5.1 — this work is still needed before Stage B1)
- The per-component architecture specs (useful as a reference if Stage 2 proceeds, not as a commitment)

---

## 9. Open Decisions and Pre-Registered Parameters

### 9.1 Decisions required

**Before Stage 0:**
1. **Squad-v2 during Stage 0:** Continue, pause, or redirect? Recommendation: pause active cycles for the duration of Stage 0 (5–8 days). Stage 0's outcome will inform squad-v2's research question.
2. **Parallel or sequential tracks:** Recommendation: parallel. Track A and Track B are independent and share no code paths.
3. **Who runs what:** Stage 0 is a data-analysis task (pandas, statsmodels, scipy.stats). Stage B0 is a backtest engineering task plus a data acquisition step. Different skill profiles; assign accordingly.

**Blocks GB0 evaluation (not optional):**
4. **Options chain data acquisition.** $200 (OptionsDX SPY/SPX daily snapshots — minimum viable) or $1000+ (CBOE DataShop / OptionMetrics — preferred for full surface). The $0 B-S/VIX path cannot evaluate GB0 (§7.3.1). Decision and acquisition must complete before GB0 evaluation. The Bdiag step (§7.3.2) can run with VIX data alone and is recommended as a pre-purchase gate — if Bdiag fails on free VIX data, do not spend the data budget.

### 9.2 Pre-registered parameters (Stage 0)

Committed to `docs/designs/options-edge-discovery/stage_0_params.md` before Step 4 (Discovery) runs. Initial values:

**Data split:**
- Period A (Discovery): first 12 months post-training
- Period B (Confirmation, sealed): second 12 months post-training

**Gate thresholds:**
- G0a IC: OOS IC ≥ 0.03; IC t-stat ≥ Holm-Bonferroni threshold (2.39 / 2.13 / 2.00 by p-value rank with 3 candidates); ≥ 2 of 3 annual sub-periods at IC ≥ 0.02
- G0b decile: top-minus-bottom mean realized return > 0.5%; top-3 > bottom-3 deciles
- G0c hold-to-horizon: gross **portfolio** Sharpe > 0.3 AND gross per-trade mean P&L > 0

**IC computation per labeler family (§4.2.1):**
- Forward Return: target = `close[t+H]/close[t] − 1`; Newey-West HAC lag = H
- ZigZag: target = signed return to next pivot; clustered SE by segment index (fallback: NW lag = mean event duration on Period A)
- Triple Barrier: target = return at event end; López de Prado purging + embargo of `ceil(max_holding_period / 10)` bars; NW lag = mean event duration on Period A

**Candidate selection rule (Step 4):** Within each labeler family, highest Period A IC; ties broken by decile spread; further ties by gross portfolio Sharpe. At most 1 candidate per family, 3 total.

**Hold-to-horizon portfolio cap:** `N_max = clip(ceil(horizon / median_signal_spacing_PeriodA), 1, 10)` per model; computed on Period A, frozen before Period B is touched.

**Transaction cost model:** SPY/major ETFs 5bps one-way, other equities 10bps, FX 2bps.
**Slippage model:** 1 bar of bid/ask crossing, 50% of bar H–L range for equities, 1 pip for FX.

### 9.3 Pre-registered parameters (Stage B0)

Committed to `docs/designs/options-edge-discovery/stage_b0_params.md` before Stage B0 evaluation runs.

**Bdiag (§7.3.2):**
- IV30 proxy: VIX close
- RV30: subsequent 30-trading-day SPX close-to-close annualized std × √252
- Bootstrap: block bootstrap, block length = 30 trading days, 10,000 resamples
- Pass condition: mean VRP > 0 with 95% CI excluding zero on full period AND on IV-percentile > 60 subset

**Strategy:**
- Instrument: SPX preferred, SPY if capital constraint
- Structure: iron condor, 0.16Δ short strikes, 0.10Δ long strikes
- Wing width: 1–2 strikes (documented per fill)
- DTE: 30–45 at entry; close at 21 DTE or 50% profit
- IV percentile threshold: 60 (above = enter)
- IV percentile lookback: 252 trading days of VIX
- Max concurrent positions: 2
- Position size: 2% of account at risk
- Hard stop: 200% of credit received
- Cost model: $0.50/contract commission + 5bps quote spread (real-chain marks)
- Backtest period: 2016-01-01 through 2024-12-31

**Stress windows (reported separately):**
- 2018-Q4, 2020 Feb-Apr, 2022 calendar year

**Sensitivity sweep (must hold gate within ±0.15 Sharpe):**
- IV-percentile threshold ∈ {48, 60, 72}
- Short-strike delta ∈ {0.12, 0.16, 0.20}
- DTE-at-entry ∈ {25, 35, 45}

**Data tier:** Real historical option chain data required for GB0 evaluation (§7.3.1). B-S/VIX path is plumbing smoke test only.

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
| 2026-05-15 | Draft v2 | Claude + Karl | Addresses hostile methodology review on PR #405. (1) Stage 0 rewritten with pre-registered model universe and sealed Period B confirmation set; Holm-Bonferroni applied; fallback-retraining clause removed. (2) IC diagnostic split per labeler family with event-end alignment, clustered/HAC SE, López de Prado purging+embargo for Triple Barrier. (3) HAC lag now matches horizon per family (Forward Return) or mean event duration (event labels). (4) Hold-to-horizon engine adds explicit portfolio cap and capital accounting; gates on portfolio Sharpe, not per-trade Sharpe. (5) Stage 1 quantile head expanded to 9 quantiles with by-construction monotonicity, GPD tail extrapolation, moneyness-stratified calibration. (6) Stage B0 $0 B-S/VIX path demoted to plumbing smoke test; GB0 evaluation requires real chain data. (7) Stage B0 adds Bdiag VRP test before strategy backtest; adds stress windows (2018Q4 / 2020Feb-Apr / 2022) and ±20% parameter sensitivity sweep. (8) Stage B1 rewritten as operational sign-off, not statistical evidence. |
