## ktrdr Product Roadmap and MVP Definition (Updated)

### Product Vision (Reminder)

ktrdr is an automated trading agent for a single user (you), built around a neuro-fuzzy decision engine. It will:

- Allow strategy prototyping and validation through backtesting
- Support paper trading to test live integration without capital risk
- Eventually enable live trading with protective mechanisms

The system is deeply visual, introspectable, and iterative. The UX serves both development and monitoring.

---

### Updated MVP Definition

The MVP should allow end-to-end strategy execution and validation *in backtesting and paper trading modes*, without risking capital.

#### ✅ MVP Must Include:

- **Data Management**

  - CSV + IB data fetching (historical + gap fill)
  - Local persistence (CSV)
  - At least one working indicator and fuzzy set defined in YAML

- **Core Decision Engine**

  - Fuzzy-to-neural flow with pluggable config
  - Working training/inference shared pipeline
  - Configurable inputs via YAML

- **Order Management**

  - Market order simulation (paper adapter)
  - IB paper trading support
  - Error handling and logging

- **UX**

  - Plot candlesticks + indicators + trades
  - Show fuzzy memberships per trade
  - Manual config reload (no UI editing)
  - Emergency stop trigger (UI button only)

- **System-Wide**

  - YAML config structure
  - Unit tests for major logic
  - Docker-compose dev setup

#### ❌ Not in MVP:

- Stop-loss / capital controls (enable later, post-paper trading)
- Multi-symbol or timeframe
- Live capital deployment
- Automated re-training or optimization

---

### Version Strategy

#### MVP (Current)

See MVP definition above.

#### Version 1 (V1): Fully Featured Paper Trading Platform

- Emergency stop logic implemented and testable
- Stop-loss and capital protection enabled
- Rich UI: logs, portfolio views, live updates
- Structured logging persisted to DB
- Support for model versions and configuration profiles
- Integrated test suite + reproducible builds (Dockerized)

#### Version 2 (V2): Production-Grade Live Trading System

**Note:** The transition to V2 represents a significant increase in requirements for reliability, security, monitoring, and operational robustness compared to V1. Foundational work supporting these aspects (e.g., robust error handling, enhanced logging, infrastructure readiness) should be considered during V1 development.

- Live IB trading with full capital risk controls
- Notification integration (email, webhook)
- Broker reconnection/resume engine
- Strategy A/B experimentation support
- Multi-symbol, multi-timeframe architecture
- Model visualization tools (weights, fuzzy activations)

**Deferred Cross-Cutting Concerns** (To be implemented in V2):
- Advanced observability and monitoring capabilities (metrics dashboards, performance tracking)
- Enhanced security measures beyond basic credential management
- Circuit breaker patterns for advanced error handling
- Comprehensive dependency management and vulnerability scanning
- Advanced configuration versioning and history tracking

---

### Roadmap Milestones (Refined by Phases)

#### Phase 1: Development – Visual + Incremental Validation (Backbone of System)

- ✅ Scaffold Python modules and configs
- ✅ Connect to IB and pull historical OHLCV (initial simple case: e.g., 1 year of data)
- ✅ Save to CSV
- ✅ Visualize candlesticks (basic charting)
- ✅ Compute and overlay one indicator (e.g., RSI)
- ✅ Fuzzy membership visualization per indicator (basic static example)

#### Phase 2: Research – Backtesting with Neuro-Fuzzy Logic (Exploration, Metrics, Tuning)

- ✅ Design and parse fuzzy inputs (YAML-based config definitions)
- ✅ Fuzzy activation visualization (indicator → set mapping)
- ✅ Define and implement one basic model architecture (e.g., MLP) with training pipeline
- ✅ Implement standalone inference logic that uses trained model on new fuzzy inputs
- ✅ Train model on simple historical data (limited set)
- ✅ Evaluate training output and log diagnostic info
- ✅ Plot trades vs. zigzag or benchmark reference
- ✅ Chart PnL, win/loss breakdown, confusion matrix
- ✅ Tune fuzzy parameters and view impact

#### Phase 3: Paper Trading – Live Data + Paper Orders (Runtime Validation, UI Feedback)

- Dependency Note: Initiation of Phase 3 assumes sufficient stability and validation of the core Neuro-Fuzzy logic and backtesting results from Phase 2. Key model performance metrics should meet baseline criteria before proceeding to paper trading.
- ✅ Live price feed from IB
- ✅ Paper order submission via broker adapter
- ✅ Order state tracking and logs
- ✅ Emergency stop button
- ✅ UI: open positions, trades, and capital snapshot

#### Phase 4: Productionization – Risk, Recovery, and Stability (Pre-Live Protection Layer)

- ✅ Stop-loss enforcement on orders
- ✅ Capital-based trading limits
- ✅ Auto-restart on system crash
- ✅ UI alerts and error visibility

#### Phase 5: Expansion and Experimentation (Advanced Capabilities & System Growth)

- ✅ Add more indicators and fuzzy configs
- ✅ Add multi-symbol support
- ✅ Add webhook/email notifications
- ✅ Enable strategy switching by config
- ✅ Add backend performance dashboards
- Configurable live vs paper switch
- Logging to DB or structured file
- More indicators and fuzzy sets
- UX performance polish

### UX/API Path – Cross-Cutting UI Enablement

- ✅ Phase 1: Console and simple static plots via Streamlit, plotly or notebook
- ✅ Phase 2: Expand visualization with fuzzy input diagnostics and performance
- ✅ Phase 3: Web UI backend with REST API endpoints (FastAPI or Flask)
- ✅ Phase 3+: React frontend or Dash (optional) for interactive dashboards
- ✅ Throughout: Ensure all visual components are testable and evolve with system maturity

---

### 📝 Notes on Neural Training and Inference Steps

- **Define and implement one basic model architecture**:
  - Choose a simple neural network structure (MLP)
  - Specify input shape based on fuzzy input vector size
  - Define model layers, activations, output (e.g., softmax for signal class)
  - Integrate with a training loop using loss/optimizer/scheduler as needed
  - Enable training on small historical sets to test viability

- **Implement standalone inference logic**:
  - Load saved model weights (e.g., `.pt` file)
  - Accept fuzzy input vector as runtime input
  - Run forward pass and produce decision output (e.g., action + confidence)
  - Integrate into backtest and paper trading modes

Let’s iterate from this structure as needed!