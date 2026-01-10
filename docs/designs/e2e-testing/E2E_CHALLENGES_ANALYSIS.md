# E2E Testing Challenges Analysis

**Date:** 2026-01-09
**Context:** M6 Indicator Standardization Cleanup Validation
**Purpose:** Document challenges encountered during E2E validation to inform better E2E testing design

---

## Executive Summary

During the M6 cleanup validation, we encountered several E2E testing challenges that led to significant debugging time. What initially appeared to be code bugs (NaN training, 0 trades) were actually **strategy configuration issues** and **environment problems**. This document catalogs these challenges to inform the design of a more robust E2E testing system.

---

## Challenge 1: False Positive - "0 Trades" Issue

### Symptoms
- Training completed with 100% accuracy (suspicious)
- Loss decreased from 0.88 to 0.0003 (too good)
- Backtesting produced **0 trades**
- Model always predicted HOLD with 100% confidence

### Initial Hypothesis
Code bug introduced during v2 cleanup - possibly broken signal generation or decision engine.

### Actual Root Cause
**Strategy configuration issue** - The zigzag threshold was inappropriate for the data:

| Parameter | Value | Problem |
|-----------|-------|---------|
| Symbol | EURUSD | Forex has low volatility |
| Zigzag threshold | 2.5% | Too high for forex |
| Training period | 31 days | Insufficient data |
| Result | 100% HOLD labels | No BUY/SELL to learn |

### Evidence

```python
# Label distribution with 2.5% threshold on EURUSD
HOLD: 100%
BUY:  0%
SELL: 0%

# Label distribution with 0.5% threshold on EURUSD
HOLD: 82%
BUY:  8%
SELL: 10%

# Label distribution with 2.5% threshold on AAPL (stocks)
HOLD: 60%
BUY:  22%
SELL: 18%
```

### Time Wasted
~2 hours investigating code paths before checking label distribution.

### Lesson Learned
**Always validate training data quality before assuming code bugs:**
- Check label distribution before training
- Flag 100% accuracy as suspicious
- Validate that training parameters are appropriate for the data

---

## Challenge 2: Docker Environment Issues

### Symptoms
- Docker daemon connectivity errors
- Port 4317 conflicts (OTEL collector)
- Containers not starting properly
- `docker compose` commands failing silently

### Root Cause
Docker daemon had become corrupted/stuck. Required full restart.

### Resolution
```bash
# Kill and restart Docker
# Then use sandbox commands
uv run ktrdr sandbox up
```

### Lesson Learned
**E2E tests should:**
- Verify Docker health before running tests
- Have clear error messages when Docker is unavailable
- Provide automated recovery/restart procedures

---

## Challenge 3: Sandbox Port Confusion

### Symptoms
- API calls to wrong port (8000 vs 8001)
- curl commands returning 404 or connection refused
- Confusion about which environment was active

### Root Cause
Sandbox environments use different ports than main environment:

| Environment | API Port | DB Port | Grafana | Jaeger |
|-------------|----------|---------|---------|--------|
| Main | 8000 | 5432 | 3000 | 16686 |
| Sandbox 1 | 8001 | 5433 | 3001 | 16687 |
| Sandbox 2 | 8002 | 5434 | 3002 | 16688 |

### Resolution
```bash
# Check which environment you're in
uv run ktrdr sandbox status
```

### Lesson Learned
**E2E tests should:**
- Auto-detect the current environment
- Use environment variables for ports
- Never hardcode port numbers in test scripts

---

## Challenge 4: API Schema Inconsistencies

### Symptoms
- Training API calls failing with validation errors
- Different endpoints expecting different parameter formats

### Root Cause
Inconsistent API schemas between endpoints:

```python
# Training endpoint
POST /api/v1/trainings/start
{
    "symbols": ["EURUSD"],      # Array
    "timeframes": ["1h"],       # Array
    "strategy_name": "..."
}

# Backtest endpoint
POST /api/v1/backtests/start
{
    "symbol": "EURUSD",         # Singular
    "timeframe": "1h",          # Singular
    "strategy_name": "..."
}
```

### Lesson Learned
**E2E tests should:**
- Have a client library that abstracts API differences
- Validate request schemas before sending
- Document expected request/response formats clearly

---

## Challenge 5: Data Location Issues

### Symptoms
- `LocalDataLoader` returning `None`
- "Data file not found" errors
- Tests working in Docker but failing locally

### Root Cause
Data lives in different locations:
- Local development: `./data/`
- Shared (sandbox): `~/.ktrdr/shared/data/`
- Docker containers: `/app/data/` (mounted from shared)

### Resolution
```python
# Must specify correct data directory
loader = LocalDataLoader(data_dir='/Users/karl/.ktrdr/shared/data')
```

