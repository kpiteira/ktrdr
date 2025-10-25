# Training Metrics Exposure: Implementation Plan

**Date**: 2025-01-17
**Status**: Implementation Planning
**Related**: [Problem Statement](./01-problem-statement.md), [Design](./02-design.md), [Architecture](./03-architecture.md)

---

## Branch Strategy

**Branch Name**: `feature/training-metrics-exposure`

**Commit Strategy**:
- Commit after each milestone (4 commits total)
- Each milestone must be testable end-to-end
- Run full test suite + quality checks before committing

---

## Overview

This implementation follows an **API-first approach**: build the complete interface first (returning stub/empty data), then progressively "light up" functionality. This allows validation at every step using the same agent scripts.

### Milestones

| Milestone | Delivers | What Changes | Validation |
|-----------|----------|--------------|------------|
| **M1: API Contract** | Complete interface | API endpoints, MCP client, agents created | Agent scripts run, show empty data |
| **M2: Local Training** | Metrics from local training | API returns real data for Docker training | Same agents show real metrics |
| **M3: Host Service** | Metrics from GPU training | Works for host service mode | Same agents work with GPU |
| **M4: Polish** | Production ready | Documentation, performance tested | Full validation |

**Key Benefit**: Run the same agent script in every milestone and watch it progressively show more data.

---

## Milestone 1: API Contract (Interface First)

### Goal

Build the complete API contract and client integration BEFORE implementing any metrics collection. Everything compiles and runs, but returns empty/stub data.

### What Gets Built

**Data Layer**:
- Add `metrics: Optional[dict]` field to Operation model
- Database migration to add metrics column (nullable)
- Field remains null/empty until M2

**API Layer**:

- GET `/operations/{id}/metrics` - returns empty metrics structure:

  ```json
  {
    "success": true,
    "data": {
      "operation_id": "op-123",
      "operation_type": "training",
      "metrics": {}
    }
  }
  ```

- POST `/operations/{id}/metrics` - accepts payload, validates structure, logs but doesn't store
- Both endpoints have proper error handling (404 for missing operation, etc.)

**Client Layer**:

- MCP client method `get_operation_metrics(operation_id)` that:
  - Makes GET request to `/operations/{id}/metrics`
  - Parses and returns response
  - Handles errors (connection, 404, etc.)

**Agent Layer**:

- `examples/agents/training_monitor.py` - Real-time monitoring agent that:
  - Polls metrics API every 30 seconds
  - Displays epoch progress, detects issues (overfitting, plateaus)
  - Handles empty metrics gracefully (shows "waiting for data")

- `examples/agents/loss_analyzer.py` - Trend analysis agent that:
  - Fetches complete metrics history
  - Analyzes loss trajectories, identifies best epoch
  - Provides recommendations (continue, stop, use checkpoint)
  - Handles insufficient data gracefully

**Testing**:
- Unit tests for all endpoints and client methods
- Integration test: agent → MCP → API → database
- Tests verify structure, not data (since empty)

### Why This Milestone

Establishes the complete interface contract. Once this works, M2 and M3 just "fill in" the data without changing the interface. You can run agent scripts from day 1 and watch them evolve.

### Acceptance Criteria

