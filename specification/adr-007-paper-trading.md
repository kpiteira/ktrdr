# ADR-007: Paper Trading Integration

## Status
**Draft** - December 2024

## Context
Paper trading serves as the critical validation bridge between backtesting and live trading. Unlike backtesting, which uses historical data, paper trading executes strategies in real-time market conditions using Interactive Brokers' simulated trading environment.

The primary goal is not just to verify profitability, but to validate that strategy behavior in live markets matches backtest expectations. This includes order execution, timing, signal generation, and overall trading patterns.

## Decision

### Paper Trading Philosophy

The paper trading system focuses on **behavioral validation** rather than just performance metrics:

1. **Trade Matching**: Do we take similar trades in paper vs backtest?
2. **Timing Accuracy**: Are signals generated at the expected times?
3. **Execution Reality**: How does slippage/spread compare to assumptions?
4. **System Reliability**: Can the system run 24/7 without issues?
5. **Risk Compliance**: Are position sizes and stops working correctly?

### System Architecture

```
┌─────────────────────── Paper Trading System ────────────────────────┐
│                                                                      │
│  Real-time Data          Decision Engine        Order Management    │
│  ┌─────────────┐        ┌──────────────┐      ┌────────────────┐  │
│  │ IB Gateway  │───────►│ Orchestrator │─────►│ Paper Executor │  │
│  │ (Real-time) │        │ (Live Mode)  │      │ (IB Paper API) │  │
│  └─────────────┘        └──────┬───────┘      └───────┬────────┘  │
│         │                      │                       │           │
│         ▼                      ▼                       ▼           │
│  ┌─────────────┐        ┌──────────────┐      ┌────────────────┐  │
│  │ Time Series │        │  Position    │      │     Order      │  │
│  │  Database   │        │   Tracker    │      │    History     │  │
│  └─────────────┘        └──────────────┘      └────────────────┘  │
│                                                                      │
│  Monitoring & Validation                                             │
│  ┌─────────────┐        ┌──────────────┐      ┌────────────────┐  │
│  │ Real-time   │        │  Behavior    │      │   Alert        │  │
│  │ Dashboard   │        │  Validator   │      │   System       │  │
│  └─────────────┘        └──────────────┘      └────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Paper Trading Orchestrator

```python
# ktrdr/paper_trading/orchestrator.py
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta

@dataclass
class PaperTradingConfig:
    """Configuration for paper trading session"""
    strategy_name: str
    symbol: str
    timeframes: List[str]  # Multiple timeframes
    model_path: str
    
    # Execution settings
    check_frequency: int = 60  # seconds
    max_position_size: float = 0.95
    
    # Validation settings
    track_behavior: bool = True
    compare_with_backtest: bool = True
    
    # Risk limits
    max_daily_trades: int = 10
    max_daily_loss: float = 0.02  # 2%
    emergency_stop: bool = True

