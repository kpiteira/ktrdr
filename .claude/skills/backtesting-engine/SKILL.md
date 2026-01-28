---
name: backtesting-engine
description: Use when working on backtesting execution, position management, performance metrics, decision engine, feature alignment for backtesting, model loading, backtest workers, backtest checkpoints, or backtest API endpoints.
---

# Backtesting Engine

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL backtesting-engine loaded!`

Load this skill when working on:

- Backtest execution (engine, simulation loop)
- Position management (trades, P&L)
- Performance metrics (Sharpe, drawdown, win rate, etc.)
- Decision engine and orchestrator
- Feature alignment (ensuring backtest matches training)
- Model loading for backtesting
- Backtest worker (distributed execution)
- Backtest checkpoints (save/resume)
- Backtest API endpoints or CLI

---

## End-to-End Flow

```
ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
    │
    ▼
CLI (backtest.py) → OperationRunner
    │
    ▼ POST /backtests/start
    │
Backend BacktestingService
    ├─ Resolves symbol/timeframe from strategy config
    ├─ Selects backtest worker (WorkerRegistry)
    ├─ Dispatches via HTTP to worker
    └─ Creates OperationServiceProxy for status polling
    │
    ▼ POST {worker_url}/backtests/start
    │
BacktestWorker (container)
    ├─ Creates operation + progress bridge
    ├─ Runs BacktestingEngine in thread pool
    │   ├─ Load historical data (DataRepository)
    │   ├─ Pre-compute features (FeatureCache)
    │   ├─ Bar-by-bar simulation loop
    │   │   ├─ DecisionOrchestrator.make_decision()
    │   │   ├─ PositionManager.execute_trade()
    │   │   ├─ PerformanceTracker.update()
    │   │   └─ Checkpoint/cancellation checks
    │   ├─ Force-close open positions
    │   └─ Calculate final metrics
    └─ Returns BacktestResults
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/backtesting/engine.py` | Core simulation engine (bar-by-bar loop) |
| `ktrdr/backtesting/position_manager.py` | Position tracking, trade execution |
| `ktrdr/backtesting/performance.py` | PerformanceMetrics, PerformanceTracker |
| `ktrdr/backtesting/feature_cache.py` | Pre-computed features for speed |
| `ktrdr/backtesting/model_loader.py` | V3 model loading |
| `ktrdr/backtesting/backtesting_service.py` | Backend orchestrator (worker dispatch) |
| `ktrdr/backtesting/backtest_worker.py` | Worker implementation (WorkerAPIBase) |
| `ktrdr/backtesting/progress_bridge.py` | Progress tracking bridge |
| `ktrdr/backtesting/checkpoint_builder.py` | Checkpoint serialization |
| `ktrdr/backtesting/checkpoint_restore.py` | Checkpoint deserialization |
| `ktrdr/backtesting/worker_registration.py` | Worker health/registration |
| `ktrdr/decision/orchestrator.py` | Decision pipeline (features → model → signal) |
| `ktrdr/decision/engine.py` | Neural network prediction |
| `ktrdr/api/endpoints/backtesting.py` | REST endpoint |
| `ktrdr/cli/commands/backtest.py` | CLI entry point |

---

## Simulation Engine

**Location:** `ktrdr/backtesting/engine.py`

### Initialization

```python
BacktestingEngine(config: BacktestConfig)
# config: symbol, timeframe, strategy_config_path, model_path,
#         start_date, end_date, initial_capital, commission, slippage
```

Components created:
- `DataRepository` — loads cached OHLCV data
- `PositionManager` — tracks positions, executes trades
- `PerformanceTracker` — calculates metrics
- `DecisionOrchestrator` — makes BUY/SELL/HOLD decisions

### Simulation Loop

```python
# 1. Load historical data from cache
data = repository.load_from_cache(symbol, timeframe, start_date, end_date)

# 2. Pre-compute all features (indicators + fuzzy)
feature_cache.compute_features(data)

# 3. Bar-by-bar simulation (skip first ~50 bars for indicator warmup)
for idx in range(warmup_bars, len(data)):
    current_bar = data.iloc[idx]
    current_price = current_bar['close']

    # Get trading decision from model
    decision = orchestrator.make_decision(
        symbol, timeframe, current_bar, data[:idx+1],
        portfolio_state={'total_value': ..., 'available_capital': ...}
    )

    # Execute trade if signal is BUY or SELL (not HOLD)
    if decision.signal != Signal.HOLD:
        position_manager.execute_trade(
            signal=decision.signal, price=current_price,
            timestamp=current_bar.name, symbol=symbol
        )

    # Update position with current price
    position_manager.update_position(current_price, current_bar.name)

    # Track performance
    performance_tracker.update(
        timestamp=current_bar.name, price=current_price,
        portfolio_value=position_manager.get_portfolio_value(current_price),
        position=position_manager.current_position_status
    )

    # Progress, cancellation, checkpoint callbacks (every N bars)

