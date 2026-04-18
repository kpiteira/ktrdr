# Earnings Play Analyzer — Design Document

## 1. Problem Statement

Options traders face a recurring challenge before every earnings announcement: **Should I trade this event? If yes, what structure? How much capital?** This decision requires synthesizing multiple data streams (historical moves, implied volatility, directional signals) under time pressure, and most traders do this ad hoc.

The Earnings Play Analyzer systematizes this workflow into a repeatable, data-driven process that combines:
- Historical earnings move analysis (what usually happens)
- Current implied volatility assessment (what the market is pricing)
- Optional ML directional signal from ktrdr (which way)
- Kelly criterion sizing (how much)

The output is a **concrete, sized options trade recommendation with rationale**.

## 2. Core Workflow

```
Ticker + (optional) ktrdr signal + (optional) risk budget
    │
    ▼
┌──────────────────────────┐
│  1. Data Acquisition     │  ← yfinance, IBKR, or screenshot
│     - Historical moves   │
│     - Current IV / chain │
│     - Earnings date      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  2. Edge Computation     │  ← Pure math, no LLM
│     - IV rank / %ile     │
│     - Implied vs actual  │
│     - Edge estimate      │
│     - Kelly sizing       │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  3. Structure Selection  │  ← Rule engine + Opus reasoning
│     - Filter candidates  │
│     - Score structures   │
│     - Apply directional  │
│       signal (if avail)  │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  4. Recommendation       │  ← Opus 4.7 reasoning
│     - Final structure    │
│     - Position size      │
│     - Risk parameters    │
│     - Natural language    │
│       rationale          │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  5. Tracking (optional)  │
│     - Record prediction  │
│     - Post-earnings:     │
│       actual vs predicted│
│     - Calibration update │
└──────────────────────────┘
```

## 3. Data Sources

### 3.1 Historical Earnings Data

| Source | Pro | Con | Decision |
|--------|-----|-----|----------|
| yfinance | Free, Python-native, has earnings dates + historical prices | No direct "earnings move" data — must compute from price history | **MVP choice** |
| Earnings Whispers / similar scrapers | Dedicated earnings data | Fragile, TOS concerns | Skip |
| IBKR historical data | Authoritative, integrated | Requires IBKR connection | M5 |

**MVP approach**: Use yfinance to fetch earnings dates (via `ticker.earnings_dates` or `ticker.calendar`), then compute actual moves from daily OHLC around each earnings date. This gives us 8-20 quarters of historical earnings move data for most tickers.

**[DECISION POINT]**: yfinance for MVP. Migrate to IBKR historical data in M5 for better reliability and options-specific historical data.

### 3.2 Implied Volatility Data

| Source | Pro | Con | Decision |
|--------|-----|-----|----------|
| yfinance options chains | Free, Python-native | IV values can be stale/inaccurate | **MVP choice** |
| IBKR live options data | Real-time, accurate Greeks | Requires connection | M5 |
| CBOE data | Authoritative | Paid, complex access | Skip |
| Broker screenshot + Opus vision | No API needed, flexible | Manual step, not automatable | **Fallback** |

**MVP approach**: yfinance `ticker.option_chain()` provides per-strike IVs. Compute IV rank from 1-year IV history (via VIX for index, or ATM straddle approximation for individual stocks).

**Bootstrap limitation**: IV rank requires ~252 trading days of IV history. On first use, this data doesn't exist. The system will: (a) for S&P 500 components, approximate IV rank from VIX percentile as a bootstrap; (b) for other tickers, report "insufficient IV history" until enough data accumulates (~2 weeks of daily caching). The output clearly flags when IV rank is bootstrapped or unavailable.

### 3.3 ktrdr Signal

ktrdr produces: `{ signal: BUY|SELL|HOLD, confidence: 0.0-1.0, timestamp }`.

**Integration approach**: Loose coupling via file or REST API. ktrdr writes its latest signal to a known location (JSON file or HTTP endpoint). The analyzer reads it if available, proceeds without it if not.

**[DECISION POINT]**: File-based integration for MVP (ktrdr writes `~/.ktrdr/signals/{TICKER}.json`). REST API in M4. Direct Python import avoided — ktrdr has its own dependency tree and runtime.

### 3.4 Opus 4.7

**Role**: Reasoning engine, not data engine. Receives structured data (numbers, computed metrics), produces:
1. Structure selection rationale (why this spread over that straddle)
2. Risk assessment narrative
3. Final recommendation in natural language + structured JSON

**Secondary role**: Vision-based data extraction from broker screenshots (fallback when APIs unavailable).

