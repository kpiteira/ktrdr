# KTRDR Architecture Guidelines

## Core Architectural Principles

### 1. Separation of Concerns

Each module has a single, well-defined responsibility:

```
Frontend → API → Core → Data → IB Gateway
         (Never skip layers or create circular dependencies)
```

**Module Responsibilities:**

- **Frontend**: User interface and visualization
- **API**: REST endpoints and request/response handling  
- **Core**: Business logic (training, indicators, fuzzy logic)
- **Data**: Data fetching, storage, and quality validation
- **IB Gateway**: External broker integration

### 2. Indicator-Agnostic Training Pipeline

**CRITICAL RULE**: The training pipeline MUST remain indicator-agnostic.

#### ✅ Training Pipeline Responsibilities:
- Load strategy configuration
- Orchestrate indicator engine (calculate indicators declared in config)
- Orchestrate fuzzy engine (convert indicators to fuzzy memberships)
- Feature engineering (scaling, selection of fuzzy outputs)
- Neural network training and evaluation

#### ❌ Training Pipeline MUST NOT:
- Perform direct indicator calculations
- Calculate derived metrics outside indicator engine
- Make assumptions about which indicators exist
- Hard-code mathematical transformations

#### Historical Context - June 21 Incident:
On June 21, 2025, commit `1efe5ab` violated this principle by adding hard-coded derived metric calculations to the training pipeline. This caused:
- Training failures with "NaN loss on first batch"
- Architectural coupling between training and indicator logic
- Violation of separation of concerns

**Prevention**: All mathematical calculations belong in indicator classes, not training pipeline.

### 3. Indicator Engine Architecture

All technical analysis calculations MUST be implemented as indicator classes:

#### Indicator Class Pattern:
```python
class IndicatorNameIndicator(BaseIndicator):
    def __init__(self, param1=default1, param2=default2):
        super().__init__(
            name="IndicatorName", 
            display_as_overlay=True/False,
            param1=param1, 
            param2=param2
        )
    
    def _validate_params(self, params):
        return INDICATOR_SCHEMA.validate(params)
    
    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        # Implementation with proper error handling
        # Use DataError for validation issues
        # Return bounded, validated values
```

#### Registration Requirements:
1. **Schema Definition**: Add parameter schema to `ktrdr/indicators/schemas.py`
2. **Factory Registration**: Register in `ktrdr/indicators/indicator_factory.py`
3. **Comprehensive Tests**: Unit tests following existing patterns
4. **Documentation**: Usage examples and parameter descriptions

#### Automatic Integration:
Following the pattern provides automatic integration with:
- ✅ API endpoints (`/api/v1/indicators`)
- ✅ CLI commands (`ktrdr indicators`)
- ✅ Strategy configurations
- ✅ Indicator engine processing
- ✅ Schema validation

### 4. Data Flow Architecture

```
Raw Data → Indicator Engine → Fuzzy Engine → Feature Engineering → Neural Network
```

**Strict Unidirectional Flow:**
- No circular dependencies
- No backwards data flow
- Each stage validates its inputs
- Errors propagate forward with context

### 5. Error Handling Architecture

Use custom exceptions from `ktrdr.errors` with context:

```python
# ✅ Good
raise DataError(
    message="Insufficient data for calculation",
    error_code="DATA-InsufficientData",
    details={"required": 100, "actual": len(data)}
)

# ❌ Bad  
raise Exception("Not enough data")
```

**Exception Hierarchy:**
- `DataError` - Data validation and quality issues
- `ConnectionError` - IB/network connectivity issues
- `ConfigError` - Configuration and parameter issues
- `CalculationError` - Indicator and model calculation issues

### 6. Configuration-Driven Architecture

All behavior MUST be configurable via YAML strategy files:

```yaml
# Strategy declares what it needs
indicators:
  - name: rsi
    type: RSI
    period: 14
  - name: bb_width  
    type: BollingerBandWidth
    bb_period: 20

# System provides only what's declared
# No assumptions about indicator existence
```

## Architectural Violations to Prevent

### 1. Training Pipeline Violations

❌ **DON'T**: Add indicator calculations to training code
```python
# WRONG - Don't do this in training pipeline
mapped_results["bb_width"] = (upper_vals - lower_vals) / middle_vals
```

✅ **DO**: Use indicator engine
```python
# CORRECT - Let indicator engine handle it
indicator_results = self.indicator_engine.apply(price_data)
```

### 2. Hardcoded Assumptions

❌ **DON'T**: Assume indicators exist
```python
# WRONG - Assumes RSI always exists
rsi_values = indicators["rsi"]
```

✅ **DO**: Check configuration
```python
# CORRECT - Only process declared indicators
for config in strategy_config["indicators"]:
    if config["name"] == "rsi":
        # Process RSI
```

### 3. Circular Dependencies

❌ **DON'T**: Create circular imports
```python
# WRONG - Creates circular dependency
from ktrdr.training import StrategyTrainer
from ktrdr.indicators import SomeIndicator
```

✅ **DO**: Follow dependency hierarchy
```python
# CORRECT - Training depends on indicators, not vice versa
from ktrdr.indicators import IndicatorEngine
```