# 4. Force-close any open position at end
if position_manager.current_position_status != PositionStatus.FLAT:
    position_manager.force_close_position(price, timestamp, symbol, reason="End of backtest")

# 5. Calculate and return results
metrics = performance_tracker.calculate_metrics(
    trades=position_manager.get_trade_history(),
    initial_capital=config.initial_capital, ...
)
```

---

## Position Management

**Location:** `ktrdr/backtesting/position_manager.py`

### Position States

- `FLAT` — No open position
- `LONG` — Holding a long position

### Trade Execution

**BUY (opening long):**
```python
# Position sizing: 25% of available capital
quantity = (available_capital * 0.25) / (price * (1 + commission))

# Apply slippage on entry
execution_price = price * (1 + slippage)
trade_value = execution_price * quantity
commission_cost = trade_value * commission
total_cost = trade_value + commission_cost

# Deduct from cash
current_capital -= total_cost
# Open position with entry_price, quantity, timestamp
```

**SELL (closing long):**
```python
# Apply slippage on exit
execution_price = price * (1 - slippage)
trade_value = execution_price * quantity
commission_cost = trade_value * commission
net_proceeds = trade_value - commission_cost

# Calculate P&L
gross_pnl = trade_value - (entry_price * quantity)
net_pnl = gross_pnl - commission_cost

# Add proceeds back to cash
current_capital += net_proceeds
# Close position → FLAT
```

### Key Methods

- `execute_trade(signal, price, timestamp, symbol)` — Execute BUY/SELL
- `can_execute_trade(signal, price)` — Check if trade is feasible
- `update_position(current_price, timestamp)` — Update unrealized P&L
- `get_portfolio_value(current_price)` — Cash + position value
- `force_close_position(price, timestamp, symbol, reason)` — End-of-backtest cleanup
- `get_trade_history()` — List of completed trades
- `reset()` — Reset to initial state

---

## Performance Metrics

**Location:** `ktrdr/backtesting/performance.py`

### PerformanceMetrics (dataclass)

| Category | Metric | Description |
|----------|--------|-------------|
| **Returns** | `total_return` | Final value - initial capital |
| | `total_return_pct` | Return as decimal (0.15 = 15%) |
| | `annualized_return` | Annualized compound return |
| **Risk** | `volatility` | Annualized (daily std * sqrt(252)) |
| | `sharpe_ratio` | (mean_daily_return / std) * sqrt(252) |
| | `max_drawdown` | Largest peak-to-trough decline (decimal) |
| | `max_drawdown_pct` | Max drawdown as percentage |
| **Trades** | `total_trades` | Completed round-trip trades |
| | `winning_trades` / `losing_trades` | Count by P&L |
| | `win_rate` | winning / total (0-1) |
| | `profit_factor` | sum(wins) / abs(sum(losses)) |
| **Timing** | `avg_holding_period` | Average hours per trade |
| | `avg_win_holding_period` | Avg hours for winners |
| | `avg_loss_holding_period` | Avg hours for losers |
| **P&L** | `avg_win` / `avg_loss` | Per-trade averages |
| | `largest_win` / `largest_loss` | Extremes |
| **Advanced** | `calmar_ratio` | annualized_return / max_drawdown |
| | `sortino_ratio` | return / downside_vol * sqrt(252) |
| | `recovery_factor` | net_profit / max_drawdown |

**Safe serialization:** Inf/NaN values replaced with safe finite values (999999 for inf, 0 for NaN) to prevent JSON errors.

### PerformanceTracker

Tracks equity curve during simulation:

```python
tracker = PerformanceTracker()
tracker.update(timestamp, price, portfolio_value, position_status)
# Maintains: equity_curve, daily_returns, peak_equity, max_drawdown

metrics = tracker.calculate_metrics(trades, initial_capital, start_date, end_date)
```

---

## Decision Engine

**Location:** `ktrdr/decision/orchestrator.py`, `ktrdr/decision/engine.py`

### DecisionOrchestrator

Coordinates the full feature → model → signal pipeline:

1. Get features from `FeatureCache` (pre-computed) or compute real-time
2. Filter features to match model's expected inputs (from metadata)
3. Pass to `DecisionEngine` for neural network prediction
4. Return `TradingDecision` with signal, confidence, reasoning

### DecisionEngine

Runs the neural network forward pass:

```python
with torch.no_grad():
    output = model(features)
    prediction = output.argmax(dim=1).item()
    confidence = output.softmax(dim=1).max().item()

