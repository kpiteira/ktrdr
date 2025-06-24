# KTRDR Indicator System Architecture Guide

**Version**: 1.0  
**Date**: December 2024  
**Purpose**: Authoritative guide for KTRDR indicator system architecture and development

---

## 🚨 CRITICAL ARCHITECTURAL PRINCIPLE

**ALL INDICATOR FUNCTIONALITY MUST GO THROUGH THE INDICATOR SYSTEM**

This is not a suggestion - it's an architectural requirement. Any indicator calculations outside this system violate the architecture and will be rejected.

---

## 📋 Table of Contents

1. [System Overview](#-system-overview)
2. [Architecture Fundamentals](#-architecture-fundamentals)
3. [Creating New Indicators](#-creating-new-indicators)
4. [Integration Patterns](#-integration-patterns)
5. [Architecture Rules](#-architecture-rules)
6. [Anti-Patterns to Avoid](#-anti-patterns-to-avoid)
7. [Reference Examples](#-reference-examples)
8. [Common Mistakes](#-common-mistakes)

---

## 🏗️ System Overview

The KTRDR indicator system is a sophisticated, schema-driven architecture that provides:

- **30+ Built-in Indicators** across 6 categories
- **Automatic Registration** and factory-based creation
- **Schema-based Parameter Validation** with type safety
- **Multi-timeframe Processing** with error isolation
- **Complete Integration** with API, CLI, training, and fuzzy systems

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    KTRDR INDICATOR SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  BaseIndicator  │    │ ParameterSchema │    │ Categories  │  │
│  │   (Abstract)    │◄──►│   Validation    │◄──►│   System    │  │
│  │                 │    │                 │    │             │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│           ▲                       ▲                     ▲       │
│           │                       │                     │       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │   30+ Concrete  │    │IndicatorFactory │    │ Indicator   │  │
│  │   Indicators    │◄──►│  Registration   │◄──►│   Engine    │  │
│  │   (RSI, SMA...) │    │   & Creation    │    │   (Apply)   │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                        INTEGRATION LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │     API     │  │     CLI     │  │  Training   │  │  Fuzzy  │  │
│  │ Endpoints   │  │  Commands   │  │  Pipeline   │  │ Logic   │  │
│  │             │  │             │  │             │  │         │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Architecture Fundamentals

### 1. BaseIndicator Abstract Class

All indicators inherit from `BaseIndicator` which provides:

```python
class BaseIndicator(ABC):
    """Abstract base class for all technical indicators."""
    
    def __init__(self, name: str, display_as_overlay: bool = True, **params):
        """Initialize indicator with parameters."""
        
    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters using schema system."""
        
    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """Calculate indicator values. MUST BE IMPLEMENTED."""
        
    def validate_input_data(self, df: pd.DataFrame, required_columns: list):
        """Validate input data format and columns."""
        
    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """Generate standardized column name."""
```

**Key Features:**
- **Template Method Pattern**: Common validation and naming logic
- **Input Security**: `InputValidator` prevents injection attacks
- **Standardized Interface**: Consistent API across all indicators
- **Error Handling**: Comprehensive validation at multiple levels

### 2. Automatic Registration System

Indicators are automatically registered via the factory pattern:

```python
# ktrdr/indicators/indicator_factory.py
BUILT_IN_INDICATORS: Dict[str, Type[BaseIndicator]] = {
    "RSI": RSIIndicator,
    "RSIIndicator": RSIIndicator,  # Multiple aliases supported
    "SMA": SimpleMovingAverage,
    "SimpleMovingAverage": SimpleMovingAverage,
    # ... 30+ indicators with aliases
}

class IndicatorFactory:
    """Factory for creating indicator instances."""
    
    @staticmethod
    def create_indicator(indicator_type: str, **params) -> BaseIndicator:
        """Create indicator instance with validation."""
```

**Registration Features:**
- **Multiple Aliases**: Each indicator accessible by multiple names
- **Type Safety**: Compile-time checking of registered indicators
- **Dynamic Import**: Support for custom indicator plugins
- **Error Recovery**: Graceful handling of creation failures

### 3. Schema-Based Parameter Validation

Advanced validation using structured schemas:

```python
# ktrdr/indicators/parameter_schema.py
class ParameterSchema:
    """Schema for validating indicator parameters."""
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[ParameterDefinition],
        constraints: Optional[List[ParameterConstraint]] = None
    ):
        """Initialize parameter schema."""

class ParameterDefinition:
    """Definition for a single parameter."""
    
    def __init__(
        self,
        name: str,
        param_type: ParameterType,
        description: str,
        default: Any,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        options: Optional[List[str]] = None
    ):
        """Initialize parameter definition."""
```

**Validation Features:**
- **Type Conversion**: Automatic conversion with validation
- **Range Checking**: Min/max values for numeric parameters
- **Options Validation**: Enum-like validation for string parameters
- **Cross-Parameter Constraints**: Validation between multiple parameters
- **Detailed Errors**: Comprehensive error messages with context

### 4. Category System

Indicators are organized into logical categories:

```python
# ktrdr/indicators/categories.py
class IndicatorCategory:
    TREND = "trend"                    # 6 indicators
    MOMENTUM = "momentum"              # 8 indicators  
    VOLATILITY = "volatility"          # 4 indicators
    VOLUME = "volume"                  # 5 indicators
    SUPPORT_RESISTANCE = "support_resistance"  # 3 indicators
    MULTI_PURPOSE = "multi_purpose"    # Advanced indicators
```

**Category Features:**
- **Logical Grouping**: Easy discovery and organization
- **API Integration**: Category-based filtering in REST API
- **Documentation**: Automatic categorization in API docs
- **Extensibility**: Easy addition of new categories

---

## 🔨 Creating New Indicators

### Step-by-Step Guide

#### 1. Create the Indicator Class

```python
# ktrdr/indicators/my_new_indicator.py
from typing import Union, Dict, Any
import pandas as pd
import numpy as np
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.parameter_schema import ParameterSchema, ParameterDefinition, ParameterType

class MyNewIndicator(BaseIndicator):
    """My new technical indicator."""
    
    def __init__(self, period: int = 14, **kwargs):
        """Initialize with parameters."""
        super().__init__(
            name="MyNewIndicator",
            display_as_overlay=False,  # Set to True for price overlays
            period=period,
            **kwargs
        )
    
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Calculate indicator values."""
        # Validate input data
        self.validate_input_data(df, required_columns=['close'])
        self.validate_sufficient_data(df, min_periods=self.period)
        
        # Your calculation logic here
        close_prices = df['close']
        
        # Example: Simple calculation
        result = close_prices.rolling(window=self.period).mean()
        
        return result
    
    @staticmethod
    def get_default_params() -> Dict[str, Any]:
        """Get default parameters."""
        return {"period": 14}
    
    @staticmethod  
    def get_parameter_schema() -> ParameterSchema:
        """Get parameter validation schema."""
        return ParameterSchema(
            name="MyNewIndicator",
            description="My new technical indicator description",
            parameters=[
                ParameterDefinition(
                    name="period",
                    param_type=ParameterType.INT,
                    description="Calculation period",
                    default=14,
                    min_value=1,
                    max_value=100
                )
            ]
        )
```

#### 2. Register in Factory

```python
# Add to ktrdr/indicators/indicator_factory.py
from ktrdr.indicators.my_new_indicator import MyNewIndicator

BUILT_IN_INDICATORS: Dict[str, Type[BaseIndicator]] = {
    # ... existing indicators ...
    "MyNewIndicator": MyNewIndicator,
    "MyNew": MyNewIndicator,  # Add alias
}
```

#### 3. Add Parameter Schema

```python
# Add to ktrdr/indicators/schemas.py
from ktrdr.indicators.my_new_indicator import MyNewIndicator

# Import schema from indicator
MY_NEW_SCHEMA = MyNewIndicator.get_parameter_schema()

# Add to registry
PARAMETER_SCHEMAS: Dict[str, ParameterSchema] = {
    # ... existing schemas ...
    "MyNewIndicator": MY_NEW_SCHEMA,
    "MyNew": MY_NEW_SCHEMA,
}
```

#### 4. Add to Categories

```python
# Add to ktrdr/indicators/categories.py
INDICATOR_CATEGORIES = {
    # ... existing categories ...
    IndicatorCategory.TREND: [
        # ... existing indicators ...
        "MyNewIndicator",
    ]
}
```

#### 5. Create Tests

```python
# tests/indicators/test_my_new_indicator.py
import pytest
import pandas as pd
import numpy as np
from ktrdr.indicators.my_new_indicator import MyNewIndicator

class TestMyNewIndicator:
    
    def test_basic_calculation(self):
        """Test basic indicator calculation."""
        # Create test data
        data = pd.DataFrame({
            'close': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        })
        
        # Create indicator
        indicator = MyNewIndicator(period=5)
        
        # Calculate
        result = indicator.compute(data)
        
        # Validate
        assert len(result) == len(data)
        assert not pd.isna(result.iloc[-1])  # Last value should not be NaN
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        with pytest.raises(ValueError):
            MyNewIndicator(period=0)  # Should fail validation
    
    def test_insufficient_data(self):
        """Test error handling for insufficient data."""
        data = pd.DataFrame({'close': [10, 11]})  # Only 2 points
        indicator = MyNewIndicator(period=5)
        
        with pytest.raises(ValueError):
            indicator.compute(data)
```

#### 6. Register in Test Registry

```python
# Add to tests/indicators/indicator_registry.py
INDICATOR_TEST_REGISTRY = {
    # ... existing indicators ...
    "MyNewIndicator": {
        "class": MyNewIndicator,
        "default_params": {"period": 14},
        "test_params": [
            {"period": 10},
            {"period": 20},
        ],
        "expected_shape": "series",  # or "dataframe" for multi-column
        "category": "trend",
    }
}
```

### Required Methods

Every indicator MUST implement:

1. **`__init__()`** - Parameter initialization
2. **`compute()`** - Core calculation logic
3. **`get_default_params()`** - Default parameter values  
4. **`get_parameter_schema()`** - Validation schema

### Optional Methods

Indicators MAY implement:

1. **`_validate_params()`** - Custom parameter validation
2. **`get_display_name()`** - Custom display name
3. **`get_description()`** - Detailed description

---

## 🔗 Integration Patterns

### 1. API Integration

The indicator system integrates seamlessly with the REST API:

```python
# API Usage Example
POST /api/v1/indicators/calculate
{
    "symbol": "AAPL",
    "timeframe": "1d", 
    "indicators": [
        {
            "id": "RSIIndicator",
            "parameters": {"period": 14},
            "output_name": "rsi_14"
        },
        {
            "id": "MyNewIndicator", 
            "parameters": {"period": 20},
            "output_name": "my_indicator_20"
        }
    ]
}
```

### 2. CLI Integration

CLI commands automatically work with new indicators:

```bash
# List indicators (including new ones)
uv run ktrdr indicators list --category trend

# Compute new indicator
uv run ktrdr indicators compute AAPL --type MyNewIndicator --period 20

# Get indicator info
uv run ktrdr indicators list --verbose | grep MyNew
```

### 3. Training Pipeline Integration

Indicators integrate automatically with neural network training:

```python
# In strategy configuration (YAML)
indicators:
  - type: "MyNewIndicator"
    params:
      period: 14
    output_name: "my_indicator"
    
# The training pipeline will automatically:
# 1. Calculate the indicator
# 2. Include it in feature engineering  
# 3. Generate fuzzy memberships (if configured)
# 4. Use in neural network training
```

### 4. Fuzzy Logic Integration

Indicators can be used in fuzzy logic systems:

```yaml
# In fuzzy configuration
fuzzy_sets:
  my_indicator:
    low:
      type: triangular
      parameters: [0, 20, 40]
    high:
      type: triangular  
      parameters: [60, 80, 100]
```

### 5. Multi-timeframe Integration

For multi-timeframe strategies:

```python
# The MultiTimeframeIndicatorEngine automatically:
# 1. Applies indicators across timeframes
# 2. Names outputs as: my_indicator_1h, my_indicator_4h, etc.
# 3. Handles errors independently per timeframe
# 4. Synchronizes data alignment
```

---

## ⚖️ Architecture Rules

### MUST Follow Rules

#### 1. **Always Use the Factory**
```python
# ✅ CORRECT
from ktrdr.indicators.indicator_factory import IndicatorFactory
indicator = IndicatorFactory.create_indicator("RSI", period=14)

# ❌ WRONG - Direct instantiation
from ktrdr.indicators.rsi_indicator import RSIIndicator
indicator = RSIIndicator(period=14)  # Bypasses validation and registration
```

#### 2. **Always Inherit from BaseIndicator**
```python
# ✅ CORRECT
class MyIndicator(BaseIndicator):
    def compute(self, df: pd.DataFrame) -> pd.Series:
        # Implementation
        pass

# ❌ WRONG - Direct implementation
class MyIndicator:
    def calculate(self, data):  # Different interface
        # Implementation
        pass
```

#### 3. **Always Implement Required Methods**
```python
# ✅ CORRECT - All required methods
class MyIndicator(BaseIndicator):
    def compute(self, df: pd.DataFrame) -> pd.Series: pass
    def get_default_params(self) -> Dict[str, Any]: pass
    def get_parameter_schema(self) -> ParameterSchema: pass

# ❌ WRONG - Missing required methods
class MyIndicator(BaseIndicator):
    def compute(self, df: pd.DataFrame) -> pd.Series: pass
    # Missing get_default_params and get_parameter_schema
```

#### 4. **Always Use Schema Validation**
```python
# ✅ CORRECT - Proper schema
def get_parameter_schema(self) -> ParameterSchema:
    return ParameterSchema(
        name="MyIndicator",
        description="My indicator description",
        parameters=[
            ParameterDefinition(
                name="period",
                param_type=ParameterType.INT,
                default=14,
                min_value=1,
                max_value=100
            )
        ]
    )

# ❌ WRONG - No validation
def get_parameter_schema(self) -> ParameterSchema:
    return None  # No validation
```

#### 5. **Always Register New Indicators**
```python
# ✅ CORRECT - Registered in factory
BUILT_IN_INDICATORS: Dict[str, Type[BaseIndicator]] = {
    "MyIndicator": MyIndicator,
}

# ❌ WRONG - Not registered
# Indicator exists but not in BUILT_IN_INDICATORS
```

### SHOULD Follow Guidelines

#### 1. **Use Descriptive Names**
```python
# ✅ GOOD
class RelativeStrengthIndexIndicator(BaseIndicator): pass
class ExponentialMovingAverageIndicator(BaseIndicator): pass

# 🔄 ACCEPTABLE
class RSIIndicator(BaseIndicator): pass
class EMAIndicator(BaseIndicator): pass

# ❌ POOR
class Indicator1(BaseIndicator): pass
class MyThing(BaseIndicator): pass
```

#### 2. **Provide Multiple Aliases**
```python
# ✅ GOOD - Multiple ways to access
BUILT_IN_INDICATORS = {
    "RSI": RSIIndicator,
    "RSIIndicator": RSIIndicator,
    "RelativeStrengthIndex": RSIIndicator,
}
```

#### 3. **Include Comprehensive Tests**
```python
# ✅ GOOD - Multiple test scenarios
def test_basic_calculation(self): pass
def test_edge_cases(self): pass
def test_parameter_validation(self): pass
def test_insufficient_data(self): pass
def test_invalid_data(self): pass
```

---

## 🚫 Anti-Patterns to Avoid

### 1. **Direct Technical Analysis Libraries**

```python
# ❌ FORBIDDEN - Bypasses indicator system
import ta
import talib
import pandas_ta

def calculate_rsi(data):
    return ta.momentum.RSIIndicator(data['close']).rsi()

# ✅ CORRECT - Use indicator system
from ktrdr.indicators.indicator_factory import IndicatorFactory
indicator = IndicatorFactory.create_indicator("RSI", period=14)
result = indicator.compute(data)
```

### 2. **Hardcoded Calculations**

```python
# ❌ FORBIDDEN - Manual calculation
def get_moving_average(data, period):
    return data['close'].rolling(window=period).mean()

# ✅ CORRECT - Use indicator
indicator = IndicatorFactory.create_indicator("SMA", period=period)
result = indicator.compute(data)
```

### 3. **Bypassing Parameter Validation**

```python
# ❌ FORBIDDEN - No validation
class BadIndicator(BaseIndicator):
    def __init__(self, period):
        self.period = period  # No validation
        
# ✅ CORRECT - Proper validation
class GoodIndicator(BaseIndicator):
    def __init__(self, period: int = 14, **kwargs):
        super().__init__(name="GoodIndicator", period=period, **kwargs)
```

### 4. **Inconsistent Naming**

```python
# ❌ FORBIDDEN - Inconsistent interface
class BadIndicator(BaseIndicator):
    def calculate_values(self, df): pass  # Wrong method name
    def get_params(self): pass           # Wrong method name

# ✅ CORRECT - Standard interface  
class GoodIndicator(BaseIndicator):
    def compute(self, df): pass          # Correct method name
    def get_default_params(self): pass   # Correct method name
```

### 5. **Missing Error Handling**

```python
# ❌ FORBIDDEN - No error handling
class BadIndicator(BaseIndicator):
    def compute(self, df):
        return df['close'].rolling(self.period).mean()  # No validation

# ✅ CORRECT - Proper error handling
class GoodIndicator(BaseIndicator):
    def compute(self, df):
        self.validate_input_data(df, ['close'])
        self.validate_sufficient_data(df, self.period)
        return df['close'].rolling(self.period).mean()
```

---

## 📚 Reference Examples

### Simple Indicator (Single Column Output)

```python
# Example: Custom Momentum Indicator
class CustomMomentumIndicator(BaseIndicator):
    """Custom momentum indicator."""
    
    def __init__(self, period: int = 14, **kwargs):
        super().__init__(
            name="CustomMomentum",
            display_as_overlay=False,
            period=period,
            **kwargs
        )
    
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Calculate momentum."""
        self.validate_input_data(df, ['close'])
        self.validate_sufficient_data(df, self.period)
        
        close = df['close']
        momentum = close - close.shift(self.period)
        
        return momentum
    
    @staticmethod
    def get_default_params() -> Dict[str, Any]:
        return {"period": 14}
    
    @staticmethod
    def get_parameter_schema() -> ParameterSchema:
        return ParameterSchema(
            name="CustomMomentum",
            description="Custom momentum calculation",
            parameters=[
                ParameterDefinition(
                    name="period",
                    param_type=ParameterType.INT,
                    description="Lookback period",
                    default=14,
                    min_value=1,
                    max_value=100
                )
            ]
        )
```

### Complex Indicator (Multiple Column Output)

```python
# Example: Custom Bands Indicator
class CustomBandsIndicator(BaseIndicator):
    """Custom volatility bands."""
    
    def __init__(self, period: int = 20, multiplier: float = 2.0, **kwargs):
        super().__init__(
            name="CustomBands",
            display_as_overlay=True,
            period=period,
            multiplier=multiplier,
            **kwargs
        )
    
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate bands."""
        self.validate_input_data(df, ['close'])
        self.validate_sufficient_data(df, self.period)
        
        close = df['close']
        sma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()
        
        upper = sma + (std * self.multiplier)
        lower = sma - (std * self.multiplier)
        
        return pd.DataFrame({
            f'{self.name}_upper': upper,
            f'{self.name}_middle': sma,
            f'{self.name}_lower': lower
        })
    
    @staticmethod  
    def get_default_params() -> Dict[str, Any]:
        return {"period": 20, "multiplier": 2.0}
    
    @staticmethod
    def get_parameter_schema() -> ParameterSchema:
        return ParameterSchema(
            name="CustomBands",
            description="Custom volatility bands",
            parameters=[
                ParameterDefinition(
                    name="period",
                    param_type=ParameterType.INT,
                    description="Calculation period",
                    default=20,
                    min_value=2,
                    max_value=100
                ),
                ParameterDefinition(
                    name="multiplier",
                    param_type=ParameterType.FLOAT,
                    description="Standard deviation multiplier",
                    default=2.0,
                    min_value=0.1,
                    max_value=5.0
                )
            ]
        )
```

### Proper Usage in Other Systems

```python
# ✅ CORRECT - Training pipeline usage
def calculate_indicators_for_training(data, indicator_configs):
    """Calculate indicators for training pipeline."""
    results = {}
    
    for config in indicator_configs:
        indicator = IndicatorFactory.create_indicator(
            config['type'], 
            **config.get('params', {})
        )
        
        result = indicator.compute(data)
        output_name = config.get('output_name', indicator.name)
        
        if isinstance(result, pd.Series):
            results[output_name] = result
        elif isinstance(result, pd.DataFrame):
            for col in result.columns:
                results[f"{output_name}_{col}"] = result[col]
    
    return pd.DataFrame(results)

# ✅ CORRECT - API endpoint usage  
async def calculate_indicators_endpoint(request: IndicatorRequest):
    """API endpoint for indicator calculation."""
    try:
        results = {}
        
        for indicator_spec in request.indicators:
            indicator = IndicatorFactory.create_indicator(
                indicator_spec.id,
                **indicator_spec.parameters
            )
            
            result = indicator.compute(request.data)
            results[indicator_spec.output_name] = result
            
        return IndicatorResponse(success=True, data=results)
        
    except Exception as e:
        return IndicatorResponse(success=False, error=str(e))
```

---

## ⚠️ Common Mistakes

### 1. Forgetting to Register

```python
# ❌ MISTAKE - Created indicator but didn't register
class NewIndicator(BaseIndicator): pass

# Result: IndicatorFactory.create_indicator("NewIndicator") fails

# ✅ SOLUTION - Add to factory registry
BUILT_IN_INDICATORS["NewIndicator"] = NewIndicator
```

### 2. Inconsistent Parameter Names

```python
# ❌ MISTAKE - Different parameter names
class BadIndicator(BaseIndicator):
    def __init__(self, periods: int = 14):  # "periods" 
        super().__init__(periods=periods)
    
    @staticmethod
    def get_default_params():
        return {"period": 14}  # "period" - MISMATCH!

# ✅ SOLUTION - Consistent naming
class GoodIndicator(BaseIndicator):
    def __init__(self, period: int = 14):   # "period"
        super().__init__(period=period)
    
    @staticmethod
    def get_default_params():
        return {"period": 14}  # "period" - MATCH!
```

### 3. Missing Data Validation

```python
# ❌ MISTAKE - No validation
class BadIndicator(BaseIndicator):
    def compute(self, df):
        return df['close'].rolling(self.period).mean()  # Will fail if no 'close' column

# ✅ SOLUTION - Proper validation
class GoodIndicator(BaseIndicator):
    def compute(self, df):
        self.validate_input_data(df, ['close'])
        self.validate_sufficient_data(df, self.period)
        return df['close'].rolling(self.period).mean()
```

### 4. Wrong Return Type

```python
# ❌ MISTAKE - Wrong return type
class BadIndicator(BaseIndicator):
    def compute(self, df):
        return df['close'].rolling(self.period).mean().values  # Returns numpy array

# ✅ SOLUTION - Correct return type
class GoodIndicator(BaseIndicator):  
    def compute(self, df):
        return df['close'].rolling(self.period).mean()  # Returns pandas Series
```

### 5. Missing Schema

```python
# ❌ MISTAKE - No parameter schema
class BadIndicator(BaseIndicator):
    @staticmethod
    def get_parameter_schema():
        return None  # No validation!

# ✅ SOLUTION - Proper schema
class GoodIndicator(BaseIndicator):
    @staticmethod
    def get_parameter_schema():
        return ParameterSchema(
            name="GoodIndicator",
            description="Proper indicator with validation",
            parameters=[
                ParameterDefinition(
                    name="period",
                    param_type=ParameterType.INT,
                    default=14,
                    min_value=1,
                    max_value=100
                )
            ]
        )
```

---

## 🎯 Enforcement Summary

### What Gets Automatically Validated

1. **Parameter Types**: Schema system validates all parameter types
2. **Parameter Ranges**: Min/max values enforced automatically
3. **Input Data**: Required columns and sufficient data validated
4. **Security**: Input validation prevents injection attacks
5. **Registration**: Factory pattern ensures all indicators are registered

### What Requires Code Review

1. **Calculation Logic**: Ensure mathematical correctness
2. **Performance**: Verify efficient pandas/numpy operations
3. **Edge Cases**: Handle divide-by-zero, empty data, etc.
4. **Documentation**: Clear docstrings and parameter descriptions
5. **Tests**: Comprehensive test coverage

### Architectural Violations Will Be Rejected

1. **Direct TA Library Usage**: No `ta`, `talib`, `pandas_ta` imports
2. **Bypassing Factory**: All indicators must go through IndicatorFactory
3. **Missing Registration**: All indicators must be in BUILT_IN_INDICATORS
4. **Inconsistent Interface**: Must inherit from BaseIndicator properly
5. **No Validation**: Must implement proper parameter schemas

---

## 📖 Conclusion

The KTRDR indicator system provides a robust, extensible foundation for technical analysis. By following this guide, developers can create new indicators that integrate seamlessly with the entire system while maintaining consistency, security, and performance.

**Remember**: This is not just a coding standard - it's an architectural requirement. ALL indicator functionality must go through this system.

For questions or clarifications, refer to the existing indicator implementations in `ktrdr/indicators/` as reference examples.

---

**Document Version**: 1.0  
**Last Updated**: December 2024  
**Next Review**: March 2025