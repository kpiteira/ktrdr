---
design: docs/designs/predictive-features/multi-timeframe-context/DESIGN.md
architecture: docs/designs/predictive-features/multi-timeframe-context/ARCHITECTURE.md
---

# M3: Context Labeling & Analysis

**Thread:** Multi-TF Context
**JTBD:** "As a researcher, I want to analyze whether daily trend context provides complementary information to hourly regime detection so I can decide whether the context gate adds value."
**Depends on:** Nothing
**Tasks:** 5

**Gate:** If context labels show no persistence (<3 days) or no return differentiation by context, the hypothesis is falsified. Stop Thread 2 here.

---

## Task 3.1: Build ContextLabeler

**File(s):**
- `ktrdr/training/context_labeler.py` (new)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement `ContextLabeler` that generates forward-looking 3-class context labels from daily OHLCV data. Labels: 0=BULLISH, 1=BEARISH, 2=NEUTRAL. Uses signed return over H daily bars.

**Implementation Notes:**
- Forward return: `(close[T+H] - close[T]) / close[T]`
- Classification: `> bullish_threshold` → 0 (BULLISH), `< bearish_threshold` → 1 (BEARISH), else → 2 (NEUTRAL)
- Default params: `horizon=5, bullish_threshold=0.005, bearish_threshold=-0.005`
- Last `horizon` bars are NaN (no future data)
- Much simpler than RegimeLabeler — single metric (signed return), no RV computation
- Follow same patterns as `RegimeLabeler` from M2 for consistency

**Testing Requirements:**
- [ ] Strongly uptrending data → BULLISH labels
- [ ] Strongly downtrending data → BEARISH labels
- [ ] Flat data → NEUTRAL labels
- [ ] Last `horizon` bars are NaN
- [ ] Symmetric thresholds produce roughly symmetric distribution on random walk
- [ ] Custom thresholds override defaults

**Acceptance Criteria:**
- [ ] `ContextLabeler.label()` returns Series with values 0-2
- [ ] Labels correctly reflect forward price direction
- [ ] Edge cases: constant price → all NEUTRAL, very short data → all NaN

---

## Task 3.2: Build ContextLabelStats Analysis

**File(s):**
- `ktrdr/training/context_labeler.py` (add `analyze_labels` method and `ContextLabelStats` dataclass)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add analysis method analogous to `RegimeLabeler.analyze_labels()`. Computes distribution, persistence (in days, not bars — since these are daily labels), return-by-context (hourly returns during each context period), and correlation with regime labels.

**Implementation Notes:**
- `distribution`: fraction of days per context class
- `mean_duration_days`: average consecutive run length per context (bullish/neutral/bearish)
- `mean_hourly_return_by_context`: requires hourly price data aligned to daily context labels. Mean hourly return during bullish/neutral/bearish context periods.
- `regime_correlation`: if regime labels are provided, compute correlation coefficient between context (3-class) and regime (4-class) labels. Low correlation means complementary information.
- For regime correlation: align daily context labels to hourly regime labels via forward-fill, then compute Cramér's V or simple correlation

**Testing Requirements:**
- [ ] Distribution sums to ~1.0
- [ ] Duration > 0 for all present classes
- [ ] Hourly return aggregation correctly groups by forward-filled context label
- [ ] Correlation is 0.0 when given independent labels
- [ ] Handles missing regime labels gracefully (returns None for correlation)

**Acceptance Criteria:**
- [ ] `ContextLabelStats` provides: distribution, mean_duration_days, mean_hourly_return_by_context, regime_correlation
- [ ] Correct on synthetic data with known properties

---

## Task 3.3: Build CLI Command `ktrdr context analyze`

**File(s):**
- `ktrdr/cli/commands/context.py` (new)
- `ktrdr/cli/app.py` (register command group)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `ktrdr context analyze EURUSD 1d --start-date 2020-01-01 --end-date 2025-01-01` CLI command. Loads daily OHLCV data, generates context labels, computes stats, prints formatted report. Optionally loads hourly data for return-by-context analysis and regime labels for correlation.

**Implementation Notes:**
- Parameters: `symbol`, `timeframe` (should be `1d`), `--start-date`, `--end-date`, `--horizon`, `--bullish-threshold`, `--bearish-threshold`
- Optional: `--hourly-timeframe 1h` to compute hourly return-by-context (loads additional hourly data)
- Optional: `--regime-labels-path` to compute correlation with regime labels (or regenerate them inline using RegimeLabeler from M2)
- Use Rich tables for formatted output
- Report format matches architecture doc Section 3.3

**Testing Requirements:**
- [ ] CLI runs without error (mock DataRepository)
- [ ] Output includes distribution, persistence, return-by-context sections
- [ ] `--hourly-timeframe` loads additional data and computes return breakdown
- [ ] Invalid timeframe gives clear warning (context analysis expects daily data)

**Acceptance Criteria:**
- [ ] `ktrdr context analyze EURUSD 1d --start-date 2020-01-01 --end-date 2025-01-01` prints report
- [ ] Report includes all `ContextLabelStats` metrics
- [ ] Command discoverable via `ktrdr context --help`

---

## Task 3.4: Generate and Analyze Labels for EURUSD 1d

**File(s):** None (research/analysis task)
**Type:** RESEARCH
**Estimated time:** 2 hours

**Description:**
Run context analysis on real data and evaluate quality. This is a validation gate.

**Quality Criteria (from design doc):**
- Distribution: bullish/neutral/bearish roughly balanced (not >60% neutral)
- Persistence: mean context duration >3 days
- Return differentiation: bullish context → positive mean hourly return, bearish → negative
- Correlation with regime labels: <0.3 (complementary, not redundant)

**Implementation Notes:**
- Run: `ktrdr context analyze EURUSD 1d --start-date 2020-01-01 --end-date 2025-01-01 --hourly-timeframe 1h`
- If distribution is skewed, tune thresholds (e.g., try 0.3%, 0.7%, 1.0%)
- If regime labels from M2 are available, compute correlation
- Save output as reference in `docs/designs/predictive-features/multi-timeframe-context/analysis/`

**Acceptance Criteria:**
- [ ] Analysis report generated with real EURUSD data
- [ ] All quality criteria met (or documented trade-offs)
- [ ] Decision: proceed with Thread 2 or stop (falsified)

---

## Task 3.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate context labeling pipeline end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Run context analysis CLI command on cached EURUSD 1d data. Verify labels are generated, stats computed, and report printed with distribution, persistence, and return-by-context metrics."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real data, real computation
5. Verify: labels include all 3 classes, persistence >3 days, return differentiation exists

**Acceptance Criteria:**
- [ ] `ktrdr context analyze` runs on real cached data
- [ ] Output contains all expected sections
- [ ] Labels include all 3 context classes
- [ ] Statistics are internally consistent
