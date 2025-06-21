# Backend Python Development Guidelines

## 🏗️ MODULE ARCHITECTURE

```
data/       - Data fetching and storage (IB integration)
api/        - FastAPI endpoints and models
models/     - Neural networks and training
indicators/ - Technical analysis calculations
fuzzy/      - Fuzzy logic membership functions
utils/      - Shared utilities
errors/     - Custom exception hierarchy
```

## 📝 PYTHON PATTERNS

### Type Hints Required
```python
# ❌ Bad
def process_data(data, params):
    return result

# ✅ Good  
def process_data(data: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    return result
```

### Docstrings Required
```python
def calculate_indicator(data: pd.DataFrame, period: int) -> pd.Series:
    """Calculate indicator values.
    
    Args:
        data: OHLCV price data
        period: Lookback period for calculation
        
    Returns:
        Series of indicator values
        
    Raises:
        DataError: If data is invalid or insufficient
    """
```

## 🚫 BACKEND ANTI-PATTERNS

❌ Hardcoded values or magic numbers
✅ Use constants or configuration

❌ Bare except clauses
✅ Catch specific exceptions

❌ Print statements for debugging
✅ Use proper logging

❌ Direct file I/O without error handling
✅ Use context managers and handle errors

## 📊 DATA HANDLING

- All timestamps MUST be timezone-aware UTC
- Use pandas for time series operations
- Validate data shape and types early
- Handle missing data explicitly

## 🔧 ERROR HANDLING

Use custom exceptions from `ktrdr.errors`:
- `DataError` - Data validation issues
- `ConnectionError` - IB/network issues  
- `ConfigError` - Configuration problems
- `CalculationError` - Indicator/model errors

Always include context:
```python
raise DataError(
    "Insufficient data for calculation",
    details={"required": 100, "actual": len(data)}
)
```

## 🧪 TESTING PATTERNS

- Test public interfaces, not implementation
- Use pytest fixtures for common setup
- Mock external dependencies (IB, filesystem)
- Test error cases, not just happy path
- Use parameterized tests for similar cases