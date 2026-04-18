# Milestone 5: IBKR Execution + Paper Trading + Calibration

---

## A. Objective

Close the loop — connect the full analysis pipeline to Interactive Brokers via IBKR MCP for paper trade execution, run the system for 60+ trading days to collect statistically meaningful performance data, and validate that live performance tracks synthetic backtest results. Target: paper Sharpe > 0.40 over 60+ days with >= 30 trades. This milestone also implements the calibration system that monitors rolling accuracy and alerts on signal degradation.

---

## B. Go/No-Go Gate (from previous milestone)

**Entry gate from M4**:
- [ ] Full analysis cycle completes end-to-end in < 90 seconds
- [ ] SQLite records (signals, positions) are written correctly each cycle
- [ ] Telegram notification fires on trade events and errors
- [ ] Matrix fallback works when Opus 4.7 is unavailable
- [ ] `KtrdrSignalClient` successfully fetches signals from running ktrdr server
- [ ] `OpusStrategyAdvisor` parses and validates Opus responses with > 95% success rate on diverse inputs

**Critical pre-check before starting M5**:
- [ ] **`[DECISION NEEDED]` IBKR MCP options capabilities validated** — Can the existing IBKR MCP integration:
  - Request options contract details? (`reqContractDetails` with `SecType=OPT`)
  - Place single-leg options orders?
  - Place combo (BAG) orders for multi-leg spreads?
  - If BAG orders unsupported: document the sequential-leg execution plan with slippage risk.

---

## C. Files to Create (proposed paths)

| # | File Path | Purpose | Key Classes/Functions |
|---|-----------|---------|----------------------|
| 1 | `ktrdr-options/ktrdr_options/execution/__init__.py` | Execution subpackage init | Exports |
| 2 | `ktrdr-options/ktrdr_options/execution/ibkr_executor.py` | IBKR MCP trade execution | `IBKRExecutor`, `OrderResult`, `IBKRExecutionError` |
| 3 | `ktrdr-options/ktrdr_options/calibration/__init__.py` | Calibration subpackage init | Exports |
| 4 | `ktrdr-options/ktrdr_options/calibration/monitor.py` | Rolling accuracy and calibration monitoring | `CalibrationMonitor`, `CalibrationReport` |
| 5 | `ktrdr-options/ktrdr_options/calibration/alerts.py` | Degradation detection and Telegram alerts | `DegradationDetector`, `AlertLevel` |
| 6 | `ktrdr-options/tests/test_ibkr_executor.py` | IBKR executor tests with mock MCP | `TestIBKRExecutor` |
| 7 | `ktrdr-options/tests/test_calibration.py` | Calibration monitor tests | `TestCalibrationMonitor` |

---

## D. Files to Modify (in ktrdr-options repo)

| # | File Path | Change | Why |
|---|-----------|--------|-----|
| 1 | `ktrdr_options/orchestrator.py` | Implement `_execute_trade()` with IBKR MCP call. Add paper/live mode toggle. Add approval gate for live trades. | Enables actual trade execution in paper and live modes. |
| 2 | `ktrdr_options/data/options_data.py` | Implement `get_options_chain()` IBKR mode — fetch real chain data via IBKR MCP. | Replaces yfinance snapshot with real-time IBKR options chain for paper/live. |
| 3 | `ktrdr_options/orchestrator.py` | Add daily calibration cycle: call `CalibrationMonitor` after each cycle, write to SQLite `calibration` table. | Enables rolling performance monitoring and degradation alerts. |
| 4 | `ktrdr-options-config.yaml` | Add `options_data.mode: "paper"` toggle and IBKR connection config. | Switches between backtest/paper/live data sources. |

---

## E. Implementation Tasks

### Task 1: Validate IBKR MCP capabilities for options
- **Action**: Investigate and document the existing IBKR MCP deployment's capabilities
- Specific questions to answer:
  - Can it call `reqContractDetails` with `SecType=OPT` to get options chains?
  - Can it call `placeOrder` with `SecType=OPT` for single-leg options orders?
  - Can it call `placeOrder` with `SecType=BAG` for combo/spread orders?
  - What is the order status flow? (Submitted → Filled, partial fills, rejections)
  - Is there an `orderStatus` or equivalent callback for fill confirmation?
- Document results in a short capability report
- **If BAG orders unsupported**: Design sequential-leg execution:
  1. Place each leg as separate order
  2. Wait for fill confirmation between legs
  3. Track partial fills and handle re-pricing between legs
  4. Add slippage tracking: actual fill price vs theoretical price
