# KTRDR MCP Server Requirements Document

## Executive Summary
The KTRDR MCP (Model Context Protocol) Server enables Claude to conduct autonomous research on neuro-fuzzy trading strategies. The primary goal is creative strategy discovery through systematic experimentation, with secondary capability to extend the system when research demands it.

## 1. Primary Objective
Enable Claude to conduct autonomous research on neuro-fuzzy trading strategies, discovering profitable approaches through systematic experimentation and creative exploration.

## 2. Core Research Requirements

### 2.1 Strategy Discovery & Creative Exploration

#### Novel Strategy Generation
- **Creative Hypothesis Formation**: Imagine new ways markets might exhibit patterns
  - "What if we could detect when institutions are accumulating?"
  - "Could lunar cycles affect trader psychology in measurable ways?"
  - "Can we identify when algorithms are fighting each other?"
- **Cross-Domain Inspiration**: Apply concepts from other fields
  - Physics (momentum, resistance, harmonics)
  - Biology (predator-prey dynamics, evolution)
  - Psychology (fear/greed cycles, herd behavior)
- **Academic Research Integration**: Search for cutting-edge papers and translate to practical strategies
- **Market Microstructure Insights**: Develop indicators that capture order flow, liquidity dynamics
- **Sentiment and Alternative Data**: Explore unconventional data relationships

#### Indicator Innovation
- **Composite Indicators**: Combine existing indicators in novel ways
- **Market Condition Detectors**: Create indicators specifically for regime identification
- **Adaptive Indicators**: Parameters that adjust based on market state
- **Relationship Indicators**: Capture inter-market dynamics (e.g., bonds vs stocks)

### 2.2 Research Workflow Capabilities

#### Imaginative Hypothesis Generation
- **"What If" Explorations**: 
  - What if volatility clusters have memory patterns?
  - What if certain price levels act as magnets?
  - What if market makers leave detectable footprints?
- **Pattern Mining**: Look for recurring patterns others might miss
- **Anomaly Investigation**: When strategies fail unexpectedly, dig deeper for insights

#### 📌 **Knowledge Accumulation System** (Priority Item)
- **Research Journal**: Document all hypotheses, tests, and insights
- **Pattern Library**: Catalog successful indicator combinations
- **Failure Museum**: Archive what doesn't work and why
- **Insight Connections**: Link related findings across experiments
- **Meta-Strategies**: Strategies about when to use strategies

#### Research Intelligence
- **Experiment Design**: Structure tests to isolate variables
- **Statistical Validation**: Ensure results are significant, not random
- **Failure Analysis**: Understand why strategies fail, not just celebrate successes
- **Pattern Recognition**: Identify what makes strategies successful

### 2.3 Performance Evaluation

#### Context-Dependent Success Metrics
- **Strategy Profiles**: Each strategy tagged with its "personality"
  - Trend Rider: High returns in strong trends, struggles in ranges
  - Mean Reverter: Steady gains in quiet markets, stops out in trends
  - Volatility Harvester: Thrives on chaos, sleeps in calm
  - Regime Switcher: Moderate gains everywhere, excels at transitions

#### Comprehensive Metrics
- **Risk-Adjusted Returns**: Sharpe, Sortino, Calmar ratios
- **Drawdown Analysis**: Maximum, average, recovery time
- **Trade Metrics**: Win rate, profit factor, average win/loss
- **Robustness Testing**: Performance across different market conditions
- **Transaction Cost Analysis**: Real-world viability with slippage/fees

#### Market Condition Detection
- **Volatility Regimes**: Low/Medium/High with transitions
- **Trend States**: Strong up/down, weak trending, ranging
- **Liquidity Conditions**: Thick/thin markets
- **Sentiment Indicators**: Risk-on/risk-off detection
- **Structural Breaks**: Regime change identification

### 2.4 Adaptive Strategy Framework

#### Self-Aware Strategies
- **Market Condition Inputs**: NN receives current regime as feature
- **Confidence-Based Position Sizing**: NN outputs "no trade" when uncertain
- **Dynamic Exit Strategies**: Different exits for different market conditions
- **Strategy Ensemble**: Multiple specialists with a meta-strategy selector

## 3. Capability Extension Requirements

### 3.1 Extension Priority Hierarchy

