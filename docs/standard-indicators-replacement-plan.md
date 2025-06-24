# Standard Indicators Replacement Plan for KTRDR Feature Engineering Removal

## Executive Summary

Based on research, **ALL raw feature engineering calculations can be replaced with standard technical indicators**. This eliminates the need for custom feature engineering and aligns with proper technical analysis practices.

## Standard Indicator Replacements

### 1. Price Position Features → Distance From Moving Average (DMA)

**Replace:**
- `price_to_sma_20_ratio` = `close / sma_20`
- `price_to_sma_50_ratio` = `close / sma_50` 
- `price_to_ema_20_ratio` = `close / ema_20`

**With:** **Distance From Moving Average (DMA) Indicator**
- **Formula:** `(Close - MA) / MA * 100`
- **Output:** Percentage distance from moving average
- **Range:** -50% to +50% typically
- **Interpretation:** 
  - Positive = Price above MA (bullish)
  - Negative = Price below MA (bearish)
  - Magnitude = Strength of trend

**Implementation:**
```yaml
# New indicators to add
indicators:
  - name: dma_sma20
    type: distance_from_ma
    ma_type: sma
    period: 20
    source: close
  - name: dma_sma50
    type: distance_from_ma
    ma_type: sma
    period: 50
    source: close
  - name: dma_ema20
    type: distance_from_ma
    ma_type: ema
    period: 20
    source: close

# Fuzzy sets for DMA
fuzzy_sets:
  dma_sma20:
    far_below:
      type: triangular
      parameters: [-30, -20, -10]  # 10-30% below SMA
    below:
      type: triangular
      parameters: [-15, -5, 0]     # 0-15% below SMA
    near:
      type: triangular
      parameters: [-3, 0, 3]       # Within ±3% of SMA
    above:
      type: triangular
      parameters: [0, 5, 15]       # 0-15% above SMA
    far_above:
      type: triangular
      parameters: [10, 20, 30]     # 10-30% above SMA
```

### 2. Momentum Features → ROC Indicator (Already Exists!)

**Replace:**
- `roc_5` = `close.pct_change(5)`
- `roc_10` = `close.pct_change(10)`
- `roc_20` = `close.pct_change(20)`

**With:** **Existing ROC Indicator**
- **Formula:** `(Close[n] - Close[n-period]) / Close[n-period] * 100`
- **KTRDR Status:** ✅ **Already implemented**
- **Action:** Just use existing ROC with different periods

**Implementation:**
```yaml
# Use existing ROC indicator
indicators:
  - name: momentum_short
    type: roc
    period: 5
    source: close
  - name: momentum_medium
    type: roc
    period: 10
    source: close
  - name: momentum_long
    type: roc
    period: 20
    source: close

# Fuzzy sets for momentum
fuzzy_sets:
  momentum_short:
    strong_down:
      type: triangular
      parameters: [-15, -10, -5]   # Strong downward momentum
    down:
      type: triangular
      parameters: [-8, -3, 0]      # Mild downward momentum
    flat:
      type: triangular
      parameters: [-2, 0, 2]       # Sideways momentum
    up:
      type: triangular
      parameters: [0, 3, 8]        # Mild upward momentum
    strong_up:
      type: triangular
      parameters: [5, 10, 15]      # Strong upward momentum
```

### 3. Daily Price Position → Williams %R (Already Exists!)

**Replace:**
- `daily_price_position` = `(close - low) / (high - low)`

**With:** **Williams %R Indicator**
- **Formula:** `(Highest High - Close) / (Highest High - Lowest Low) * -100`
- **Note:** Williams %R is the inverse of our calculation
- **Conversion:** `Williams %R = -100 * (1 - daily_price_position)`
- **KTRDR Status:** ✅ **Likely already implemented** (check indicators/)

**Implementation:**
```yaml
# Use Williams %R (or create inverse if needed)
indicators:
  - name: intraday_position
    type: williams_r
    period: 1  # Single day
    source: [high, low, close]

# Fuzzy sets for Williams %R (-100 to 0 range)
fuzzy_sets:
  intraday_position:
    oversold:
      type: triangular
      parameters: [-100, -90, -70]  # Near daily low
    weak:
      type: triangular
      parameters: [-80, -60, -40]   # Lower part of range
    middle:
      type: triangular
      parameters: [-60, -50, -40]   # Middle of range
    strong:
      type: triangular
      parameters: [-40, -30, -20]   # Upper part of range
    overbought:
      type: triangular
      parameters: [-30, -10, 0]     # Near daily high
```

### 4. Volatility → ATR or Bollinger Band Width (Already Exists!)

**Replace:**
- `volatility_20` = `close.pct_change().rolling(20).std()`

