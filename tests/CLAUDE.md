# Testing Guidelines

## 🧪 TESTING PHILOSOPHY

- **Test behavior, not implementation**
- **Write tests BEFORE fixing bugs**
- **Each test should test ONE thing**
- **Test names should describe what they test**

## 📁 TEST STRUCTURE

```
tests/
├── unit/              # <15s total (74 files), no external deps, comprehensive mocking
│   ├── api/           # API models, validation, business logic
│   ├── cli/           # CLI command parsing, validation, logic  
│   ├── config/        # Configuration loading and validation
│   ├── core/          # System fundamentals, metadata
│   ├── data/          # Data adapters, transformations
│   ├── fuzzy/         # Fuzzy logic calculations and algorithms
│   ├── ib/            # IB connection logic, error handling
│   ├── indicators/    # Technical indicator calculations
│   ├── neural/        # Neural network foundations
│   ├── training/      # Model storage, processors
│   ├── utils/         # Utility functions and helpers
│   └── visualization/ # Chart generation logic
├── integration/       # <30s total (18 files), component interactions, mocked externals
│   ├── api/           # HTTP endpoint integration
│   ├── cli/           # CLI command integration
│   ├── data_pipeline/ # Data flow integration
│   ├── fuzzy/         # Multi-timeframe fuzzy integration
│   ├── host_services/ # Service orchestration with mocked externals
│   ├── ib/            # Complex IB parsing integration
│   ├── services/      # Service orchestration
│   ├── visualization/ # End-to-end chart generation
│   └── workflows/     # Decision orchestration, backtesting
├── e2e/               # <5min total, full system tests
│   ├── container/     # Container-based system tests
│   └── real/          # Real service integration
├── host_service/      # Tests requiring real host services (manual only)
│   ├── ib_integration/     # Real IB Gateway/TWS tests
│   └── training_service/   # Real training service tests
└── manual/            # Manual/nightly tests only
    ├── performance/   # Performance benchmarks
    ├── stress/        # Stress testing
    └── real_trading/  # Real market tests
```

## 🏃 RUNNING TESTS

### Standard Commands (Use Makefile)

```bash
# Fast development loop - run on every change
make test-unit          # Unit tests only (<15s) - DEFAULT CHOICE
make test-fast          # Alias for test-unit

# Integration testing - run when testing component interactions  
make test-integration   # Integration tests (<30s)

# Full system testing - run before major commits
make test-e2e          # End-to-end tests (<5min)

# Host service testing - requires real services running
make test-host         # Host service tests (IB Gateway, training services)

# Coverage and reporting
make test-coverage     # Unit tests with HTML coverage report
make test-all          # All tests (unit + integration + e2e)

# Performance testing
make test-performance  # Performance benchmarks (manual category)

# Code quality - run before committing
make quality           # Lint + format + typecheck
make lint              # Ruff linting only  
make format            # Black formatting only
make typecheck         # MyPy type checking only

# CI simulation - matches GitHub Actions
make ci                # Run unit tests + quality checks
```

### Direct Pytest Commands

```bash
# Unit tests (fastest feedback)
uv run pytest tests/unit/ -v

# Specific test categories
uv run pytest tests/unit/indicators/ -v     # Specific module
uv run pytest tests/integration/api/ -v     # Integration tests
uv run pytest tests/e2e/container/ -v       # Container E2E tests

# With markers
uv run pytest -m "unit" -v                  # Only unit tests
uv run pytest -m "integration" -v           # Only integration tests  
uv run pytest -m "host_service" -v          # Only host service tests

# Coverage reporting
uv run pytest tests/unit/ --cov=ktrdr --cov-report=html
uv run pytest --cov=ktrdr --cov-report=term-missing
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

## 🚀 CI/CD PIPELINE

### GitHub Actions Workflow

The CI pipeline runs automatically on pushes and pull requests:

#### Default Run (Every Push)
- **unit-tests-and-quality**: Unit tests + code quality checks
  - Runs `make test-coverage` (unit tests with coverage)
  - Runs `make quality` (lint + format + typecheck) 
  - Uploads coverage to Codecov
  - **Performance**: <30 seconds total

#### Manual Trigger (workflow_dispatch)
- **integration-tests**: Component interaction tests  
  - Runs `make test-integration`
  - Uses mocked external services
  - **Performance**: <45 seconds total
  
- **e2e-tests**: Full system tests
  - Starts Docker containers
  - Runs `make test-e2e` 
  - Tests container-based system workflows
  - **Performance**: <8 minutes total

### Local Testing Before Commit

```bash
# Essential pre-commit checks (< 30 seconds)
make test-unit          # Unit tests - MUST PASS
make quality           # Code quality - MUST PASS

# Optional comprehensive testing
make test-integration  # Integration tests
make test-coverage     # Coverage report
```

### Host Service Tests (Manual Only)

Tests requiring real services are NOT run in CI:

```bash
# Real IB Gateway tests (requires IB Gateway/TWS running)
make test-host         # All host service tests
uv run pytest tests/host_service/ib_integration/ -v

# Real training service tests (requires training service running)  
uv run pytest tests/host_service/training_service/ -v

# Real E2E tests (requires real external services)
uv run pytest tests/e2e/real/ -v
```

### Performance Standards

| Test Category | Target Time | Current Performance | Status |
|---------------|-------------|-------------------|---------|
| Unit Tests | <15s | 8.89s | ✅ EXCELLENT |
| Integration | <30s | 6.67s (fast subset) | ✅ EXCELLENT |
| E2E Container | <5min | ~8min (with startup) | ⚠️ ACCEPTABLE |
| Host Service | Manual | N/A (skip in CI) | ⏭️ MANUAL |

### Coverage Targets

- **Unit test coverage**: >30% (current: 32%)
- **Core modules**: >85% (indicators: 87-100%, metadata: 89%)  
- **Coverage reporting**: Codecov integration active
- **HTML reports**: Generated locally with `make test-coverage`

## ⚠️ HOST SERVICE TESTS

Located in `tests/host_service/`:
- **Require real services**: IB Gateway/TWS, training services
- **Not run in CI**: Manual execution only
- **Usage**: `make test-host` or direct pytest commands
- **Requirements**: Document service setup clearly