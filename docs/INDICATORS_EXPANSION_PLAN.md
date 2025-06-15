# KTRDR Indicators Expansion Plan

## 🎯 Project Overview

This document outlines the comprehensive plan for expanding KTRDR's technical analysis indicators from 5 to 20+ indicators, implementing enhanced parameter handling, and integrating with fuzzy logic systems.

## 📊 Current State Analysis

### ✅ Existing Indicators (5)
1. **RSI** - Relative Strength Index (momentum oscillator)
2. **SMA** - Simple Moving Average (trend indicator)  
3. **EMA** - Exponential Moving Average (trend indicator)
4. **MACD** - Moving Average Convergence Divergence (momentum indicator) ⚠️ *needs parameter fix*
5. **ZigZag** - Pattern analysis indicator

### 🔧 Infrastructure Status
- **Strong Foundation**: Well-designed BaseIndicator architecture
- **API Integration**: Robust but needs enhancement for complex parameters
- **Test Coverage**: Good framework, needs completion
- **Fuzzy Integration**: Established system, needs expansion

---

## 🚀 Implementation Strategy

### **Phase 1: Foundation (4 new indicators + MACD fix)**
**Timeline**: First iteration
**Goal**: Establish enhanced parameter system and test integration

**New Indicators:**
1. **Stochastic Oscillator** - Momentum indicator with %K and %D lines
2. **Williams %R** - Momentum oscillator similar to Stochastic
3. **Average True Range (ATR)** - Volatility measure
4. **On-Balance Volume (OBV)** - Volume-based trend indicator

**Technical Tasks:**
- [ ] Fix MACD `_validate_params()` implementation
- [ ] Implement schema-based parameter validation system
- [ ] Create Phase 1 indicators with full test coverage
- [ ] Add fuzzy sets for each new indicator
- [ ] Update API endpoints and CLI integration
- [ ] Test with real data and document breaking changes

### **Phase 2: Advanced (4 indicators)**
**Timeline**: Second iteration  
**Goal**: Complex multi-output indicators

**New Indicators:**
1. **Bollinger Bands** - Volatility indicator with upper/lower bands
2. **Average Directional Index (ADX)** - Trend strength with DI+ and DI-
3. **Parabolic SAR** - Trend-following stop and reverse
4. **Money Flow Index (MFI)** - Volume-weighted RSI

### **Phase 3: Specialized (7 indicators)**
**Timeline**: Third iteration
**Goal**: Complete comprehensive indicator suite

**New Indicators:**
1. **Donchian Channels** - Breakout indicator
2. **Commodity Channel Index (CCI)** - Momentum oscillator
3. **Aroon Oscillator** - Trend identification
4. **Accumulation/Distribution Line** - Volume flow indicator
5. **Chaikin Money Flow** - Volume-based momentum
6. **Elder Impulse System** - Multi-indicator system
7. **Envelope Indicator** - Moving average envelope

---

## 🛠️ Technical Architecture

### **Enhanced Parameter System (Schema-Based)**

**Current MACD Issue:**
```python
# CURRENT (PROBLEMATIC)
class MACDIndicator(BaseIndicator):
    def __init__(self, fast_period=12, slow_period=26, signal_period=9, source="close"):
        # Validation in constructor - inconsistent pattern
        if fast_period >= slow_period:
            raise ConfigurationError(...)
```

**New Schema-Based System:**
```python
# NEW (CONSISTENT)
class MACDIndicator(BaseIndicator):
    def _validate_params(self, params):
        """Follow standard BaseIndicator pattern"""
        schema = MACDParameterSchema()
        return schema.validate(params)
        
    @property 
    def parameter_schema(self):
        return {
            "fast_period": {"type": "int", "min": 1, "max": 50, "default": 12},
            "slow_period": {"type": "int", "min": 2, "max": 100, "default": 26},
            "signal_period": {"type": "int", "min": 1, "max": 50, "default": 9},
            "source": {"type": "str", "options": ["open", "high", "low", "close"], "default": "close"},
            "constraints": [
                {"rule": "fast_period < slow_period", "message": "Fast period must be less than slow period"}
            ]
        }
```

### **API Enhancements**

**Current Indicator Config:**
```python
# CURRENT
class IndicatorConfig(BaseModel):
    id: str
    parameters: Dict[str, Any]  # Too generic
```

**Enhanced Indicator Config:**
```python
# NEW - With validation schema support
class IndicatorConfig(BaseModel):
    id: str
    parameters: Dict[str, Any]
    parameter_schema: Optional[Dict[str, Any]] = None  # For validation
    
    @model_validator(mode='after')
    def validate_parameters(self) -> 'IndicatorConfig':
        # Use parameter_schema to validate parameters
        if self.parameter_schema:
            # Validate using schema
            pass
        return self
```

