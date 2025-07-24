# Paper Trading Validation Requirements

## 1. Executive Summary

### Vision
We are building a paper trading validation system that bridges the gap between backtesting and live trading. The system executes discovered strategies against real-time market data through IB's paper trading API, providing empirical validation before risking real capital.

### Core Purpose
Paper trading serves as the final validation gate, confirming that our neuro-fuzzy strategies perform in real-time conditions as expected from backtests. This phase focuses on understanding execution dynamics, measuring realistic performance, and building confidence for V2's real money deployment.

### Key Deliverables
- Real-time decision engine connected to IB paper trading
- Position and order tracking system
- Performance comparison framework (paper vs backtest)
- Execution quality analytics

### Success Criteria
- Paper trading performance matches backtest expectations (>85% correlation)
- Slippage and timing differences documented and acceptable
- System runs stably for 2+ weeks without intervention
- Clear go/no-go decision for real capital deployment

---

## 2. System Architecture

### 2.1 Paper Trading Flow

The paper trading system operates as a real-time loop that mirrors production trading:

```
Market Data (IB) → Decision Engine → Signal Generation → Order Management → IB Paper Account
       ↑                                                                              ↓
       ←──────────────────── Position Tracking ←─────────────────────────────────────
```

#### Real-Time Processing Pipeline
1. **Market Data Ingestion**
   - Subscribe to real-time bars via IB API (configurable timeframe)
   - Process completed bars as they arrive
   - Maintain current market state for all tracked symbols

2. **Decision Execution**
   - Run trained neural network models on bar completion
   - Apply same fuzzy logic transformations as training
   - Generate BUY/HOLD/SELL signals with confidence scores

3. **Order Generation**
   - Convert signals to executable orders
   - Apply position sizing rules (fixed size for paper trading)
   - Check existing positions before new entries

4. **Execution & Tracking**
   - Submit orders to IB paper trading account
   - Monitor order status and fills
   - Update position tracking system
   - Calculate real-time P&L

### 2.2 Component Integration

Paper trading reuses existing KTRDR components with minimal modifications:

- **Data Layer**: Existing IB integration adapted for real-time bars
- **Decision Engine**: Latest trained models loaded from storage
- **New Components**: Order management and position tracking
- **Monitoring**: Extended metrics for paper trading performance

### 2.3 Validation Framework

The system continuously compares paper trading results to backtest expectations:

1. **Signal Alignment**: Do we generate the same signals?
2. **Timing Analysis**: How much delay between signal and execution?
3. **Fill Quality**: What prices do we actually get vs expected?
4. **Performance Tracking**: How do returns compare over time?

---

## 3. Detailed Requirements

### 3.1 Real-Time Decision Engine

#### Purpose
Execute trained neuro-fuzzy models against live market data to generate trading signals in real-time.

#### Functional Requirements

**Market Data Processing**
- Subscribe to real-time bars for all strategy symbols
- Use IB's real-time bar API (supports various timeframes: 5s, 1m, 5m, etc.)
- Maintain rolling windows of OHLCV data for indicator calculation
- Handle data gaps and anomalies gracefully
- Update indicators when bars complete

**Model Execution**
- Load the latest trained model for each strategy
- Calculate all required technical indicators in real-time
- Apply fuzzy transformations using existing engine
- Generate predictions on bar completion (timeframe matches training)

**Signal Generation**
- Convert model outputs to actionable signals
- Apply confidence thresholds from strategy configuration
- Implement signal persistence (avoid flip-flopping)
- Generate clear BUY/SELL signals only (no partial positions)

#### Technical Specifications
- Update frequency: On bar completion (1m, 5m, etc. - matches model training)
- Latency requirement: <100ms from bar close to signal
- Memory usage: Maintain only necessary historical data
- Error handling: Graceful degradation if model unavailable

### 3.2 Order Management System

#### Purpose
Translate trading signals into executable orders while maintaining accurate state of all positions and pending orders.

#### Functional Requirements

**Order Lifecycle Management**
- Create orders from trading signals
- Submit to IB paper trading API
- Track order status (pending, filled, cancelled)
- Handle partial fills appropriately
- Implement order timeout logic
- Apply simple slippage to market orders

**Position Tracking**
- Maintain real-time position state
- Track entry price, quantity, and timestamps
- Calculate unrealized P&L continuously
- Enforce one position per symbol rule (MVP simplification)

**Risk Controls**
- Maximum position size limits
- Daily loss limits (stop trading if exceeded)
- Prevent duplicate orders
- Cancel opposing orders when reversing

**Simple Slippage Model**
- Add configurable basis points to market orders (e.g., 2-5 bps)
- Buy orders: Execute at ask + slippage
- Sell orders: Execute at bid - slippage
- Log slippage amount for analysis

