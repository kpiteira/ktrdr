# M2: Analysis Engine

**Goal**: Given fetched data, compute earnings edge estimate, select candidate options structures, apply Kelly sizing, and output a structured recommendation object. No LLM involved — pure computation.

**Success criteria**: `epa analyze AAPL --budget 65000` outputs a rule-based recommendation with edge estimate, recommended structure, and position size.

**Depends on**: M1 (data models, provider, store, CLI)

---

## Task 2.1: Edge Calculator

**Files to create**:
- `epa/analysis/__init__.py`
- `epa/analysis/edge.py` — `EdgeCalculator` class

**Behavior**:
- `compute_edge(history, snapshot)` → `EdgeEstimate`
  - `edge_pct = history.avg_move - snapshot.implied_move_pct`
  - `direction = "long_vol"` if edge > 0, `"short_vol"` if edge < 0
  - `confidence` based on: sample size (more quarters = higher), consistency of moves (lower stdev = higher), magnitude of edge (larger = higher)
  - Confidence formula: `min(1.0, (n_quarters / 12) * (1 - stdev/avg_move) * min(abs(edge) / 2.0, 1.0))`
- `estimate_iv_crush(iv_data, snapshot)` → `float`
  - Estimates post-earnings IV drop
  - `post_iv = min(current_iv * 0.5, pre_runup_iv_estimate)`
  - `iv_crush = current_iv - post_iv`
  - Used by structure scorer for short premium strategies
- Generates human-readable rationale string

**Tests**:
- `test_edge.py`:
  - Positive edge: historical avg > implied → long_vol direction
  - Negative edge: historical avg < implied → short_vol direction
  - Zero edge: edge ~0 → low confidence
  - High consistency (low stdev) → higher confidence
  - Small sample (4 quarters) → lower confidence
  - IV crush estimation with various IV levels

---

## Task 2.2: Structure Selector

**Files to create**:
- `epa/analysis/structures.py` — `StructureSelector` class, `OptionsStructure` and `OptionLeg` dataclasses

**Behavior**:
- `select_candidates(edge, snapshot, history, signal=None)` → `list[OptionsStructure]`
- Builds candidate structures from the options chain:
  - **Long straddle**: ATM call + ATM put. Suitable when edge > 0, no directional view.
  - **Long strangle**: OTM call + OTM put (1 strike out from ATM). Cheaper, needs bigger move.
  - **Iron condor**: Sell OTM strangle, buy further OTM wings. Suitable when edge < 0.
  - **Bull call spread / bull put spread**: When signal = BUY. Uses ATM/OTM strikes.
  - **Bear put spread / bear call spread**: When signal = SELL.
- For each structure, computes:
  - `max_profit`, `max_loss` from strike widths and premiums
  - `breakeven` points
  - `score` = expected value using historical move distribution:
    - Simulate each historical move against the structure's P&L profile
    - `EV = mean(simulated P&L across historical moves)`
    - Normalize to 0-1 score
- Sorts candidates by score descending
- Filters out structures with negative EV (unless all are negative → return best with warning)

**Tests**:
- `test_structures.py`:
  - Long vol edge + no signal → straddle/strangle ranked highest
  - Short vol edge + no signal → iron condor ranked highest
  - BUY signal + positive edge → bull spread ranked high
  - SELL signal + negative edge → bear spread ranked high
  - Verify breakeven calculations for each structure type
  - Verify max_profit and max_loss calculations

---

## Task 2.3: Kelly Criterion Sizing

**Files to create**:
- `epa/analysis/sizing.py` — `KellySizer` class, `SizingResult` dataclass

**Behavior**:
- `compute_size(edge, structure, account_size, max_risk_pct=2.0, kelly_fraction=0.5)` → `SizingResult`
- Estimates win probability from edge confidence and historical win rate at similar edge levels
- `kelly_raw = (p * b - q) / b` where:
  - `p` = estimated win probability
  - `b` = structure.max_profit / structure.max_loss (reward/risk ratio)
  - `q` = 1 - p
