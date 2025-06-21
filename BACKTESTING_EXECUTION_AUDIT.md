# KTRDR Backtesting Execution Audit

## Executive Summary

This audit identifies critical execution realism issues in the KTRDR backtesting system that could cause significant performance differences between backtest and real/paper trading results. The most severe issue is **look-ahead bias** where decisions use future price information impossible to obtain in real trading.

## 🔍 Critical Realism Issues

### 1. Instant Order Execution (MAJOR ISSUE)

**Location**: `engine.py:254-296`, `position_manager.py:234-386`

**Current Implementation**:
```python
# Orders execute immediately at bar-close prices
trade = self.position_manager.execute_trade(
    signal=decision.signal,
    price=current_price,  # Bar close price
    timestamp=current_timestamp,
)
```

**Real Trading Reality**: 
- Orders take time to transmit to broker
- Execution occurs across multiple price levels
- Market conditions can change during transmission
- Slippage varies with market volatility and liquidity

**Impact**: Backtest assumes perfect execution that's impossible in real trading

---

### 2. Look-Ahead Bias (CRITICAL - HIGHEST PRIORITY)

**Location**: `engine.py:192-208`

**Current Problematic Code**:
```python
# Line 192: Uses current complete bar in decision making
historical_data = data.iloc[:idx + 1]  # INCLUDES current bar with close price

decision = self.orchestrator.make_decision(
    current_bar=current_bar,  # Complete OHLC data including close
    historical_data=historical_data,  # Includes current complete bar
)
```

**Real Trading Reality**: 
- Decisions must be made during bar formation, not after bar completion
- Close price is unknown when making intraday decisions
- Only open, high, low, and partial volume available during decision time

**Impact**: Backtest has future information, significantly inflating performance

**Required Fix**:
```python
# Use only previous complete bars for decisions
historical_data = data.iloc[:idx]  # Exclude current bar
decision_price = current_bar['open']  # Use open price for decisions
```

---

### 3. Perfect Price Execution (UNREALISTIC)

**Location**: `position_manager.py:264-266`, `position_manager.py:342`

**Current Implementation**:
```python
# Buy orders - fixed slippage
execution_price = price * (1 + self.slippage)  # 0.05% fixed

# Sell orders - fixed slippage  
execution_price = price * (1 - self.slippage)  # 0.05% fixed
```

**Real Trading Reality**:
- Execution price depends on bid-ask spread
- Slippage varies with order size relative to average volume
- Market impact increases with position size
- Spread widens during volatile periods

**Impact**: Underestimates real trading costs

---

### 4. Fixed Position Sizing (UNREALISTIC)

**Location**: `position_manager.py:388-407`

**Current Implementation**:
```python
# Always uses 25% of available capital
fraction_to_invest = 0.25  # Fixed 25% regardless of conditions
available = self.available_capital * fraction_to_invest
```

**Real Trading Reality**:
- Position sizing should vary with market volatility
- Risk management adjusts size based on stop distance
- Portfolio heat limits total risk exposure
- Correlation between positions affects sizing

**Impact**: Ignores real risk management practices

---

### 5. Missing Order Management Features

**Current Gaps**:
- No partial fills simulation
- No order rejection scenarios
- No gap risk modeling
- No market hours restrictions
- No liquidity constraints

**Real Trading Reality**:
- Large orders often fill partially
- Orders can be rejected for insufficient margin
- Gaps can cause slippage beyond stop levels
- Trading restricted outside market hours
- Low liquidity can prevent execution

---

## 📊 Specific Execution Timing Issues

### Decision-to-Execution Flow

**Current Flow** (Unrealistic):
1. **Bar Completes** → Full OHLCV data available
2. **Decision Made** → Uses complete bar data including close price
3. **Order Executes** → Immediately at close price + slippage
4. **Next Bar** → Process repeats

**Realistic Flow** Should Be:
1. **Bar Opens** → Previous bar data available, current bar forming
2. **Decision Made** → Uses only previous complete bars + current open
3. **Order Submitted** → During current bar formation
4. **Order Executes** → At realistic price based on spread/liquidity
5. **Bar Completes** → Position tracking updated

### Code Locations for Timing Issues

```python
# engine.py:158-208 - Main simulation loop
for idx in range(len(data)):
    current_bar = data.iloc[idx]  # Complete bar including close
    current_price = current_bar["close"]  # Uses close price
    
    # ISSUE: Historical data includes current complete bar
    historical_data = data.iloc[:idx + 1]
    
    decision = self.orchestrator.make_decision(
        current_bar=current_bar,  # Has future close price
        historical_data=historical_data,  # Includes current bar
    )
```

