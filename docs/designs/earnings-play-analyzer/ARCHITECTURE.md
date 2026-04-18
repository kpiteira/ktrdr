# Earnings Play Analyzer — Architecture Document

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLI Interface (Click)                       │
│  epa analyze | epa review | epa calibration | epa upcoming     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestrator                                │
│  Routes commands, manages workflow, handles errors              │
└───┬──────────┬──────────┬──────────┬──────────┬────────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐┌────────┐┌─────────┐┌────────┐┌──────────┐
│  Data  ││Analysis││  Opus   ││ ktrdr  ││  Store   │
│ Layer  ││ Engine ││Reasoner ││Adapter ││  (DB)    │
└────────┘└────────┘└─────────┘└────────┘└──────────┘
    │                    │          │
    ▼                    ▼          ▼
┌────────┐         ┌─────────┐┌────────┐
│yfinance│         │Anthropic││ ktrdr  │
│  IBKR  │         │  API    ││ signal │
│  (M5)  │         └─────────┘│  file  │
└────────┘                    └────────┘
```

## 2. Component Design

### 2.1 CLI Interface (`epa/cli.py`)

Framework: **Click** (standard Python CLI framework, already common in Karl's stack)

Responsibilities:
- Parse commands and arguments
- Format output for terminal (rich tables, colored text)
- Handle `--json` flag for machine-readable output

Dependencies: `click`, `rich` (for formatted output)

```python
# Command structure
@click.group()
def cli(): ...

@cli.command()
@click.argument('ticker')
@click.option('--budget', type=float, help='Account size in USD')
@click.option('--signal', help='Manual signal override: BUY:0.73')
@click.option('--json', 'output_json', is_flag=True)
def analyze(ticker, budget, signal, output_json): ...

@cli.command()
@click.argument('ticker')
def review(ticker): ...

@cli.command()
def calibration(): ...

@cli.command()
def upcoming(): ...
```

### 2.2 Data Layer (`epa/data/`)

Responsible for all external data acquisition. Returns normalized data objects regardless of source.

#### `epa/data/models.py` — Data Models

```python
@dataclass
class EarningsEvent:
    ticker: str
    date: datetime
    time_of_day: str          # "BMO" | "AMC" | "UNKNOWN"
    actual_move_pct: float | None   # None if not yet occurred
    direction: int | None           # +1 or -1

@dataclass
class EarningsHistory:
    ticker: str
    events: list[EarningsEvent]
    avg_move: float
    median_move: float
    max_move: float
    min_move: float
    stdev_move: float
    up_pct: float             # % of events that moved up

@dataclass
class OptionsSnapshot:
    ticker: str
    underlying_price: float
    timestamp: datetime
    expiry: date
    calls: list[OptionQuote]
    puts: list[OptionQuote]
    atm_straddle_price: float
    implied_move_pct: float

@dataclass
class OptionQuote:
    strike: float
    bid: float
    ask: float
    mid: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    volume: int
    open_interest: int

@dataclass
class IVData:
    ticker: str
    current_iv: float
    iv_52w_high: float
    iv_52w_low: float
    iv_rank: float            # 0-100
    iv_percentile: float      # 0-100
    iv_history: list[tuple[date, float]]  # for charting
```

#### `epa/data/providers/yfinance_provider.py`

```python
class YFinanceProvider:
    def get_earnings_history(self, ticker: str, quarters: int = 16) -> EarningsHistory
    def get_options_snapshot(self, ticker: str, target_expiry: date | None = None) -> OptionsSnapshot
    def get_iv_data(self, ticker: str) -> IVData
    def get_next_earnings_date(self, ticker: str) -> EarningsEvent | None
```

#### `epa/data/providers/ibkr_provider.py` (M5)

Same interface as YFinanceProvider, but backed by IBKR TWS/Gateway API.

#### `epa/data/providers/vision_provider.py` (M3)

```python
class VisionProvider:
    def extract_options_chain(self, image_path: str) -> OptionsSnapshot
    # Uses Opus 4.7 vision to extract structured data from screenshot
```

#### `epa/data/provider.py` — Provider interface + factory

```python
class DataProvider(Protocol):
    def get_earnings_history(self, ticker: str, quarters: int = 16) -> EarningsHistory: ...
    def get_options_snapshot(self, ticker: str, target_expiry: date | None = None) -> OptionsSnapshot: ...
    def get_iv_data(self, ticker: str) -> IVData: ...
    def get_next_earnings_date(self, ticker: str) -> EarningsEvent | None: ...