- **Test**: Place a single-leg paper options order on SPY via IBKR MCP. Verify fill confirmation is received.
- `[DECISION NEEDED]`: Result of this investigation determines execution strategy for all subsequent tasks.

### Task 2: Implement `IBKRExecutor` — IBKR MCP trade execution wrapper
- **File**: `ktrdr_options/execution/ibkr_executor.py`
- **Class**: `IBKRExecutor`
- **Method**: `execute_spread(self, recommendation: TradeRecommendation, symbol: str) -> OrderResult`
  - If BAG orders supported: submit single combo order with all legs
  - If BAG orders NOT supported: submit legs sequentially with 2-second delay between legs
  - Wait for fill confirmation (timeout: 30 seconds per leg)
  - Return `OrderResult(order_id, fill_price, fill_time, status, slippage)`
- **Method**: `execute_single_leg(self, leg: OptionsLeg, symbol: str) -> OrderResult`
  - Submit single options order via IBKR MCP
  - Map `OptionsLeg` to IBKR contract specification:
    - `Symbol: symbol`
    - `SecType: "OPT"`
    - `Strike: leg.strike`
    - `Right: "C" if CALL, "P" if PUT`
    - `Expiry: leg.expiry` (YYYYMMDD format)
    - `Exchange: "SMART"`
    - `Currency: "USD"`
    - `Action: "BUY" or "SELL"`
    - `TotalQuantity: leg.contracts`
    - `OrderType: "LMT"` with limit price from estimated_price + slippage margin
  - **Test**: Mock IBKR MCP → verify correct contract specification. Mock fill → verify OrderResult fields.

### Task 3: Implement `LuxOrchestrator._execute_trade()` — with approval gate
- **File**: `ktrdr_options/orchestrator.py`
- **Method**: `_execute_trade(self, recommendation, decision_input) -> str`
- Flow:
  1. **Paper mode** (`self._mode == "paper"`):
     - Call `IBKRExecutor.execute_spread(recommendation, symbol)` directly
     - Log execution result
     - Return order status
  2. **Live mode** (`self._mode == "live"`):
     - Send Telegram approval request:
       ```
       TRADE APPROVAL REQUIRED
       {structure} {symbol} {strikes} exp {expiry}
       Max risk: ${max_risk}
       Max profit: ${max_profit}
       Source: {opus/matrix}
       
       Reply YES within 10 minutes to approve.
       ```
     - Wait for Karl's Telegram reply (poll or webhook, timeout: 10 minutes)
     - If "YES": execute via `IBKRExecutor`
     - If "NO" or timeout: log rejection, return "rejected"
  3. Record execution in SQLite `trades` table
- **Test**: Paper mode → verify IBKR executor called. Live mode + mock "YES" reply → verify execution. Live mode + timeout → verify rejection logged.

### Task 4: Implement `OptionsDataProvider.get_options_chain()` in IBKR mode
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: Extend `get_options_chain()` for `mode == "paper"` or `mode == "live"`:
  - Call IBKR MCP `reqContractDetails` with `SecType=OPT`, `Symbol=symbol`
  - Fetch available strikes and expiries
  - Fetch bid/ask, IV, and Greeks for each contract (if provided by IBKR)
  - Filter by DTE and delta range
  - Map to `OptionsChain` with `OptionContract` list
- Fall back to yfinance if IBKR is unreachable
- **Test**: Mock IBKR MCP chain response → verify OptionsChain populated correctly. Mock IBKR failure → verify yfinance fallback.

### Task 5: Implement paper trading mode toggle
- **File**: `ktrdr-options-config.yaml` and `ktrdr_options/orchestrator.py`
- Config: `options_data.mode: "paper"` enables:
  - IBKR connection to paper port (7497 vs 7496 for live)
  - Real options chain from IBKR paper
  - Trade execution on IBKR paper
  - No approval gate (auto-execute)
- Verify `LuxOrchestrator.__init__()` reads mode from config
- Verify mode propagates to `OptionsDataProvider`, `IBKRExecutor`
- **Test**: Initialize with mode="paper" → verify IBKR port=7497. Initialize with mode="live" → verify port=7496.

### Task 6: Implement `CalibrationMonitor` — rolling accuracy computation
- **File**: `ktrdr_options/calibration/monitor.py`
- **Class**: `CalibrationMonitor`
- **Method**: `compute_calibration(self, symbol: str, window_days: int = 30) -> CalibrationReport`
- From SQLite `trades` and `signals` tables, compute:
  - **ktrdr accuracy**: rolling win rate of ktrdr directional signal (was the predicted direction correct?)
  - **ktrdr signal distribution**: % BUY, SELL, HOLD over window (detect all-HOLD degeneration)
  - **Kronos regime accuracy**: did the predicted vol regime match the realized outcome? (SELL_VOL correct if actual RV < IV at time of prediction)
  - **System win rate**: % of closed options trades with positive PnL
  - **Rolling Sharpe**: 30-day rolling Sharpe from equity curve
  - **Structure performance**: win rate per structure type