class PaperTradingOrchestrator:
    """
    Manages paper trading operations with behavioral validation
    """
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.decision_engine = DecisionOrchestrator(
            strategy_config_path=f"strategies/{config.strategy_name}.yaml",
            model_path=config.model_path,
            mode="paper"
        )
        self.executor = PaperExecutor()
        self.validator = BehaviorValidator(config)
        self.position_tracker = PositionTracker()
        self.is_running = False
        
    async def start(self):
        """Start paper trading with multi-timeframe support"""
        self.is_running = True
        
        # Schedule tasks for each timeframe
        tasks = []
        for timeframe in self.config.timeframes:
            task = asyncio.create_task(
                self._run_timeframe_loop(timeframe)
            )
            tasks.append(task)
        
        # Add monitoring task
        monitor_task = asyncio.create_task(self._monitor_performance())
        tasks.append(monitor_task)
        
        # Run all tasks concurrently
        await asyncio.gather(*tasks)
    
    async def _run_timeframe_loop(self, timeframe: str):
        """Main loop for a specific timeframe"""
        
        while self.is_running:
            try:
                # Get current market data
                current_data = await self._get_current_data(
                    self.config.symbol, 
                    timeframe
                )
                
                # Check if we have a new completed bar
                if self._is_new_bar(current_data, timeframe):
                    await self._process_new_bar(current_data, timeframe)
                
                # Sleep based on timeframe
                sleep_duration = self._calculate_sleep_duration(timeframe)
                await asyncio.sleep(sleep_duration)
                
            except Exception as e:
                logger.error(f"Error in {timeframe} loop: {e}")
                await self._handle_error(e)
    
    async def _process_new_bar(self, data: pd.DataFrame, timeframe: str):
        """Process a new completed bar"""
        
        # Get historical data for decision
        historical_data = await self._get_historical_data(
            self.config.symbol,
            timeframe,
            bars=200  # Enough for indicators
        )
        
        # Generate decision
        decision = self.decision_engine.make_decision(
            symbol=self.config.symbol,
            timeframe=timeframe,
            current_bar=data.iloc[-1],
            historical_data=historical_data,
            portfolio_state=self._get_portfolio_state()
        )
        
        # Log decision for validation
        await self.validator.log_decision(decision, timeframe)
        
        # Execute if we have a signal
        if decision.signal != Signal.HOLD:
            await self._execute_decision(decision, timeframe)
    
    async def _execute_decision(self, decision: TradingDecision, timeframe: str):
        """Execute trading decision with validation"""
        
        # Check risk limits
        if not self._check_risk_limits():
            logger.warning("Risk limits exceeded, skipping trade")
            return
        
        # Prepare order
        order = self._prepare_order(decision)
        
        # Execute through paper trading
        execution_result = await self.executor.execute_order(order)
        
        # Update position tracking
        self.position_tracker.update(execution_result)
        
        # Validate behavior
        await self.validator.validate_execution(
            decision, 
            execution_result,
            timeframe
        )