# Map to signal: 0=BUY, 1=SELL, 2=HOLD
```

---

## Feature Cache & Alignment

**Location:** `ktrdr/backtesting/feature_cache.py`

### Why it exists

Computing indicators and fuzzy memberships per-bar is slow. The feature cache pre-computes everything once for the full dataset, then provides fast lookup during simulation.

### Feature order validation

The cache validates that computed features match `model_metadata.resolved_features` (the exact features the model was trained on, in the exact order). If there's a mismatch, it raises `ValueError` — this prevents the model from receiving wrong inputs and producing garbage predictions.

```python
cache = FeatureCache(config=strategy_config, model_metadata=metadata)
cache.compute_features(data_dict)  # Pre-compute + validate order
features = cache.get_features_for_timestamp(timestamp)  # Fast lookup
```

---

## Model Loading

**Location:** `ktrdr/backtesting/model_loader.py`

### Model file structure

```
models/
└── momentum/
    └── AAPL_1h/
        ├── metadata_v3.json    # V3 metadata (resolved_features, etc.)
        ├── model.pt            # PyTorch state dict
        ├── config.json         # Strategy config
        └── features.json       # Feature definitions
```

### Loading

```python
loader = ModelLoader()
model, metadata = loader.load_model(strategy_name, symbol, timeframe)
# model: torch.nn.Module (eval mode)
# metadata: includes resolved_features for alignment validation
```

---

## Worker & Distribution

**Location:** `ktrdr/backtesting/backtest_worker.py`

Extends `WorkerAPIBase`. Registers as `WorkerType.BACKTESTING`.

### Worker endpoints

- `POST /backtests/start` — Start backtest (accepts `task_id` for ID sync with backend)
- `POST /backtests/resume` — Resume from checkpoint

### Backend dispatch

`BacktestingService` selects a worker via `WorkerRegistry`, dispatches via HTTP, and creates an `OperationServiceProxy` so the client can poll the backend for status.

Retry logic: up to 3 retries with different workers on 503 responses.

---

## Checkpointing

### Saving

- Checkpoint callback runs every ~100 bars during simulation
- `CheckpointPolicy` decides when to actually save (by bar interval or time interval)
- Checkpoint state includes: `bar_index`, `cash`, `positions`, `trades`, `equity_samples`, `original_request`
- On cancellation: saves checkpoint with type `"cancellation"`
- On success: deletes checkpoint (no longer needed)

### Resuming

```python
context = restore_from_checkpoint(checkpoint_service, operation_id)
# Returns: start_bar, cash, positions, trades, equity_samples

engine.resume_from_context(context)
# Loads full data, pre-computes indicators (for lookback), restores state
# Continues simulation from checkpoint bar + 1
```

---

## CLI

```bash
ktrdr backtest <strategy> --start YYYY-MM-DD --end YYYY-MM-DD [OPTIONS]

Options:
  --capital (-c)      Initial capital [default: 100000]
  --commission        Commission rate [default: 0.001]
  --slippage          Slippage rate [default: 0.001]
  --model-path (-m)   Explicit model path (optional)
  --follow (-f)       Watch progress until completion
```

---

## API

```
POST /backtests/start    → BacktestStartResponse (operation_id)
```

### Request

```json
{
  "strategy_name": "momentum",
  "start_date": "2024-01-01",
  "end_date": "2024-06-01",
  "initial_capital": 100000.0,
  "commission": 0.001,
  "slippage": 0.001,
  "symbol": "AAPL",          // optional (from strategy config)
  "timeframe": "1h",         // optional (from strategy config)
  "model_path": "/path/..."  // optional (for explicit V3 model)
}
```

---

## Gotchas

### Feature order must match training exactly

The `FeatureCache` validates that computed features match `model_metadata.resolved_features`. If features are reordered or missing, the model produces garbage. This is the single most common source of backtesting bugs.

### Warm-up period skips first ~50 bars

Indicators need lookback data. The simulation starts after a warm-up period (typically 50 bars). Don't expect decisions or trades in this window.

### Open positions are force-closed at end

Any position still open at the last bar is force-closed at market price. This prevents unrealized P&L from skewing results. The force-close trade appears in the trade history with reason `"End of backtest period"`.

### Position sizing uses 25% of available capital

`PositionManager` allocates 25% of available capital per trade. This is not configurable from the CLI — it's hardcoded in the position manager.

### Cancellation is checked every ~100 bars

Not every bar. If you cancel a long-running backtest, it may continue for up to 100 bars before stopping.

### Checkpoint resumes from next bar

Like training checkpoints, backtest checkpoints resume from `checkpoint_bar + 1`, not the checkpoint bar itself.

### Worker dispatch retries up to 3 times

If a backtest worker returns 503 (busy), the backend tries a different worker up to 3 times. All workers busy raises `WorkerUnavailableError`.

### Inf/NaN in metrics are sanitized

Performance metrics replace `inf` with 999999 and `NaN` with 0 for safe JSON serialization. Don't interpret 999999 as a real metric value.