- Return `CalibrationReport` dataclass with all fields
- Write row to SQLite `calibration` table
- **Test**: Given 10 mock trades (7 wins, 3 losses), verify win_rate=0.70. Verify rolling Sharpe computed correctly.

### Task 7: Implement `DegradationDetector` — alert on accuracy drops
- **File**: `ktrdr_options/calibration/alerts.py`
- **Class**: `DegradationDetector`
- **Method**: `check(self, current_calibration: CalibrationReport, backtest_baseline: dict) -> list[tuple[AlertLevel, str]]`
- Alert conditions:
  1. ktrdr win rate drops > 20% from backtest baseline → `AlertLevel.WARNING`
  2. System win rate drops below 40% → `AlertLevel.WARNING`
  3. ktrdr HOLD percentage > 70% (degeneration) → `AlertLevel.CRITICAL`
  4. Rolling Sharpe < 0 for 14+ consecutive days → `AlertLevel.CRITICAL`
  5. Kronos regime accuracy < random (33%) → `AlertLevel.INFO` (regime may not be adding value)
- Return list of (level, message) tuples
- **CRITICAL alerts**: Pause new trade openings, continue monitoring/closing existing positions
- **Test**: Mock calibration with 15% win rate drop → verify WARNING alert. Mock 75% HOLD rate → verify CRITICAL alert. Mock Sharpe = -0.5 for 14 days → verify CRITICAL.

### Task 8: Wire calibration into `LuxOrchestrator`
- **File**: `ktrdr_options/orchestrator.py`
- After each cycle (or daily):
  - Call `CalibrationMonitor.compute_calibration()`
  - Call `DegradationDetector.check()`
  - If any alerts: send Telegram notification with alert level and message
  - If CRITICAL alert: set `self._pause_new_trades = True` (continue monitoring only)
  - Write calibration row to SQLite
- Add daily summary Telegram message (end of trading day):
  - Open positions count and total PnL
  - Today's trades (opened/closed)
  - Rolling 30-day Sharpe
  - Any active alerts
- **Test**: Run cycle → verify calibration computed. Trigger CRITICAL alert → verify new trades paused. Verify daily summary message format.

### Task 9: Run 60-day paper trading period
- **Action**: Deploy and run the full system in paper mode for 60+ trading days
- Setup:
  1. Start ktrdr server with trained SPY model
  2. Start `LuxOrchestrator` in paper mode: `python -m ktrdr_options.orchestrator --mode paper`
  3. Configure 60-minute cycle interval during market hours
  4. Monitor Telegram for trade notifications and alerts
- During the period:
  - Track: trades opened, trades closed, PnL per trade, exit reasons
  - Monitor: calibration alerts, signal degradation, IBKR connectivity
  - Intervene only on CRITICAL alerts — otherwise let the system run autonomously
- **Acceptance**: 60+ trading days, >= 30 trades, all trades logged to SQLite
- `[VALIDATE EMPIRICALLY]`: This is the live Sharpe > 0.40 gate.

### Task 10: Write performance report — compare live vs backtest
- **Action**: After 60-day paper period, generate comprehensive comparison report
- Compare:
  - Paper Sharpe vs synthetic backtest Sharpe
  - Paper win rate vs backtest win rate
  - Structure breakdown: which structures performed differently live vs backtest?
  - Exit reason distribution: live vs backtest
  - Signal distribution: did ktrdr/Kronos signal patterns change?
  - Slippage analysis: how much did actual fills deviate from theoretical prices?
  - Opus vs matrix: what % of trades used Opus, what % fell back to matrix?
  - Calibration trends: any degradation over the 60-day period?
- Flag significant discrepancies for investigation
- **Test**: Report generates without error from SQLite data. All metrics present.

---

## F. Acceptance Criteria

### Unit Tests
- [ ] `IBKRExecutor.execute_spread()` correctly maps TradeRecommendation legs to IBKR contract specs
- [ ] `IBKRExecutor.execute_single_leg()` handles fill confirmation and timeout
- [ ] `IBKRExecutor` handles sequential leg execution when BAG orders unavailable
- [ ] `LuxOrchestrator._execute_trade()` calls IBKR executor in paper mode
- [ ] `LuxOrchestrator._execute_trade()` sends approval request and waits in live mode
- [ ] `OptionsDataProvider.get_options_chain()` fetches real chain from IBKR MCP
- [ ] `CalibrationMonitor.compute_calibration()` produces correct metrics from mock data
- [ ] `DegradationDetector.check()` fires correct alerts for degradation scenarios
- [ ] Paper mode uses IBKR port 7497, live mode uses 7496