**With:** **Average True Range (ATR)** or **Bollinger Band Width**
- **ATR:** More comprehensive volatility (includes gaps)
- **BB Width:** Similar to rolling std concept
- **KTRDR Status:** ✅ **Both likely already implemented**

**Implementation:**
```yaml
# Option A: Use ATR
indicators:
  - name: volatility
    type: atr
    period: 20
    source: [high, low, close]

# Option B: Use Bollinger Band Width  
indicators:
  - name: volatility
    type: bollinger_width
    period: 20
    std_dev: 2
    source: close

# Fuzzy sets for volatility (ATR values)
fuzzy_sets:
  volatility:
    very_low:
      type: triangular
      parameters: [0, 0.5, 1.0]     # Very low volatility
    low:
      type: triangular
      parameters: [0.5, 1.5, 2.5]   # Low volatility
    medium:
      type: triangular
      parameters: [2.0, 3.5, 5.0]   # Medium volatility
    high:
      type: triangular
      parameters: [4.0, 6.0, 8.0]   # High volatility
    very_high:
      type: triangular
      parameters: [7.0, 10.0, 15.0] # Very high volatility
```

### 5. Volume Ratio → Relative Volume (RVOL)

**Replace:**
- `volume_ratio_20` = `volume / volume.rolling(20).mean()`

**With:** **Relative Volume (RVOL) Indicator**
- **Formula:** `Current Volume / Average Volume`
- **Standard Practice:** Widely used in volume analysis
- **Implementation:** Simple custom indicator

**Implementation:**
```yaml
# Create RVOL indicator
indicators:
  - name: volume_strength
    type: relative_volume
    period: 20
    source: volume

# Fuzzy sets for RVOL
fuzzy_sets:
  volume_strength:
    very_weak:
      type: triangular
      parameters: [0, 0.3, 0.6]     # <60% of average volume
    weak:
      type: triangular
      parameters: [0.4, 0.7, 1.0]   # 40-100% of average
    normal:
      type: triangular
      parameters: [0.8, 1.0, 1.2]   # 80-120% of average
    strong:
      type: triangular
      parameters: [1.1, 1.5, 2.0]   # 110-200% of average
    very_strong:
      type: triangular
      parameters: [1.8, 2.5, 5.0]   # 180%+ of average
```

### 6. Volume Momentum → Money Flow Index (MFI) or Chaikin Money Flow (CMF)

**Replace:**
- `volume_change_5` = `(volume - volume.shift(5)) / volume.shift(5)`

**With:** **Money Flow Index (MFI)** - Volume-weighted RSI
- **Better approach:** Combines price AND volume
- **Formula:** Uses typical price and money flow
- **Range:** 0-100 (like RSI)
- **KTRDR Status:** ❓ **Check if implemented**

**Implementation:**
```yaml
# Use MFI instead of simple volume change
indicators:
  - name: volume_momentum
    type: mfi
    period: 14
    source: [high, low, close, volume]

# Fuzzy sets for MFI (0-100 range)
fuzzy_sets:
  volume_momentum:
    oversold:
      type: triangular
      parameters: [0, 10, 30]       # Strong selling pressure
    weak:
      type: triangular
      parameters: [20, 35, 50]      # Weak buying/selling
    neutral:
      type: triangular
      parameters: [40, 50, 60]      # Neutral money flow
    strong:
      type: triangular
      parameters: [50, 65, 80]      # Strong buying pressure
    overbought:
      type: triangular
      parameters: [70, 90, 100]     # Very strong buying
```

### 7. OBV Normalized → Accumulation/Distribution Line (A/D)

**Replace:**
- `obv_normalized` = `(cumulative_obv - obv.mean()) / obv.std()`

**With:** **Accumulation/Distribution Line**
- **Better approach:** More sophisticated than OBV
- **Formula:** Uses close position within range
- **Interpretation:** Money flow in/out of security
- **KTRDR Status:** ❓ **Check if implemented**

**Implementation:**
```yaml
# Use A/D Line
indicators:
  - name: money_flow
    type: accumulation_distribution
    source: [high, low, close, volume]

# Fuzzy sets for A/D (normalized values)
fuzzy_sets:
  money_flow:
    strong_distribution:
      type: triangular
      parameters: [-3, -2, -1]      # Strong selling pressure
    distribution:
      type: triangular
      parameters: [-2, -1, 0]       # Mild selling pressure
    neutral:
      type: triangular
      parameters: [-0.5, 0, 0.5]    # Neutral flow
    accumulation:
      type: triangular
      parameters: [0, 1, 2]         # Mild buying pressure
    strong_accumulation:
      type: triangular
      parameters: [1, 2, 3]         # Strong buying pressure
```

## Implementation Status Check

