# Milestone 3: Full Synthetic Backtest Loop

---

## A. Objective

Run an end-to-end synthetic backtest on 2-year SPY data (2022-01-01 to 2024-01-01) combining ktrdr directional signals, Kronos vol regime classification, Black-Scholes options pricing, the decision matrix, and full position management. This milestone proves the combined system generates positive risk-adjusted returns in simulation. Target: Sharpe > 0.50 on at least 50 trades with max drawdown < 25%.

---

## B. Go/No-Go Gate (from previous milestone)

**Entry gate from M2**:
- [ ] `BlackScholesEngine` passes all validation tests: put-call parity holds within 1e-6, prices match textbook references within 1%
- [ ] Greeks signs verified: call delta > 0, put delta < 0, gamma > 0, theta < 0, vega > 0
- [ ] `OptionsDataProvider` successfully downloads and caches VIX history
- [ ] `compute_iv_rank()` and `compute_realized_vol()` produce valid results
- [ ] All dataclasses (`OptionsLeg`, `OptionsPosition`, `OptionPrice`, etc.) implemented and tested
- [ ] `StructureType` enum and `OptionsDecisionMatrix.suggest()` cover all 9 matrix cells

**Additional prerequisites**:
- [ ] ktrdr installed as a Python package or on PYTHONPATH (library imports required)
- [ ] Trained ktrdr model available for SPY (e.g., `trend_tb_lstm_signal_v1`)
- [ ] Kronos classifier trained from M1 (or IV rank heuristic fallback ready)
- [ ] Pre-computed Kronos embeddings from M1

---

## C. Files to Create (proposed paths)

| # | File Path | Purpose | Key Classes/Functions |
|---|-----------|---------|----------------------|
| 1 | `ktrdr-options/ktrdr_options/backtest/engine.py` | Options backtest engine — main bar-by-bar loop | `OptionsBacktestEngine`, `OptionsBacktestConfig`, `OptionsBacktestTrade`, `OptionsBacktestResults` |
| 2 | `ktrdr-options/ktrdr_options/positions/manager.py` | Position lifecycle management + SQLite persistence | `OptionsPositionManager` |
| 3 | `ktrdr-options/ktrdr_options/persistence/__init__.py` | Persistence subpackage init | Exports |
| 4 | `ktrdr-options/ktrdr_options/persistence/schema.py` | SQLite schema creation for backtest tables | `create_backtest_schema()`, `create_live_schema()` |
| 5 | `ktrdr-options/ktrdr_options/signals/aggregator.py` | Signal aggregation (combines ktrdr + Kronos + IV) | `SignalAggregator`, `DecisionInput` |
| 6 | `ktrdr-options/ktrdr_options/backtest_cli.py` | CLI: run synthetic backtest | `main()` |
| 7 | `ktrdr-options/tests/test_decision_matrix.py` | Decision matrix unit tests | `TestOptionsDecisionMatrix` |
| 8 | `ktrdr-options/tests/test_position_manager.py` | Position manager unit tests | `TestOptionsPositionManager` |
| 9 | `ktrdr-options/tests/test_backtest_engine.py` | Backtest engine integration tests | `TestOptionsBacktestEngine` |

---

## D. Files to Modify (in ktrdr repo)

| # | File Path | Change | Why |
|---|-----------|--------|-----|
| — | None required for M3 | The backtest engine imports ktrdr as a library. No code changes needed in ktrdr for backtest mode. The `nn_probabilities` are already available via `TradingDecision.reasoning["nn_probabilities"]` when using library imports. | ktrdr API extension (adding `probabilities` to REST response) is deferred to M4. |

**Setup requirement**: ktrdr must be installed as a Python package (`pip install -e /path/to/ktrdr`) or on `PYTHONPATH`. Document this in the backtest CLI help text.

---

## E. Implementation Tasks

