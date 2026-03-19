---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M1: Triple Barrier Labeler

**Phase:** 1 — Fix the Target (Layer 1)
**Dependencies:** None (can run in parallel with M2 and M4)
**Branch:** `impl/sme-M1-triple-barrier`

---

## Task 1.1: TripleBarrierLabeler Core

**File(s):** `ktrdr/training/triple_barrier_labeler.py` (new)
**Type:** CODING
**Estimated time:** 3-4 hours

**Description:**
Create a `TripleBarrierLabeler` class that generates path-dependent, volatility-adaptive trade outcome labels. For each candidate entry bar, compute daily volatility (EWMA of log returns), set upper/lower/vertical barriers, and walk forward to determine which barrier is hit first. Returns a Series with labels: +1 (take-profit hit), 0 (time expiry), -1 (stop-loss hit).

**Implementation Notes:**
- Follow the interface pattern in `ktrdr/training/forward_return_labeler.py`: constructor with params, `generate_labels(price_data: pd.DataFrame) -> pd.Series`, `get_label_statistics(labels) -> dict`
- Daily volatility: `EWMA(log_returns, span=vol_span)` — use `pd.Series.ewm(span=vol_span).std()`
- Upper barrier: `entry_price * (1 + pt_multiplier * daily_vol[t])`
- Lower barrier: `entry_price * (1 - sl_multiplier * daily_vol[t])`
- Vertical barrier: `t + max_holding_period`
- Walk forward through `high` and `low` columns (not just `close`) for barrier hit detection — this captures intrabar extremes
- At vertical barrier: use `sign(close[t+max_holding] - entry_price)` for label, or 0 if return < some threshold
- Last `max_holding_period` bars have NaN (no future data) — trim like `ForwardReturnLabeler`
- Raise `DataError` for validation failures (insufficient data, missing columns)
- Use `high` and `low` for intrabar barrier detection: if `high >= upper_barrier` → +1 hit; if `low <= lower_barrier` → -1 hit. If both in same bar, use close direction to disambiguate

**Constructor parameters:**
```python
def __init__(
    self,
    pt_multiplier: float = 2.0,
    sl_multiplier: float = 1.5,
    max_holding_period: int = 50,
    vol_span: int = 50,
):
```

**Testing Requirements:**
- [ ] Test with synthetic uptrending data: should produce mostly +1 labels
- [ ] Test with synthetic downtrending data: should produce mostly -1 labels
- [ ] Test with sideways data: should produce mostly 0 labels (time expiry)
- [ ] Test barrier hit on high/low (intrabar): create bar where high crosses upper barrier but close doesn't
- [ ] Test simultaneous barrier hit (both high and low cross in same bar)
- [ ] Test vertical barrier: no barrier hit within max_holding_period → label based on close
- [ ] Test with real-ish EURUSD data: class distribution should be roughly balanced (not 68%+ any class)
- [ ] Test insufficient data raises DataError
- [ ] Test missing OHLC columns raises DataError
- [ ] Test `get_label_statistics()` returns correct distribution percentages
- [ ] Test vol_span parameter affects barrier widths (higher vol → wider barriers)

**Acceptance Criteria:**
- [ ] `TripleBarrierLabeler` produces labels with 3 distinct classes (+1, 0, -1)
- [ ] Barriers scale with daily volatility (volatile periods → wider barriers)
- [ ] High/low used for intrabar barrier detection (not just close)
- [ ] Label statistics include class distribution, mean holding period, avg barrier width

---

## Task 1.2: CUSUM Event Filter

**File(s):** `ktrdr/training/cusum_filter.py` (new)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement a CUSUM (cumulative sum) filter that identifies bars where a significant price move has accumulated. Instead of labeling every bar, the CUSUM filter emits events only when cumulative returns exceed a threshold, producing a smaller but higher-quality training set.

**Implementation Notes:**
- The CUSUM filter maintains two running sums: `S_pos` and `S_neg`
- At each bar: `S_pos = max(0, S_pos + (r_t - threshold))`, `S_neg = min(0, S_neg + (r_t + threshold))`
- Emit event when `S_pos > threshold` or `S_neg < -threshold`, then reset the triggered sum
- `threshold` is typically `daily_vol * cusum_multiplier` (uses same vol estimate as TB labeler)
- Returns a boolean Series (True = event bar) or index array of event bar positions
- This is a pure filter — it selects WHICH bars to label, not HOW to label them. Applied before `TripleBarrierLabeler.generate_labels()`

**Constructor parameters:**
```python
def __init__(self, threshold: float | None = None, cusum_multiplier: float = 1.0, vol_span: int = 50):
```

If `threshold` is None, compute it as `cusum_multiplier * ewma_vol(close, vol_span)`.

**Testing Requirements:**
- [ ] Test with monotonically rising prices: should emit events at regular intervals
- [ ] Test with flat prices (tiny moves): should emit very few events
- [ ] Test with volatile prices: should emit more events
- [ ] Test threshold sensitivity: higher threshold → fewer events
- [ ] Test reset behavior: after event fires, sum resets
- [ ] Test both positive and negative CUSUM branches fire independently
- [ ] Test output is boolean Series aligned with input index