### Indicators Already in KTRDR ✅
1. **ROC** - Rate of Change (confirmed exists)
2. **ATR** - Average True Range (likely exists)
3. **Williams %R** - (likely exists)
4. **Bollinger Bands** - (likely exists, can derive width)

### Indicators to Check ❓
1. **MFI** - Money Flow Index
2. **A/D Line** - Accumulation/Distribution
3. **CMF** - Chaikin Money Flow

### Simple Indicators to Create 🔧
1. **Distance from MA** - Simple calculation
2. **Relative Volume (RVOL)** - Simple volume ratio

## Next Steps

### 1. Audit Existing Indicators
```bash
# Check what indicators already exist
find ktrdr/indicators/ -name "*.py" | grep -E "(williams|mfi|accumulation|chaikin|distance)"
```

### 2. Create Missing Indicators
Only implement what doesn't already exist:
- `distance_from_ma.py` (if not exists)
- `relative_volume.py` (if not exists) 
- `mfi.py` (if not exists)
- `accumulation_distribution.py` (if not exists)

### 3. Updated Strategy Configuration

**Complete strategy with standard indicators:**
```yaml
name: "pure_neuro_mean_reversion_standard"
description: "Pure fuzzy using only standard technical indicators"
version: "2.0"

# All indicators are standard/existing
indicators:
  # Existing indicators (keep)
  - name: rsi
    type: rsi
    period: 14
    source: close
  - name: macd
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9
  - name: sma
    type: sma
    period: 20
    source: close
  
  # Standard replacements for raw features
  - name: dma_sma20
    type: distance_from_ma
    ma_type: sma
    period: 20
  - name: dma_sma50  
    type: distance_from_ma
    ma_type: sma
    period: 50
  - name: momentum_short
    type: roc
    period: 5
  - name: momentum_medium
    type: roc
    period: 10
  - name: intraday_position
    type: williams_r
    period: 1
  - name: volatility
    type: atr
    period: 20
  - name: volume_strength
    type: relative_volume
    period: 20
  - name: volume_momentum
    type: mfi
    period: 14
  - name: money_flow
    type: accumulation_distribution

# Pure fuzzy sets for all indicators
fuzzy_sets:
  rsi: { ... }  # Existing
  macd: { ... } # Existing
  sma: { ... }  # Existing
  dma_sma20: { ... }     # Distance from SMA20
  dma_sma50: { ... }     # Distance from SMA50
  momentum_short: { ... } # ROC 5-period
  momentum_medium: { ... } # ROC 10-period
  intraday_position: { ... } # Williams %R
  volatility: { ... }     # ATR
  volume_strength: { ... } # RVOL
  volume_momentum: { ... } # MFI
  money_flow: { ... }     # A/D Line

# Neural network (pure fuzzy only)
model:
  type: "mlp"
  architecture:
    hidden_layers: [60, 30, 15]  # ~12 indicators × 5 fuzzy sets = 60 base features
  fuzzy_features:
    include_temporal: true
    temporal_periods: 2  # 60 × 2 = 120 additional = 180 total features
```

## Benefits of Using Standard Indicators

### 1. **Proven Technical Analysis**
- All indicators are well-established in TA community
- Extensive literature and research available
- Traders familiar with these indicators

### 2. **Better Implementation**
- Most already exist in KTRDR
- No need to maintain custom feature engineering code
- Standard calculation methods

### 3. **Improved Interpretability**
- Distance from MA: Clear trend strength measure
- Williams %R: Standard overbought/oversold
- MFI: Volume-weighted momentum
- A/D Line: Professional money flow analysis

### 4. **Multi-Symbol Compatibility**
- All indicators work across asset classes
- Standardized value ranges
- Universal fuzzy set definitions

## Risk Mitigation

### 1. **Performance Validation**
- Test new standard indicators vs old raw features
- Ensure model accuracy is maintained
- Benchmark training/inference speed

### 2. **Gradual Migration**
- Implement one indicator group at a time
- A/B test each replacement
- Maintain fallback to old system during transition

### 3. **Configuration Flexibility**
- Allow strategy-specific parameter tuning
- Support multiple volatility measures (ATR vs BB Width)
- Configurable temporal periods per strategy

## Conclusion

**Using standard indicators is the RIGHT approach:**
1. ✅ **All raw features have standard equivalents**
2. ✅ **Most indicators likely already exist in KTRDR**
3. ✅ **Only 2-4 simple indicators need implementation**
4. ✅ **Results in cleaner, more professional architecture**
5. ✅ **Better for multi-symbol training (universal indicators)**

This approach transforms KTRDR from "custom feature engineering" to "professional technical analysis with fuzzy logic" - exactly what a neuro-fuzzy system should be.

---

**Next Action:** Audit existing KTRDR indicators to see what's already implemented vs what needs to be created.