### Task 1: Implement `OptionsDecisionMatrix.select()` — full 8-cell grid with confidence gates
- **File**: `ktrdr_options/strategy/decision_matrix.py`
- **Method**: `select(self, decision_input: DecisionInput) -> StructureChoice`
- Implement the decision matrix per ARCHITECTURE.md Section 2.E and DESIGN.md Section 4:

  | ktrdr \ Kronos | SELL_VOL | NEUTRAL | BUY_VOL |
  |---------------|----------|---------|---------|
  | BUY | bull_put_spread | bull_call_spread | long_call |
  | HOLD | iron_condor | NO_TRADE | long_straddle |
  | SELL | bear_call_spread | bear_put_spread | long_put |

- Apply confidence gates:
  1. `ktrdr_confidence < min_ktrdr_confidence (0.45)` → NO_TRADE
  2. For long_call/long_put: `ktrdr_confidence < min_ktrdr_confidence_naked (0.65)` → NO_TRADE
  3. For iron_condor/long_straddle: `kronos_confidence < min_kronos_confidence_vol (0.70)` → NO_TRADE
  4. For all others: `kronos_confidence < min_kronos_confidence_other (0.50)` → NO_TRADE
- Populate `StructureChoice` with target DTE range, delta, width from config
- Set `confidence_gate_passed = True/False` accordingly
- **Test**: All 9 (signal, regime) combinations map to expected structure. Confidence gates correctly reject trades below thresholds. Edge case: HOLD+NEUTRAL → NO_TRADE always.

### Task 2: Implement `OptionsPositionManager.open_position()`
- **File**: `ktrdr_options/positions/manager.py`
- **Method**: `open_position(self, recommendation: TradeRecommendation, decision_input: DecisionInput) -> OptionsPosition`
- Validate risk limits:
  - `recommendation.max_risk <= decision_input.max_risk_per_trade`
  - Total open risk + new risk <= total risk budget
- Assign UUID to position and each leg
- Create `OptionsPosition` with all entry metrics from recommendation
- Persist to SQLite `positions` table (or `backtest_trades` in backtest mode)
- Add to `self._open_positions` in-memory cache
- **Test**: Open position, verify it appears in `get_open_positions()`. Verify risk validation rejects position exceeding budget. Verify UUID is unique.

### Task 3: Implement `OptionsPositionManager.mark_to_market()`
- **File**: `ktrdr_options/positions/manager.py`
- **Method**: `mark_to_market(self, position, underlying_price, current_iv, risk_free_rate, current_date) -> OptionsPosition`
- For each leg in position:
  - Compute remaining DTE from `leg.expiry` and `current_date`
  - Re-price via `BlackScholesEngine.price_option()` with current S, T, r, sigma
  - Update `leg.current_price`, `leg.current_delta/gamma/theta/vega`
- Compute position-level:
  - `current_pnl`: sum of (current_price - entry_price) * contracts * 100 * direction
  - `current_pnl_pct`: pnl / abs(max_loss) * 100
  - `dte_remaining`: min DTE across all legs
  - `net_delta/gamma/theta/vega`: sum across legs (accounting for direction)
- Update SQLite record
- **Test**: Open bull put spread at known prices, mark-to-market with underlying 2% higher → verify positive PnL. Verify Greeks update correctly.

### Task 4: Implement `OptionsPositionManager.check_exit_conditions()`
- **File**: `ktrdr_options/positions/manager.py`
- **Method**: `check_exit_conditions(self, position, current_ktrdr_signal) -> tuple[bool, str]`
- Check conditions in priority order:
  1. `dte_remaining < position.time_exit_dte (7)` → `(True, "time_exit")`
  2. `current_pnl >= position.max_profit * (position.take_profit_pct / 100)` → `(True, "take_profit")`
  3. `current_pnl <= -abs(position.max_loss) * (position.stop_loss_pct / 100)` → `(True, "stop_loss")`
  4. Signal reversal: ktrdr signal flipped (BUY→SELL or SELL→BUY) AND `signal_reversal_exit == True` → `(True, "signal_reversal")`
  - HOLD does not trigger signal reversal (only actual direction flip)
