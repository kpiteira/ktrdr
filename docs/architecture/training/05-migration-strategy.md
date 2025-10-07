# Training Architecture Migration Strategy

## Overview

This document outlines the progressive migration strategy from the current StrategyTrainer implementation to the unified training architecture. The strategy follows the **Strangler Fig Pattern** - gradually replacing legacy code while maintaining full system functionality and rollback capability at every step.

**Key Principle**: Never break what works. Build alongside, validate thoroughly, switch gradually with feature flags, maintain rollback capability.

## Migration Philosophy

### The "Big Bang" Anti-Pattern

❌ **What NOT to do**:
```
Current Code → [Delete Everything] → [Rewrite Everything] → Hope it works
```

This leads to:
- Weeks of broken functionality
- Loss of battle-tested patterns
- Difficult debugging (too many changes at once)
- No rollback capability
- Massive waste of time on piecemeal fixes

✅ **What TO do**:
```
Current Code → [Add New Alongside] → [Validate] → [Gradual Rollout 0%→10%→50%→100%] → [Remove Old]
```

This provides:
- Always-working system
- Incremental validation
- Easy rollback at any point
- Clear quality gates
- Battle-tested patterns preserved

## Three-Phase Migration

### Phase 1: Foundation (Add Alongside)

**Goal**: New implementation exists alongside old, fully validated but not used in production.

**Duration**: 2-3 weeks

**Activities**:

1. **Create New Modules** (without touching existing code):
   ```
   ktrdr/training/
   ├── executor.py                    # NEW - TrainingExecutor
   ├── execution_mode_selector.py     # NEW - Mode selection logic
   ├── progress_bridge.py             # NEW - Unified progress handling
   ├── train_strategy.py              # UNTOUCHED - Legacy StrategyTrainer
   └── model_trainer.py               # UNTOUCHED - Battle-tested core
   ```

2. **Environment Variable Control**:
   ```python
   USE_UNIFIED_TRAINING = os.getenv("USE_UNIFIED_TRAINING", "false").lower() == "true"

   if USE_UNIFIED_TRAINING:
       executor = TrainingExecutor(...)
       result = executor.execute(...)
   else:
       trainer = StrategyTrainer(...)
       result = trainer.train_multi_symbol_strategy(...)
   ```

3. **Comprehensive Testing**:
   - Unit tests for all new modules (>90% coverage)
   - Integration tests against host service
   - Side-by-side validation: run both old and new, compare results
   - Performance benchmarks: ensure new ≥ old performance

4. **Quality Gates for Phase 1 → Phase 2**:
   - ✅ All unit tests pass (new modules)
   - ✅ All integration tests pass (new modules)
   - ✅ Side-by-side validation shows equivalent results
   - ✅ Performance benchmarks meet targets
   - ✅ Manual testing with `USE_UNIFIED_TRAINING=true` succeeds
   - ✅ All existing tests still pass (regression check)

**Rollback**: Simply don't set `USE_UNIFIED_TRAINING=true`. Zero risk.

---

### Phase 2: Gradual Rollout (Controlled Production Use)

**Goal**: Progressively increase production traffic to new implementation while monitoring for issues.

**Duration**: 3-4 weeks (careful, deliberate)

**Rollout Stages**:

#### Stage 2.1: Canary (10% traffic)

**Who**: Internal development team only
**Duration**: 1 week
**Configuration**:
```python
UNIFIED_TRAINING_ROLLOUT_PERCENTAGE = 10
USE_UNIFIED_TRAINING = True  # Enable feature flag system

def should_use_unified_training(user_id: str) -> bool:
    """Deterministic selection based on user ID hash."""
    if not USE_UNIFIED_TRAINING:
        return False

    # Hash user ID to get deterministic 0-100 value
    hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
    return hash_val < UNIFIED_TRAINING_ROLLOUT_PERCENTAGE
```

**Monitoring**:
- Error rates: new vs old implementation
- Training completion times
- Progress reporting accuracy
- Cancellation latency
- Resource usage (CPU/GPU/memory)

**Quality Gates for 2.1 → 2.2**:
- ✅ Error rate < 1% for new implementation
- ✅ Performance within 10% of old implementation
- ✅ No critical bugs reported
- ✅ All monitoring metrics green for 1 week
- ✅ Manual spot-checks confirm correct behavior

**Rollback**: Set `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0`

#### Stage 2.2: Expanded Testing (50% traffic)

