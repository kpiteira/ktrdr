# Testing Guidelines

## 🧪 TESTING PHILOSOPHY

- **Test behavior, not implementation**
- **Write tests BEFORE fixing bugs**
- **Each test should test ONE thing**
- **Test names should describe what they test**

## 📁 TEST STRUCTURE

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Component interaction tests
├── e2e_real/       # Real IB Gateway tests
└── fixtures/       # Shared test data
```

## 🏃 RUNNING TESTS

```bash
# All tests (except real IB)
uv run pytest

# Fast tests only (skip slow integration)
uv run pytest -m "not integration_slow"

# Specific module
uv run pytest tests/unit/data/

# With coverage
uv run pytest --cov=ktrdr
```

## 🚫 TESTING ANTI-PATTERNS

❌ Tests that depend on test order
✅ Each test independent

❌ Tests that use real external services
✅ Mock external dependencies

❌ Tests with no assertions
✅ Always assert expected behavior

❌ Commenting out failing tests
✅ Fix or properly skip with reason

## 📝 TEST PATTERNS

### Arrange-Act-Assert
```python
def test_indicator_calculation():
    # Arrange
    data = create_test_data()
    indicator = RSI(period=14)
    
    # Act
    result = indicator.calculate(data)
    
    # Assert
    assert len(result) == len(data)
    assert result.iloc[-1] == pytest.approx(65.4, rel=0.01)
```

### Parameterized Tests
```python
@pytest.mark.parametrize("period,expected", [
    (14, 65.4),
    (21, 58.2),
    (7, 72.1),
])
def test_rsi_periods(period, expected):
    # Test multiple cases efficiently
```

## 🔧 FIXTURES

Common fixtures in `conftest.py`:
- `sample_ohlcv_data` - Standard price data
- `mock_ib_connection` - Mocked IB client
- `test_config` - Test configuration

## ⚠️ REAL IB TESTS

Only in `tests/e2e_real/`:
- Require `--real-ib` flag
- Need IB Gateway running
- Test actual IB behavior
- Document requirements clearly