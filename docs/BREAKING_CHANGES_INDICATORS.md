# Breaking Changes: Indicators Expansion

## 🚨 Breaking Changes Overview

This document outlines all breaking changes introduced by the indicators expansion project. **These changes will require frontend updates and may affect existing API integrations.**

---

## 🔧 API Breaking Changes

### 1. **Enhanced Parameter Validation System**

**Change**: All indicators now use schema-based parameter validation instead of ad-hoc validation.

**Impact**: 
- Stricter parameter validation
- More descriptive error messages
- Consistent validation patterns across all indicators

**Before**:
```python
# Parameter validation varied by indicator
# Some indicators validated in constructor, others in _validate_params()
```

**After**:
```python
# All indicators follow consistent schema-based validation
# Validation includes type checking, range validation, and constraint validation
```

**Migration Required**: 
- ✅ No immediate action needed - backward compatible
- ⚠️ May expose previously hidden parameter errors
- 📋 Review existing indicator configurations for compliance

### 2. **MACD Parameter Validation Consistency**

**Change**: MACD indicator now follows standard `_validate_params()` pattern like other indicators.

**Impact**: 
- Parameter validation timing changes (moves from constructor to base class)
- More consistent error handling
- Better parameter constraint validation

**Before**:
```python
# Validation in MACD constructor
macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
# Error thrown immediately in constructor
```

**After**:
```python
# Validation follows BaseIndicator pattern
macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
# Error thrown when compute() is called, consistent with other indicators
```

**Migration Required**: 
- ✅ No API changes required
- 📋 Internal consistency improvement only

### 3. **Multi-Output Indicator Response Format**

**Change**: Indicators that return multiple values will have standardized nested response format.

**Impact**: 
- **HIGH IMPACT** - Response structure changes for complex indicators
- Affects MACD, and future Bollinger Bands, Stochastic Oscillator, ADX

**Before**:
```json
{
  "success": true,
  "data": {
    "indicators": {
      "MACD_12_26": [0.1, 0.2, 0.15, ...],
      "MACD_signal_12_26_9": [0.05, 0.15, 0.12, ...],
      "MACD_hist_12_26_9": [0.05, 0.05, 0.03, ...]
    }
  }
}
```

**After**:
```json
{
  "success": true,
  "data": {
    "indicators": {
      "MACD": {
        "line": [0.1, 0.2, 0.15, ...],
        "signal": [0.05, 0.15, 0.12, ...],
        "histogram": [0.05, 0.05, 0.03, ...]
      }
    }
  }
}
```

**Migration Required**: 
- 🚨 **CRITICAL** - Frontend must update MACD response parsing
- 🚨 **CRITICAL** - Update chart integration for multi-line indicators
- 📋 Test all existing MACD integrations

### 4. **New Indicator Metadata Endpoints**

**Change**: Added new endpoints for parameter schema information and validation.

**Impact**: 
- New functionality available
- Enhanced parameter validation capabilities

**New Endpoints**:
```
GET /api/v1/indicators/{id}/schema
POST /api/v1/indicators/validate-config  
POST /api/v1/indicators/{id}/fuzzy-evaluate
```

**Migration Required**: 
- ✅ Optional - can enhance frontend parameter validation
- 📋 Consider integrating schema-based form validation

### 5. **Enhanced Error Response Format**

**Change**: Parameter validation errors now include schema information and constraint details.

**Impact**: 
- More detailed error messages
- Better debugging capabilities

**Before**:
```json
{
  "success": false,
  "error": {
    "message": "Invalid parameter",
    "code": "VALIDATION_ERROR"
  }
}
```

**After**:
```json
{
  "success": false,
  "error": {
    "message": "Parameter validation failed",
    "code": "PARAMETER_VALIDATION_ERROR",
    "details": {
      "parameter": "fast_period",
      "constraint": "fast_period < slow_period",
      "provided_value": 26,
      "schema": {
        "type": "int",
        "min": 1,
        "max": 50
      }
    }
  }
}
```

**Migration Required**: 
- ✅ Backward compatible - existing error handling will work
- 📋 Consider updating frontend to use enhanced error details

---

## 💻 CLI Breaking Changes

### 1. **Enhanced Parameter Validation**