### Integration Tests
- [ ] Paper trade execution: submit order → receive fill confirmation → record in SQLite
- [ ] Options chain from IBKR: fetch → filter → verify contracts have realistic bid/ask
- [ ] Full cycle in paper mode: signal → analysis → recommendation → execution → notification
- [ ] Calibration cycle: compute → check alerts → write SQLite → send Telegram
- [ ] Daily summary Telegram message fires at market close

### Empirical Validation Gates
- [ ] **`[VALIDATE EMPIRICALLY]`** Paper Sharpe > 0.40 over 60+ trading days
- [ ] **`[VALIDATE EMPIRICALLY]`** >= 30 paper trades executed
- [ ] System runs autonomously for 60+ days without CRITICAL unrecoverable failures
- [ ] All trades have fill confirmation and PnL recorded
- [ ] Calibration alerts fire correctly on simulated degradation

### Performance Requirements
- [ ] IBKR order submission to fill confirmation: < 30 seconds per leg
- [ ] Full cycle with execution: < 120 seconds total
- [ ] Calibration computation: < 5 seconds
- [ ] System uptime during paper trading: > 95% (excludes scheduled downtime)

---

## G. Estimated Effort

**8 developer-days** (excluding the 60-day paper trading period)

| Task | Days |
|------|------|
| IBKR MCP capability validation (Task 1) | 1.0 |
| IBKRExecutor implementation (Task 2) | 1.5 |
| Orchestrator execution + approval gate (Task 3) | 1.0 |
| IBKR options chain provider (Task 4) | 1.0 |
| Paper mode toggle (Task 5) | 0.5 |
| CalibrationMonitor (Task 6) | 1.0 |
| DegradationDetector + wiring (Tasks 7-8) | 1.0 |
| Performance report (Task 10) | 1.0 |

The 60-day paper trading period (Task 9) runs in production and does not count as development effort — it is a validation period. During this time, the developer monitors for issues and makes hotfixes as needed.

---

## H. Open Questions / Risks

1. **`[DECISION NEEDED]` IBKR MCP multi-leg support**: This is the critical unknown for M5. If the existing IBKR MCP does NOT support BAG orders, multi-leg spreads must be executed as sequential single-leg orders. This introduces:
   - **Leg risk**: time between legs creates exposure (e.g., selling a put before buying the protective put)
   - **Slippage risk**: prices may move between legs
   - **Mitigation**: Execute protective leg (buy) first, then income leg (sell). Track slippage vs theoretical price.

2. **IBKR paper account setup**: Karl must have an IBKR paper trading account configured. IBKR paper accounts mirror live market data with 15-minute delay (or real-time with market data subscription). `[DECISION NEEDED]`: Is IBKR paper already set up? Is IB Gateway or TWS running?

3. **Fill quality**: Paper trading fills may be unrealistically good (instant fills at mid-price). Real fills will have slippage. The slippage analysis in the performance report (Task 10) is critical for assessing this gap.

4. **Market data subscription**: IBKR options chain data requires a market data subscription. If Karl's IBKR account doesn't have options data, the chain will be empty. `[DECISION NEEDED]`: Verify IBKR market data subscription includes options.

5. **60-day timeline**: 60 trading days = ~3 calendar months. This is a significant calendar commitment. If the system shows promise early (positive Sharpe after 30 days), consider a preliminary review to build confidence.

6. **Signal degradation during paper period**: Market regime may shift during the 60-day period. The calibration system (Tasks 6-8) is designed to detect this, but corrective action (retraining models, adjusting thresholds) is outside M5 scope. Document degradation for post-M5 analysis.

7. **Approval gate UX**: The Telegram approval gate (Task 3, live mode only) requires Karl to respond within 10 minutes. If Karl misses the window, the trade is skipped. This is by design for safety, but may result in missed opportunities. `[DECISION NEEDED]`: Is 10 minutes the right timeout? Should it be configurable?

8. **`[VALIDATE EMPIRICALLY]`** Backtest-to-live performance gap: Expect 20-40% degradation from synthetic Sharpe (0.50) to paper Sharpe. If the gap is > 50%, investigate: is it fill quality (slippage), is it signal timing (stale data), is it regime shift (model degradation)?
