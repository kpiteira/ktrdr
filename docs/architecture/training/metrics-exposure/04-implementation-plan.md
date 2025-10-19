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
- Database migration to add metrics column
- Field remains null/empty until M2

**API Layer**:
- GET `/operations/{id}/metrics` - returns `{metrics: {}}`
- POST `/operations/{id}/metrics` - accepts payload, logs it, doesn't store yet
- Both endpoints fully functional with proper error handling

**Client Layer**:
- MCP client method `get_operation_metrics(operation_id)`
- Calls GET endpoint, parses response

**Agent Layer**:
- `examples/agents/training_monitor.py` - monitors training, handles empty data gracefully
- `examples/agents/loss_analyzer.py` - analyzes trends, handles empty data gracefully

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
```bash
# Start a training operation
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 5 &

# Run monitoring agent (M1: shows "no metrics yet")
python examples/agents/training_monitor.py {operation_id}

# Expected: Agent runs, handles empty gracefully, shows valid structure
```

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
- Includes: train/val loss, accuracy, learning_rate, duration, timestamp

**Metrics Storage**:
- OperationsService gains `add_metrics()` method
- Stores metrics in Operation.metrics field
- Computes trend indicators: best_epoch, is_overfitting, is_plateaued

**Metrics Flow**:
- TrainingProgressBridge forwards metrics to OperationsService
- LocalTrainingOrchestrator wires callback between bridge and service

**API Changes**:
- POST `/operations/{id}/metrics` now actually stores data (was no-op in M1)
- GET `/operations/{id}/metrics` returns real data from database

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
```bash
# Train locally (same command as M1)
export USE_TRAINING_HOST_SERVICE=false
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 10

# Run THE SAME agent from M1
python examples/agents/training_monitor.py {operation_id}

# M1 output: "⏳ No metrics yet"
# M2 output: "✅ Epoch 0: train_loss=0.8234, val_loss=0.8912"
#            "✅ Epoch 1: train_loss=0.7123, val_loss=0.7456"
#            ... continues for all 10 epochs

# Run analyzer
python examples/agents/loss_analyzer.py {operation_id}

# Expected: Real analysis with recommendations
# "📈 Loss Trend Analysis: improving, -15.3% change"
# "💡 Recommendation: CONTINUE TRAINING"
```

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
```bash
# Start training host service
cd training-host-service && ./start.sh

# Train with GPU (same command structure as M1/M2)
export USE_TRAINING_HOST_SERVICE=true
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 10

# Run THE SAME agents (work with no changes!)
python examples/agents/training_monitor.py {operation_id}

# Expected: Same output as M2, but training ran on GPU
```

**Validation - HTTP Flow**:
```bash
# Watch logs during training
tail -f training-host-service/logs/training-host-service.log
# Should see: "Forwarding metrics for session {id}"

docker logs ktrdr-backend -f
# Should see: "Received metrics for operation {id}"
```

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
```bash
# End-to-end test with all modes
# 1. Local training
export USE_TRAINING_HOST_SERVICE=false
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 50
python examples/agents/loss_analyzer.py {operation_id}

# 2. GPU training
export USE_TRAINING_HOST_SERVICE=true
uv run ktrdr models train --strategy config/strategies/example.yaml --epochs 50
python examples/agents/loss_analyzer.py {operation_id}

# 3. Multiple concurrent trainings
# Start 3 trainings in parallel, verify all work correctly
```

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
