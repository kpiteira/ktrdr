# Milestone 2: Black-Scholes Engine + Synthetic Data Infrastructure

---

## A. Objective

Implement the options pricing engine (Black-Scholes with full Greeks) and the data infrastructure required for synthetic backtesting: VIX history, risk-free rate, IV estimation, and synthetic options chain construction. This milestone produces all the mathematical and data machinery needed to price options without live market data, enabling the full backtest loop in M3. No live data or external APIs (beyond VIX/FRED) are required.

---

## B. Go/No-Go Gate (from previous milestone)

**Entry gate from M1**:
- [ ] Kronos vol regime classifier trained with AUC > 0.60 on held-out test set
- [ ] Classifier weights saved to `models/kronos_classifier/SPY_head.pt`
- [ ] Pre-computed Kronos embeddings cached at `cache/kronos/SPY_1d_embeddings.pt`
- [ ] `ktrdr-options` package structure established and installable

If M1 AUC < 0.60 but > 0.55: proceed with M2 (B-S engine is useful regardless) while tuning Kronos classifier. If AUC < 0.55: proceed with M2 using IV rank heuristic as vol regime signal.

---

## C. Files to Create (proposed paths)

| # | File Path | Purpose | Key Classes/Functions |
|---|-----------|---------|----------------------|
| 1 | `ktrdr-options/ktrdr_options/backtest/__init__.py` | Backtest subpackage init | Exports |
| 2 | `ktrdr-options/ktrdr_options/backtest/black_scholes.py` | Black-Scholes pricing engine with full Greeks | `BlackScholesEngine`, `OptionPrice` |
| 3 | `ktrdr-options/ktrdr_options/data/options_data.py` | Options data provider (VIX, risk-free rate, IV rank) | `OptionsDataProvider`, `OptionsChain`, `OptionContract`, `IVData` |
| 4 | `ktrdr-options/ktrdr_options/positions/__init__.py` | Positions subpackage init | Exports |
| 5 | `ktrdr-options/ktrdr_options/positions/position.py` | Position and leg dataclasses | `OptionsPosition`, `OptionsLeg`, `PositionStatus` |
| 6 | `ktrdr-options/ktrdr_options/strategy/__init__.py` | Strategy subpackage init | Exports |
| 7 | `ktrdr-options/ktrdr_options/strategy/decision_matrix.py` | Deterministic decision matrix (stub for M3, full impl) | `OptionsDecisionMatrix`, `StructureType`, `StructureChoice` |
| 8 | `ktrdr-options/tests/test_black_scholes.py` | Comprehensive B-S unit tests | `TestBlackScholesEngine` |
| 9 | `ktrdr-options/tests/test_options_data.py` | Options data provider tests | `TestOptionsDataProvider` |

---

## D. Files to Modify (in ktrdr repo)

None. Milestone 2 does not require any changes to the ktrdr codebase.

---

## E. Implementation Tasks

### Task 1: Implement `BlackScholesEngine.price_call()` — full Greeks
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `price_call(self, S, K, T, r, sigma) -> OptionPrice`
- Implement Black-Scholes call formula:
  - `d1 = (ln(S/K) + (r + sigma^2/2) * T) / (sigma * sqrt(T))`
  - `d2 = d1 - sigma * sqrt(T)`
  - `C = S * N(d1) - K * exp(-rT) * N(d2)`
- Compute all Greeks:
  - `delta = N(d1)`
  - `gamma = n(d1) / (S * sigma * sqrt(T))` where `n()` is standard normal PDF
  - `theta = -(S * n(d1) * sigma) / (2 * sqrt(T)) - r * K * exp(-rT) * N(d2)` (per calendar day: divide by 365)
  - `vega = S * n(d1) * sqrt(T) / 100` (per 1% vol change)
  - `rho = K * T * exp(-rT) * N(d2) / 100`
- Return `OptionPrice(price, delta, gamma, theta, vega, rho)`
- Handle edge cases: `T <= 0` (intrinsic value only), `sigma <= 0` (raise ValueError), `S <= 0` or `K <= 0` (raise ValueError)
- **Test**: SPY at $523.45, K=$525, T=28/365, r=0.05, sigma=0.22 → verify price within 1% of known reference. Verify delta is between 0 and 1. Verify gamma > 0. Verify theta < 0.