**Functional**:
- [ ] Can query GET `/operations/{id}/metrics` via cURL, returns 200 with empty metrics
- [ ] Can POST to `/operations/{id}/metrics`, returns 200 (but doesn't store)
- [ ] MCP client can call API successfully
- [ ] Agent scripts run without errors, display "No metrics yet" message
- [ ] Swagger UI shows new endpoints with descriptions

**Technical**:
- [ ] All unit tests pass (`make test-unit`)
- [ ] All quality checks pass (`make quality`)
- [ ] Database migration runs cleanly
- [ ] No breaking changes to existing operations

**User Validation**:

Start any training operation and capture its operation ID. Then:

1. **Test API directly**: Use cURL or Swagger UI to query `GET /operations/{id}/metrics`. Should return 200 with empty metrics structure.

2. **Test MCP client**: Write a simple Python script that imports the MCP client and calls `get_operation_metrics()`. Should return the same structure as the API.

3. **Run agent scripts**: Execute the monitoring and analyzer agent scripts with the operation ID. They should run without crashing, display a message indicating no metrics are available yet, and show the response structure they received.

All three layers (API, MCP, agents) should work end-to-end even with empty data.

### Risks & Decisions

**Risk**: Database migration conflicts with existing operations
**Mitigation**: Add column as nullable, existing operations unaffected

**Decision**: POST endpoint accepts but doesn't store
**Rationale**: Validates payload structure, makes M2 easier (just add storage logic)

### Commit Message

```text
feat(training): add complete metrics API contract + MCP client + agents

API-first approach: Build complete interface before implementation.

Added:
- Operation.metrics field (nullable, database migration)
- GET /operations/{id}/metrics (returns empty until M2)
- POST /operations/{id}/metrics (validates, doesn't store until M2)
- MCP client method get_operation_metrics()
- Agent scripts: training_monitor.py, loss_analyzer.py

M1 complete: Interface in place, agents work with empty data.
M2 will "light up" same endpoints with real data.

Validation: python examples/agents/training_monitor.py {op_id}
Tests: make test-unit && make quality
```

---

## Milestone 2: Light Up Local Training

### Goal

Make the API return REAL metrics when training locally. The agent scripts you ran in M1 now show actual data without any code changes!

### What Gets Built

**Metrics Collection**:

- ModelTrainer emits full epoch metrics in progress callback
- Each epoch includes: train_loss, val_loss, train_accuracy, val_accuracy, learning_rate, duration, timestamp
- Added to existing progress callback payload as `"full_metrics"` key (backward compatible)

**Metrics Storage**:

- OperationsService gains `add_metrics(operation_id, metrics_data)` method that:
  - Validates operation exists
  - Routes by operation type (training vs others)
  - Stores epoch data in Operation.metrics field
  - Computes trend indicators: best_epoch, is_overfitting, is_plateaued
  - Persists to database asynchronously (non-blocking)

**Metrics Flow**:

- TrainingProgressBridge receives progress callback with metrics
- Extracts `"full_metrics"` and forwards to OperationsService via callback
- LocalTrainingOrchestrator creates and wires the callback

**API Changes**:

- POST `/operations/{id}/metrics` now stores data (was validation-only in M1)
- GET `/operations/{id}/metrics` returns populated data structure:

  ```json
  {
    "metrics": {
      "epochs": [{...}, {...}],
      "best_epoch": 7,
      "best_val_loss": 0.4123,
      "is_overfitting": false,
      "is_plateaued": false
    }
  }
  ```

**Testing**:
- Unit tests for metrics emission, storage, trend analysis
- Integration test: full 10-epoch training, verify all metrics stored
- Trend analysis tests: overfitting, plateau, best epoch detection

### Why This Milestone

Local training is simpler (no HTTP layer), easier to debug. Validates core metrics logic before adding host service complexity.

### Acceptance Criteria

**Functional**:
- [ ] Train 10 epochs locally, all epochs appear in metrics
- [ ] Each epoch has: train_loss, val_loss, accuracy, learning_rate, duration, timestamp
- [ ] Trend analysis computed correctly: best_epoch, epochs_since_improvement
- [ ] Overfitting detection works (synthetic test with diverging losses)
- [ ] Plateau detection works (synthetic test with flat losses)

**Technical**:
- [ ] All unit tests pass
- [ ] Integration test passes (10-epoch training)
- [ ] All quality checks pass
- [ ] No performance degradation vs baseline training
- [ ] Metrics storage < 50KB for 100 epochs

**User Validation**:

Train locally for 10 epochs (set `USE_TRAINING_HOST_SERVICE=false`). During and after training:

1. **Verify metrics collection**: Query `GET /operations/{id}/metrics` - should now return populated metrics with 10 epochs, each containing train_loss, val_loss, accuracy, learning_rate, duration, timestamp.

2. **Verify trend analysis**: Check that computed fields exist: `best_epoch`, `epochs_since_improvement`, `is_overfitting`, `is_plateaued`.

3. **Run monitoring agent**: Execute the same agent script from M1. Should now display real-time epoch progress instead of "no metrics yet". Watch it update as training progresses.

4. **Run analyzer agent**: Execute the analyzer. Should now provide actual trend analysis (improving/worsening) and recommendations (continue/stop/use checkpoint).

5. **Validate synthetic cases**: Create unit tests with synthetic loss data to verify overfitting detection (train↓, val↑) and plateau detection (no improvement for N epochs) work correctly.

The key validation is that the **same agent scripts from M1 now show real data** without code changes.

### Risks & Decisions

**Risk**: Metrics storage fails, training continues
**Mitigation**: Storage errors logged but don't crash training. Metrics collection is best-effort.

**Risk**: Database writes slow down training
**Mitigation**: Metrics stored async via `asyncio.create_task()`, non-blocking

**Decision**: Store metrics incrementally (per epoch)
**Rationale**: Allows real-time monitoring. Alternative (store at end) defeats purpose.

**Decision**: Compute trend analysis on write
**Rationale**: <1ms overhead, avoids computation on every read. Re-computing on each API call wasteful.

### Commit Message

```text
feat(training): add metrics collection for local training

Complete end-to-end metrics pipeline for local training:
- ModelTrainer emits full epoch metrics
- OperationsService stores and analyzes metrics
- Trend analysis: best epoch, overfitting, plateau detection
- POST endpoint now stores data (was stub in M1)

M2 complete: Local training metrics fully functional.
Agent scripts from M1 now show real data (no code changes needed).

Validation: Train 10 epochs, run same agent scripts from M1
Tests: make test-unit && make test-integration && make quality
```

---

## Milestone 3: Light Up Host Service (GPU Training)

### Goal

Extend metrics to work when training runs on host service (for GPU access). Same agent scripts work without modification.

### What Gets Built

**Host Service Endpoints**:
- POST `/sessions/{id}/metrics` on training host service
- Receives metrics from bridge, forwards to Docker API

**API Endpoint**:
- Enhance POST `/operations/{id}/metrics` to handle requests from host service
- Already functional from M2, just needs to accept remote calls

**Orchestrator Changes**:
- HostTrainingOrchestrator sends metrics via HTTP to host service
- Uses same callback pattern as local mode, but over HTTP

**Testing**:
- Unit tests for HTTP forwarding
- Integration test: full GPU training with host service
- Test error handling: timeouts, connection failures

### Why This Milestone

Host service adds HTTP complexity. Core logic validated in M2, now just extending transport layer.

### Acceptance Criteria

**Functional**:
- [ ] Train 10 epochs on GPU, all epochs appear in metrics
- [ ] Metrics structure identical to local mode
- [ ] No HTTP errors in logs (host service or Docker)
- [ ] Trend analysis works correctly

**Technical**:
- [ ] All tests pass
- [ ] Quality checks pass
- [ ] HTTP calls are async, non-blocking
- [ ] Handles timeouts gracefully (training continues)
- [ ] No performance impact vs M2

**User Validation**:

Start training host service, then train with GPU for 10 epochs (set `USE_TRAINING_HOST_SERVICE=true`). Validate:

1. **Verify HTTP flow**: Monitor logs in both training-host-service and Docker container. Should see metrics forwarding messages in host service logs and receipt confirmation in Docker logs.

2. **Verify metrics appear**: Query `GET /operations/{id}/metrics` - should return same populated structure as M2 (10 epochs with all fields).

3. **Run same agent scripts**: Execute the monitoring and analyzer agents from M1/M2. Should work identically to M2 - agents don't know or care that training happened on GPU.

4. **Test error handling**: Temporarily stop training host service mid-training, verify graceful degradation (training continues, metrics just aren't collected).

5. **Performance check**: Compare training time to M2. HTTP calls are async and should not add noticeable overhead.

The validation proves that **location of training (Docker vs host) is transparent to agents**.

### Risks & Decisions

**Risk**: HTTP forwarding fails, metrics lost
**Mitigation**: Failure logged but doesn't crash training. Metrics are best-effort.

**Risk**: Network latency impacts training
**Mitigation**: HTTP calls async with short timeout (5s). Training doesn't wait.

**Decision**: Two HTTP hops (host service → Docker API)
**Rationale**: Maintains separation. Host service is relay, Docker API is storage. Simpler than direct host → database.

### Commit Message

```text
feat(training): add metrics collection for host service training

Extend metrics to GPU training via host service:
- Training host service forwards metrics to Docker API
- HostTrainingOrchestrator sends via HTTP
- Same metrics structure as local mode
- Graceful error handling for network issues

M3 complete: Metrics work for both local and GPU training.
Same agent scripts work for both modes (no changes needed).

Validation: Train 10 epochs with GPU, run same agents
Tests: make test-unit && make test-integration && make quality
```

---

## Milestone 4: Polish & Production Ready

### Goal

Documentation, performance validation, and final polish. Make it production-ready.

### What Gets Built

**Documentation**:
- Update main README with metrics capabilities
- Update API documentation (Swagger descriptions)
- Agent usage guide for developers
- Troubleshooting guide

**Performance Validation**:
- Run 100-epoch training, verify storage < 50KB
- Verify no training performance degradation
- Test with concurrent operations

**Optional Enhancements** (if time permits):
- Jupyter notebook for metrics visualization
- Comparison tool for multiple training runs

**Final Cleanup**:
- Remove debug logging
- Ensure all TODOs resolved
- Code review checklist

### Acceptance Criteria

**Documentation**:
- [ ] README updated with metrics examples
- [ ] API docs complete and accurate
- [ ] Agent usage guide clear
- [ ] Troubleshooting section added

**Performance**:
- [ ] 100-epoch training: storage verified < 50KB
- [ ] Training time unchanged vs baseline (±2%)
- [ ] Database queries < 100ms
- [ ] Concurrent training operations work correctly

**Production Readiness**:
- [ ] All TODOs resolved or documented
- [ ] Error messages user-friendly
- [ ] Logs appropriate (not too verbose)
- [ ] All edge cases tested

**Final Validation**:

Comprehensive end-to-end testing:

1. **Local training test**: Run 50-epoch training locally, use analyzer agent to verify complete metrics history and accurate recommendations.

2. **GPU training test**: Run 50-epoch training with host service, verify identical behavior to local mode.

3. **Concurrency test**: Start 3 training operations simultaneously (mix of local and GPU), verify all collect metrics correctly without interference.

4. **Performance validation**: Compare training times to baseline (pre-metrics), verify < 2% difference. Measure database query response times, verify < 100ms. Check metrics storage size for 100-epoch training, verify < 50KB.

5. **Agent scenario validation**: Run agents in realistic scenarios (long training, early stopping needed, overfitting detection) and verify recommendations are sensible.

### Commit Message

```text
docs(training): complete metrics exposure documentation and polish

Final polish for production readiness:
- Updated README with metrics capabilities
- Enhanced API documentation
- Performance validation (100 epochs, <50KB, no degradation)
- Agent usage guide for developers

All 4 milestones complete:
✅ M1: API Contract (interface first)
✅ M2: Local training metrics
✅ M3: Host service training metrics
✅ M4: Production ready

Agents can now intelligently monitor training and make decisions
about early stopping, overfitting, and training health.

Validation: Full end-to-end tests with local and GPU training
```

---

## Testing Strategy

### Per Milestone

**M1: Interface**
- Unit tests: Models, API endpoints, MCP client
- Integration: Agent → MCP → API flow
- Manual: Run agents, verify structure

**M2: Local Training**
- Unit tests: ModelTrainer, OperationsService, Bridge
- Integration: Full 10-epoch training
- Manual: Run agents, verify real data

**M3: Host Service**
- Unit tests: HTTP forwarding, error handling
- Integration: Full GPU training
- Manual: Run agents, verify GPU metrics

**M4: Polish**
- Performance tests: 100-epoch training
- Concurrency tests: Multiple trainings
- Manual: Full end-to-end validation

### Test Pyramid

- **Unit tests** (fast, many): Test individual components
- **Integration tests** (medium, some): Test component interactions
- **End-to-end tests** (slow, few): Test full user workflows

### Before Each Commit

```bash
# Required checks
make test-unit          # Must pass
make test-integration   # Must pass
make quality            # Must pass

# Manual validation
# (specific commands per milestone above)
```

---

## Rollback Plan

**Per Milestone**:
- **M1**: Safe to revert - only added new endpoints, no breaking changes
- **M2**: Safe to revert - metrics callback optional, training works without it
- **M3**: Safe to revert - falls back to M2 behavior if host service unavailable
- **M4**: Safe to revert - only documentation and polish

**Nuclear Option**: Delete branch, start over
```bash
git checkout main
git branch -D feature/training-metrics-exposure
```

---

## Timeline Estimate

**Total**: 2-3 days focused work

| Milestone | Estimated Time | Confidence |
|-----------|----------------|------------|
| M1: API Contract | 6-8 hours | High - straightforward interface work |
| M2: Local Training | 8-10 hours | Medium - core implementation, most complex |
| M3: Host Service | 4-6 hours | High - adds HTTP layer to M2 |
| M4: Polish | 2-4 hours | High - documentation and validation |

**Contingency**: +1 day buffer for unexpected issues

---

## Dependencies

**External**:
- None - uses existing infrastructure

**Internal**:
- ModelTrainer (exists, needs enhancement)
- OperationsService (exists, needs new methods)
- TrainingProgressBridge (exists, needs enhancement)
- MCP client infrastructure (exists, needs new methods)

**Blockers**:
- None identified

---

## Success Criteria (Overall)

At completion, agents must be able to:

- ✅ Monitor training in real-time (both local and GPU)
- ✅ Detect overfitting (train_loss ↓ while val_loss ↑)
- ✅ Detect plateaus (no improvement in N epochs)
- ✅ Identify best epoch (lowest validation loss)
- ✅ Recommend early stopping or continuation
- ✅ Provide intelligent analysis of training health

**User Experience**:
- Single command to monitor any training
- Clear, actionable recommendations
- Works identically for local and GPU training

---

## Post-Implementation

### Monitoring

After deployment, monitor:
- Metrics storage size (should stay < 50KB per operation)
- API response times (should stay < 100ms)
- Training performance (no degradation)

### Future Enhancements

Potential follow-ups (not in scope):
- Real-time streaming (current: polling)
- Historical comparison across runs
- Automated early stopping triggers
- TensorBoard integration
- Custom metric definitions

---

**END OF IMPLEMENTATION PLAN**