```

### 2.3 Analysis Engine (`epa/analysis/`)

Pure computation — no external calls, no LLM, fully testable with synthetic data.

#### `epa/analysis/edge.py`

```python
class EdgeCalculator:
    def compute_edge(self, history: EarningsHistory, snapshot: OptionsSnapshot) -> EdgeEstimate
    # Returns: edge_pct, direction (long_vol | short_vol), confidence

    def estimate_iv_crush(self, iv_data: IVData, snapshot: OptionsSnapshot) -> float
    # Estimates post-earnings IV as min(current_iv * 0.5, pre_runup_iv)
    # Used to improve short premium structure scoring

@dataclass
class EdgeEstimate:
    edge_pct: float           # positive = long vol edge, negative = short vol
    direction: str            # "long_vol" | "short_vol"
    confidence: float         # 0-1, based on sample size and consistency
    iv_crush_estimate: float  # expected IV drop post-earnings (percentage points)
    rationale: str            # human-readable explanation
```

#### `epa/analysis/sizing.py`

```python
class KellySizer:
    def compute_size(
        self,
        edge: EdgeEstimate,
        structure: OptionsStructure,
        account_size: float,
        max_risk_pct: float = 2.0,
        kelly_fraction: float = 0.5
    ) -> SizingResult

@dataclass
class SizingResult:
    contracts: int
    capital_at_risk: float
    risk_pct: float           # of account
    kelly_raw: float          # raw Kelly fraction
    kelly_applied: float      # after half-Kelly and cap
    rationale: str
```

#### `epa/analysis/structures.py`

```python
class StructureSelector:
    def select_candidates(
        self,
        edge: EdgeEstimate,
        snapshot: OptionsSnapshot,
        history: EarningsHistory,
        signal: KtrdrSignal | None = None
    ) -> list[OptionsStructure]
    # Returns ranked list of candidate structures scored by expected value:
    #   EV = prob_profit * avg_profit - prob_loss * avg_loss
    # Uses historical move distribution to estimate prob_profit per structure

@dataclass
class OptionsStructure:
    name: str                 # "long_straddle", "bull_put_spread", etc.
    legs: list[OptionLeg]
    max_profit: float | None  # None if unlimited
    max_loss: float
    breakeven: list[float]    # 1 or 2 breakeven points
    score: float              # 0-1, higher is better match
    rationale: str

@dataclass
class OptionLeg:
    side: str                 # "buy" | "sell"
    option_type: str          # "call" | "put"
    strike: float
    expiry: date
    quantity: int
    premium: float            # per contract
```

### 2.4 Opus Reasoner (`epa/reasoner/`)

Thin wrapper around Claude API that sends structured data and receives structured + narrative output.

#### `epa/reasoner/opus.py`

```python
class OpusReasoner:
    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def reason_about_trade(
        self,
        history: EarningsHistory,
        iv_data: IVData,
        edge: EdgeEstimate,
        candidates: list[OptionsStructure],
        sizing: SizingResult,
        signal: KtrdrSignal | None = None
    ) -> TradeRecommendation:
        # Constructs structured prompt with all data
        # Returns final recommendation with natural language rationale

    def extract_from_screenshot(self, image_path: str) -> OptionsSnapshot:
        # Vision-based extraction

@dataclass
class TradeRecommendation:
    ticker: str
    earnings_date: datetime
    action: str               # "TRADE" | "SKIP"
    structure: OptionsStructure | None
    sizing: SizingResult | None
    rationale: str            # Natural language explanation
    confidence: float         # 0-1
    risk_factors: list[str]   # Key risks to be aware of
    raw_data: dict            # All input data for audit trail
```

**Prompt design**: The system prompt establishes the role (experienced options trader analyzing earnings), the input format (structured JSON), and the expected output format (JSON + rationale). The prompt includes:
1. All historical earnings data
2. Current IV data and snapshot
3. Computed edge estimate
4. Candidate structures with scores
5. Kelly sizing calculation
6. ktrdr signal (if available)

Opus is asked to:
1. Validate or challenge the edge estimate
2. Select the best structure from candidates (or propose an alternative)
3. Confirm or adjust sizing
4. Provide narrative rationale connecting all factors

### 2.5 ktrdr Adapter (`epa/integrations/ktrdr.py`)

```python
class KtrdrAdapter:
    def __init__(self, signal_dir: str = "~/.ktrdr/signals/"):
        self.signal_dir = Path(signal_dir).expanduser()

    def get_signal(self, ticker: str) -> KtrdrSignal | None:
        # Read from {signal_dir}/{TICKER}.json
        # Return None if file doesn't exist or is stale (> 24h old)

    def is_available(self) -> bool:
        # Check if signal directory exists