**Who**: Internal + selected power users
**Duration**: 2 weeks
**Configuration**: `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE = 50`

**Additional Monitoring**:
- User feedback on progress visibility
- Edge case handling (large models, many symbols, long date ranges)
- Cancellation behavior under load
- Host service stability

**Quality Gates for 2.2 → 2.3**:
- ✅ Error rate < 0.5% for new implementation
- ✅ Performance equivalent to old implementation
- ✅ Positive user feedback
- ✅ All edge cases handled correctly
- ✅ No regressions in existing functionality
- ✅ Cancellation works reliably (<100ms latency)

**Rollback**: Set `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0`

#### Stage 2.3: Full Rollout (100% traffic)

**Who**: All users
**Duration**: 1 week observation
**Configuration**: `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE = 100`

**Monitoring**:
- Same as Stage 2.2 but at full scale
- Watch for any edge cases that only appear at scale

**Quality Gates for 2.3 → Phase 3**:
- ✅ Error rate < 0.1% (better or equal to legacy)
- ✅ Performance meets or exceeds legacy
- ✅ All monitoring green for 1 week
- ✅ Zero critical bugs
- ✅ Confidence to remove legacy code

**Rollback**: Set `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0` (still possible but increasingly costly)

---

### Phase 3: Cleanup (Remove Legacy)

**Goal**: Remove legacy code, simplify codebase, finalize unified architecture.

**Duration**: 1 week

**Activities**:

1. **Remove Feature Flags**:
   ```python
   # Delete this entire block:
   if USE_UNIFIED_TRAINING:
       executor = TrainingExecutor(...)
   else:
       trainer = StrategyTrainer(...)  # DELETE

   # Keep only:
   executor = TrainingExecutor(...)
   result = executor.execute(...)
   ```

2. **Remove Legacy Files**:
   ```
   ktrdr/training/
   ├── train_strategy.py              # DELETE (StrategyTrainer class)
   ├── executor.py                    # KEEP
   ├── execution_mode_selector.py     # KEEP
   ├── progress_bridge.py             # KEEP
   └── model_trainer.py               # KEEP (battle-tested core)
   ```

3. **Update Documentation**:
   - Remove migration-specific docs
   - Update architecture diagrams
   - Finalize API documentation
   - Update deployment guides

4. **Final Validation**:
   - Full test suite passes
   - No references to legacy code remain
   - Documentation reflects current state
   - Performance benchmarks still meet targets

**Rollback**:
- **BEFORE removing code**: Git revert is trivial
- **AFTER removing code**: Git revert still works but requires more testing
- **Best Practice**: Tag the commit before Phase 3 as `pre-cleanup-rollback-point`

---

## Rollback Procedures

### Quick Rollback (Production Issue)

**Severity**: Critical bug in production

**Steps**:
1. Set environment variable: `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0`
2. Restart affected services (no code deployment needed)
3. Monitor error rates return to normal
4. Investigate issue in staging environment

**Time to Rollback**: < 5 minutes

**Example**:
```bash
# In production environment
export UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0
systemctl restart ktrdr-api
systemctl restart training-host-service

# Verify rollback
curl http://localhost:8000/api/v1/health
```

### Partial Rollback (Specific Users)

**Severity**: Issue affecting subset of users

**Steps**:
1. Identify affected users by ID
2. Add to rollback exclusion list:
   ```python
   ROLLBACK_USER_IDS = ["user123", "user456"]

   def should_use_unified_training(user_id: str) -> bool:
       if user_id in ROLLBACK_USER_IDS:
           return False  # Force legacy for these users
       # ... normal rollout logic
   ```
3. Deploy updated exclusion list
4. Notify affected users

**Time to Rollback**: < 15 minutes

### Full Rollback (Architectural Issue)

**Severity**: Fundamental design flaw discovered

**Steps**:
1. **Immediate**: Set `UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=0`
2. **Short-term**: Set `USE_UNIFIED_TRAINING=false`
3. **Medium-term**:
   - Document issue thoroughly
   - Update architecture docs with learnings
   - Create new implementation plan
   - Re-enter Phase 1 when ready
4. **Long-term**: Remove new code if abandoning approach

**Time to Rollback**: < 30 minutes (production stable), days-weeks (fix and retry)

---

## Feature Flag Implementation

### Environment Variables