**Change**: CLI commands now use the same schema-based validation as the API.

**Impact**: 
- More consistent error messages
- Better parameter validation
- Clearer constraint violation messages

**Before**:
```bash
$ ktrdr compute-indicator AAPL --type MACD --fast-period 30 --slow-period 20
Error: Fast period must be less than slow period
```

**After**:
```bash
$ ktrdr compute-indicator AAPL --type MACD --fast-period 30 --slow-period 20
Error: Parameter validation failed for 'fast_period'
Constraint violated: fast_period < slow_period
Provided: fast_period=30, slow_period=20
Valid range: fast_period (1-50), slow_period (2-100)
```

**Migration Required**: 
- ✅ No command syntax changes
- 📋 Update documentation with enhanced error examples

### 2. **New CLI Commands**

**Change**: Added new commands for indicator management and validation.

**Impact**: 
- Enhanced CLI functionality
- Better developer experience

**New Commands**:
```bash
# List parameter schemas for all indicators
ktrdr indicators list-schemas

# Validate indicator configuration from file
ktrdr indicators validate-config config.yaml

# Evaluate indicator with fuzzy logic
ktrdr indicators fuzzy-evaluate AAPL RSI

# Get detailed parameter schema for specific indicator
ktrdr indicators schema MACD
```

**Migration Required**: 
- ✅ No existing commands affected
- 📋 Update help documentation and examples

### 3. **Enhanced Output Format for Multi-Output Indicators**

**Change**: CLI output for complex indicators (MACD) now shows structured data.

**Impact**: 
- More readable multi-value indicator output
- Consistent with API response format

**Before**:
```bash
$ ktrdr compute-indicator AAPL --type MACD
MACD_12_26: 0.1, 0.2, 0.15
MACD_signal_12_26_9: 0.05, 0.15, 0.12
MACD_hist_12_26_9: 0.05, 0.05, 0.03
```

**After**:
```bash
$ ktrdr compute-indicator AAPL --type MACD
MACD:
  line: 0.1, 0.2, 0.15
  signal: 0.05, 0.15, 0.12
  histogram: 0.05, 0.05, 0.03
```

**Migration Required**: 
- ⚠️ CLI output parsing scripts may need updates
- 📋 Update CLI documentation examples

---

## 🎨 Frontend Breaking Changes

### 1. **Indicator Configuration Interface**

**Change**: Parameter configuration must support schema-based validation and complex parameter types.

**Impact**: 
- **HIGH IMPACT** - Need to fetch and use parameter schemas
- Enhanced user experience with better validation
- Support for parameter constraints

**Required Updates**:
```typescript
// Before: Simple parameter object
interface IndicatorConfig {
  id: string;
  parameters: Record<string, any>;
}

// After: Schema-aware configuration
interface IndicatorConfig {
  id: string;
  parameters: Record<string, any>;
  schema?: ParameterSchema;
}

interface ParameterSchema {
  [paramName: string]: {
    type: 'int' | 'float' | 'str' | 'bool';
    min?: number;
    max?: number;
    default: any;
    options?: any[];
    description: string;
  };
  constraints?: Array<{
    rule: string;
    message: string;
  }>;
}
```

**Migration Tasks**:
- 🚨 **CRITICAL** - Update indicator configuration forms
- 🚨 **CRITICAL** - Implement client-side parameter validation
- 🚨 **CRITICAL** - Add parameter schema fetching from API
- 📋 Add parameter constraint validation UI

### 2. **MACD Chart Integration**

**Change**: MACD and other multi-output indicators now return nested data structure.

**Impact**: 
- **HIGH IMPACT** - Chart component must handle nested indicator data
- Affects existing MACD chart displays

**Required Updates**:
```typescript
// Before: Flat indicator data
interface IndicatorData {
  [indicatorName: string]: number[];
}

// After: Support nested multi-output indicators
interface IndicatorData {
  [indicatorName: string]: number[] | {
    [outputName: string]: number[];
  };
}

// Chart integration example
function renderMACDChart(macdData: {
  line: number[];
  signal: number[];
  histogram: number[];
}) {
  // Render three separate chart series
}
```

