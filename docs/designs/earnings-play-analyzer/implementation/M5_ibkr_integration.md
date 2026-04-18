# M5: IBKR Integration

**Goal**: Replace yfinance with live IBKR data for real-time options chains and accurate Greeks. Enable paper trade placement for recommended structures.

**Success criteria**: `epa analyze AAPL --provider ibkr` uses live IBKR data, and `epa execute AAPL --paper` places the recommended trade on IBKR paper trading account.

**Depends on**: M1 (data provider interface)

---

## Task 5.1: IBKR Data Provider

**Files to create**:
- `epa/data/providers/ibkr_provider.py` — `IBKRProvider` class

**Behavior**:
- Implements the same `DataProvider` protocol as `YFinanceProvider`
- Connects to TWS/Gateway via `ib_insync` library
- `get_earnings_history(ticker, quarters)` → fetches from IBKR fundamental data or falls back to yfinance
- `get_options_snapshot(ticker, target_expiry)` → real-time options chain with accurate Greeks
  - Uses `ib.reqSecDefOptParams()` for available expirations
  - Uses `ib.reqMktData()` for live bid/ask/IV/Greeks
  - Accurate Greeks directly from IBKR (no Black-Scholes approximation needed)
- `get_iv_data(ticker)` → uses IBKR historical volatility data
- `get_next_earnings_date(ticker)` → from IBKR corporate events calendar

- Connection management:
  - Connects on first use, keeps connection alive for session
  - Handles reconnection on drop
  - Respects IBKR rate limits (50 messages/second)
  - Defaults to paper trading port (7497)

**Tests**:
- `test_ibkr_provider.py`:
  - Mock `ib_insync.IB` — verify correct API calls made
  - Verify data mapped correctly to `OptionsSnapshot` model
  - Connection error handling
  - Rate limit compliance

**Config**:
```toml
[ibkr]
host = "127.0.0.1"
port = 7497         # 7497=paper, 7496=live
client_id = 1
timeout = 30
```

---

## Task 5.2: Provider Selection

**Files to modify**:
- `epa/orchestrator.py` — provider factory based on config
- `epa/cli.py` — add `--provider` flag
- `epa/config.py` — add provider selection

**Behavior**:
- `epa analyze AAPL --provider ibkr` → uses IBKR provider
- `epa analyze AAPL --provider yfinance` → uses yfinance (default)
- Config `data.provider` sets default: `"yfinance"` or `"ibkr"`
- If IBKR selected but TWS not running → clear error: "Cannot connect to TWS/Gateway at 127.0.0.1:7497. Is TWS running?"
- Hybrid mode: IBKR for live options data, yfinance for historical earnings (IBKR earnings history is less accessible)

**Tests**:
- `test_provider_selection.py`:
  - Config says yfinance → yfinance provider created
  - CLI override → override takes precedence
  - IBKR selected but unavailable → clear error message

---

## Task 5.3: Paper Trade Execution

**Files to create**:
- `epa/integrations/ibkr_trader.py` — `IBKRTrader` class

**Behavior**:
- `execute_recommendation(rec: TradeRecommendation, paper: bool = True)` → `TradeResult`
  - Builds IBKR order objects from `OptionsStructure` legs
  - For multi-leg structures: uses combo/bag orders
  - Submits to paper account (port 7497) by default
  - `--live` flag required for real money (port 7496) — with explicit confirmation prompt
  - Returns fill prices, commission, actual position details

- Pre-flight checks before order submission:
  1. Verify account has sufficient buying power
  2. Verify option contracts exist and are tradeable
  3. Verify bid/ask spread is reasonable (warn if > 10% of mid)
  4. Display order preview and require confirmation

- `TradeResult` dataclass:
  ```python
  @dataclass
  class TradeResult:
      order_id: int
      status: str           # "FILLED" | "PARTIAL" | "REJECTED" | "CANCELLED"
      fill_price: float
      commission: float
      legs: list[FilledLeg]
      timestamp: datetime
  ```

**Tests**:
- `test_ibkr_trader.py`:
  - Mock IB connection — verify order construction for each structure type
  - Combo order for iron condor (4 legs)
  - Vertical spread (2 legs)
  - Pre-flight check failures → order not submitted
  - Paper vs live port selection

---

## Task 5.4: CLI Execute Command

**Files to modify**:
- `epa/cli.py` — add `execute` command

**Behavior**:
- `epa execute AAPL --paper` — execute most recent recommendation for AAPL
  1. Load most recent prediction from store
  2. Verify it's still current (earnings hasn't passed, data not stale)
  3. Display order preview with current live prices
  4. Require explicit "yes" confirmation
  5. Submit order
  6. Display result
  7. Save trade result to store

- `epa execute AAPL --live` — live trading
  - Requires TWS connected to live account
  - Additional confirmation: "WARNING: This will place a LIVE trade. Type 'EXECUTE' to confirm"
  - Saves to store with `live=True` flag

**Tests**:
- `test_cli_execute.py`:
  - No prediction exists → error
  - Prediction is stale → warning + confirmation
  - Paper trade flow with mocked IB
  - Live trade requires explicit confirmation text

---

## Task 5.5: M5 Validation

**Files to create**:
- `epa/tests/test_m5_e2e.py`

**Test cases** (require TWS paper trading running):
1. `epa analyze AAPL --provider ibkr --budget 65000` → recommendation using live IBKR data
2. Compare IBKR data vs yfinance data for same ticker → verify IBKR has better Greeks
3. `epa execute AAPL --paper` → paper trade placed successfully
4. Verify trade result saved to store
5. `epa review AAPL` → includes actual trade P&L from paper account

**Validation script** (manual):
```bash
# Requires TWS Paper Trading running on port 7497
epa analyze AAPL --provider ibkr --budget 65000
epa execute AAPL --paper
# Wait for fill...
epa review AAPL  # After earnings
```

**Done when**: Karl can go from analysis to paper trade execution in a single CLI session, with live IBKR data powering the analysis and paper trades testing the recommendations.

---

## Safety Notes

- **Paper trading is always the default**. Live trading requires `--live` flag AND explicit confirmation.
- **No auto-execution**. Even with IBKR connected, the system recommends — Karl decides and confirms.
- **Position limits**: System respects the max_risk_pct cap regardless of Kelly output. No single trade can exceed the configured risk budget.
- **IBKR credentials**: Handled entirely by TWS/Gateway. This tool never touches login credentials.