```bash
# Phase 1: Foundation
USE_UNIFIED_TRAINING=false              # Default: new code exists but not used

# Phase 2: Gradual Rollout
USE_UNIFIED_TRAINING=true               # Enable feature flag system
UNIFIED_TRAINING_ROLLOUT_PERCENTAGE=10  # Start at 10%

# Phase 3: Cleanup
# (Remove environment variables, hardcode new implementation)
```

### Code Pattern

```python
# ktrdr/training/training_manager.py

import os
import hashlib
from typing import Optional

class TrainingManager:
    def __init__(self):
        self.use_unified = os.getenv("USE_UNIFIED_TRAINING", "false").lower() == "true"
        self.rollout_pct = int(os.getenv("UNIFIED_TRAINING_ROLLOUT_PERCENTAGE", "0"))

    def _should_use_unified(self, user_id: Optional[str] = None) -> bool:
        """Determine if this request should use unified training."""
        if not self.use_unified:
            return False

        if self.rollout_pct >= 100:
            return True

        if self.rollout_pct <= 0:
            return False

        if user_id is None:
            user_id = "default"

        # Deterministic hash-based selection
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
        return hash_val < self.rollout_pct

    async def train_strategy(self, user_id: str, **kwargs):
        """Route to unified or legacy implementation."""
        if self._should_use_unified(user_id):
            logger.info(f"Using unified training for user {user_id}")
            return await self._train_unified(**kwargs)
        else:
            logger.info(f"Using legacy training for user {user_id}")
            return await self._train_legacy(**kwargs)
```

---

## Monitoring and Metrics

### Key Metrics to Track

#### Performance Metrics
- **Training Duration**: Total time to complete training
  - Target: Within 10% of legacy implementation
  - Alert: >20% slower than legacy

- **Resource Usage**: CPU/GPU/Memory utilization
  - Target: Equivalent to legacy
  - Alert: >30% increase in resource usage

- **Progress Update Latency**: Time between progress updates
  - Target: ~300ms intervals
  - Alert: >1s intervals or <100ms (too slow or too fast)

#### Reliability Metrics
- **Error Rate**: Training failures / total training requests
  - Target: <0.1% (equivalent to legacy)
  - Alert: >1% error rate

- **Cancellation Latency**: Time from cancel request to actual stop
  - Target: <100ms
  - Alert: >500ms

- **Host Service Uptime**: Availability of training host service
  - Target: 99.9%
  - Alert: <99.5%

#### Quality Metrics
- **Model Accuracy**: Validation loss/accuracy
  - Target: Equivalent to legacy (within 1%)
  - Alert: >5% degradation

- **Progress Accuracy**: Reported progress vs actual progress
  - Target: ±1% accuracy
  - Alert: >5% deviation

### Monitoring Dashboard

```python
# Example Prometheus metrics

from prometheus_client import Counter, Histogram, Gauge

# Training requests
training_requests_total = Counter(
    'training_requests_total',
    'Total training requests',
    ['implementation', 'status']
)

# Training duration
training_duration_seconds = Histogram(
    'training_duration_seconds',
    'Training duration in seconds',
    ['implementation']
)

# Active training sessions
active_training_sessions = Gauge(
    'active_training_sessions',
    'Number of active training sessions',
    ['implementation']
)

# Progress update intervals
progress_update_interval_seconds = Histogram(
    'progress_update_interval_seconds',
    'Time between progress updates',
    ['implementation']
)

# Cancellation latency
cancellation_latency_seconds = Histogram(
    'cancellation_latency_seconds',
    'Time from cancel request to actual stop',
    ['implementation']
)
```

### Alerting Rules

```yaml
# Example Prometheus alerting rules

groups:
  - name: training_migration
    interval: 1m
    rules:
      # Error rate too high
      - alert: UnifiedTrainingHighErrorRate
        expr: |
          rate(training_requests_total{implementation="unified",status="error"}[5m])
          /
          rate(training_requests_total{implementation="unified"}[5m])
          > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Unified training error rate >1%"
          description: "Consider rolling back unified training"

      # Performance degradation
      - alert: UnifiedTrainingSlowPerformance
        expr: |
          avg(training_duration_seconds{implementation="unified"})
          /
          avg(training_duration_seconds{implementation="legacy"})
          > 1.2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Unified training >20% slower than legacy"

      # Cancellation latency too high
      - alert: UnifiedTrainingSlowCancellation
        expr: |
          histogram_quantile(0.95,
            rate(cancellation_latency_seconds_bucket{implementation="unified"}[5m])
          ) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile cancellation latency >500ms"
```