### Task 2: Implement `BlackScholesEngine.price_put()` — full Greeks
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `price_put(self, S, K, T, r, sigma) -> OptionPrice`
- Implement Black-Scholes put formula:
  - `P = K * exp(-rT) * N(-d2) - S * N(-d1)`
- Greeks:
  - `delta = N(d1) - 1` (negative for puts)
  - `gamma = n(d1) / (S * sigma * sqrt(T))` (same as call)
  - `theta = -(S * n(d1) * sigma) / (2 * sqrt(T)) + r * K * exp(-rT) * N(-d2)` (per calendar day)
  - `vega = S * n(d1) * sqrt(T) / 100` (same as call)
  - `rho = -K * T * exp(-rT) * N(-d2) / 100`
- **Test**: Verify delta is between -1 and 0. Verify theta < 0. Verify put-call parity: `C - P = S - K * exp(-rT)` within tolerance 1e-6.

### Task 3: Implement `BlackScholesEngine.price_option()` — dispatch
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `price_option(self, S, K, T, r, sigma, option_type: str) -> OptionPrice`
- Dispatch to `price_call()` if `option_type == "CALL"`, `price_put()` if `option_type == "PUT"`
- Raise `ValueError` for unknown `option_type`
- **Test**: Verify dispatch works correctly for both types. Verify unknown type raises ValueError.

### Task 4: Implement `BlackScholesEngine.find_strike_by_delta()` — Newton's method
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `find_strike_by_delta(self, S, T, r, sigma, target_delta, option_type, strike_step=1.0) -> float`
- Newton's method to find K such that `delta(S, K, T, r, sigma) == target_delta`
  - Initial guess: `K = S` (ATM)
  - Iteration: `K_new = K - (delta(K) - target_delta) / gamma(K)` (using gamma as derivative of delta w.r.t. K, with appropriate sign)
  - Convergence: `|delta(K) - target_delta| < 1e-4`
  - Max iterations: 50
  - If no convergence: raise `ValueError("Newton's method did not converge")`
- Round result to nearest `strike_step` (e.g., 1.0 for SPY → $515, $516, etc.)
- **Test**: 
  - For call with target_delta=0.30: verify result delta is within 0.02 of target after rounding
  - For put with target_delta=-0.30: same verification
  - With strike_step=5.0: verify result is multiple of 5
  - Verify convergence in < 50 iterations for typical inputs

### Task 5: Implement `BlackScholesEngine.price_spread()` — multi-leg pricing
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `price_spread(self, S, legs: list[OptionsLeg], T, r, sigma) -> dict`
- For each leg in the spread:
  - Price the option via `price_option()`
  - Multiply by `leg.contracts * 100` (options multiplier)
  - If `leg.action == "SELL"`: negate price and delta (credit)
  - If `leg.action == "BUY"`: keep as-is (debit)
- Aggregate:
  - `net_price`: sum of all leg prices (positive = net credit, negative = net debit)
  - `max_profit` and `max_loss`: computed from structure (for verticals: width - credit for max_loss, credit for max_profit)
  - `breakeven`: computed from structure type
  - `net_delta`, `net_gamma`, `net_theta`, `net_vega`: sum across legs
- Return dict with all fields per ARCHITECTURE.md Section 2.G
- **Test**: Bull put spread (sell 515 put, buy 510 put): verify net_price > 0 (credit), verify net_delta > 0 (bullish), verify max_loss = (515-510)*100 - credit per contract

### Task 6: Implement `BlackScholesEngine.apply_haircut()` — bid/ask simulation
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `apply_haircut(self, price: float, side: str) -> float`
- `side == "credit"`: `price * (1 - self._haircut)` — you receive less
- `side == "debit"`: `price * (1 + self._haircut)` — you pay more
- Default `self._haircut = 0.10` (10%)
- **Test**: Credit of $1.85 with 10% haircut → $1.665. Debit of $1.85 → $2.035. Verify.

### Task 7: Implement `BlackScholesEngine.estimate_iv_from_vix()` — static method
- **File**: `ktrdr_options/backtest/black_scholes.py`
- **Method**: `estimate_iv_from_vix(vix: float, beta: float = 1.0) -> float`
- Formula: `sigma = vix / 100 * max(0.8, min(2.0, beta * 0.9 + 0.3))`
- For SPY (beta=1.0): `sigma = vix / 100 * 1.2` → but spec says `beta=1.0` default with `IV_scalar = 1.0` for SPY. Reconcile: for SPY, use `sigma = vix / 100` directly (beta=1.0, scalar=1.0).
- **Test**: VIX=22.4, beta=1.0 → sigma=0.224. VIX=30.0, beta=1.5 → sigma = 30/100 * max(0.8, min(2.0, 1.5*0.9+0.3)) = 0.3 * 1.65 = 0.495.