#### State Management
```
Positions Table:
- symbol: String
- quantity: Integer (positive=long, negative=short, 0=flat)
- entry_price: Float
- entry_time: Timestamp
- unrealized_pnl: Float
- realized_pnl: Float

Orders Table:
- order_id: Integer (IB assigned)
- symbol: String
- action: BUY/SELL
- quantity: Integer
- status: PENDING/FILLED/CANCELLED
- submit_time: Timestamp
- fill_price: Float (nullable)
- fill_time: Timestamp (nullable)
```

### 3.3 Performance Monitoring

#### Purpose
Track paper trading performance and compare against backtest expectations to validate strategy behavior.

#### Functional Requirements

**Real-Time Metrics**
- Track win rate, average win/loss
- Calculate running Sharpe ratio
- Monitor maximum drawdown
- Count trades per day/week

**Comparison Analytics**
- Signal correlation with backtest
- Timing difference analysis
- Slippage measurement
- Performance deviation tracking

**Reporting Dashboard**
- Daily performance summary (manual review)
- Trade-by-trade analysis
- Execution quality metrics
- Manual monitoring sufficient for MVP

#### Key Metrics
1. **Signal Accuracy**: % of signals matching backtest
2. **Execution Delay**: Average time from signal to fill
3. **Slippage**: Actual fill vs expected price
4. **Performance Delta**: Paper trading returns vs backtest
5. **System Uptime**: Hours of successful operation

### 3.4 Data Collection & Analysis

#### Purpose
Collect comprehensive data during paper trading for post-analysis and system improvement.

#### Data Requirements

**Trade Level Data**
- Every signal generated (even if not traded)
- Order submission and fill details
- Market conditions at decision time
- Indicator values used for decision

**System Performance Data**
- Decision engine latency
- API response times
- Memory and CPU usage
- Error logs and warnings

**Market Context**
- Spread at order time
- Volume profiles
- News events (if available)
- Market hours/holidays

#### Storage Schema
- Extend existing PostgreSQL schema
- New tables for paper_trades, paper_positions
- Link to original backtest results
- Maintain full audit trail

### 3.5 Integration Requirements

#### IB API Integration
- Use existing IB connection from V1
- Subscribe to paper trading account
- Handle paper trading specific responses
- Maintain connection stability

#### KTRDR Component Reuse
- Load models using existing model manager
- Use data management for historical context
- Apply same fuzzy logic engine
- Extend API for paper trading endpoints

#### Monitoring Integration
- Add paper trading metrics to dashboards
- Alert on connection issues
- Track order rejections
- Monitor account status

---

## 4. Implementation Considerations

### 4.1 MVP Simplifications

Keeping with MVP principles, we explicitly exclude:
- Complex order types (limit, stop) - market orders only
- Multi-position per symbol - one directional position at a time
- Portfolio optimization - trade each symbol independently
- Intraday position sizing - fixed size per trade
- Advanced execution algorithms - simple immediate execution
- Automated alerting - manual monitoring is sufficient

### 4.2 Testing Strategy

**Paper Trading Phases:**
1. **Single Symbol Test** (Days 1-3)
   - One strategy on most liquid symbol
   - Verify basic functionality
   - Compare first 20 trades to backtest

2. **Multi-Symbol Validation** (Days 4-10)
   - Add remaining symbols gradually
   - Monitor system stability
   - Verify no cross-symbol interference

3. **Full Operation** (Days 11-14)
   - All strategies running simultaneously
   - Collect comprehensive metrics
   - Final go/no-go assessment

### 4.3 Failure Scenarios

**Critical Failures (Stop Trading)**
- IB connection lost >5 minutes
- Position state mismatch
- Orders rejected repeatedly
- Model loading failures

**Warning Conditions (Monitor Closely)**
- High slippage (>0.5%)
- Signals deviating from backtest
- Unusual market conditions
- Performance significantly below expectations

### 4.4 Success Path

**Week 1 Milestones:**
- ✓ Orders executing successfully
- ✓ Positions tracked accurately
- ✓ No critical errors
- ✓ Initial metrics collected

**Week 2 Validation:**
- ✓ Performance within 15% of backtest
- ✓ Slippage acceptable (<0.3%)
- ✓ System stable without intervention
- ✓ Clear patterns in execution differences

**Go Decision Criteria:**
- Predictable relationship between paper and backtest
- Acceptable execution costs
- System reliability proven
- Risk controls functioning correctly

---

## 5. Deliverables Checklist

### Technical Deliverables
- [ ] Real-time decision engine
- [ ] Order management system
- [ ] Position tracking database
- [ ] Performance monitoring dashboard
- [ ] Comparison analytics tools

### Documentation Deliverables
- [ ] Paper trading operation guide
- [ ] Troubleshooting procedures
- [ ] Performance analysis report
- [ ] Go/no-go decision framework
- [ ] V2 migration plan

### Validation Deliverables
- [ ] 2 weeks of paper trading data
- [ ] Backtest comparison analysis
- [ ] Execution quality report
- [ ] Risk control verification
- [ ] System stability assessment