### Lesson Learned
**E2E tests should:**
- Use consistent data paths across environments
- Have clear data setup/teardown procedures
- Document data requirements for each test

---

## Challenge 6: Model Collapse Detection

### Symptoms
- Model predicts same class for all inputs
- 100% accuracy during training
- Very low loss (< 0.001)

### Root Cause
Class imbalance in training data. Model learns to predict majority class.

### How to Detect
```python
# Test model with diverse inputs
test_cases = [
    [1.0, 0.0, 0.0],  # Should predict differently
    [0.0, 1.0, 0.0],  # than this
    [0.0, 0.0, 1.0],  # and this
]

# If all predictions are identical, model has collapsed
for tc in test_cases:
    prediction = model(tc)
    if all_same(predictions):
        raise ModelCollapseError("Model always predicts same class")
```

### Lesson Learned
**E2E tests should:**
- Include model diversity checks post-training
- Flag 100% accuracy as suspicious
- Validate predictions on synthetic edge cases

---

## Challenge 7: Slow Feedback Loops

### Symptoms
- Had to wait for training to complete before seeing issues
- Backtesting took time to reveal 0 trades problem
- Multiple iterations needed to diagnose

### Root Cause
No early validation of:
- Label distribution before training
- Model predictions before backtesting
- Configuration validity before execution

### Lesson Learned
**E2E tests should have fast-fail checks:**
1. Validate label distribution (< 1 second)
2. Validate strategy configuration (< 1 second)
3. Run training with 1-2 epochs first (quick sanity check)
4. Check model predictions before full backtest

---

## Proposed E2E Testing Improvements

### 1. Pre-Flight Checks
```python
def preflight_check(strategy_name, symbol, timeframe, date_range):
    """Run before any E2E test."""

    # Check Docker health
    assert docker_healthy(), "Docker not running"

    # Check data availability
    assert data_exists(symbol, timeframe, date_range), "Data not found"

    # Check label distribution
    labels = generate_labels(strategy, data)
    distribution = labels.value_counts(normalize=True)
    assert distribution.min() > 0.05, f"Class imbalance: {distribution}"

    # Check strategy configuration
    validate_strategy_config(strategy)
```

### 2. Quick Smoke Test
```python
def quick_smoke_test(strategy):
    """2-minute smoke test before full E2E."""

    # Train for 2 epochs only
    result = train(strategy, epochs=2)
    assert not np.isnan(result.loss), "NaN in training"

    # Check model produces diverse predictions
    predictions = predict_sample_inputs(result.model)
    assert len(set(predictions)) > 1, "Model collapsed"
```

### 3. Environment Abstraction
```python
class E2EEnvironment:
    """Abstract away environment differences."""

    def __init__(self):
        self.env = detect_environment()  # main, sandbox-1, sandbox-2
        self.api_port = get_api_port(self.env)
        self.data_dir = get_data_dir(self.env)

    def api_url(self, endpoint):
        return f"http://localhost:{self.api_port}/api/v1/{endpoint}"

    def ensure_healthy(self):
        if not self.docker_healthy():
            self.restart_docker()
```

### 4. Diagnostic Output
```python
def run_e2e_test(strategy):
    """E2E test with rich diagnostics."""

    # Capture all intermediate state
    diagnostics = {
        "label_distribution": None,
        "training_loss_history": [],
        "model_predictions_sample": None,
        "trade_signals": [],
    }

    try:
        # ... run test ...
    except Exception as e:
        # Dump diagnostics for debugging
        save_diagnostics(diagnostics, f"failed_test_{timestamp}.json")
        raise
```

---

## Summary of Root Causes

| Issue | Appeared As | Actually Was |
|-------|-------------|--------------|
| 0 trades | Code bug | Strategy config (zigzag too high) |
| NaN training | Code bug | Docker environment issue |
| API failures | Code bug | Schema differences between endpoints |
| Data not found | Code bug | Wrong data directory path |
| 100% accuracy | Success | Model collapse (class imbalance) |

---

## Key Takeaways

1. **Validate data before blaming code** - Check label distribution, data availability, and configuration first.

2. **Environment matters** - Docker health, port numbers, and data paths can all cause "code bugs" that aren't.

3. **100% accuracy is a red flag** - In classification problems, perfect accuracy usually indicates a problem (class imbalance, data leakage, or trivial task).

4. **Fast feedback loops are essential** - Pre-flight checks and quick smoke tests can catch issues in seconds instead of minutes.

5. **Diagnostic output is critical** - When tests fail, having label distributions, loss histories, and sample predictions makes debugging much faster.

---

## Next Steps

Use this analysis to design a comprehensive E2E testing framework that:
- Runs pre-flight checks before each test
- Provides fast smoke tests for quick validation
- Abstracts environment differences
- Captures rich diagnostics on failure
- Validates data quality, not just code correctness