**Acceptance Criteria:**
- [ ] CUSUM filter reduces sample count (fewer events than total bars)
- [ ] Events cluster at moments of significant price movement
- [ ] Threshold scales with volatility when using `cusum_multiplier` mode

---

## Task 1.3: Uniqueness Weighting

**File(s):** `ktrdr/training/sample_weights.py` (new)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement sample uniqueness weighting for triple barrier labels. Because TB labels have overlapping active periods (bar t's label depends on prices up to t+max_holding, bar t+1's up to t+1+max_holding), samples are not independent. Uniqueness weighting assigns `w_t = 1 / (average number of concurrent labels at time t)`.

**Implementation Notes:**
- Input: the label Series from `TripleBarrierLabeler` and the `max_holding_period`
- For each labeled bar t, its "active period" is `[t, t + actual_holding_period]` where actual_holding_period is the number of bars until barrier hit (not necessarily max_holding_period)
- Need a secondary output from TB labeler: the actual holding period per bar (which bar the barrier was hit)
- Concurrency at time t = number of labels whose active period includes t
- Weight for sample starting at t = `mean(1 / concurrency[s] for s in active_period(t))`
- Returns a float array of weights, same length as labels
- These weights will be used as `sample_weight` in the DataLoader (M2)

**Testing Requirements:**
- [ ] Test with non-overlapping labels: all weights should be 1.0
- [ ] Test with fully overlapping labels: weights should be < 1.0
- [ ] Test weight sum is less than number of samples (weighting reduces effective sample count)
- [ ] Test that bars with high concurrency get lower weights
- [ ] Test edge case: single label (weight = 1.0)
- [ ] Test alignment: weights array matches labels array in length and index

**Acceptance Criteria:**
- [ ] Weights are inversely proportional to label concurrency
- [ ] Weights are normalized (mean ≈ 1 or sum ≈ N for compatibility with loss functions)
- [ ] `TripleBarrierLabeler` extended to return holding periods alongside labels

---

## Task 1.4: Integrate TB Labeler into Training Pipeline

**File(s):** `ktrdr/training/training_pipeline.py`, `ktrdr/training/triple_barrier_labeler.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `source: "triple_barrier"` support to `TrainingPipeline.create_labels()`, following the existing dispatch pattern (see `forward_return` branch at line 456-474). The TB labeler should be instantiated with parameters from the label config, generate labels, and return a LongTensor.

**Implementation Notes:**
- Add `elif source == "triple_barrier":` branch in `create_labels()` after the existing `forward_return` branch
- Lazy import: `from ktrdr.training.triple_barrier_labeler import TripleBarrierLabeler`
- Extract params from `label_config`: `pt_multiplier`, `sl_multiplier`, `max_holding_period`, `vol_span`
- Optionally apply CUSUM filter if `cusum_threshold` is present in config (filter events before labeling)
- Optionally compute uniqueness weights if `compute_weights: true` in config
- Return `torch.LongTensor(labels.values)` — labels are class indices: map +1→0, 0→1, -1→2 (to match BUY/HOLD/SELL convention in DecisionFunction)
- Log label statistics (class distribution) like existing branches do
- Store weights alongside labels if computed (return as tuple or attach to pipeline state)

**Class mapping rationale:**
The existing `DecisionFunction._CLASS_NAMES["classification"]` is `["BUY", "HOLD", "SELL"]` with indices 0, 1, 2. Triple barrier maps: +1 (take-profit) → BUY candidate (0), 0 (time expiry) → HOLD (1), -1 (stop-loss) → SELL candidate (2). This preserves the existing classification inference path without changes.

**Testing Requirements:**
- [ ] Test `create_labels()` with `source: "triple_barrier"` produces LongTensor with values in {0, 1, 2}
- [ ] Test label_config parameters pass through to TripleBarrierLabeler constructor
- [ ] Test CUSUM filtering reduces label count vs all-bar labeling
- [ ] Test with multi-timeframe price_data: uses base (highest frequency) timeframe for labeling
- [ ] Test invalid source raises appropriate error
- [ ] Test statistics are logged (class distribution)

**Acceptance Criteria:**
- [ ] `source: "triple_barrier"` is a fully supported label source in the training pipeline
- [ ] All existing label sources continue to work unchanged
- [ ] CUSUM filtering is optional (applied only when `cusum_threshold` is in config)

---

## Task 1.5: Validation — TB Label Quality

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that the TripleBarrierLabeler produces high-quality labels using real EURUSD data. This is NOT an integration test — it validates the labeler's output characteristics match the design's expectations.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing tests covering triple barrier labeling
3. If no match, use `ke2e-test-designer` to design a test that:
   - Trains a signal model using `source: triple_barrier` on EURUSD 1h data (2020-2023)
   - Measures label class distribution (expect 20-40% each class, not 68%+ any class)
   - Compares with `source: forward_return` baseline on same data
   - Verifies barriers scale with volatility (wider in 2020 COVID vol vs 2023 low vol)
4. Execute via `ke2e-test-runner`

**Success Criteria (from Design Section 11):**
- [ ] Class distribution within 20/60/20 to 40/20/40 range (no single class >60%)
- [ ] Barriers scale with daily volatility (higher vol periods → wider barriers)
- [ ] CUSUM filter reduces sample count by 30-70% (not too aggressive, not too lenient)
- [ ] Label statistics show meaningful structure (not uniform noise)