### Task 8: Implement `OptionsDataProvider.get_vix_history()` — download and cache
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: `get_vix_history(self, start: str, end: str) -> pd.Series`
- Download VIX daily close from yfinance: `yfinance.download("^VIX", start=start, end=end)["Close"]`
- Cache to `cache/vix_daily.csv` after download
- On subsequent calls: load from cache if cache exists and covers requested date range, else re-download
- Return `pd.Series` with `DatetimeIndex`
- **Test**: Verify returned Series has DatetimeIndex, no NaN values (forward-fill gaps), values > 0.

### Task 9: Implement `OptionsDataProvider.get_risk_free_rate()` — FRED T-bill
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: `get_risk_free_rate(self, as_of: str | None = None) -> float`
- Fetch 3-month T-bill rate from FRED via `pandas_datareader.data.DataReader("DGS3MO", "fred")`
- Cache to `cache/risk_free_rate.json` with timestamp
- Refresh if cache > 1 day old
- Fallback: if FRED is unreachable, return config override value or default 0.05
- Return annualized rate as decimal (e.g., 0.0525 for 5.25%)
- **Test**: Verify returned value is in reasonable range [0.0, 0.10]. Verify fallback works when mock raises error.

### Task 10: Implement `OptionsDataProvider.compute_iv_rank()` and `compute_realized_vol()`
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: `compute_iv_rank(self, iv_current: float, iv_history_252d: pd.Series) -> float`
  - `rank = (iv_current - min) / (max - min) * 100`
  - Return 50.0 if `max == min` (no range)
- **Method**: `compute_realized_vol(self, prices: pd.Series, window: int = 20) -> float`
  - `log_returns = np.log(prices / prices.shift(1))`
  - `rv = log_returns.rolling(window).std() * np.sqrt(252)`
  - Return last valid value as float
- **Test**: 
  - IV rank: iv_current=20, history=[10, 15, 20, 25, 30] → rank = (20-10)/(30-10)*100 = 50.0
  - IV rank: identical values → 50.0
  - RV: constant prices → RV ~ 0.0
  - RV: prices with known volatility → verify within 10% of expected

### Task 11: Implement dataclasses — `OptionsLeg`, `OptionsPosition`, `OptionPrice`, `OptionContract`, `OptionsChain`, `IVData`
- **Files**: `ktrdr_options/positions/position.py`, `ktrdr_options/data/options_data.py`, `ktrdr_options/backtest/black_scholes.py`
- Implement all dataclasses as specified in ARCHITECTURE.md Sections 2.C, 2.H, 2.G
- Include `to_dict()` methods where specified
- **Test**: Instantiate each dataclass with valid data, verify all fields accessible. Verify `to_dict()` returns JSON-serializable dict.

### Task 12: Implement `StructureType` enum and `OptionsDecisionMatrix` stub
- **File**: `ktrdr_options/strategy/decision_matrix.py`
- Implement `StructureType` enum with all 9 values from ARCHITECTURE.md Section 2.E
- Implement `StructureChoice` dataclass
- Implement `OptionsDecisionMatrix.__init__()` with confidence thresholds
- Implement `OptionsDecisionMatrix.suggest()` — quick lookup without confidence gates (used by SignalAggregator)
- Stub `OptionsDecisionMatrix.select()` — full implementation in M3 Task 1
- **Test**: `suggest("BUY", "SELL_VOL")` → `("bull_put_spread", "...")`. All 9 combinations mapped correctly.

### Task 13: Validate B-S prices against known references
- **File**: `ktrdr-options/tests/test_black_scholes.py`
- Create comprehensive test suite:
  - **Put-call parity**: For multiple (S, K, T, r, sigma) combinations: verify `C - P = S - K*exp(-rT)` within 1e-6
  - **Known prices**: Compare against at least 3 textbook/CBOE reference prices within 1% tolerance
  - **Greeks signs**: Verify call delta ∈ (0,1), put delta ∈ (-1,0), gamma > 0 always, theta < 0 always, vega > 0 always
  - **Greeks limits**: As T → 0 for ATM options, gamma should increase. Deep ITM call delta → 1.0.
  - **Edge cases**: Very deep OTM (delta near 0), very deep ITM (delta near ±1), very short T (near expiry), very long T
  - **Haircut**: Verify credit haircut reduces price, debit haircut increases price
  - **Spread pricing**: Bull put spread net credit is positive, max_loss = width - credit