- `kelly_applied = kelly_raw * kelly_fraction` (default half-Kelly)
- `capital_at_risk = account_size * min(kelly_applied, max_risk_pct / 100)`
- `contracts = floor(capital_at_risk / structure.max_loss)` (at least 1 if capital allows)
- If `kelly_raw <= 0`: no edge → recommend SKIP, contracts = 0
- Generates rationale explaining the sizing

**Tests**:
- `test_sizing.py`:
  - Positive edge → positive Kelly → non-zero contracts
  - Large edge → more contracts (up to cap)
  - Kelly exceeds max_risk_pct → capped
  - Negative Kelly → 0 contracts, SKIP recommendation
  - Half-Kelly vs full-Kelly gives different sizes
  - Account too small for even 1 contract → 0 contracts with warning

---

## Task 2.4: Rule-Based Recommendation Builder

**Files to create**:
- `epa/analysis/recommender.py` — `RuleBasedRecommender` class

**Behavior**:
- `recommend(history, iv_data, snapshot, edge, candidates, sizing, signal=None)` → `TradeRecommendation`
- Decision logic:
  1. If `edge.confidence < 0.2` → action = "SKIP", rationale = "insufficient confidence"
  2. If `iv_data.iv_rank < 30` and `edge.direction == "long_vol"` → action = "SKIP", rationale = "low IV rank, poor setup for buying premium"
  3. If `sizing.contracts == 0` → action = "SKIP", rationale = "Kelly sizing suggests no edge"
  4. Otherwise → action = "TRADE", pick top-scored structure, apply sizing
- Generates template-based rationale explaining the decision
- Compiles all input data into `raw_data` field for audit

**Tests**:
- `test_recommender.py`:
  - Strong positive edge → TRADE with long vol structure
  - Strong negative edge → TRADE with short vol structure
  - Low confidence → SKIP
  - Low IV rank + long vol → SKIP
  - No edge (Kelly <= 0) → SKIP

---

## Task 2.5: CLI Integration

**Files to modify**:
- `epa/orchestrator.py` — add analysis pipeline after data fetching
- `epa/cli.py` — update output formatting for full recommendation

**Behavior**:
- `epa analyze AAPL --budget 65000` now outputs:
  ```
  AAPL Earnings Analysis — 2026-04-24 (AMC)
  ═══════════════════════════════════════════
  Historical moves (12Q): avg 4.2%, med 3.8%, max 8.1%
  Implied move: 5.1%
  IV Rank: 72 | IV Percentile: 81
  Edge: -0.9% (short_vol, confidence: 0.65)

  Recommendation: TRADE — SHORT IRON CONDOR
    Sell AAPL 200C/190P, Buy AAPL 205C/185P — Apr 25 expiry
    Max profit: $2.40 | Max loss: $2.60 | R:R = 1:1.08

  Sizing: 5 contracts ($1,300 risk, 2.0% of $65,000)
    Kelly raw: 4.1% → half-Kelly: 2.05% → capped at 2.0%

  [Rule-based recommendation — Opus reasoning not enabled]
  ```
- Saves prediction to SQLite store
- `--json` outputs structured JSON

**Tests**:
- `test_orchestrator.py`: End-to-end with mocked provider, verify full pipeline produces recommendation

---

## Task 2.6: M2 Validation

**Files to create**:
- `epa/tests/test_m2_e2e.py`

**Test cases**:
1. Full pipeline with fixture data covering each recommendation path (TRADE/SKIP)
2. Edge cases: ticker with only 4 quarters of history, ticker with no options chain
3. Verify prediction saved to SQLite after analysis
4. Verify `--json` output matches `TradeRecommendation` schema
5. Multiple structure types correctly scored and ranked

**Validation script** (manual):
```bash
epa analyze AAPL --budget 65000
epa analyze TSLA --budget 65000          # typically high IV, volatile
epa analyze KO --budget 65000            # typically low IV, small moves
epa analyze AAPL --budget 65000 --json   # verify JSON schema
```

**Done when**: The system produces reasonable, sized trade recommendations for various tickers based purely on data and rules, without any LLM involvement.