---

## Risk Mitigation Strategies

### Risk 1: Event Loop Blocking

**Symptom**: Host service appears hung, status checks timeout

**Mitigation**:
- Always use `asyncio.to_thread()` for CPU-bound work
- Add monitoring for event loop lag
- Test under load during Phase 1

**Detection**:
```python
# Add to host service
import asyncio
import time

async def monitor_event_loop_lag():
    """Alert if event loop is blocked."""
    while True:
        start = time.time()
        await asyncio.sleep(0)  # Should be instant
        lag = time.time() - start
        if lag > 0.1:  # >100ms lag
            logger.warning(f"Event loop lag: {lag*1000:.0f}ms")
        await asyncio.sleep(1)
```

### Risk 2: Progress Callback Signature Mismatch

**Symptom**: `TypeError: takes 2 positional arguments but 3 were given`

**Mitigation**:
- Preserve exact ModelTrainer callback signature: `(epoch, total_epochs, metrics)`
- No adapter wrappers that change signatures
- Add type hints and runtime validation

**Prevention**:
```python
# Type hints enforce contract
ProgressCallbackType = Callable[[int, int, Dict[str, float]], None]

def execute(
    self,
    progress_callback: Optional[ProgressCallbackType] = None,
    **kwargs
) -> dict:
    # Pass through unchanged
    trainer = ModelTrainer(
        ...,
        progress_callback=progress_callback,  # Direct pass-through
    )
```

### Risk 3: Progress Flooding

**Symptom**: Thousands of log entries per second

**Mitigation**:
- Adaptive throttling (target ~300ms intervals)
- Time-based instead of fixed-stride
- Test with large datasets during Phase 1

**Implementation**:
```python
# Already implemented in architecture
batch_stride = [10]  # Mutable to update in closure
target_interval = 0.3  # 300ms

if time_since_last < target_interval * 0.5:
    batch_stride[0] = min(batch_stride[0] * 2, 100)  # Too fast
elif time_since_last > target_interval * 1.5:
    batch_stride[0] = max(batch_stride[0] // 2, 1)  # Too slow
```

### Risk 4: Cancellation Not Working

**Symptom**: Training continues after cancel request

**Mitigation**:
- Check cancellation token every batch (latency <100ms)
- Implement all CancellationToken protocol methods
- Test cancellation thoroughly during Phase 1

**Quality Gate**:
```python
# Integration test
async def test_cancellation_latency():
    """Ensure cancellation latency <100ms."""
    token = create_cancellation_token()

    # Start training
    task = asyncio.create_task(executor.execute(..., cancellation_token=token))
    await asyncio.sleep(1)  # Let it start

    # Cancel and measure latency
    start = time.time()
    token.cancel()

    try:
        await asyncio.wait_for(task, timeout=1.0)
    except CancellationError:
        latency = time.time() - start
        assert latency < 0.1, f"Cancellation took {latency*1000:.0f}ms (target <100ms)"
```

### Risk 5: Strategy Path Mismatch

**Symptom**: `No such file or directory: /app/strategies/...`

**Mitigation**:
- Pass strategy name only (not full path)
- Host service resolves to local filesystem
- Document path resolution logic

**Fix**:
```python
# Backend (Docker) - send name only
response = await adapter.train_multi_symbol_strategy(
    strategy_config_path="neuro_mean_reversion",  # Just name
    ...
)

# Host service (Mac) - resolve to local path
strategy_path = f"/Users/user/strategies/{strategy_config_path}.yaml"
```

### Risk 6: Loss of Battle-Tested Patterns

**Symptom**: Issues that didn't exist before (e.g., device mismatch, broken pipe)

**Mitigation**:
- Preserve ModelTrainer completely (no changes)
- Extract patterns from StrategyTrainer, don't rewrite
- Side-by-side validation in Phase 1

**Quality Gate**:
```python
# Side-by-side validation test
async def test_equivalent_results():
    """Ensure new implementation produces same results as legacy."""
    params = {...}  # Same parameters

    # Run both implementations
    legacy_result = await legacy_trainer.train(**params)
    unified_result = await unified_executor.execute(**params)

    # Compare outputs
    assert abs(legacy_result['val_loss'] - unified_result['val_loss']) < 0.01
    assert abs(legacy_result['val_accuracy'] - unified_result['val_accuracy']) < 0.01
```