- **Test**: All above assertions pass.

---

## F. Acceptance Criteria

### Unit Tests
- [ ] `price_call()` matches textbook reference values within 1%
- [ ] `price_put()` matches textbook reference values within 1%
- [ ] Put-call parity holds: `|C - P - (S - K*exp(-rT))| < 1e-6` for 10+ test cases
- [ ] Greeks signs correct: call delta > 0, put delta < 0, gamma > 0, theta < 0, vega > 0
- [ ] `find_strike_by_delta()` converges within 50 iterations for all standard inputs
- [ ] `find_strike_by_delta()` result delta is within 0.02 of target (after strike rounding)
- [ ] `price_spread()` returns correct net price for bull put spread, iron condor, bull call spread
- [ ] `apply_haircut()` correctly reduces credit, increases debit
- [ ] `estimate_iv_from_vix()` returns expected values for known inputs
- [ ] `get_vix_history()` returns non-empty Series with valid dates
- [ ] `compute_iv_rank()` returns values in [0, 100]
- [ ] `compute_realized_vol()` returns non-negative values
- [ ] All dataclasses instantiate correctly and `to_dict()` returns valid dicts

### Integration Tests
- [ ] `OptionsDataProvider` downloads VIX history, computes IV rank and RV for a given date range
- [ ] `BlackScholesEngine` can price a full bull put spread from underlying price + VIX → strikes + entry price
- [ ] `StructureType` enum covers all 9 structure types from decision matrix

### Performance Requirements
- [ ] `price_call()` / `price_put()`: < 1ms per call (pure numpy/scipy)
- [ ] `find_strike_by_delta()`: < 10ms per call
- [ ] `price_spread()` for 4-leg iron condor: < 5ms

---

## G. Estimated Effort

**7 developer-days**

| Task | Days |
|------|------|
| B-S call + put pricing (Tasks 1-3) | 1.5 |
| find_strike_by_delta — Newton's method (Task 4) | 1.0 |
| price_spread + haircut (Tasks 5-6) | 1.0 |
| IV estimation (Task 7) | 0.5 |
| VIX history + risk-free rate (Tasks 8-9) | 1.0 |
| IV rank + RV computation (Task 10) | 0.5 |
| Dataclasses + decision matrix stub (Tasks 11-12) | 0.5 |
| B-S validation test suite (Task 13) | 1.0 |

The B-S implementation (Tasks 1-4) is pure math — low uncertainty. The data infrastructure (Tasks 8-9) depends on external API reliability (yfinance, FRED) but has clear fallback strategies.

---

## H. Open Questions / Risks

1. **`[VALIDATE EMPIRICALLY]`** The 10% bid/ask haircut is a conservative guess. If OptionsDX data is acquired later (`[DECISION NEEDED]` — budget), calibrate the haircut against real bid/ask spreads for SPY options.

2. **FRED API access**: `pandas_datareader` FRED access is free but can be rate-limited. The fallback to a config-override risk-free rate (`backtest.risk_free_rate_override` in YAML) handles this. For backtesting, a static rate is acceptable since risk-free rate changes slowly.

3. **VIX data gaps**: yfinance VIX history may have gaps on holidays/weekends. Forward-fill (or use last valid value) is the standard approach. Document this behavior.

4. **Known B-S limitations**: The implementation deliberately ignores vol smile, dividends, early exercise, and term structure. These are documented in DESIGN.md Section 5 and are acceptable for synthetic backtest. The haircut compensates partially for these approximations.

5. **Spread max profit/loss computation**: For simple vertical spreads, max profit and max loss are straightforward. For iron condors, the computation is slightly more complex (max loss on each side). Ensure `price_spread()` handles all in-scope structures: bull put, bear call, bull call, bear put, iron condor, long call, long put, long straddle.

6. **`scipy` dependency**: `scipy.stats.norm.cdf` and `norm.pdf` are the only scipy functions needed. If scipy is not available, `math.erf` can substitute for `norm.cdf`. However, scipy is a standard dependency and should be included.