---

## 🎯 Prioritized Recommendations

### Priority 1: Fix Look-Ahead Bias (CRITICAL)

**Change Required**: `engine.py:192`
```python
# Current (problematic)
historical_data = data.iloc[:idx + 1]

# Fixed (realistic)
historical_data = data.iloc[:idx]
decision_price = current_bar['open']  # Use open for decisions
```

**Impact**: This single change will likely reduce backtest performance to realistic levels

---

### Priority 2: Implement Dynamic Slippage

**Add to**: `position_manager.py:264-342`
```python
def calculate_dynamic_slippage(self, base_slippage: float, volume_ratio: float) -> float:
    """Calculate slippage based on volume and market conditions."""
    # Higher slippage when volume is below average
    volume_impact = 1.0 + (1.0 / max(volume_ratio, 0.1) - 1.0) * 0.5
    return base_slippage * volume_impact
```

---

### Priority 3: Add Execution Delay

**Implementation**: Delay order execution by 1 bar
```python
class OrderQueue:
    """Queue orders for next-bar execution."""
    
    def __init__(self):
        self.pending_orders = []
    
    def add_order(self, signal, price, timestamp, metadata):
        """Add order for next bar execution."""
        self.pending_orders.append({
            'signal': signal,
            'price': price,  # Open price of next bar
            'timestamp': timestamp,
            'metadata': metadata
        })
    
    def execute_pending_orders(self, current_bar):
        """Execute orders using current bar's price action."""
        # Execute at open price with realistic slippage
        pass
```

---

### Priority 4: Implement ATR-Based Position Sizing

**Add to**: `position_manager.py`
```python
def calculate_atr_position_size(self, price_data: pd.DataFrame, 
                               current_price: float, 
                               risk_per_trade: float) -> int:
    """Calculate position size based on ATR and risk management."""
    atr = price_data['high'].sub(price_data['low']).rolling(14).mean().iloc[-1]
    stop_distance = 2 * atr  # 2-ATR stop loss
    
    if stop_distance > 0:
        shares = int(risk_per_trade / stop_distance)
        return max(shares, 0)
    return 0
```

---

### Priority 5: Add Market Impact Model

**Implementation**: Size-dependent slippage
```python
def calculate_market_impact(self, order_size: int, avg_volume: float, 
                           base_slippage: float) -> float:
    """Calculate market impact based on order size."""
    volume_participation = order_size / max(avg_volume, 1)
    
    # Increase slippage for larger orders
    if volume_participation > 0.1:  # More than 10% of average volume
        impact_multiplier = 1 + (volume_participation - 0.1) * 2
        return base_slippage * impact_multiplier
    
    return base_slippage
```

---

## 🧪 Validation Strategy

### Comparing Backtest vs Paper Trading

1. **Run identical strategy** on both backtest and paper trading
2. **Track key metrics**:
   - Fill rates (% of signals that execute)
   - Average slippage per trade
   - Execution delay impact
   - Position sizing differences

3. **Expected Results** after fixes:
   - Backtest performance should decrease
   - Metrics should align closer with paper trading
   - Slippage should be more variable and realistic

### Test Cases to Implement

1. **High Volatility Periods**: Test execution during market stress
2. **Low Volume Periods**: Verify increased slippage simulation
3. **Gap Events**: Test overnight gap impact on stops
4. **Large Position Sizes**: Verify market impact modeling

---

## 🚨 Most Critical Fix Summary

**The look-ahead bias in `engine.py:192` is the most serious flaw.** The backtest currently makes decisions using complete bar data including the close price, which is impossible in real trading where decisions must be made during bar formation.

**Immediate Action Required**:
```python
# File: ktrdr/backtesting/engine.py
# Line: 192

# Change from:
historical_data = data.iloc[:idx + 1]  # Includes current complete bar

# Change to:
historical_data = data.iloc[:idx]  # Only previous complete bars
```

This single line change will make the backtest significantly more realistic and should bring performance metrics closer to paper trading results.

---

## 📋 Implementation Checklist

- [ ] **Fix look-ahead bias** (engine.py:192)
- [ ] **Implement execution delay** (1-bar delay)
- [ ] **Add dynamic slippage** calculation
- [ ] **Implement ATR-based position sizing**
- [ ] **Add market impact model**
- [ ] **Create order queue system**
- [ ] **Add bid-ask spread simulation**
- [ ] **Implement partial fill logic**
- [ ] **Add liquidity constraints**
- [ ] **Test against paper trading results**

The fixes should be implemented in priority order, with look-ahead bias correction being the most critical for realistic backtesting results.