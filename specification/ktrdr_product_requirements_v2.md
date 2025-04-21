# KTRDR Product Requirements

## Implementation Prioritization

The KTRDR system will be implemented using a vertical slice approach, delivering incremental, testable value at each step. Features are prioritized in this sequence:

1. **Data Foundation (Highest Priority)**
   - Local data storage and retrieval for development
   - Basic configuration management
   - Command-line interface for data inspection

2. **Technical Analysis Capabilities**
   - Indicator computation and validation
   - Data integrity and gap detection
   - Enhanced configuration for indicators

3. **Visual Analysis Tools**
   - Interactive visualizations of price data and indicators
   - Export capabilities for analysis

4. **Fuzzy Logic System**
   - Membership function implementation
   - Configuration-driven fuzzy set definition
   - Indicator-to-fuzzy transformation

5. **Research UI**
   - Streamlit-based interactive interface
   - Integration of visualization components
   - Parameter adjustment capabilities

6. **Data Pipeline Enhancement**
   - Interactive Brokers integration
   - Intelligent data fetching and caching
   - Rate limiting and connection management

7. **Neural Implementation**
   - Basic neural network training
   - Data preparation pipeline
   - Model visualization and validation

8. **Trading Logic (Final Phase 1)**
   - Decision boundary implementation
   - Signal generation from neural outputs
   - Basic trade simulation and logging

This prioritization ensures that fundamental capabilities are solid before building more complex features, while still delivering testable value at each step.

---

## Product Plan Requirements Update – Data Management

### Historical and Real-Time Market Data Requirements

The ktrdr system must support robust and flexible access to market data, particularly from Interactive Brokers (IB). This includes:

- **Automated Data Presence Checking**: Before loading any data, the system should check whether the required historical or recent OHLCV data is already available in local storage (CSV or PostgreSQL).
- **Intelligent Gap Filling**: If data is partially missing or incomplete, the system should automatically fetch only the missing date/time ranges from IB.
- **Historical Backfill Support**: The system must allow for controlled, incremental backfilling of older historical data. This is crucial for expanding the dataset used during backtesting and strategy development.
- **Rate-Limit Awareness**: Because Interactive Brokers enforces strict rate limits on API requests, the system should throttle requests intelligently to stay within permitted bounds.
- **Interruptible and Resumable Fetching**: Backfilling should be designed to run in manageable chunks (e.g., fetch 5 days at a time) and allow resuming later, so that long operations can be split across sessions without losing progress.
- **Dual Persistence Support**: All data retrieved from IB should be storable into either:
  - A lightweight, file-based format (e.g., CSV) for rapid development and portability.
  - A robust, queryable database system (e.g., PostgreSQL, TimescaleDB, or similar) offering scalability and performance for larger datasets and complex analysis in production.

These features ensure that the Data Management module provides both fast developer iteration and long-term extensibility while supporting safe, resumable, and scalable access to high-quality market data.

### Acceptance Criteria for Data Management Vertical Slice
- Load and validate CSV data with consistent OHLCV format
- Save data to CSV with configurable path and naming conventions
- Handle common data irregularities (gaps, errors, duplicates)
- Provide command-line interface for basic data operations
- Include unit tests for core data loading functionality

---

## Product Plan Requirements Update – Core Decision Engine (Neuro-Fuzzy)

### Model Training, Configuration, and Execution Requirements

The ktrdr Core Decision Engine module is responsible for ingesting time-series market data, applying fuzzy logic transformation, and making trading decisions using a neural network. Requirements include:

- **Flexible Input Definitions**: The system must support defining and modifying the set of indicators and their corresponding fuzzy sets. This includes:

  - Membership function parameters for fuzzy classification
  - Logical partitioning of values (e.g., "low", "neutral", "high")
  - Fuzzy set definitions stored and editable in human-readable YAML files

- **Retrainable Model Pipeline**: The system must allow training and re-training of neural networks based on modified inputs, model structures, or fuzzy logic definitions. This includes:

  - Using the same processing and model interface for both training and inference
  - Compatibility with historical data from the Data Management module
  - Ability to switch between different model configurations as experiments evolve

- **Incremental Model Improvement**: In the early stages, the model will likely undergo frequent retraining and input redesign as part of exploratory development. The architecture must support:

  - Rapid prototyping and testing cycles
  - Clear separation of model versions (e.g., by config file and saved model name)

- **Future-Oriented Extensions** (not MVP, but should be considered in the architecture):

  - Support for model visualization, such as weights or signal paths
  - Integration of genetic optimization for fuzzy membership tuning