---

## Communication Plan

### Phase 1: Foundation
- **Week 0**: Announce migration project, share architecture docs
- **Week 1-2**: Weekly updates on development progress
- **Week 3**: Demo new implementation to team (with `USE_UNIFIED_TRAINING=true`)

### Phase 2: Gradual Rollout
- **Stage 2.1 (10%)**:
  - Announce canary rollout to dev team
  - Daily monitoring reports
  - Request feedback on any issues

- **Stage 2.2 (50%)**:
  - Announce expanded rollout
  - Weekly updates with metrics
  - User feedback survey

- **Stage 2.3 (100%)**:
  - Announce full rollout
  - Daily monitoring for first 3 days
  - Weekly updates until stable

### Phase 3: Cleanup
- **Week 1**: Announce legacy code removal
- **Week 2**: Final documentation updates, close migration project

---

## Success Criteria

### Technical Success
- ✅ All tests pass (unit, integration, e2e)
- ✅ Performance equivalent or better than legacy
- ✅ Error rate <0.1% (equivalent to legacy)
- ✅ Zero regressions in existing functionality
- ✅ Cancellation latency <100ms
- ✅ Progress updates at ~300ms intervals
- ✅ Clean separation of concerns (Progress vs Logging)
- ✅ Battle-tested patterns preserved

### Process Success
- ✅ Zero production outages during migration
- ✅ Rollback capability maintained at all times
- ✅ Clear quality gates passed before each stage
- ✅ Comprehensive monitoring and alerting in place
- ✅ Documentation updated and accurate

### Team Success
- ✅ Positive developer feedback on new architecture
- ✅ Reduced debugging time (clearer separation of concerns)
- ✅ Easier to add new execution modes (cloud, etc.)
- ✅ Maintainable, understandable codebase
- ✅ Learnings documented for future migrations

---

## Timeline Summary

| Phase | Duration | Key Activities | Rollback |
|-------|----------|----------------|----------|
| **Phase 1: Foundation** | 2-3 weeks | Build new modules, validate thoroughly | Zero risk |
| **Phase 2.1: Canary (10%)** | 1 week | Internal testing, monitoring | `ROLLOUT_PERCENTAGE=0` |
| **Phase 2.2: Expanded (50%)** | 2 weeks | Broader rollout, edge case testing | `ROLLOUT_PERCENTAGE=0` |
| **Phase 2.3: Full (100%)** | 1 week | Full production use, observation | `ROLLOUT_PERCENTAGE=0` |
| **Phase 3: Cleanup** | 1 week | Remove legacy code | Git revert |
| **Total** | **7-9 weeks** | Progressive, safe migration | Always possible |

---

## Lessons Learned (From Failed Big-Bang Attempt)

### What Went Wrong

1. **Changed everything at once**: Impossible to isolate issues
2. **Ignored battle-tested patterns**: Introduced bugs that didn't exist before
3. **No incremental validation**: Issues discovered too late
4. **Conflated Progress and Logging**: Fundamental misunderstanding
5. **Missing architecture details**: Threading model, interface contracts unclear
6. **No rollback plan**: Only option was to abandon branch

### What to Do Differently

1. **Progressive changes**: One module at a time, validate each
2. **Preserve working patterns**: Extract, don't rewrite
3. **Continuous validation**: Side-by-side testing throughout
4. **Clear architectural docs**: Include threading, interfaces, pitfalls
5. **Feature flags from day 1**: Always have rollback capability
6. **Quality gates**: Don't proceed until validated

### Key Insight

> "The 'sin' was doing everything in one big swoop, instead of progressive changes. We should design a plan that goes progressively from one to the other smoothly."

This migration strategy embodies that insight: **build alongside, validate thoroughly, switch gradually, maintain rollback capability**.

---

## Conclusion

This migration strategy prioritizes **safety and reliability** over speed. The gradual rollout approach ensures:

- ✅ Production system always works
- ✅ Easy rollback at any point
- ✅ Issues discovered early (canary testing)
- ✅ Clear quality gates before proceeding
- ✅ Battle-tested patterns preserved
- ✅ Team confidence in new architecture

**Total timeline: 7-9 weeks**

This may seem slow, but compared to a failed big-bang approach requiring weeks of debugging and potential branch abandonment, it's far more efficient and lower risk.

**Remember**: You're not just migrating code, you're migrating production systems that people depend on. Do it right, do it safely, do it progressively.