#### Level 1: Configuration Changes (Hours)
- Modify indicator parameters
- Adjust fuzzy set definitions
- Change neural network hyperparameters
- Alter backtest date ranges

#### Level 2: New Components (Days)
- Add new indicators (following existing patterns)
- Create new fuzzy membership functions
- Design alternative neural architectures
- Implement new performance metrics

#### Level 3: System Enhancements (Weeks)
- Multi-timeframe analysis
- Portfolio-level strategies
- Alternative ML models (LSTM, Random Forests)
- Advanced position management

#### Level 4: Architectural Changes (Months)
- Real-time streaming architecture
- Distributed backtesting
- Alternative data sources
- Multi-strategy coordination

### 3.2 Extension Triggers
The system should only pursue extensions when:
1. Multiple research paths converge on the same limitation
2. Potential improvement justifies complexity
3. Extension enables fundamentally new research directions
4. Current tools have been exhaustively explored

### 3.3 Code Evolution Process
- **Sandbox Development**: Isolated environment for experiments
- **Staged Integration**: Sandbox → Review → Production
- **Version Control**: Git-based branching strategy
- **Quality Assurance**: Automated testing before integration

## 4. System Architecture Requirements

### 4.1 Container Architecture
- **Production Backend**: Stable API and trading operations
- **MCP Research Container(s)**: Isolated research environments
- **Data Cache Service**: Centralized market data management
- **Experiment Database**: Research tracking and metrics

### 4.2 Data Access
- **Read-Only Market Data**: Shared volume with production
- **Centralized Data Fetching**: Avoid duplicate IB requests
- **Research Data Requests**: Register needs with data cache service
- **Historical Data Support**: Multi-year backtesting capability

### 4.3 Safety & Isolation
- **No Production Modifications**: Cannot change live trading code directly
- **No Order Execution**: Cannot place trades (even paper)
- **Resource Isolation**: Separate compute resources
- **Crash Recovery**: Research continues despite failures

## 5. Operational Requirements

### 5.1 Monitoring & Alerting
- **Real-Time Dashboards**: Current experiments and progress
- **Simple Notification System**: HTTP POST to stateless endpoint with notification data
  - Endpoint will trigger LogicApps/n8n for complex notification routing
  - Keep notification system simple and decoupled
- **Interesting Findings Alerts**: Notify when promising strategies found
- **Failure Notifications**: Alert on systematic issues

### 5.2 Collaboration Interface
- **Research Reports**: Regular summaries of findings
- **Decision Points**: Clear escalation for important choices
- **Review Cadence**: Weekly sync on research progress
- **Knowledge Transfer**: Documentation of insights

### 5.3 Resource Management
- **Future Consideration**: Resource limits will be addressed when scaling issues arise
- **Monitoring First**: Track usage patterns before implementing hard limits

## 6. Data Requirements

### 6.1 Historical Data
- **Minimum History**: 2 years for initial validation, 5+ years preferred
- **Granularity**: Support for multiple timeframes (1m to 1D minimum)
- **Quality Standards**: Handle gaps, validate price relationships
- **Corporate Actions**: Adjust for splits, dividends

### 6.2 Symbol Universe
- **Research-Driven Selection**: Strategy research determines data needs
- **Data Availability Constraints**: Work within IB data limitations initially
- **Future Expansion**: Better data sources if research proves successful
- **Flexible Approach**: Communicate data needs, negotiate availability

## 7. Integration Requirements

### 7.1 API Compatibility
- **Industry Best Practices**: Follow semantic versioning and deprecation policies
- **Selective Compatibility**: Maintain compatibility for successful strategies only
- **Evolution Over Legacy**: Prioritize system improvement over maintaining failed experiments

### 7.2 Migration Path
- **Strategy Export**: Clean handoff from research to production
- **Configuration Management**: YAML-based strategy definitions
- **Model Versioning**: Track and deploy specific versions
- **Performance Validation**: Verify research results in production

## 8. Security & Compliance

### 8.1 Access Control
- **Secrets Management**: Critical requirement - secure handling of all credentials
- **Network Access**: Controlled external access for research purposes
- **Audit Trail**: Complete log of all operations and decisions
- **Data Privacy**: No exposure of sensitive information