- **Unified Training/Inference Logic**: Training and inference must share a consistent codebase and APIs, so models can be validated and deployed without inconsistencies in logic or inputs.

These requirements ensure that the Core Decision Engine is flexible enough for rapid experimentation while being structured enough for eventual production deployment once a high-performing strategy is identified.

### Acceptance Criteria for Indicator Engine Vertical Slice
- Calculate common technical indicators (RSI, MA) from OHLCV data
- Validate indicator calculations against known reference values
- Support configuration-based indicator creation and parameters
- Provide command-line interface for indicator computation
- Include comprehensive tests for each implemented indicator

---

## Product Plan Requirements Update – Order Management

### Trade Execution, Lifecycle Tracking, and Broker Integration Requirements

The ktrdr Order Management module is responsible for safely translating trade signals into executable orders and maintaining accurate records of trading activity through a broker (initially Interactive Brokers). Requirements include:

- **Signal-Based Execution Flow**: The system must receive trading signals (from the Core Decision Engine) and convert them into actual trade requests:

  - Signals include action type (buy/sell), quantity, instrument, and optional confidence or metadata
  - Only valid and complete signals should be submitted to the broker

- **Broker Adapter Abstraction**: The system must abstract away broker-specific logic behind a modular adapter interface. The initial implementation must support Interactive Brokers, with flexibility to support other brokers later.

- **Order Lifecycle Management**:

  - Track orders from submission to completion or cancellation
  - Handle partial fills, rejections, and network errors
  - Maintain consistent internal state reflecting all live and historical orders

- **Risk Control and Guardrails**:

  - Enforce max position size limits per instrument
  - Enforce global exposure and drawdown limits
  - Include circuit breakers or emergency stop toggles

- **Persistent Logging and State Tracking**:

  - All submitted orders, modifications, status updates, and errors should be logged
  - Data must be saved either in CSV (for development) or PostgreSQL (for production)

- **Interactive Brokers API Compliance**:

  - Must respect rate limits and pacing rules enforced by IB
  - Must establish and maintain stable session with IB Gateway or TWS
  - Must reconnect and retry gracefully on dropped sessions

- **Order Type Support**:

  - The system will primarily support market orders based on the neural network's immediate evaluation of entry and exit conditions
  - Stop-loss orders may be introduced early in development to provide protection against large losses, in line with the system's bankruptcy-avoidance principle
  - Limit orders and time-based entry/exit logic are not prioritized for the MVP, as they conflict with the continuous decision-making model of the neural network

- **Event-Driven Monitoring (IB-Aligned)**:

  - Order state changes should be handled using event-driven callbacks from the Interactive Brokers API
  - This design aligns with how IB sessions work and allows timely tracking of fills, errors, and cancellations without constant polling

- **Error Handling Philosophy**:

  - Errors on entry orders should trigger light retry logic but not compromise the overall system state
  - Errors on exit orders are considered critical: the system must aggressively retry and trigger alerts if the exit cannot be processed within defined limits
  - In severe error cases, the system should halt trading activity and notify the user for manual intervention

- **Emergency Stop Behavior**:

  - Must include a mechanism to fully exit all open positions and cancel all outstanding orders
  - Should be triggered either manually via the UI or automatically when specific capital, position, or error thresholds are crossed
  - If supported by the broker (e.g., IB), should attempt an all-positions liquidation command; otherwise, loop through and close all known positions individually

These requirements ensure that Order Management provides not only robust and auditable execution but also integrates safely with live brokers under real-world conditions. The system must protect capital and provide the user with confidence that trade logic is being carried out transparently and safely.

### Acceptance Criteria for Interactive Brokers Integration Vertical Slice
- Connect to IB API and maintain stable connection
- Fetch historical data with proper rate limiting
- Implement gap detection and intelligent data merging
- Handle common connection errors and timeouts
- Store fetched data in consistent local format

---

## Product Plan Requirements Update – User Experience (UX)

### Visualization, Oversight, and Runtime Control Requirements (Across Development, Research, and Live Operation Phases)

The UX module is intended to provide clear, reliable, and intuitive access to both system internals and real-time trading behavior, catering to development, debugging, and live supervision. Requirements include:

- **Visual Feedback for Indicators and Trades**:
  - Plot price and indicator data in context over time (candlesticks, overlays)
  - Annotate trades (entry/exit) and signals on charts for traceability
  - Show fuzzy membership breakdowns used for NN input at each decision point

