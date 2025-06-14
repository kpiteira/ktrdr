# Exhaustive IB Resilience Testing - Quick Reference

## 🚀 Quick Start (When IB Servers Are Back Online)

### 1. Prerequisites Check
```bash
cd tests/e2e_real
uv run python run_exhaustive_tests.py --test-level basic
```
**Expected Output**: 
- ✅ API server: running
- ⚠️ IB Gateway: not connected (will change to ✅ when IB is up)
- ✅ Backend container: running  
- ✅ Test environment: ready

### 2. Standard Testing (Recommended)
```bash
cd tests/e2e_real
uv run python run_exhaustive_tests.py --test-level standard --report
```
**This runs**: All resilience tests with real IB connections

### 3. Maximum Confidence Testing
```bash
cd tests/e2e_real
uv run python run_exhaustive_tests.py --test-level exhaustive --report --verbose
```
**This runs**: Full stress testing, memory leak detection, concurrent load testing

## 📋 What the Tests Validate

### ✅ Critical Success Criteria
- **Zero async/coroutine errors** (the original bug is fixed)
- **Resilience score ≥ 75/100** with IB connected
- **All 6 phases working** (validation, garbage collection, client ID preference)
- **Silent connection detection** working (hanging connections caught)
- **Memory stability** under stress
- **Connection pool integrity** maintained

### ❌ Critical Failure Indicators
- **Async/coroutine errors**: `RuntimeWarning: coroutine was never awaited`
- **Silent connection bugs**: Operations hanging without timeout
- **Connection pool failures**: Memory leaks or exhaustion
- **Low resilience score**: < 65/100

## 🔧 Manual Test Commands (Alternative)

### Core Resilience Validation
```bash
# Test all 6 phases with real IB
pytest tests/e2e_real/test_exhaustive_resilience.py -v --real-ib

# Test specific phases
pytest tests/e2e_real/test_exhaustive_resilience.py::TestPhase1SystematicValidationExhaustive -v --real-ib
pytest tests/e2e_real/test_exhaustive_resilience.py::TestPhase2GarbageCollectionExhaustive -v --real-ib
pytest tests/e2e_real/test_exhaustive_resilience.py::TestPhase3ClientIdPreferenceExhaustive -v --real-ib
```

### API/CLI Integration Testing
```bash
# API resilience under load
pytest tests/e2e_real/test_exhaustive_api_cli_resilience.py::TestAPIResilienceUnderRealLoad -v --real-ib

# CLI command resilience (critical for async error detection)
pytest tests/e2e_real/test_exhaustive_api_cli_resilience.py::TestCLIResilienceUnderRealLoad -v --real-ib
```

### Infrastructure Tests (No IB Required)
```bash
# Test resilience infrastructure without IB
pytest tests/e2e/test_connection_resilience_e2e.py -v
pytest tests/e2e/test_resilience_scenarios.py -v
```

## 📊 Checking Results

### Resilience Score Check
```bash
curl -s "http://localhost:8000/api/v1/ib/resilience" | jq '.data.overall_resilience_score'
# Should return: 100.0 (with IB connected) or 65+ (without IB)
```

### Phase Status Check
```bash
curl -s "http://localhost:8000/api/v1/ib/resilience" | jq '.data | {
  phase1: .phase_1_systematic_validation.status,
  phase2: .phase_2_garbage_collection.status,
  phase3: .phase_3_client_id_preference.status
}'
# Should return: {"phase1": "working", "phase2": "working", "phase3": "working"}
```

### Health Check
```bash
curl -s "http://localhost:8000/api/v1/ib/health" | jq '.data.healthy'
# Should return: true (with IB) or false (without IB, but graceful)
```

## 🎯 Expected Test Outcomes

### With IB Gateway Connected
- **Resilience Score**: 100/100
- **All Tests**: Should pass
- **Test Duration**: 5-15 minutes for standard, 30+ minutes for exhaustive
- **Connection Pool**: Active connections visible in metrics

### Without IB Gateway (Current State)
- **Resilience Score**: 65-75/100 (infrastructure points)
- **Graceful Handling**: Tests validate proper error handling
- **Test Duration**: 2-5 minutes
- **Expected Behavior**: System handles IB unavailability gracefully

## 🔍 If Tests Fail

### Check for Async Errors (Critical)
```bash
# Check recent logs for async/coroutine errors
grep -r "RuntimeWarning" logs/ | tail -10
grep -r "coroutine.*never awaited" logs/ | tail -10
```

### Check Resilience Status
```bash
# Get detailed resilience breakdown
curl -s "http://localhost:8000/api/v1/ib/resilience" | jq '.data'
```

### Check Connection Pool Health
```bash
# Get connection pool metrics
curl -s "http://localhost:8000/api/v1/ib/resilience" | jq '.data.connection_pool_health'
```

## 🚨 Critical Test Files

If you need to reference specific tests:

### Primary Test Suites
- `tests/e2e_real/test_exhaustive_resilience.py` - Core resilience validation
- `tests/e2e_real/test_exhaustive_api_cli_resilience.py` - API/CLI integration
- `tests/e2e_real/run_exhaustive_tests.py` - Automated test runner

### Test Documentation
- `tests/e2e_real/README.md` - Complete testing guide
- `docs/ib-connection-resilience-implementation.md` - Full implementation context

## 📞 Quick Context Summary

**Problem Solved**: IB Gateway "silent connections" where TCP connects but operations hang
**Solution**: 6-phase connection resilience with systematic validation
**Key Fix**: `isConnected()` + `reqCurrentTime()` validation before every connection handoff
**Critical Test**: Zero `RuntimeWarning: coroutine was never awaited` errors
**Production Ready**: When tests pass with 75+ resilience score

## 🎉 Success Confirmation

When you see this output from the test runner:
```
🎉 RESILIENCE VALIDATION SUCCESSFUL!
Your IB connection implementation is bulletproof.
✅ No async/coroutine errors detected
✅ Resilience score: 100/100
✅ All 6 phases working
```

**You can deploy to production with complete confidence.**

---

*This quick reference provides everything needed to run and validate the exhaustive resilience testing when IB servers are back online.*