- Return `(False, "")` if no exit condition met
- **Test**: Position with dte=5 → exits with "time_exit". Position at 60% of max profit with take_profit_pct=50 → exits with "take_profit". Position at max loss → exits with "stop_loss". Signal flip BUY→SELL → exits. Signal BUY→HOLD → does NOT exit.

### Task 5: Implement `OptionsPositionManager.close_position()`
- **File**: `ktrdr_options/positions/manager.py`
- **Method**: `close_position(self, position, exit_reason, exit_timestamp) -> OptionsPosition`
- Apply bid/ask haircut to exit prices:
  - For credit spreads being closed: haircut the debit-to-close
  - For debit spreads being closed: haircut the credit-to-close
- Compute final `exit_pnl` with haircut applied
- Update position: `status = CLOSED`, `exit_timestamp`, `exit_reason`, `exit_pnl`
- Write to SQLite `trades` table (or `backtest_trades` in backtest mode)
- Remove from `self._open_positions`
- **Test**: Close position, verify it no longer appears in `get_open_positions()`. Verify `exit_pnl` includes haircut (less favorable than theoretical).

### Task 6: Implement `OptionsPositionManager.get_portfolio_greeks()`
- **File**: `ktrdr_options/positions/manager.py`
- **Method**: `get_portfolio_greeks(self) -> dict[str, float]`
- Sum across all open positions: `total_delta`, `total_gamma`, `total_theta`, `total_vega`
- Compute `total_risk`: sum of `abs(max_loss)` across open positions
- Return dict with all fields + `position_count`
- **Test**: Two open positions, verify aggregates match manual sum.

### Task 7: Implement `SignalAggregator.aggregate()`
- **File**: `ktrdr_options/signals/aggregator.py`
- **Method**: `aggregate(self, ktrdr_signal, kronos_regime, iv_data, current_price, ...) -> DecisionInput`
- Combine all inputs into `DecisionInput` dataclass:
  - Compute `price_change_1d` and `price_change_5d` from `price_history_5d`
  - Compute `position_size_multiplier` from ktrdr probability distribution:
    - `probability_spread = max_prob - second_highest_prob`
    - `< 0.10` → 0.5x, `< 0.25` → 0.75x, else 1.0x
  - `max_risk_per_trade = account_value * max_risk_pct * multiplier`
  - Pre-populate `matrix_suggestion` via `OptionsDecisionMatrix.suggest()`
- **Test**: Aggregate with known inputs, verify `max_risk_per_trade` computed correctly. Verify `matrix_suggestion` populated. Verify position size multiplier: uniform-ish probabilities → 0.5x, skewed → 1.0x.

### Task 8: Implement SQLite schema for backtest tables
- **File**: `ktrdr_options/persistence/schema.py`
- **Function**: `create_backtest_schema(db_path: str) -> sqlite3.Connection`
  - Create `backtest_runs` table per ARCHITECTURE.md Section 4
  - Create `backtest_trades` table per ARCHITECTURE.md Section 4
  - Create indexes
- **Function**: `create_live_schema(db_path: str) -> sqlite3.Connection` (stub for M4)
  - Create `positions`, `trades`, `signals`, `calibration` tables
- **Test**: Create schema, verify all tables exist with correct columns. Insert + query test row.

### Task 9: Implement `OptionsBacktestEngine._load_ktrdr_pipeline()`
- **File**: `ktrdr_options/backtest/engine.py`
- **Method**: `_load_ktrdr_pipeline(self) -> None`
- Import and initialize ktrdr components:
  ```python
  from ktrdr.backtesting.decision_function import DecisionFunction
  from ktrdr.backtesting.model_bundle import ModelBundle
  from ktrdr.indicators.indicator_engine import IndicatorEngine
  from ktrdr.fuzzy.engine import FuzzyEngine
  ```