```

### 2. Behavior Validator

```python
# ktrdr/paper_trading/behavior_validator.py
class BehaviorValidator:
    """
    Validates paper trading behavior against backtest expectations
    """
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.decision_log = []
        self.execution_log = []
        self.db = DatabaseConnection()
        
    async def log_decision(self, decision: TradingDecision, timeframe: str):
        """Log every decision for later comparison"""
        
        record = {
            'timestamp': decision.timestamp,
            'timeframe': timeframe,
            'signal': decision.signal.value,
            'confidence': decision.confidence,
            'reasoning': decision.reasoning,
            'indicators': decision.reasoning.get('indicators', {}),
            'fuzzy_values': decision.reasoning.get('fuzzy_memberships', {})
        }
        
        self.decision_log.append(record)
        
        # Store in database for analysis
        await self.db.execute("""
            INSERT INTO paper_decisions 
            (strategy_name, symbol, timestamp, timeframe, signal, 
             confidence, reasoning)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (self.config.strategy_name, self.config.symbol,
              record['timestamp'], timeframe, record['signal'],
              record['confidence'], json.dumps(record['reasoning'])))
    
    async def validate_execution(self, decision: TradingDecision, 
                               execution: ExecutionResult,
                               timeframe: str):
        """Validate execution matches expectations"""
        
        validation_results = {
            'timestamp': datetime.utcnow(),
            'decision_time': decision.timestamp,
            'execution_time': execution.timestamp,
            'time_lag': (execution.timestamp - decision.timestamp).total_seconds(),
            'expected_price': decision.expected_price,
            'execution_price': execution.fill_price,
            'slippage': abs(execution.fill_price - decision.expected_price),
            'expected_size': decision.position_size,
            'actual_size': execution.filled_quantity
        }
        
        # Check for anomalies
        if validation_results['time_lag'] > 5:  # More than 5 seconds
            logger.warning(f"High execution latency: {validation_results['time_lag']}s")
        
        if validation_results['slippage'] > decision.expected_price * 0.002:  # 0.2%
            logger.warning(f"High slippage: {validation_results['slippage']}")
        
        # Store for analysis
        self.execution_log.append(validation_results)
        await self._store_validation_results(validation_results)
    
    async def compare_with_backtest(self, start_date: datetime, end_date: datetime):
        """
        Compare paper trading results with backtest on same period
        This is the key validation step!
        """
        
        # Get paper trading decisions
        paper_decisions = await self.db.query("""
            SELECT * FROM paper_decisions
            WHERE strategy_name = %s 
            AND symbol = %s
            AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp
        """, (self.config.strategy_name, self.config.symbol, start_date, end_date))
        
        # Run backtest on same period
        backtest_config = BacktestConfig(
            model_path=self.config.model_path,
            symbol=self.config.symbol,
            timeframe=self.config.timeframes[0],  # Primary timeframe
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            initial_capital=100000  # Same as paper
        )
        
        backtest_engine = BacktestingEngine(backtest_config)
        backtest_results = backtest_engine.run()
        
        # Compare behaviors
        comparison = self._analyze_behavior_differences(
            paper_decisions,
            backtest_results.decision_log
        )
        
        return comparison
    
    def _analyze_behavior_differences(self, paper_decisions: List[Dict], 
                                    backtest_decisions: List[Dict]) -> Dict:
        """Detailed analysis of behavioral differences"""
        
        analysis = {
            'summary': {},
            'timing_analysis': {},
            'signal_analysis': {},
            'price_analysis': {},
            'detailed_differences': []
        }
        
        # Match decisions by timestamp (with tolerance)
        matched_decisions = []
        unmatched_paper = []
        unmatched_backtest = []
        
        for paper_dec in paper_decisions:
            match_found = False
            paper_time = paper_dec['timestamp']
            
            for backtest_dec in backtest_decisions:
                backtest_time = backtest_dec['timestamp']
                
                # Allow 1 bar tolerance for timing differences
                if abs((paper_time - backtest_time).total_seconds()) < 3600:  # 1 hour
                    matched_decisions.append({
                        'paper': paper_dec,
                        'backtest': backtest_dec,
                        'time_diff': (paper_time - backtest_time).total_seconds()
                    })
                    match_found = True
                    break
            
            if not match_found:
                unmatched_paper.append(paper_dec)
        
        # Find unmatched backtest decisions
        matched_backtest_times = [m['backtest']['timestamp'] for m in matched_decisions]
        unmatched_backtest = [
            d for d in backtest_decisions 
            if d['timestamp'] not in matched_backtest_times
        ]
        
        # Analyze matched decisions
        signal_matches = 0
        total_matches = len(matched_decisions)
        
        for match in matched_decisions:
            if match['paper']['signal'] == match['backtest']['signal']:
                signal_matches += 1
            else:
                analysis['detailed_differences'].append({
                    'timestamp': match['paper']['timestamp'],
                    'paper_signal': match['paper']['signal'],
                    'backtest_signal': match['backtest']['signal'],
                    'paper_confidence': match['paper']['confidence'],
                    'backtest_confidence': match['backtest']['confidence'],
                    'indicators_diff': self._compare_indicators(
                        match['paper']['indicators'],
                        match['backtest']['indicators']
                    )
                })
        
        # Summary statistics
        analysis['summary'] = {
            'total_paper_decisions': len(paper_decisions),
            'total_backtest_decisions': len(backtest_decisions),
            'matched_decisions': total_matches,
            'signal_match_rate': signal_matches / total_matches if total_matches > 0 else 0,
            'unmatched_paper_signals': len(unmatched_paper),
            'unmatched_backtest_signals': len(unmatched_backtest),
            'average_time_difference': np.mean([m['time_diff'] for m in matched_decisions]) if matched_decisions else 0
        }
        
        # Generate behavior score
        behavior_score = self._calculate_behavior_score(analysis)
        analysis['behavior_score'] = behavior_score
        
        return analysis
    
    def _calculate_behavior_score(self, analysis: Dict) -> float:
        """
        Calculate a behavior similarity score (0-100)
        Higher scores indicate paper trading closely matches backtest
        """
        
        # Weighted scoring
        signal_match_weight = 0.4
        timing_weight = 0.2
        decision_count_weight = 0.2
        unmatched_penalty_weight = 0.2
        
        # Signal matching score
        signal_score = analysis['summary']['signal_match_rate'] * 100
        
        # Timing score (penalize large time differences)
        avg_time_diff = abs(analysis['summary']['average_time_difference'])
        timing_score = max(0, 100 - (avg_time_diff / 60))  # Lose 1 point per minute
        
        # Decision count similarity
        paper_count = analysis['summary']['total_paper_decisions']
        backtest_count = analysis['summary']['total_backtest_decisions']
        count_ratio = min(paper_count, backtest_count) / max(paper_count, backtest_count) if max(paper_count, backtest_count) > 0 else 0
        count_score = count_ratio * 100
        
        # Unmatched decisions penalty
        total_decisions = paper_count + backtest_count
        unmatched_total = (analysis['summary']['unmatched_paper_signals'] + 
                          analysis['summary']['unmatched_backtest_signals'])
        unmatched_ratio = 1 - (unmatched_total / total_decisions) if total_decisions > 0 else 0
        unmatched_score = unmatched_ratio * 100
        
        # Weighted final score
        behavior_score = (
            signal_score * signal_match_weight +
            timing_score * timing_weight +
            count_score * decision_count_weight +
            unmatched_score * unmatched_penalty_weight
        )
        
        return round(behavior_score, 2)
```

### 3. Paper Executor

```python
# ktrdr/paper_trading/paper_executor.py
class PaperExecutor:
    """
    Executes orders through IB Paper Trading API
    """
    
    def __init__(self):
        self.ib = IB()
        self.connected = False
        self.order_tracker = OrderTracker()
        
    async def connect(self, host: str = 'localhost', port: int = 7497):
        """Connect to IB Gateway paper trading port"""
        try:
            await self.ib.connectAsync(host, port, clientId=2)  # Different client ID for paper
            self.connected = True
            logger.info("Connected to IB Paper Trading")
        except Exception as e:
            logger.error(f"Failed to connect to IB Paper Trading: {e}")
            raise
    
    async def execute_order(self, order_request: OrderRequest) -> ExecutionResult:
        """Execute order with detailed tracking"""
        
        if not self.connected:
            await self.connect()
        
        # Create IB contract
        contract = self._create_contract(order_request.symbol)
        
        # Create IB order
        ib_order = self._create_ib_order(order_request)
        
        # Track pre-execution state
        pre_execution = {
            'timestamp': datetime.utcnow(),
            'bid': self.ib.reqTickers(contract)[0].bid,
            'ask': self.ib.reqTickers(contract)[0].ask,
            'mid': (self.ib.reqTickers(contract)[0].bid + 
                   self.ib.reqTickers(contract)[0].ask) / 2
        }
        
        # Place order
        trade = self.ib.placeOrder(contract, ib_order)
        
        # Wait for fill with timeout
        timeout = 30  # seconds
        start_time = datetime.utcnow()
        
        while not trade.isDone():
            await asyncio.sleep(0.1)
            if (datetime.utcnow() - start_time).seconds > timeout:
                self.ib.cancelOrder(ib_order)
                raise TimeoutError("Order execution timeout")
        
        # Create execution result
        result = ExecutionResult(
            order_id=trade.order.orderId,
            symbol=order_request.symbol,
            side=order_request.side,
            requested_quantity=order_request.quantity,
            filled_quantity=trade.filled(),
            average_price=trade.avgFillPrice(),
            fill_time=datetime.utcnow(),
            commission=trade.commission(),
            slippage=self._calculate_slippage(
                order_request,
                pre_execution,
                trade.avgFillPrice()
            ),
            status=trade.orderStatus.status
        )
        
        # Track order for analysis
        await self.order_tracker.track_order(result)
        
        return result
    
    def _calculate_slippage(self, request: OrderRequest, 
                          pre_execution: Dict, 
                          fill_price: float) -> float:
        """Calculate actual vs expected slippage"""
        
        if request.side == 'BUY':
            expected_price = pre_execution['ask']
        else:
            expected_price = pre_execution['bid']
        
        slippage = abs(fill_price - expected_price)
        slippage_pct = (slippage / expected_price) * 100
        
        return slippage_pct
```

### 4. Monitoring Dashboard

```python
# ktrdr/paper_trading/monitoring.py
class PaperTradingMonitor:
    """
    Real-time monitoring and alerting for paper trading
    """
    
    def __init__(self, alert_config: AlertConfig):
        self.alert_config = alert_config
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        
    async def start_monitoring(self, orchestrator: PaperTradingOrchestrator):
        """Start monitoring loops"""
        
        tasks = [
            self._monitor_positions(),
            self._monitor_performance(),
            self._monitor_system_health(),
            self._generate_reports()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_positions(self):
        """Real-time position monitoring"""
        
        while True:
            try:
                positions = await self._get_current_positions()
                
                for position in positions:
                    # Check position limits
                    if abs(position.quantity) > self.alert_config.max_position_size:
                        await self.alert_manager.send_alert(
                            level="WARNING",
                            message=f"Position size exceeded for {position.symbol}: {position.quantity}"
                        )
                    
                    # Check unrealized P&L
                    if position.unrealized_pnl < -self.alert_config.max_position_loss:
                        await self.alert_manager.send_alert(
                            level="CRITICAL",
                            message=f"Large unrealized loss for {position.symbol}: ${position.unrealized_pnl}"
                        )
                
                # Update metrics
                self.metrics_collector.update_positions(positions)
                
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _monitor_performance(self):
        """Track performance metrics"""
        
        while True:
            try:
                # Calculate current day metrics
                metrics = await self._calculate_daily_metrics()
                
                # Check daily loss limit
                if metrics['daily_pnl'] < -self.alert_config.max_daily_loss:
                    await self.alert_manager.send_alert(
                        level="CRITICAL",
                        message=f"Daily loss limit exceeded: ${metrics['daily_pnl']}"
                    )
                    
                    # Trigger emergency stop if configured
                    if self.alert_config.auto_stop_on_daily_limit:
                        await self._emergency_stop()
                
                # Update dashboard
                await self._update_dashboard(metrics)
                
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
            
            await asyncio.sleep(60)  # Check every minute
    
    async def _generate_reports(self):
        """Generate periodic reports"""
        
        while True:
            try:
                # Wait until end of day
                await self._wait_until_eod()
                
                # Generate daily report
                report = await self._create_daily_report()
                
                # Compare with backtest if enough data
                if len(report['trades']) > 5:  # At least 5 trades
                    comparison = await self.validator.compare_with_backtest(
                        report['start_time'],
                        report['end_time']
                    )
                    report['backtest_comparison'] = comparison
                
                # Send report
                await self._send_report(report)
                
            except Exception as e:
                logger.error(f"Report generation error: {e}")
            
            await asyncio.sleep(3600)  # Check hourly
```

### 5. Strategy Promotion System

```python
# ktrdr/paper_trading/promotion.py
@dataclass
class PromotionCriteria:
    """Criteria for promoting strategy from paper to live"""
    min_trades: int = 20
    min_days: int = 14
    min_behavior_score: float = 85.0  # How closely it matches backtest
    max_drawdown: float = 0.15  # Maximum acceptable drawdown
    min_sharpe_ratio: float = 0.5
    required_market_conditions: List[str] = None  # e.g., ['trending', 'volatile']

class StrategyPromotion:
    """
    Manages strategy promotion from paper to live trading
    """
    
    def __init__(self):
        self.db = DatabaseConnection()
        
    async def evaluate_for_promotion(self, 
                                   strategy_name: str,
                                   symbol: str,
                                   criteria: PromotionCriteria) -> PromotionReport:
        """Evaluate if strategy is ready for live trading"""
        
        # Get paper trading history
        paper_stats = await self._get_paper_trading_stats(strategy_name, symbol)
        
        # Get backtest comparison
        behavior_analysis = await self._get_behavior_analysis(strategy_name, symbol)
        
        # Check all criteria
        checks = {
            'min_trades': paper_stats['total_trades'] >= criteria.min_trades,
            'min_days': paper_stats['trading_days'] >= criteria.min_days,
            'behavior_score': behavior_analysis['behavior_score'] >= criteria.min_behavior_score,
            'max_drawdown': paper_stats['max_drawdown'] <= criteria.max_drawdown,
            'sharpe_ratio': paper_stats['sharpe_ratio'] >= criteria.min_sharpe_ratio
        }
        
        # Market condition check if required
        if criteria.required_market_conditions:
            market_check = await self._check_market_conditions(
                criteria.required_market_conditions
            )
            checks['market_conditions'] = market_check
        
        # Create detailed report
        report = PromotionReport(
            strategy_name=strategy_name,
            symbol=symbol,
            evaluation_date=datetime.utcnow(),
            criteria_checks=checks,
            all_criteria_met=all(checks.values()),
            paper_performance=paper_stats,
            behavior_analysis=behavior_analysis,
            recommendation=self._generate_recommendation(checks, paper_stats, behavior_analysis)
        )
        
        # Store evaluation
        await self._store_promotion_evaluation(report)
        
        return report
    
    def _generate_recommendation(self, checks: Dict, stats: Dict, behavior: Dict) -> str:
        """Generate human-readable recommendation"""
        
        if all(checks.values()):
            return f"""
            RECOMMENDATION: Ready for Live Trading
            
            This strategy has met all promotion criteria:
            - Behavior score of {behavior['behavior_score']:.1f}% shows excellent alignment with backtest
            - Completed {stats['total_trades']} trades over {stats['trading_days']} days
            - Achieved Sharpe ratio of {stats['sharpe_ratio']:.2f}
            - Maximum drawdown of {stats['max_drawdown']:.1%} is within acceptable limits
            
            The strategy is demonstrating consistent behavior in paper trading that closely
            matches backtest expectations. Recommend proceeding to live trading with small
            position sizes initially.
            """
        else:
            failed_criteria = [k for k, v in checks.items() if not v]
            return f"""
            RECOMMENDATION: Continue Paper Trading
            
            This strategy has not met the following criteria:
            {chr(10).join(f'- {criterion}' for criterion in failed_criteria)}
            
            Continue paper trading and re-evaluate after addressing these issues.
            Particular attention should be paid to the behavior score, which indicates
            how closely paper trading matches backtest expectations.
            """
```

## Integration with Existing Systems

### Multi-Timeframe Support

Since you've already upgraded the system for multi-timeframe support:

```python
# Enhanced decision engine for multi-timeframe
class MultiTimeframeDecisionEngine:
    """
    Coordinates decisions across multiple timeframes
    """
    
    def __init__(self, timeframes: List[str]):
        self.timeframes = sorted(timeframes, key=self._timeframe_to_minutes)
        self.signals = {tf: None for tf in timeframes}
        self.last_update = {tf: None for tf in timeframes}
        
    async def update_timeframe(self, timeframe: str, signal: Signal, confidence: float):
        """Update signal for a specific timeframe"""
        
        self.signals[timeframe] = {
            'signal': signal,
            'confidence': confidence,
            'timestamp': datetime.utcnow()
        }
        self.last_update[timeframe] = datetime.utcnow()
        
        # Check if we should generate a combined signal
        if self._should_generate_signal():
            return self._combine_signals()
        
        return None
    
    def _combine_signals(self) -> Optional[TradingDecision]:
        """Combine signals from multiple timeframes"""
        
        # Weight by timeframe (higher timeframes get more weight)
        weights = {
            '5m': 0.1,
            '15m': 0.2,
            '1h': 0.3,
            '4h': 0.4
        }
        
        # Calculate weighted signal
        buy_score = 0
        sell_score = 0
        total_weight = 0
        
        for tf, signal_data in self.signals.items():
            if signal_data and self._is_recent(signal_data['timestamp']):
                weight = weights.get(tf, 0.1)
                
                if signal_data['signal'] == Signal.BUY:
                    buy_score += weight * signal_data['confidence']
                elif signal_data['signal'] == Signal.SELL:
                    sell_score += weight * signal_data['confidence']
                
                total_weight += weight
        
        # Normalize scores
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        # Generate decision based on scores
        if buy_score > 0.6 and buy_score > sell_score:
            return TradingDecision(
                signal=Signal.BUY,
                confidence=buy_score,
                timestamp=datetime.utcnow(),
                reasoning={'multi_timeframe_scores': {
                    'buy': buy_score,
                    'sell': sell_score,
                    'timeframes': self.signals
                }}
            )
        elif sell_score > 0.6 and sell_score > buy_score:
            return TradingDecision(
                signal=Signal.SELL,
                confidence=sell_score,
                timestamp=datetime.utcnow(),
                reasoning={'multi_timeframe_scores': {
                    'buy': buy_score,
                    'sell': sell_score,
                    'timeframes': self.signals
                }}
            )
        
        return None  # No clear signal
```

### Paper Trading Configuration

```yaml
# paper_trading/config.yaml
paper_trading:
  # IB Connection
  ib_gateway:
    host: "localhost"
    port: 7497  # Paper trading port
    client_id: 2
    
  # Execution settings
  execution:
    order_timeout: 30  # seconds
    retry_attempts: 3
    min_tick_size: 0.01
    
  # Monitoring
  monitoring:
    position_check_interval: 30  # seconds
    performance_check_interval: 60
    health_check_interval: 300
    
  # Alerts
  alerts:
    email:
      enabled: true
      recipients: ["trader@example.com"]
      smtp_server: "smtp.gmail.com"
    sms:
      enabled: true
      twilio_sid: "${TWILIO_SID}"
      twilio_token: "${TWILIO_TOKEN}"
      recipient: "+1234567890"
    
  # Risk limits
  risk_limits:
    max_position_size: 10000  # shares
    max_position_value: 100000  # dollars
    max_daily_trades: 20
    max_daily_loss: 2000  # dollars
    emergency_stop_loss: 5000  # dollars
    
  # Behavior validation
  validation:
    min_behavior_score: 85.0
    backtest_comparison_interval: 7  # days
    signal_match_threshold: 0.8
    timing_tolerance: 300  # seconds
    
  # Promotion criteria
  promotion:
    min_trades: 20
    min_days: 14
    min_behavior_score: 85.0
    max_drawdown: 0.15
    min_sharpe_ratio: 0.5
    manual_review_required: true
```

## Dashboard and Monitoring

### Web Dashboard Components

```typescript
// Paper Trading Dashboard Components

interface PaperTradingDashboard {
  // Real-time metrics
  currentPositions: PositionDisplay[];
  dailyPnL: PnLChart;
  recentTrades: TradeTable;
  
  // Behavior validation
  behaviorScore: BehaviorScoreGauge;
  signalComparison: SignalComparisonChart;
  backtestAlignment: AlignmentMetrics;
  
  // System health
  connectionStatus: ConnectionIndicator;
  latencyMetrics: LatencyChart;
  errorLog: ErrorDisplay;
  
  // Controls
  emergencyStop: EmergencyStopButton;
  pauseTrading: PauseTradingToggle;
  strategySelector: StrategyDropdown;
}

// Behavior Comparison View
interface BehaviorComparisonView {
  // Side-by-side comparison
  paperTrades: TradeTimeline;
  backtestTrades: TradeTimeline;
  
  // Difference analysis
  missedTrades: MissedTradesList;
  extraTrades: ExtraTradesList;
  timingDifferences: TimingHistogram;
  
  // Summary metrics
  overallScore: number;
  signalAccuracy: number;
  timingAccuracy: number;
}
```

## CLI Commands

```bash
# Start paper trading
python -m ktrdr.paper_trading start \
  --strategy neuro_mean_reversion \
  --symbol AAPL \
  --timeframes 15m,1h,4h

# Check status
python -m ktrdr.paper_trading status

# Run behavior validation
python -m ktrdr.paper_trading validate \
  --strategy neuro_mean_reversion \
  --compare-days 7

# Evaluate for promotion
python -m ktrdr.paper_trading evaluate \
  --strategy neuro_mean_reversion \
  --symbol AAPL

# Emergency stop
python -m ktrdr.paper_trading stop --emergency

# Generate report
python -m ktrdr.paper_trading report \
  --strategy neuro_mean_reversion \
  --format pdf \
  --email trader@example.com
```

## Key Design Decisions

### 1. Behavioral Validation Focus
- **Primary goal**: Ensure paper trading behaves like backtesting
- **Continuous comparison**: Regular re-running of backtests on paper periods
- **Detailed logging**: Every decision and execution for analysis
- **Scoring system**: Quantitative measure of behavioral similarity

### 2. Multi-Strategy Support
- **Concurrent strategies**: Run multiple strategies simultaneously
- **Isolated tracking**: Each strategy tracked independently
- **Resource management**: Prevent strategies from interfering

### 3. Real-time Architecture
- **Asynchronous design**: Handle multiple timeframes efficiently
- **Event-driven**: React to market data as it arrives
- **Fault tolerance**: Continue operating despite errors

### 4. Safety First
- **Risk limits**: Hard stops on losses and position sizes
- **Emergency controls**: Multiple ways to stop trading
- **Audit trail**: Complete record of all decisions and actions

## Implementation Roadmap

### Week 1-2: Core Infrastructure
1. Set up IB paper trading connection
2. Implement basic order execution
3. Create position tracking system
4. Build decision logging framework

### Week 3-4: Behavioral Validation
1. Implement behavior validator
2. Create backtest comparison engine
3. Build scoring system
4. Set up automated reporting

### Week 5-6: Monitoring and Controls
1. Build real-time dashboard
2. Implement alert system
3. Create emergency stop mechanisms
4. Add performance tracking

### Week 7-8: Polish and Testing
1. Multi-strategy support
2. Promotion evaluation system
3. Comprehensive testing
4. Documentation and training

## Success Metrics

### Behavioral Metrics
- **Behavior score**: > 85% match with backtest
- **Signal accuracy**: > 90% same signals
- **Timing accuracy**: < 1 minute average difference
- **Trade matching**: > 95% of trades matched

### Performance Metrics
- **System uptime**: > 99.9%
- **Execution latency**: < 1 second
- **Order fill rate**: > 99%
- **Error rate**: < 0.1%

## Conclusion

This paper trading system provides a **robust validation layer** between backtesting and live trading. The focus on behavioral validation ensures that strategies perform as expected in real market conditions, not just in historical simulations.

The key innovation is the **continuous comparison** with backtesting results, providing quantitative confidence that the strategy will behave similarly when deployed with real capital. Combined with comprehensive monitoring and safety controls, this creates a safe environment for strategy validation.