**[DECISION POINT]**: Opus is called via Anthropic API with structured prompts. Input is always structured data (JSON). Output is structured JSON + natural language. Vision extraction is a separate utility function, not the main path.

## 4. Options Structures Supported

The analyzer should reason about these structures, ranked by complexity:

### MVP (M2-M3)
1. **Long straddle** — buy ATM call + put. Bet on large move, direction agnostic.
2. **Long strangle** — buy OTM call + put. Cheaper than straddle, needs bigger move.
3. **Short iron condor** — sell OTM strangle, buy further OTM for protection. Bet on small move / IV crush.
4. **Vertical spread** (call or put) — directional bet with defined risk. Used when ktrdr has a signal.

### Full (M5)
5. **Calendar spread** — sell near-term, buy next-term. Exploit IV crush differential.
6. **Butterfly** — precision bet on landing zone.
7. **Custom** — Opus reasons about non-standard structures when the setup warrants it.

## 5. Key Computations

### 5.1 Historical Earnings Move

For each past earnings event:
- `actual_move = abs(close_after - close_before) / close_before`
- `direction = sign(close_after - close_before)`
- Compute: mean, median, max, min, stdev of actual moves
- Compute: directional bias (% up vs down)

### 5.2 Implied Move (from current options pricing)

- `implied_move = straddle_price / stock_price` (ATM straddle approximation)
- More precise: use weekly options expiring right after earnings

### 5.3 IV Rank & IV Percentile

- `IV_rank = (current_IV - 52w_low_IV) / (52w_high_IV - 52w_low_IV)`
- `IV_percentile = % of days in past year where IV was below current IV`
- Both range 0-100. High IV rank = options are expensive relative to history.

### 5.4 Edge Estimate

- `edge = historical_avg_move - implied_move` (for long vol plays)
- If edge > 0: market is underpricing the move → long straddle/strangle
- If edge < 0: market is overpricing → short premium (iron condor)
- Adjusted for directional signal from ktrdr

### 5.5 Kelly Criterion Sizing

- `kelly_fraction = (p * b - q) / b`
  - p = probability of winning (from historical win rate at this edge level)
  - b = payout ratio (risk/reward of the structure)
  - q = 1 - p
- Apply half-Kelly as default (standard conservative adjustment)
- Cap at configurable max risk per trade (default: 2% of account)

**[DECISION POINT]**: Default to half-Kelly, capped at 2% of account value. Karl can override both.

## 6. Use Cases — Detailed

### UC1: Pre-Earnings Analysis

**Trigger**: `epa analyze AAPL` (CLI) or "Analyze AAPL earnings" (conversational)

**Inputs**: Ticker, optional risk budget, optional ktrdr signal override

**Process**:
1. Fetch next earnings date for AAPL
2. Fetch historical earnings moves (past 8-20 quarters)
3. Fetch current options chain for nearest post-earnings expiry
4. Compute IV rank, implied move, historical move stats
5. Compute edge estimate
6. If ktrdr signal available, incorporate directional view
7. Select candidate structures based on edge direction + magnitude
8. Compute Kelly sizing for top candidates
9. Send structured data to Opus 4.7 for reasoning + final recommendation
10. Output recommendation

**Output**:
```
AAPL Earnings Analysis — 2026-04-24 (AMC)
═══════════════════════════════════════════
Historical moves (12Q): avg 4.2%, med 3.8%, max 8.1%
Implied move: 5.1% (market pricing > historical avg)
IV Rank: 72 | IV Percentile: 81
Edge: -0.9% (market overpricing move)

ktrdr signal: BUY (confidence: 0.73)

Recommendation: BULL PUT SPREAD
  Sell AAPL 195P / Buy AAPL 190P — Apr 25 expiry
  Credit: $1.85 | Max risk: $3.15 | R:R = 1:1.7

Sizing: 3 contracts (1.4% of $65,000 account)
  Kelly suggests 2.8% → half-Kelly = 1.4%

Rationale: Market is overpricing the move (implied 5.1% vs
historical 4.2%). IV crush favors short premium. ktrdr BUY
signal with 0.73 confidence supports directional tilt toward
bull put spread over neutral iron condor.
```

### UC2: No ktrdr Signal Available

Same as UC1 but:
- Skip step 6
- Structure selection defaults to non-directional (straddle, strangle, or iron condor)
- Recommendation explicitly notes: "No directional signal available — defaulting to direction-neutral structure"

### UC3: Low IV Rank (Poor Setup)

If IV rank < 30:
- Flag setup as **unfavorable** for earnings plays
- Explain: "IV is low relative to history — options are cheap, but that means the market isn't pricing much of a move. Historical earnings moves for this ticker are modest."
- If edge is still positive: "There may be a small edge in buying premium here, but sizing should be minimal"
- If edge is negative: "**SKIP RECOMMENDATION** — no edge, low IV, no trade here"