- Load model via `ModelBundle.load(config.model_path)`
- Initialize `DecisionFunction` with loaded model
- Load OHLCV data via ktrdr's `LocalDataLoader`
- **Test**: Verify import succeeds (requires ktrdr on PYTHONPATH). Verify model loads without error. Verify OHLCV data has expected date range.

### Task 10: Implement `OptionsBacktestEngine._load_kronos()` and `_load_vix_data()`
- **File**: `ktrdr_options/backtest/engine.py`
- **Method**: `_load_kronos(self) -> None`
  - If `config.kronos_embeddings_path` set: load pre-computed embeddings from `.pt`
  - If `config.kronos_classifier_path` set: load classifier weights
  - Else: initialize `KronosVolClassifier` and compute embeddings (slow)
- **Method**: `_load_vix_data(self) -> None`
  - If `config.vix_data_path` set: load from CSV
  - Else: download via `OptionsDataProvider.get_vix_history()`
  - Store in `self._vix_history`
- **Test**: Load with pre-computed embeddings, verify shape matches expected. Load VIX, verify covers backtest date range.

### Task 11: Implement `OptionsBacktestEngine.run()` — main bar-by-bar loop
- **File**: `ktrdr_options/backtest/engine.py`
- **Method**: `run(self) -> OptionsBacktestResults`
- Main loop per ARCHITECTURE.md Section 2.J:
  ```
  for each bar t in [start_date, end_date]:
      1. ktrdr_decision = self._compute_ktrdr_signal(features_t, ...) → TradingDecision
         Extract: signal, nn_probabilities from decision.reasoning
      2. kronos_regime = self._compute_kronos_regime(bar_index, iv_rank, timestamp)
      3. iv_rank, current_iv, rv_20d = self._compute_iv_context(timestamp, price)
      4. decision_input = aggregator.aggregate(...)
      5. structure_choice = decision_matrix.select(decision_input)
      6. If structure != NO_TRADE and confidence gates pass:
         a. strikes = bs_engine.find_strike_by_delta(...)
         b. entry = bs_engine.price_spread(...) + apply_haircut(...)
         c. recommendation = build TradeRecommendation from structure_choice + B-S results
         d. position_manager.open_position(recommendation, decision_input)
      7. For each open position:
         a. position_manager.mark_to_market(position, S_t, sigma_t, r, date)
         b. should_exit, reason = position_manager.check_exit_conditions(position, signal)
         c. If exit: position_manager.close_position(position, reason, timestamp)
      8. Record equity curve point: {date, equity, drawdown}
  ```
- After loop: compute all metrics, write `backtest_runs` row to SQLite
- **Test**: Run on small date range (3 months), verify: at least some trades opened and closed, equity curve has correct length, SQLite has records.

### Task 12: Implement `OptionsBacktestEngine._compute_ktrdr_signal()`
- **File**: `ktrdr_options/backtest/engine.py`
- **Method**: `_compute_ktrdr_signal(self, features, position_status, bar, last_signal_time) -> TradingDecision`
- Call ktrdr's `DecisionFunction.__call__()` with same interface as ktrdr's existing BacktestingEngine
- Extract `nn_probabilities` from `decision.reasoning["nn_probabilities"]`
- **Test**: Verify returns valid `TradingDecision` with signal in {"BUY", "SELL", "HOLD"} and nn_probabilities dict with 3 keys summing to ~1.0.

### Task 13: Implement `OptionsBacktestEngine._compute_metrics()`
- **File**: `ktrdr_options/backtest/engine.py`
- **Method**: `_compute_metrics(self, trades, equity_curve) -> dict`
- Compute from trade list:
  - `total_return` and `total_return_pct`
  - `sharpe_ratio`: annualized Sharpe from equity curve daily returns, `mean(returns) / std(returns) * sqrt(252)`
  - `max_drawdown_pct`: max peak-to-trough decline in equity curve
  - `win_rate`: % of trades with positive PnL
  - `profit_factor`: sum of wins / sum of losses
  - `avg_win_pct`, `avg_loss_pct`
  - `avg_dte_at_entry`, `avg_holding_period_days`