### **Fuzzy Logic Integration**

**Alignment with Current System:**
```python
# Follow existing pattern from ktrdr/fuzzy/
class IndicatorFuzzySet:
    """Fuzzy sets for technical indicators following existing patterns"""
    
    # Oscillator indicators (RSI, Stochastic, Williams %R)
    OSCILLATOR_SETS = {
        "oversold": FuzzyTriangular(0, 0, 30),      # Strong buy signal
        "neutral": FuzzyTrapezoid(20, 30, 70, 80),  # No clear signal  
        "overbought": FuzzyTriangular(70, 100, 100) # Strong sell signal
    }
    
    # Trend strength indicators (ADX, MACD strength)
    TREND_STRENGTH_SETS = {
        "weak": FuzzyTriangular(0, 0, 25),
        "moderate": FuzzyTrapezoid(20, 25, 45, 50), 
        "strong": FuzzyTriangular(45, 100, 100)
    }
```

---

## 💥 Breaking Changes Documentation

### **API Breaking Changes**

#### 1. **Enhanced Parameter Validation**
**Change**: All indicators now require schema-compliant parameters
**Impact**: Parameter validation will be stricter
**Migration**: 
- Review existing indicator configurations
- Ensure all parameters follow schema definitions
- Update parameter names if needed

#### 2. **MACD Parameter Structure** 
**Change**: MACD will follow standard `_validate_params()` pattern
**Impact**: Parameter validation timing changes (validation moves from constructor to base class)
**Migration**: No external API changes, internal consistency improvement

#### 3. **Multi-Output Indicator Response Format**
**Change**: Indicators returning multiple values (MACD, Bollinger Bands, Stochastic) will have standardized column naming
**Impact**: Response structure may change for complex indicators
**Before**:
```json
{
  "indicators": {
    "MACD_12_26": [0.1, 0.2, ...],
    "MACD_signal_12_26_9": [0.05, 0.15, ...]
  }
}
```
**After**:
```json
{
  "indicators": {
    "MACD": {
      "line": [0.1, 0.2, ...],
      "signal": [0.05, 0.15, ...], 
      "histogram": [0.05, 0.05, ...]
    }
  }
}
```

#### 4. **New Indicator Metadata Endpoints**
**Addition**: New endpoints for indicator parameter schemas
- `GET /api/v1/indicators/{id}/schema` - Get parameter schema
- `POST /api/v1/indicators/validate-config` - Validate indicator configuration

#### 5. **Enhanced Fuzzy Integration**
**Addition**: New fuzzy evaluation endpoints per indicator
- `POST /api/v1/indicators/{id}/fuzzy-evaluate` - Evaluate indicator with fuzzy logic

### **CLI Breaking Changes**

#### 1. **Enhanced Parameter Syntax**
**Change**: Support for complex parameter validation
**Before**: `ktrdr compute-indicator AAPL --type MACD --fast-period 12 --slow-period 26`
**After**: Same syntax but with enhanced validation and error messages

#### 2. **New Commands**
**Addition**: New CLI commands for indicator management
- `ktrdr indicators list-schemas` - List all parameter schemas
- `ktrdr indicators validate-config CONFIG_FILE` - Validate indicator configuration
- `ktrdr indicators fuzzy-evaluate SYMBOL INDICATOR` - Evaluate with fuzzy logic

### **Frontend Breaking Changes**

#### 1. **Indicator Configuration Interface**
**Change**: Need to support parameter schemas and validation
**Required Updates**:
- Add parameter schema fetching from API
- Implement client-side parameter validation
- Update indicator configuration forms
- Handle multi-output indicator display

#### 2. **Chart Integration** 
**Change**: Support for new indicator types and fuzzy visualization
**Required Updates**:
- Add support for volume-based indicators
- Implement multi-line indicator display (Bollinger Bands, etc.)
- Add fuzzy logic overlay capabilities

---

## 📋 Phase 1 Detailed Implementation Plan

### **1. MACD Parameter Fix (Day 1)**
- [ ] Implement `_validate_params()` method in MACDIndicator
- [ ] Move validation logic from constructor
- [ ] Add comprehensive parameter constraint validation  
- [ ] Update tests to verify new validation pattern
- [ ] Commit: "fix: standardize MACD parameter validation pattern"

### **2. Schema-Based Parameter System (Days 2-3)**
- [ ] Create `IndicatorParameterSchema` base class
- [ ] Implement schema validation engine
- [ ] Create parameter schemas for existing indicators
- [ ] Update BaseIndicator to use schema validation
- [ ] Add parameter constraint validation (e.g., fast < slow)
- [ ] Update API models to support schemas
- [ ] Commit: "feat: implement schema-based parameter validation system"