- **Backtesting and Evaluation Reporting**:
  - Show training and test data results: PnL, win rate, drawdown
  - Segment performance by symbol, timeframe, or strategy version
  - Display confusion matrices or signal statistics if applicable

- **Live Monitoring and Alerting**:
  - Display active orders, current positions, and capital usage
  - Provide log streams for strategy execution, data updates, and errors
  - Trigger warnings or alerts for risk violations or broker errors

- **Emergency Controls and Manual Overrides**:
  - Include a visible emergency stop button to close all positions and halt trading
  - Provide optional ability to approve, reject, or cancel individual trades

- **Config Management Interface**:
  - Surface YAML-based configuration parameters with live read-back and reload
  - Show active model name, indicator set, and fuzzy definition files

- **Usability Requirements**:
  - Interface must be intuitive, fast to load, and robust against backend restarts
  - For MVP, Streamlit or Dash can be used for rapid local UI development
  - Longer term, UI may be upgraded to a decoupled web frontend (e.g., React + API). Note: Transitioning from the MVP UI framework to a full web frontend represents a significant effort and should be planned accordingly.

- **Phase-Based Design Considerations**:
  - **Development Phase**: UI must help verify correctness of system components
  - **Research Phase**: UI supports exploring indicators and strategy behavior
  - **Production Phase**: UI must emphasize monitoring, safety, and control

### Acceptance Criteria for Visualization Vertical Slice
- Generate interactive candlestick charts with Plotly
- Overlay technical indicators on price charts
- Create separate indicator subplots with proper scaling
- Support zooming, panning, and date range selection
- Export visualizations as HTML or image files

---

## Product Plan Requirements Update – System-Wide & Cross-Cutting Concerns

### Configuration, Logging, Testing, Deployment, and Security Requirements

- YAML config system with no hardcoded credentials (env or secrets manager instead)
- Automated testing from unit to full integration with reproducible results
- Docker-based deployment preferred for modular setup and containerization
- Clear crash recovery expectations during live trading
- Notification path from console logs to UI alerts, and eventually out-of-band methods
- Security: Beyond avoiding hardcoded credentials (using env vars or secrets manager), ensure secure storage and handling of sensitive configuration (like broker API keys) both at rest and in transit. Implement appropriate access controls if deployed in a shared environment

### Cross-Cutting Concerns Implementation Strategy

KTRDR adopts a pragmatic approach to cross-cutting concerns that balances robust architecture with development efficiency. Features are categorized by implementation priority:

#### Error Handling and Logging Strategy (High Priority)

The system implements a focused error handling and logging approach:

- **User-Facing Error Messages**:
  - Balance information detail with clarity (actionable without technical jargon)
  - Use consistent terminology and formatting across all interfaces
  - Include basic error codes for reference
  - Suggest possible solutions for common errors

- **Logging System**:
  - Implement standard logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - Support both console and file-based logging with simple configuration
  - Allow disabling console output while maintaining file logging
  - Configure basic log rotation to prevent excessive file sizes
  - Include essential context such as timestamp, module, and function

- **Error Categorization**:
  - Data errors (missing, corrupt, or invalid data)
  - Connection errors (network issues, API failures)
  - Configuration errors (invalid settings, missing required parameters)
  - Processing errors (calculation failures, unexpected results)
  - System errors (resource limitations, unexpected crashes)

- **Error Recovery** (Simplified):
  - Implement retry logic with exponential backoff for network operations
  - Provide basic cleanup for partial operations when errors occur
  - Define fallback behaviors for critical components

- **Debugging Support**:
  - Global debug flag to toggle extended debug information
  - Include stack traces in log files (but not in user-facing messages)

#### Testing Strategy (Medium Priority)

- Focus testing on critical algorithms and data transformations
- Implement smoke tests for integration points
- Use standard pytest framework with fixtures
- Prioritize tests for indicator calculations and fuzzy logic

#### Security Basics (Medium Priority)

- Store API keys and credentials securely using environment variables
- Implement basic input validation for user-provided data
- Ensure sensitive configuration is not committed to version control

#### Deferred Capabilities (For Future Versions)

The following capabilities are recognized as valuable but deferred to later versions:

- Advanced circuit breaker patterns for error handling
- Comprehensive error metrics and analysis
- Performance monitoring dashboards
- Advanced dependency management beyond UV basics
- Automated security scanning

This pragmatic approach ensures that essential cross-cutting concerns are addressed while maintaining development velocity on core functionality.