**Migration Tasks**:
- 🚨 **CRITICAL** - Update chart components to handle nested indicator data
- 🚨 **CRITICAL** - Modify MACD chart rendering logic
- 🚨 **CRITICAL** - Test all existing chart integrations
- 📋 Add support for multi-line indicator display

### 3. **New Indicator Types Support**

**Change**: Need to support new indicator categories (volume, volatility) and their specific display requirements.

**Impact**: 
- Chart panel management for different indicator scales
- Volume-based indicators need different visualization

**Required Updates**:
```typescript
// Support for different indicator display types
enum IndicatorDisplayType {
  OVERLAY = 'overlay',        // Price overlay (SMA, EMA)
  OSCILLATOR = 'oscillator',  // Separate panel (RSI, Stochastic)
  VOLUME = 'volume',          // Volume panel (OBV)
  VOLATILITY = 'volatility'   // Volatility panel (ATR)
}

interface IndicatorMetadata {
  id: string;
  name: string;
  displayType: IndicatorDisplayType;
  scale?: {
    min?: number;
    max?: number;
  };
}
```

**Migration Tasks**:
- 📋 Add support for volume-based indicators visualization
- 📋 Implement chart panel management for different indicator types
- 📋 Add volatility indicator display capabilities

### 4. **Fuzzy Logic Integration**

**Change**: Enhanced fuzzy logic evaluation endpoints and visualization.

**Impact**: 
- Optional enhancement - can improve user experience
- New fuzzy evaluation capabilities available

**New Capabilities**:
```typescript
interface FuzzyEvaluation {
  indicator: string;
  value: number;
  fuzzyValues: {
    [setName: string]: number;  // membership degree 0-1
  };
  signal: 'buy' | 'sell' | 'hold';
  confidence: number;
}
```

**Migration Tasks**:
- ✅ Optional - can add fuzzy logic overlay to charts
- 📋 Consider fuzzy signal visualization features

---

## 📋 Migration Checklist

### **Immediate Actions Required**

#### 🚨 Critical (Must Fix Before Release)
- [ ] **Frontend**: Update MACD response parsing to handle nested structure
- [ ] **Frontend**: Modify chart components for multi-output indicators  
- [ ] **Frontend**: Update indicator configuration forms to use parameter schemas
- [ ] **Frontend**: Test all existing chart integrations with new data format

#### ⚠️ Important (Should Fix)
- [ ] **Frontend**: Implement client-side parameter validation using schemas
- [ ] **Frontend**: Add support for new indicator display types (volume, volatility)
- [ ] **CLI**: Update documentation with new command examples
- [ ] **API**: Review existing integrations for parameter validation compliance

#### 📋 Optional (Nice to Have)
- [ ] **Frontend**: Add fuzzy logic evaluation and visualization
- [ ] **Frontend**: Enhance error handling with detailed parameter validation messages
- [ ] **CLI**: Create migration scripts for existing configurations
- [ ] **Documentation**: Update API documentation with new endpoints

### **Testing Strategy**

#### Phase 1 Testing (Before Release)
- [ ] Test existing MACD API integrations
- [ ] Verify CLI backward compatibility
- [ ] Test parameter validation edge cases
- [ ] Validate chart rendering with new data format

#### Phase 2 Testing (After Migration)
- [ ] Test new indicators integration
- [ ] Verify schema-based parameter validation
- [ ] Test fuzzy logic endpoints
- [ ] Performance testing with new validation system

---

## 🚀 Timeline

### **Week 1**: Core Breaking Changes
- Fix MACD parameter validation
- Implement schema-based validation system
- Update API response format for multi-output indicators

### **Week 2**: Frontend Migration
- Update MACD chart integration
- Implement parameter schema support
- Test and fix breaking changes

### **Week 3**: New Indicators (Phase 1)
- Add 4 new indicators with new system
- Complete CLI and API integration
- Final testing and documentation

---

## 🆘 Support and Migration Help

If you encounter issues during migration:

1. **Check the examples** in this document
2. **Review the parameter schemas** using new CLI commands
3. **Test with the validation endpoints** before integrating
4. **Refer to the technical specification** in `INDICATORS_EXPANSION_PLAN.md`

This migration will significantly enhance KTRDR's technical analysis capabilities while maintaining system consistency and improving user experience.