### UC4: Screenshot Input

**Trigger**: User provides screenshot of broker options chain

**Process**:
1. Send image to Opus 4.7 vision
2. Extract: strike prices, bid/ask, IV per strike, expiration date, underlying price
3. Construct structured data object from extracted values
4. Proceed with analysis as normal (steps 4-10 of UC1)

**Constraints**: Opus 4.7 vision extraction is best-effort. System should ask user to confirm extracted values before proceeding with analysis.

### UC5: Post-Earnings Review

**Trigger**: `epa review AAPL` (after earnings have occurred)

**Process**:
1. Look up previous prediction for this ticker
2. Fetch actual post-earnings move
3. Compare predicted vs actual
4. Update calibration database
5. Output performance summary

**Output**:
```
AAPL Post-Earnings Review — 2026-04-24
═══════════════════════════════════════
Predicted: -0.9% edge (market overpricing)
Actual move: 3.1% (vs 5.1% implied) ← Market DID overprice
Trade result: Bull put spread → PROFIT ($555 on $945 risk)

Cumulative accuracy: 7/11 correct edge direction (63.6%)
Calibration: system slightly overestimates historical move reversion
```

## 7. Non-Goals

1. **Not a trading bot** — does not auto-execute trades. Produces recommendations; Karl decides.
2. **Not real-time** — runs on demand, not streaming. No need for WebSocket connections or live tickers.
3. **Not multi-asset** — equities with listed options only. No futures, no forex, no crypto.
4. **Not a backtester** — does not simulate portfolio-level P&L over time. Single-event analysis.
5. **Not a general options analytics platform** — focused exclusively on earnings plays. Does not analyze non-event options strategies.
6. **Not portfolio-aware** — does not consider existing positions, margin requirements, or correlation with other holdings (future enhancement).

## 8. Interface

**[DECISION POINT]**: CLI for MVP. Reasoning:
- Karl is a developer; CLI is natural
- Fastest to build and iterate
- Easy to call from scripts or notebooks
- Can be wrapped in Telegram bot or web UI later

**CLI design**:
```bash
# Core commands
epa analyze AAPL                    # Full analysis
epa analyze AAPL --budget 65000     # With account size
epa analyze AAPL --signal BUY:0.73  # Manual signal override
epa analyze AAPL --earnings-date 2026-04-24  # Override earnings date
epa review AAPL                     # Post-earnings review
epa calibration                     # Show calibration stats
epa upcoming                        # List upcoming earnings for watchlist
epa set-earnings AAPL 2026-04-24 AMC  # Pre-set known earnings date

# Configuration
epa config set account_size 65000
epa config set max_risk_pct 2.0
epa config set kelly_fraction 0.5
epa watchlist add AAPL MSFT GOOGL AMZN META
```

## 9. Persistence

**[DECISION POINT]**: SQLite for MVP. Reasoning:
- Queryable (unlike flat files) — important for calibration history
- Zero infrastructure (unlike PostgreSQL)
- Single file, portable, backup-friendly
- Python stdlib support (`sqlite3`)

**What's stored**:
- Predictions: ticker, date, predicted edge, recommended structure, sizing
- Actuals: ticker, date, actual move, trade P&L
- Calibration: running accuracy stats, systematic biases
- Configuration: account size, risk parameters, watchlist
- IV history: cached IV time series for IV rank computation

**Schema**: defined in ARCHITECTURE.md

## 10. MVP Definition

**MVP = M1 + M2 + M3** (Data Foundation + Analysis Engine + Opus Reasoning)

MVP delivers: `epa analyze AAPL` → structured recommendation with rationale

MVP does NOT require:
- IBKR connection (uses yfinance only)
- ktrdr signal (optional, file-based if available)
- Trade execution
- Telegram/web interface

**Success criteria for MVP**: Karl can run it before an earnings event, get a recommendation he considers reasonable, and decide whether to trade based on it.

## 11. Open Questions for Karl

1. **Watchlist scope**: How many tickers will you typically analyze? (10? 50? 500?) Affects data caching strategy.
2. **Signal format**: Is the ktrdr signal output format fixed? Where does it write? What's the schema?
3. **Account sizing**: Do you want to input account size per-run or configure once? Multiple accounts?
4. **Earnings data quality**: Have you validated yfinance earnings dates against your actual trading? Any known gaps?
5. **Risk appetite**: Is 2% max risk per trade right, or do you size differently for earnings?
6. **Deployment**: Mac laptop only, or also want to run on Azure ACA? Affects persistence choices.
