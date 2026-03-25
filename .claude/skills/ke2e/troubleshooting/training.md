# Troubleshooting: Training

Common training test failures and their solutions.

---

## Model Collapse (100% Accuracy)

**Symptom:**
- Training completes "successfully"
- Accuracy is 100% or very high (>99%)
- Loss is very low (<0.001)
- Model predicts same class for all inputs

**Cause:** Class imbalance in training data. Typically because:
- Zigzag threshold too high for asset volatility
- Date range has no significant price movements
- Wrong labeling configuration

**Diagnosis Steps:**
```bash
# Check what the model predicts
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.training_metrics'

# If accuracy is 100%, check label distribution
# (Requires checking training logs or re-running with verbose)
```

**Solution:**
1. For forex (EURUSD, GBPUSD, etc.): Use 0.5% zigzag, not 2.5%
2. For stocks: 2.5% zigzag is usually fine
3. Extend date range to capture more price movement

**Prevention:**
- Always check label distribution before training
- Sanity check: accuracy < 99%

---

## 0 Trades in Backtest

**Symptom:**
- Backtest completes
- Trade count is 0
- All predictions are HOLD

**Cause:** Model collapse (see above) caused model to never predict BUY/SELL.

**Diagnosis Steps:**
```bash
# Check backtest results
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | \
  jq '.data.result_summary.trade_count'
```

**Solution:** Fix the underlying model collapse issue, retrain.

---

## NaN in Training Metrics

**Symptom:**
- Training metrics show NaN values
- Loss is NaN
- Accuracy is NaN or 0

**Cause:** Usually numerical instability:
- Learning rate too high
- Data has NaN values
- Normalization issue

**Diagnosis Steps:**
```bash
# Check for NaN in data
docker compose logs backend --since 5m | grep -i "nan\|inf"
```

**Solution:**
1. Check data for NaN values
2. Try lower learning rate
3. Check normalization in strategy config

---

## Training Timeout

**Symptom:**
- Training doesn't complete within expected time
- Status stays "running" indefinitely

**Cause:**
- Dataset too large
- Worker overwhelmed
- Deadlock in training loop

**Diagnosis Steps:**
```bash
# Check training progress
curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TASK_ID" | jq '.data.progress'

# Check worker health
curl -s http://localhost:5002/health

# Check for errors
docker compose logs backend --since 10m | grep -i "error\|timeout"
```

**Solution:**
1. Cancel stuck operation: `DELETE /api/v1/operations/$TASK_ID`
2. Use smaller dataset for testing
3. Restart training worker if stuck

---

## Strategy File Not Found

**Symptom:**
- Training fails immediately
- Error: "Strategy file not found: {name}.yaml"

**Cause:** Strategy file not in expected location.

**Diagnosis Steps:**
```bash
# Check strategy exists
ls ~/.ktrdr/shared/strategies/{strategy_name}.yaml

# Check mounted in Docker
docker compose exec backend ls /app/strategies/
```

**Solution:**
1. Copy strategy to `~/.ktrdr/shared/strategies/`
2. Verify Docker volume mount is correct