### 4. Mixed Responsibilities

❌ **DON'T**: Mix data processing with business logic
```python
# WRONG - Data loading mixed with calculation
def load_and_calculate(symbol):
    data = load_data(symbol)
    rsi = calculate_rsi(data)  # Should be in indicator
    return rsi
```

✅ **DO**: Separate concerns
```python
# CORRECT - Clear separation
data = data_manager.load_data(symbol)
indicators = indicator_engine.apply(data)
```

## Code Organization Guidelines

### 1. Module Structure

```
ktrdr/
├── api/           # REST API endpoints and models
├── data/          # Data fetching, storage, validation
├── indicators/    # Technical analysis calculations
├── fuzzy/         # Fuzzy logic membership functions
├── training/      # Neural network training orchestration
├── neural/        # Neural network models and utilities
├── ib/            # Interactive Brokers integration
├── cli/           # Command line interface
├── config/        # Configuration management
├── errors/        # Custom exception hierarchy
└── utils/         # Shared utilities
```

### 2. File Naming Conventions

- **Indicators**: `{name}_indicator.py` (e.g., `rsi_indicator.py`)
- **Tests**: `test_{module_name}.py` (e.g., `test_rsi_indicator.py`)
- **Schemas**: Centralized in `schemas.py` per module
- **Factories**: `{module}_factory.py` (e.g., `indicator_factory.py`)

### 3. Import Guidelines

```python
# ✅ Good - Explicit imports
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.errors import DataError

# ❌ Bad - Star imports
from ktrdr.indicators import *
```

## Testing Architecture

### 1. Test Organization

```
tests/
├── unit/          # Unit tests for individual classes
├── integration/   # Integration tests across modules
├── e2e/          # End-to-end system tests
└── fixtures/     # Test data and mocks
```

### 2. Testing Principles

- **Test interfaces, not implementation**
- **Mock external dependencies** (IB, filesystem)
- **Test error cases**, not just happy path
- **Use parameterized tests** for similar cases
- **Validate mathematical correctness** for indicators

### 3. Test Coverage Requirements

- **Indicators**: 100% coverage of compute logic
- **Training**: 90% coverage of orchestration
- **API**: 95% coverage of endpoints
- **Data**: 95% coverage of validation logic

## Performance Guidelines

### 1. Data Processing

- **Use vectorized operations** (NumPy/Pandas)
- **Avoid loops** for large datasets
- **Cache expensive calculations** when appropriate
- **Use proper data types** (float32 vs float64)

### 2. Memory Management

- **Stream large datasets** instead of loading all in memory
- **Clean up temporary objects** in long-running processes
- **Use generators** for data processing pipelines
- **Monitor memory usage** in production

### 3. API Performance

- **Use async/await** for I/O operations
- **Implement request caching** for expensive operations
- **Use connection pooling** for database/IB connections
- **Set appropriate timeouts** for external calls

## Monitoring and Observability

### 1. Logging Standards

```python
# ✅ Good - Structured logging
logger.info(
    "Training completed",
    extra={
        "strategy": strategy_name,
        "symbol": symbol,
        "accuracy": final_accuracy,
        "duration_seconds": training_time
    }
)

# ❌ Bad - Unstructured logging
print(f"Training done: {accuracy}")
```

### 2. Metrics Collection

- **Training metrics**: Accuracy, loss, training time
- **API metrics**: Request count, response time, error rate
- **Data metrics**: Data quality, gap detection, update frequency
- **System metrics**: Memory usage, CPU usage, disk I/O

### 3. Error Tracking

- **Structured error context** with relevant details
- **Error categorization** by module and severity
- **Recovery procedures** for common error scenarios
- **Alerting thresholds** for critical errors

## Security Guidelines

### 1. API Security

- **Input validation** on all endpoints
- **Rate limiting** to prevent abuse
- **Authentication** for sensitive operations
- **HTTPS** for all external communications

### 2. Data Security

- **No secrets in code** or configuration files
- **Environment variables** for sensitive configuration
- **Encrypted storage** for sensitive data
- **Access controls** on data directories

### 3. IB Integration Security

- **Read-only mode** by default
- **Connection validation** before trading operations
- **Audit logging** for all trading actions
- **Emergency stop** mechanisms

## Documentation Standards

### 1. Code Documentation

- **Docstrings** for all public methods
- **Type hints** for all function signatures
- **Usage examples** in docstrings
- **Parameter descriptions** with valid ranges

### 2. Architecture Documentation

- **Decision records** for major architectural choices
- **Sequence diagrams** for complex workflows
- **API documentation** with examples
- **Troubleshooting guides** for common issues

### 3. User Documentation

- **Getting started guides** for new users
- **Configuration examples** for different use cases
- **Best practices** for each module
- **Migration guides** for breaking changes

## Conclusion

These guidelines ensure KTRDR maintains clean architecture, prevents violations like the June 21 incident, and supports sustainable development. All developers must follow these principles to maintain system integrity and prevent architectural debt.

For questions or clarifications, refer to the architectural decision records in `docs/decisions/` or reach out to the core development team.