- Options-specific metrics:
  - `avg_theta_collected`: average daily theta on open positions
  - `avg_delta_exposure`: average net delta across all open days
  - `gamma_risk_events`: count of days where any position had gamma > threshold near expiry
  - `structure_breakdown`: dict of trade count per structure type
- Signal distribution: count of BUY/SELL/HOLD signals generated
- **Test**: Given known trade list with 3 wins ($100 each) and 2 losses ($-50 each), verify Sharpe, win_rate=0.6, profit_factor=3.0.

### Task 14: Write `backtest_runs` and `backtest_trades` to SQLite
- **File**: `ktrdr_options/backtest/engine.py`
- After loop completes:
  - Insert `backtest_runs` row with all metrics (per ARCHITECTURE.md Section 4)
  - Verify all `backtest_trades` rows were written during the loop
  - Include `execution_time_seconds`
- **Test**: After backtest run, query SQLite and verify: run_id matches, trade count matches, metrics stored correctly.

### Task 15: Write CLI entry point
- **File**: `ktrdr_options/backtest_cli.py`
- **Function**: `main()`
- CLI: `python -m ktrdr_options.backtest --config ktrdr-options-config.yaml --start 2022-01-01 --end 2024-01-01 [--db-path backtest_results.db]`
- Flow:
  1. Load config from YAML
  2. Build `OptionsBacktestConfig`
  3. Create `OptionsBacktestEngine`
  4. Run backtest
  5. Print results table: metrics summary, top trades, structure breakdown
  6. Print trade log: date, structure, entry, exit, PnL, exit_reason
  7. Exit with code 0 if Sharpe > 0.50, code 1 otherwise
- **Test**: Run CLI end-to-end on 3-month period. Verify stdout has expected sections.

### Task 16: Tune and validate — sweep parameters if gate fails
- If initial backtest does NOT meet Sharpe > 0.50:
  - Sweep confidence thresholds: `min_ktrdr_confidence` in [0.40, 0.45, 0.50]
  - Sweep exit parameters: `take_profit_pct` in [40, 50, 60], `stop_loss_pct` in [75, 100, 150]
  - Sweep DTE: test 14, 21, 30, 45 day windows
  - Analyze structure breakdown: which structures are profitable, which are not?
  - Consider removing unprofitable structures from the matrix
- Document findings in backtest results
- **Test**: At least 3 parameter configurations tested. Best configuration documented with metrics.
- `[VALIDATE EMPIRICALLY]`: This is the Sharpe > 0.50 gate.

---

## F. Acceptance Criteria

### Unit Tests
- [ ] `OptionsDecisionMatrix.select()` correctly maps all 9 (signal, regime) combinations
- [ ] `OptionsDecisionMatrix.select()` returns NO_TRADE when confidence gates fail
- [ ] `OptionsPositionManager.open_position()` creates valid position with UUID
- [ ] `OptionsPositionManager.open_position()` rejects position exceeding risk budget
- [ ] `OptionsPositionManager.mark_to_market()` updates PnL and Greeks correctly
- [ ] `OptionsPositionManager.check_exit_conditions()` triggers on time_exit, take_profit, stop_loss, signal_reversal
- [ ] `OptionsPositionManager.close_position()` applies haircut and records exit
- [ ] `OptionsPositionManager.get_portfolio_greeks()` sums correctly across positions
- [ ] `SignalAggregator.aggregate()` computes position size multiplier correctly
- [ ] `SignalAggregator.compute_position_size_multiplier()` returns 0.5/0.75/1.0 for appropriate spreads
- [ ] `_compute_metrics()` computes Sharpe, win_rate, profit_factor correctly for known inputs
- [ ] SQLite schema creates all tables with correct columns and indexes

