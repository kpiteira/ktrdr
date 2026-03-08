---
design: docs/designs/predictive-features/regime-detection/DESIGN.md
architecture: docs/designs/predictive-features/regime-detection/ARCHITECTURE.md
---

# M2: Regime Labeling & Analysis

**Thread:** Regime Detection
**JTBD:** "As a researcher, I want to analyze whether meaningful market regimes exist in historical data so I can decide whether regime-routed strategies are worth pursuing."
**Depends on:** Nothing
**Tasks:** 5

**Gate:** If regimes show no persistence (<24h average) or no return differentiation, the hypothesis is falsified. Stop Thread 1 here.

---

## Task 2.1: Build RegimeLabeler

**File(s):**
- `ktrdr/training/regime_labeler.py` (new)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Implement `RegimeLabeler` that generates forward-looking 4-class regime labels using Signed Efficiency Ratio (SER) and Realized Volatility ratio (RV). Labels: 0=TRENDING_UP, 1=TRENDING_DOWN, 2=RANGING, 3=VOLATILE.

**Implementation Notes:**
- `compute_signed_efficiency_ratio(close, horizon)`: SER = (close[T+H] - close[T]) / Σ|close[t+1] - close[t]| for t in [T, T+H). Range: -1.0 to +1.0.
- `compute_realized_volatility_ratio(close, horizon, lookback)`: Forward RV / rolling historical RV. RV_ratio > threshold = crisis.
- Classification priority: VOLATILE (3) first (if RV_ratio > vol_crisis_threshold), then TRENDING_UP (0) if SER > +trending_threshold, TRENDING_DOWN (1) if SER < -trending_threshold, else RANGING (2).
- Last `horizon` bars are NaN (no future data available).
- Default params: `horizon=24, trending_threshold=0.5, vol_crisis_threshold=2.0, vol_lookback=120`
- Follow existing labeler patterns — see `ktrdr/training/forward_return_labeler.py` for structure

**Testing Requirements:**
- [ ] Perfect uptrend data → all TRENDING_UP labels
- [ ] Perfect downtrend data → all TRENDING_DOWN labels
- [ ] Flat/oscillating data → all RANGING labels
- [ ] Extreme volatility spike → VOLATILE labels
- [ ] Last `horizon` bars are NaN
- [ ] SER values in [-1, 1] range
- [ ] RV ratio correctly normalizes by historical vol

**Acceptance Criteria:**
- [ ] `RegimeLabeler.generate_labels()` returns Series with values 0-3
- [ ] Classification priority: VOLATILE > TRENDING_UP > TRENDING_DOWN > RANGING
- [ ] Edge cases handled: constant price (division by zero in SER), very short data

---

## Task 2.2: Build RegimeLabelStats Analysis

**File(s):**
- `ktrdr/training/regime_labeler.py` (add `analyze_labels` method and `RegimeLabelStats` dataclass)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `analyze_labels()` method to `RegimeLabeler` that computes label quality statistics. Returns a `RegimeLabelStats` dataclass with distribution, persistence, return-by-regime, and transition analysis.

**Implementation Notes:**
- `distribution`: fraction of bars per regime (dict)
- `mean_duration_bars`: average consecutive run length per regime
- `mean_return_by_regime`: mean forward return (close[T+H]/close[T]-1) grouped by regime label
- `transition_matrix`: from-regime → to-regime probability (normalized rows)
- `total_bars`, `total_transitions` for summary
- Compute transitions by finding indices where label changes (`labels.diff() != 0`)
- For duration: use `groupby` on consecutive runs (the standard pandas run-length encoding pattern)

**Testing Requirements:**
- [ ] Distribution sums to ~1.0
- [ ] Mean duration > 0 for all regimes present
- [ ] Transition matrix rows sum to ~1.0
- [ ] Return-by-regime matches manual calculation on small dataset
- [ ] Handles case where a regime has 0 bars (excluded from stats)

**Acceptance Criteria:**
- [ ] `RegimeLabelStats` provides all fields from architecture doc Section 2.1
- [ ] Stats are correct on synthetic data with known properties

---

## Task 2.3: Build CLI Command `ktrdr regime analyze`

**File(s):**
- `ktrdr/cli/commands/regime.py` (new)
- `ktrdr/cli/app.py` (register command group)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `ktrdr regime analyze EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` CLI command. Loads OHLCV data from cache, runs `RegimeLabeler.generate_labels()`, then `analyze_labels()`, and prints a formatted report to the terminal.

**Implementation Notes:**
- Follow existing CLI command patterns — see `ktrdr/cli/commands/` for structure
- Register as `regime_app = typer.Typer()` and add to `app.py`
- Use `DataRepository.load_from_cache()` to load OHLCV data (same as other CLI commands)
- Print report in a table format using Rich (already a dependency)
- Parameters: `symbol` (required), `timeframe` (required), `--start-date`, `--end-date`, optional labeler params (`--horizon`, `--trending-threshold`, `--vol-crisis-threshold`, `--vol-lookback`)
- Output should match the format in architecture doc Section 2.1 (distribution, persistence, return-by-regime, transition matrix)

**Testing Requirements:**
- [ ] CLI command runs without error (mock DataRepository for unit tests)
- [ ] Output includes distribution, persistence, and return-by-regime sections
- [ ] Invalid symbol/timeframe gives clear error
- [ ] Custom labeler params override defaults

**Acceptance Criteria:**
- [ ] `ktrdr regime analyze EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` prints formatted report
- [ ] Report includes all metrics from `RegimeLabelStats`
- [ ] Command is discoverable via `ktrdr regime --help`

---

## Task 2.4: Generate and Analyze Labels for EURUSD 1h

**File(s):** None (research/analysis task)
**Type:** RESEARCH
**Estimated time:** 2 hours

**Description:**
Run `ktrdr regime analyze EURUSD 1h --start-date 2019-01-01 --end-date 2024-01-01` and evaluate whether regimes are meaningful. This is a validation gate — if results are poor, Thread 1 stops here.

**Quality Criteria (from architecture doc):**
- Distribution: no single regime >60% of bars
- Persistence: mean regime duration >24 bars (24h for 1h data)
- Return differentiation: trending_up has positive mean return, trending_down has negative
- Transition frequency: <3 transitions/day on average
- VOLATILE class exists and is <20% of bars (not overwhelming or absent)

**Implementation Notes:**
- If thresholds need tuning, adjust `--trending-threshold` and `--vol-crisis-threshold` and re-run
- Record final threshold values for the seed strategy
- Save output as a reference in `docs/designs/predictive-features/regime-detection/analysis/` for future comparison

**Acceptance Criteria:**
- [ ] Analysis report generated with real EURUSD 1h data
- [ ] All quality criteria met (or documented why they're acceptable)
- [ ] Decision: proceed with Thread 1 or stop (falsified)

---

## Task 2.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate the regime labeling pipeline end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Run regime analysis CLI command on cached EURUSD 1h data. Verify labels are generated, statistics are computed, and report is printed with distribution, persistence, and return-by-regime metrics."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real data loading, real label computation
5. Verify: CLI runs, output contains expected sections, labels are non-degenerate

**Acceptance Criteria:**
- [ ] `ktrdr regime analyze` runs on real cached data
- [ ] Output contains distribution, persistence, return-by-regime sections
- [ ] Labels include all 4 regimes (none absent)
- [ ] Statistics are internally consistent (distribution sums to ~1.0)