### **3. Stochastic Oscillator Implementation (Days 4-5)**
- [ ] Research and implement Stochastic calculation (%K and %D lines)
- [ ] Create StochasticIndicator with proper parameter schema
- [ ] Add comprehensive unit tests with reference data
- [ ] Create fuzzy sets (overbought/oversold/neutral)
- [ ] Update indicator registry and factory
- [ ] Test CLI and API integration
- [ ] Commit: "feat: add Stochastic Oscillator indicator with fuzzy sets"

### **4. Williams %R Implementation (Day 6)**
- [ ] Implement Williams %R calculation
- [ ] Create WilliamsRIndicator with parameter schema
- [ ] Add unit tests and reference datasets
- [ ] Create fuzzy sets (oversold/neutral/overbought) 
- [ ] Test integration
- [ ] Commit: "feat: add Williams %R momentum indicator"

### **5. Average True Range (ATR) Implementation (Day 7)**
- [ ] Implement ATR volatility calculation
- [ ] Create ATRIndicator with parameter schema
- [ ] Add tests and reference data
- [ ] Create volatility-based fuzzy sets (low/normal/high)
- [ ] Test integration
- [ ] Commit: "feat: add Average True Range (ATR) volatility indicator"

### **6. On-Balance Volume (OBV) Implementation (Day 8)**
- [ ] Implement OBV volume flow calculation
- [ ] Create OBVIndicator with parameter schema
- [ ] Add tests and reference data
- [ ] Create volume flow fuzzy sets (bearish/neutral/bullish)
- [ ] Test integration  
- [ ] Commit: "feat: add On-Balance Volume (OBV) indicator"

### **7. API and CLI Integration (Days 9-10)**
- [ ] Update API endpoints to handle new indicators
- [ ] Add new indicator metadata endpoints
- [ ] Update CLI commands and help documentation
- [ ] Add parameter validation to CLI
- [ ] Test batch indicator calculations
- [ ] Create integration tests
- [ ] Update API documentation
- [ ] Commit: "feat: complete Phase 1 API and CLI integration"

### **8. Testing and Documentation (Day 11)**
- [ ] Run comprehensive test suite
- [ ] Add missing test coverage
- [ ] Update CLAUDE.md with new commands
- [ ] Create migration guide for breaking changes
- [ ] Test with real market data
- [ ] Performance testing and optimization
- [ ] Commit: "docs: complete Phase 1 documentation and testing"

---

## 🧪 Testing Strategy

### **Definition of Done for Each Indicator:**
1. ✅ **Calculation Accuracy**: Reference datasets with known correct values
2. ✅ **Parameter Validation**: Complete schema with constraint testing
3. ✅ **Unit Tests**: 90%+ code coverage with edge cases
4. ✅ **Integration Tests**: API and CLI functionality verified
5. ✅ **Fuzzy Sets**: Appropriate membership functions implemented
6. ✅ **Documentation**: Parameter descriptions and usage examples
7. ✅ **Performance**: Benchmarks for large datasets

### **Test Categories:**
- **Unit Tests**: Individual indicator calculations
- **Integration Tests**: API endpoint functionality
- **CLI Tests**: Command-line interface operations
- **Fuzzy Logic Tests**: Membership function evaluations
- **Performance Tests**: Large dataset calculations
- **Real Data Tests**: Validation with actual market data

---

## 📈 Success Metrics

### **Phase 1 Goals:**
- [ ] 5 total indicators working (4 new + MACD fixed)
- [ ] Schema-based parameter system operational
- [ ] All tests passing with 90%+ coverage
- [ ] CLI and API integration complete
- [ ] Breaking changes documented and migration path clear
- [ ] Performance benchmarks established

### **Future Phase Goals:**
- **Phase 2**: 9 total indicators with complex multi-output support
- **Phase 3**: 16+ total indicators with comprehensive fuzzy rule systems

---

## 🔄 Future Fuzzy Logic Enhancement Proposal

*Note: This is for future implementation after Phase 3*

### **Current Fuzzy System Analysis**
The existing fuzzy system uses individual indicator fuzzy sets. Research suggests opportunities for:

1. **Multi-Indicator Fuzzy Rules**: Combine multiple indicators with rules like:
   - "IF RSI is Oversold AND MACD is Bullish AND Volume is High THEN Strong Buy"

2. **Adaptive Fuzzy Sets**: Dynamic membership functions based on market volatility

3. **Fuzzy Inference Engine**: Complete FIS for trading signal generation

**Recommendation**: Implement after Phase 3 completion to maintain focus and avoid scope creep.

---

This plan provides a solid foundation for expanding KTRDR's technical analysis capabilities while maintaining code quality and system consistency. Each phase builds on the previous one, allowing for iterative testing and refinement.