### Integration Tests
- [ ] Full backtest runs end-to-end on 3+ month SPY data without errors
- [ ] ktrdr library imports work (DecisionFunction, ModelBundle, etc.)
- [ ] Kronos embeddings load from cache and classifier produces regimes
- [ ] SQLite contains all trades and run summary after backtest
- [ ] Equity curve has correct number of data points (one per trading day)

### Empirical Validation Gates
- [ ] **`[VALIDATE EMPIRICALLY]`** Sharpe > 0.50 on 2022-2024 SPY data
- [ ] **`[VALIDATE EMPIRICALLY]`** >= 50 trades produced
- [ ] **`[VALIDATE EMPIRICALLY]`** Max drawdown < 25%
- [ ] Win rate reported and reasonable (> 40%)
- [ ] Profit factor > 1.0

### Performance Requirements
- [ ] Full 2-year backtest completes in < 10 minutes (excluding Kronos embedding extraction, which is pre-cached)
- [ ] Memory usage < 4GB during backtest

---

## G. Estimated Effort

**12 developer-days**

| Task | Days |
|------|------|
| Decision matrix full impl (Task 1) | 1.0 |
| Position manager — open/close/MTM (Tasks 2-5) | 2.5 |
| Portfolio Greeks (Task 6) | 0.5 |
| Signal aggregator (Task 7) | 1.0 |
| SQLite schema (Task 8) | 0.5 |
| ktrdr pipeline loading (Task 9) | 1.0 |
| Kronos + VIX loading (Task 10) | 0.5 |
| Main backtest loop (Task 11) | 2.0 |
| ktrdr signal computation (Task 12) | 0.5 |
| Metrics computation (Task 13) | 1.0 |
| SQLite writes + CLI (Tasks 14-15) | 1.0 |
| Tuning and validation (Task 16) | 1.0 |

This is the largest milestone. The main backtest loop (Task 11) integrates all prior work and has the most complexity. The ktrdr pipeline loading (Task 9) may require debugging import issues.

---

## H. Open Questions / Risks

1. **ktrdr as library**: The backtest engine imports ktrdr directly (not via REST). This requires ktrdr to be installed (`pip install -e .` or on PYTHONPATH). If ktrdr has complex dependencies or installation issues, this could block M3. **Mitigation**: Test `import ktrdr` early. Document exact setup steps.

2. **ktrdr model availability**: The backtest needs a trained ktrdr model for SPY. If no model exists for SPY at the required timeframe, one must be trained first. `[DECISION NEEDED]`: Confirm which ktrdr model and timeframe to use for SPY backtest.

3. **`[VALIDATE EMPIRICALLY]`** The Sharpe > 0.50 target on synthetic data with B-S reconstruction and 10% haircut is achievable but not guaranteed. If the signal quality is insufficient, the system may produce Sharpe < 0.50 even with parameter tuning. In that case: investigate whether the ktrdr signal itself is profitable on stock trades during the same period — if not, the options layer cannot rescue a non-predictive signal.

4. **Position overlap**: Multiple positions may be open simultaneously. The backtest engine must track and mark-to-market all open positions each bar. The `max_positions: 5` config limit prevents unbounded position count.

5. **Data alignment**: ktrdr signals are generated on bar timeframes (e.g., 1h), but VIX and options pricing use daily data. The backtest must align these: use end-of-day VIX and risk-free rate, but use intrabar prices for underlying. Document the alignment strategy.

6. **Look-ahead bias**: The Kronos classifier was trained on the same date range as the backtest. This introduces optimistic bias. **Mitigation**: The classifier test set (Jul-Dec 2023) is separate from training, but the backtest covers the full 2022-2024 period. Ideally, train Kronos on 2020-2021 and backtest on 2022-2024 to avoid any overlap. `[DECISION NEEDED]`: Should we retrain Kronos on earlier data for cleaner backtest?

7. **`[VALIDATE EMPIRICALLY]`** Exit timing: take profit at 50% of max profit is a standard heuristic for credit spreads. For debit spreads and long options, the take profit threshold should likely be different (higher, e.g., 100-200%). The decision matrix should set structure-specific exit parameters.