@dataclass
class KtrdrSignal:
    ticker: str
    signal: str               # "BUY" | "SELL" | "HOLD"
    confidence: float         # 0-1
    timestamp: datetime
    model_version: str | None
```

**Staleness**: Signals older than 24 hours are discarded (earnings setups change fast). Configurable.

### 2.6 Store (`epa/store/`)

#### `epa/store/db.py`

```python
class EpaStore:
    def __init__(self, db_path: str = "~/.epa/epa.db"):
        self.db = sqlite3.connect(Path(db_path).expanduser())
        self._init_schema()

    # Predictions
    def save_prediction(self, rec: TradeRecommendation) -> int
    def get_prediction(self, ticker: str, earnings_date: date) -> TradeRecommendation | None

    # Actuals
    def save_actual(self, ticker: str, earnings_date: date, actual_move: float, pnl: float | None)

    # Calibration
    def get_calibration_stats(self) -> CalibrationStats
    def get_ticker_history(self, ticker: str) -> list[PredictionActualPair]

    # Config
    def get_config(self, key: str) -> str | None
    def set_config(self, key: str, value: str)

    # Watchlist
    def get_watchlist(self) -> list[str]
    def add_to_watchlist(self, ticker: str)
    def remove_from_watchlist(self, ticker: str)

    # IV history cache
    def cache_iv_history(self, ticker: str, data: list[tuple[date, float]])
    def get_cached_iv_history(self, ticker: str) -> list[tuple[date, float]] | None
```

#### SQLite Schema

```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    earnings_date DATE NOT NULL,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL,           -- TRADE or SKIP
    structure_name TEXT,
    structure_json TEXT,            -- full OptionsStructure as JSON
    edge_pct REAL,
    kelly_fraction REAL,
    contracts INTEGER,
    capital_at_risk REAL,
    rationale TEXT,
    confidence REAL,
    ktrdr_signal TEXT,              -- BUY/SELL/HOLD or NULL
    ktrdr_confidence REAL,
    raw_data_json TEXT,             -- complete input data for audit
    UNIQUE(ticker, earnings_date)
);

CREATE TABLE actuals (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    earnings_date DATE NOT NULL,
    actual_move_pct REAL NOT NULL,
    actual_direction INTEGER,       -- +1 or -1
    pnl REAL,                       -- actual P&L if traded
    notes TEXT,
    FOREIGN KEY (ticker, earnings_date)
        REFERENCES predictions(ticker, earnings_date)
);

CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE watchlist (
    ticker TEXT PRIMARY KEY,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE iv_cache (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    iv_value REAL NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE data_cache (
    cache_key TEXT PRIMARY KEY,      -- e.g., "options:AAPL:2026-04-25"
    data_json TEXT NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ttl_seconds INTEGER NOT NULL     -- 900 for options, 86400 for earnings history
);
```

## 3. Data Flow — Full Scenario

### 3.1 `epa analyze AAPL --budget 65000`

```
1. CLI parses args: ticker=AAPL, budget=65000
2. Orchestrator begins:
   a. store.get_config("account_size") → fallback to --budget
   b. provider.get_next_earnings_date("AAPL") → 2026-04-24 AMC
   c. provider.get_earnings_history("AAPL", quarters=16) → EarningsHistory
   d. provider.get_options_snapshot("AAPL", target_expiry=2026-04-25) → OptionsSnapshot
   e. provider.get_iv_data("AAPL") → IVData
   f. ktrdr_adapter.get_signal("AAPL") → KtrdrSignal | None
3. Analysis engine:
   a. edge_calc.compute_edge(history, snapshot) → EdgeEstimate
   b. structure_selector.select_candidates(edge, snapshot, signal) → list[OptionsStructure]
   c. For each candidate: kelly_sizer.compute_size(edge, structure, budget) → SizingResult
4. Opus reasoner:
   a. opus.reason_about_trade(history, iv_data, edge, candidates, sizing, signal) → TradeRecommendation
5. Output:
   a. store.save_prediction(recommendation)
   b. CLI formats and prints recommendation
```

### 3.2 Error Handling

| Failure | Behavior |
|---------|----------|
| yfinance rate limited / down | Retry 3x with exponential backoff, then fail with clear message |
| No earnings date found | "No upcoming earnings found for {ticker}. Check the ticker symbol." |
| Options chain empty | "No options data available for {ticker}. Options may not be listed or market may be closed." |
| ktrdr signal unavailable | Proceed without signal, note in output: "No directional signal — using neutral assumption" |
| ktrdr signal stale (>24h) | Same as unavailable |
| Anthropic API error | Retry 2x, then fall back to rule-based recommendation without Opus narrative |
| IV history insufficient (<30 days) | Use available data, flag low confidence in IV rank calculation |
| SQLite write failure | Log warning, continue (analysis is primary, storage is secondary) |

### 3.3 Fallback Mode (No Opus)

If Anthropic API is unavailable, the system still produces a recommendation using pure rules:
1. Edge > 0 + no signal → long straddle
2. Edge > 0 + BUY signal → bull call spread
3. Edge > 0 + SELL signal → bear put spread
4. Edge < 0 + no signal → short iron condor
5. Edge < 0 + directional signal → skip (conflicting signals)

Rationale is template-based instead of LLM-generated. Clearly marked as "rule-based recommendation (Opus unavailable)".

## 4. Project Structure

```
epa/
├── __init__.py
├── __main__.py              # python -m epa
├── cli.py                   # Click CLI
├── orchestrator.py          # Main workflow coordination
├── config.py                # Config management
├── data/
│   ├── __init__.py
│   ├── models.py            # All dataclasses
│   ├── provider.py          # DataProvider protocol
│   └── providers/
│       ├── __init__.py
│       ├── yfinance_provider.py
│       ├── ibkr_provider.py     # M5
│       └── vision_provider.py   # M3
├── analysis/
│   ├── __init__.py
│   ├── edge.py              # Edge computation
│   ├── sizing.py            # Kelly criterion sizing
│   └── structures.py        # Structure selection
├── reasoner/
│   ├── __init__.py
│   ├── opus.py              # Opus 4.7 integration
│   └── prompts.py           # Prompt templates
├── integrations/
│   ├── __init__.py
│   └── ktrdr.py             # ktrdr signal adapter
├── store/
│   ├── __init__.py
│   └── db.py                # SQLite store
└── tests/
    ├── __init__.py
    ├── test_edge.py
    ├── test_sizing.py
    ├── test_structures.py
    ├── test_yfinance_provider.py
    ├── test_orchestrator.py
    └── fixtures/             # Sample data for tests
        ├── aapl_earnings.json
        ├── aapl_options.json
        └── sample_signal.json
```

## 5. Dependencies

### Core (MVP)
```
click>=8.0          # CLI framework
rich>=13.0          # Terminal formatting
yfinance>=0.2.36    # Market data
anthropic>=0.40     # Opus 4.7 API
```

### Development
```
pytest>=8.0
pytest-cov
ruff                # Linting
```

### M5 Additions
```
ib_insync>=0.9      # IBKR TWS API (or ibapi)
```

## 6. Configuration

Stored in `~/.epa/config.toml` (human-readable) and `~/.epa/epa.db` (runtime state).

```toml
[account]
size = 65000.0
max_risk_pct = 2.0
kelly_fraction = 0.5

[data]
provider = "yfinance"           # "yfinance" | "ibkr"
history_quarters = 16
iv_cache_days = 1               # re-fetch IV history daily

[ktrdr]
enabled = true
signal_dir = "~/.ktrdr/signals"
max_signal_age_hours = 24

[opus]
model = "claude-opus-4-6"
max_tokens = 4096
enabled = true                  # false = rule-based only

[ibkr]                          # M5
host = "127.0.0.1"
port = 7497                     # 7497=paper, 7496=live
client_id = 1
```

## 7. Security Considerations

- **API keys**: Anthropic API key stored in environment variable `ANTHROPIC_API_KEY`, never in config files
- **IBKR credentials**: Handled by TWS/Gateway, not by this tool
- **No credentials in SQLite**: DB stores analysis data only
- **Paper trading default**: IBKR integration (M5) defaults to paper trading port (7497). Live trading requires explicit `--live` flag

## 8. Deployment

### MVP (Mac laptop)
- `pip install -e .` in a virtualenv
- `epa` command available in PATH
- Data stored in `~/.epa/`

### Production (Azure ACA) — future
- Containerized with Docker
- SQLite → PostgreSQL migration
- Telegram bot or web API frontend
- Scheduled scans of watchlist before earnings