### 8.2 Ethical Constraints
- **No Market Manipulation**: Avoid strategies that could manipulate prices
- **Fair Trading Practices**: Comply with market regulations
- **Risk Transparency**: Clear understanding of strategy risks
- **Honest Reporting**: Accurate representation of performance

## 9. Success Criteria

### 9.1 Research Productivity
- **Strategies Tested**: 100+ strategies per week
- **Novel Ideas**: 5-10 creative hypotheses per week
- **Profitable Discoveries**: 1-2 viable strategies per month
- **Knowledge Growth**: Measurable insight accumulation

### 9.2 Quality Metrics
- **Out-of-Sample Performance**: 70% correlation with backtest
- **Strategy Diversity**: <0.5 correlation between strategies
- **Robustness Score**: Strategies work across 3+ market regimes
- **Real-World Viability**: Profitable after costs in 60%+ cases

### 9.3 System Evolution
- **Extension Velocity**: New capability within 48 hours of need
- **Integration Success**: 90%+ of extensions work first time
- **Research Acceleration**: 2x productivity after 3 months
- **Insight Application**: 80% of learnings influence future research

## 10. Constraints & Boundaries

### 10.1 Risk Limits
- **Primary Rule**: Don't bankrupt the user
- **Capital Allocation**: Work within designated research capital allocation
- **Leverage Awareness**: Avoid positions that could impact beyond allocated capital
- **Position Sizing**: Respect portfolio management constraints

### 10.2 Complexity Boundaries
- **Adaptive Approach**: Learn boundaries through experience
- **Retrospective Analysis**: Regular reviews to identify complexity patterns
- **Journal Insights**: Document when complexity becomes problematic
- **Evolution Over Time**: Let research guide acceptable complexity levels

## 11. Implementation Priorities

### Phase 1: Foundation (Week 1-2)
- Basic MCP server with API passthrough
- Research experiment tracking
- Simple strategy testing capability

### Phase 2: Creative Research (Week 3-4)
- Advanced hypothesis generation
- Pattern mining tools
- Knowledge accumulation system

### Phase 3: Extension Capability (Week 5-6)
- Code generation framework
- Sandbox environment
- Review and integration process

### Phase 4: Scale & Optimize (Week 7+)
- Multi-container orchestration
- Performance optimization
- Advanced monitoring

---

## Appendix: Example Research Projects

### Project 1: "Market Maker Detector"
- Hypothesis: Market makers leave footprints in order flow
- Approach: Analyze bid-ask patterns, volume clusters
- Success Metric: Identify MM activity with 70% accuracy

### Project 2: "Regime Transition Trader"
- Hypothesis: Markets telegraph regime changes before they happen
- Approach: Multi-timeframe divergence analysis
- Success Metric: Catch 60% of major trend changes

### Project 3: "The Harmonics Hunter"
- Hypothesis: Price movements follow musical harmonic patterns
- Approach: Fourier analysis on price series
- Success Metric: Find repeating patterns with >1.5 Sharpe

---

## 12. Open Questions for Future Design

### 12.1 End-to-End Experience
- **Research Session Lifecycle**: How are research sessions initiated, managed, and concluded?
- **State Management**: What state needs to be saved? How do we recover from crashes?
- **Research Boundaries**: How many strategies per session? When to stop?
- **Progress Communication**: How does the system communicate ongoing status?

### 12.2 Backup & Recovery Architecture
- **Crash Scenarios**: What components can fail and how?
- **State Persistence**: What needs to be saved and when?
- **Recovery Procedures**: How to resume interrupted research?
- **Data Integrity**: Ensuring research results aren't lost

### 12.3 Success Metrics Definition
- **Performance Dimensions**: Which metrics matter most?
- **Evaluation Timeframes**: How long to test before declaring success?
- **Comparative Baselines**: What to compare strategies against?
- **Statistical Significance**: How to ensure results aren't random?

### 12.4 Research Boundaries
- **Session Scope**: How much research per trigger?
- **Termination Criteria**: When to stop exploring a hypothesis?
- **Resource Allocation**: How to divide effort across ideas?
- **Priority Management**: Which research directions to pursue first?

### 12.5 Integration Details
- **Migration Workflows**: How to move strategies from research to production?
- **Version Management**: How to handle strategy evolution?
- **Performance Validation**: Ensuring research results translate to live trading?

---

**Document Version**: 1.0  
**Last Updated**: December 2024  
**Status**: Draft for Review