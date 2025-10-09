# Training Service Architecture - Phase 2 Improvements

**Date**: 2025-01-07
**Status**: Future Design (Phase 2)
**Previous**: [03-architecture.md](./03-architecture.md) (Phase 1)
**Prerequisite**: Phase 1 must be complete and stable

---

## Executive Summary

Phase 2 explores improvements that carry risk or add complexity. These should only be attempted **after Phase 1 is complete, tested, and proven stable in production**.

**Prerequisites for Phase 2**:
1. Phase 1 implementation complete
2. All equivalence tests passing
3. Both execution modes stable in production for at least 1 month
4. Zero known bugs in Phase 1 implementation

**Phase 2 Improvements** (in priority order):
1. Async pattern harmonization
2. Cancellation mechanism unification
3. Dynamic execution mode selection
4. Progress streaming improvements
5. Performance optimizations

**Key Principle**: Each improvement must justify its added complexity with measurable benefit.

---

## Improvement 1: Async Pattern Harmonization

### Problem

Phase 1 preserves two different async patterns:

**Local Orchestrator**:
```python
async def run(self):
    # Wrap ENTIRE execution in thread pool
    return await asyncio.to_thread(self._execute_training)

def _execute_training(self):
    # Synchronous execution
    for step in pipeline_steps:
        result = self._pipeline.step(...)
```

**Host Orchestrator**:
```python
async def run(self):
    # Direct async execution
    for step in pipeline_steps:
        result = self._pipeline.step(...)  # Sync call from async context
```

**Question**: Should we unify these patterns?

### Option A: Keep Current Patterns (Recommend for Phase 2 Start)

**Decision**: Accept they're different

**Rationale**:
- Both patterns work correctly
- Difference reflects environment reality (local vs host)
- Unifying adds complexity without clear benefit
- Risk: Breaking working code for aesthetic consistency

**Recommendation**: **Skip this improvement unless problems emerge**

### Option B: Make Host Use asyncio.to_thread() Like Local

**Decision**: Host orchestrator wraps execution like local

**Pattern**:
```python
# Host orchestrator becomes:
async def run(self):
    return await asyncio.to_thread(self._execute_training)

def _execute_training(self):
    # Synchronous execution (same as local)
    for step in pipeline_steps:
        if self._check_stop_requested():
            raise CancellationError()
        self._update_progress(...)
        result = self._pipeline.step(...)
```

**Benefits**:
- ✅ Both orchestrators use identical pattern
- ✅ Simpler mental model (one async pattern)
- ✅ Easier to maintain (identical structure)

**Costs**:
- ⚠️ Changes working host service code
- ⚠️ Must ensure session state updates work from thread
- ⚠️ Testing overhead to prove equivalence

**Prerequisites**:
1. Verify `session.update_progress()` is thread-safe
2. Verify `session.stop_requested` can be checked from thread
3. Comprehensive testing of threaded pattern on host

**Risk**: Medium (changing working code)
**Benefit**: Low (aesthetic consistency, not functional improvement)

**Recommendation**: **Low priority - only if maintaining two patterns becomes burdensome**

### Option C: Make Local Use Direct Async Like Host

**Decision**: Remove asyncio.to_thread() from local orchestrator

**Pattern**:
```python
# Local orchestrator becomes:
async def run(self):
    # Direct async execution (same as host)
    for step in pipeline_steps:
        self._check_cancellation()
        self._bridge.on_phase(...)
        result = self._pipeline.step(...)
```

**Benefits**:
- ✅ Both orchestrators use identical pattern
- ✅ Simpler (no threading overhead)

**Costs**:
- ⚠️ Changes working local code
- ⚠️ Pipeline methods block async event loop
- ⚠️ Potential responsiveness issues during long operations

**Risk**: High (local training is primary path, heavily used)
**Benefit**: Low (no performance gain, potential responsiveness loss)

**Recommendation**: **Do not pursue - too risky for no benefit**

### Decision for Phase 2

**Recommendation**: **Option A - Keep current patterns**

**Rationale**:
- Both patterns work well
- Unifying is aesthetic, not functional
- Risk > benefit for both alternatives
- Could revisit if maintenance burden increases

**Success Criteria**: N/A (recommendation is to skip)

---

## Improvement 2: Cancellation Mechanism Unification

### Problem

Phase 1 preserves two different cancellation mechanisms:

**Local**: In-memory `CancellationToken` (< 50ms latency)
**Host**: HTTP-based `session.stop_requested` flag (< 2.5s latency)

**Question**: Can we provide faster, more unified cancellation for host service?

### Current Cancellation Flow (Phase 1)

```
User cancels
  ↓
Backend: cancellation_token.cancel()
  ↓
[Local Path]                    [Host Path]
  ↓                               ↓
Check token.is_cancelled()      Wait for next poll (up to 2s)
  ↓                               ↓
Raise CancellationError         POST /training/stop
  ↓                               ↓
Training stops (< 50ms)         session.stop_requested = True
                                  ↓
                                Check stop_requested
                                  ↓
                                Training stops (< 2.5s)
```

### Option A: Pass Token ID to Host Service

**Design**: Backend sends cancellation token ID with training request

**Flow**:
```
POST /training/start
{
  "config": {...},
  "cancellation_token_id": "abc-123"
}
  ↓
Host service stores token ID
  ↓
During training:
  Check local session.stop_requested OR
  Poll backend: GET /api/v1/cancellation/{token_id}
    ↓
  Returns: {"cancelled": true/false}
```

**Benefits**:
- ✅ Host service can check cancellation more frequently (every batch)
- ✅ Potentially faster cancellation (< 500ms vs < 2.5s)
- ✅ More unified conceptual model

**Costs**:
- ⚠️ Host service now depends on backend availability
- ⚠️ Additional HTTP requests during training (overhead)
- ⚠️ Need to handle network failures gracefully
- ⚠️ Backend needs new endpoint for token status
- ⚠️ Increased system complexity

**Implementation Requirements**:
1. Backend: New endpoint `GET /api/v1/cancellation/{token_id}`
2. Backend: Token registry (token_id → CancellationToken mapping)
3. Host service: Periodic token status polling (e.g., every batch)
4. Host service: Fallback to session.stop_requested if backend unreachable
5. Testing: Network failure scenarios

**Trade-offs Analysis**:

| Aspect | Current (Phase 1) | Token Passing |
|--------|-------------------|---------------|
| Latency | < 2.5s | < 500ms |
| Complexity | Low | Medium |
| Dependencies | Independent | Host → Backend |
| Network overhead | Minimal (2s polls) | Higher (per-batch) |
| Failure modes | Simple | More scenarios |

**Risk**: Medium (adds network dependency)
**Benefit**: Medium (faster cancellation)

**Recommendation**: **Consider for Phase 2 if < 2.5s cancellation is problematic**

**Success Criteria**:
- Cancellation latency < 500ms (measured)
- No training failures due to network issues
- Graceful degradation when backend unavailable

### Option B: WebSocket-Based Cancellation

**Design**: Host service maintains WebSocket connection to backend for real-time cancellation

**Flow**:
```
Host service starts training
  ↓
Opens WebSocket: ws://backend/training/control/{session_id}
  ↓
Backend sends: {"type": "cancel"}
  ↓
Host service receives immediately
  ↓
Sets session.stop_requested = True
  ↓
Training stops (< 100ms)
```

**Benefits**:
- ✅ Near-immediate cancellation (< 100ms)
- ✅ No polling overhead
- ✅ Can send other control messages (pause, adjust params)

**Costs**:
- ⚠️ Significant infrastructure complexity (WebSocket management)
- ⚠️ Connection management (reconnect logic)
- ⚠️ More failure modes
- ⚠️ Harder to debug

**Risk**: High (significant complexity)
**Benefit**: High (very fast cancellation, enables future control features)

**Recommendation**: **Only if building real-time control dashboard**

**Success Criteria**:
- Cancellation latency < 100ms
- WebSocket reliability > 99.9%
- Graceful handling of disconnects

### Option C: Keep Current Mechanism (Recommend)

**Decision**: Accept < 2.5s cancellation latency for host service

**Rationale**:
- Training runs for hours - 2.5s is negligible
- Users don't frequently cancel training
- Current mechanism is simple and reliable
- Adding complexity not justified by benefit

**Recommendation**: **Keep Phase 1 mechanism unless user complaints emerge**

**Success Criteria**: N/A (no change)

### Decision for Phase 2

**Recommendation**: **Option C - Keep current mechanism**

**Rationale**:
- < 2.5s latency is acceptable for training workflows
- Simpler is better unless proven problematic
- Could implement Option A if users complain
- Option B only if building control dashboard

**Trigger to reconsider**: User feedback that cancellation is too slow

---

## Improvement 3: Dynamic Execution Mode Selection

### Problem

Phase 1 uses static execution mode selection (env var at startup):
- `USE_TRAINING_HOST_SERVICE=true` → always host
- `USE_TRAINING_HOST_SERVICE=false` → always local
- Requires restart to change

**Question**: Should we support dynamic mode selection?

### Current System (Phase 1)

**Characteristics**:
- ✅ Simple and predictable
- ✅ No runtime complexity
- ✅ Easy to debug (mode never changes)
- ❌ No automatic fallback
- ❌ Requires restart to change
- ❌ No health checking

### Option A: Health-Checked Selection with Fallback

**Design**: Check host service health before each training request

**Flow**:
```
TrainingService.start_training()
  ↓
Check: is host service preferred? (env var)
  ↓
YES: Health check host service
  ↓
  Healthy → Use host service
  ↓
  Unhealthy → Fallback to local (with warning)
  ↓
NO: Use local directly
```

**Benefits**:
- ✅ Automatic fallback if host service down
- ✅ More reliable (degraded mode vs failure)
- ✅ Better user experience (training continues)

**Costs**:
- ⚠️ Health check adds latency (50-200ms per request)
- ⚠️ More failure modes to test
- ⚠️ Fallback might surprise users (expected GPU, got CPU)
- ⚠️ Need to log/alert when falling back
- ⚠️ What if local also can't handle it? (e.g., requires GPU)

**Design Questions**:

1. **What defines "healthy"?**
   - Responds to HTTP health check?
   - Has available GPU memory?
   - Not overloaded with other training?

2. **When to fallback vs fail?**
   - Always fallback? (even if training requires GPU)
   - User preference? (fail-fast vs best-effort)
   - Config parameter? (`fallback_to_local: true/false`)

3. **How to communicate fallback?**
   - Log warning?
   - Return in API response?
   - Send notification?

**Implementation Requirements**:
1. Host service: Robust health endpoint with GPU status
2. Backend: Health check before routing
3. Backend: Fallback logic with user preference
4. Backend: Logging/alerting when fallback occurs
5. Testing: All fallback scenarios

**Risk**: Medium (more failure modes)
**Benefit**: High (better reliability)

**Recommendation**: **Good candidate for Phase 2**

**Success Criteria**:
- Health check adds < 100ms latency
- Fallback works correctly 100% of time
- No training failures due to fallback logic
- Clear logs when fallback occurs

### Option B: User-Selectable Mode per Request

**Design**: User specifies execution mode in API request

**API**:
```python
POST /api/v1/training/start
{
  "symbols": ["EURUSD"],
  "strategy": "macd_rsi",
  "execution_mode": "host",  # or "local" or "auto"
  ...
}
```

**Modes**:
- `"local"`: Force local execution
- `"host"`: Force host service (fail if unavailable)
- `"auto"`: Health-checked with fallback (Option A)

**Benefits**:
- ✅ Maximum flexibility
- ✅ User controls trade-off (speed vs reliability)
- ✅ Easy to test both modes without restart

**Costs**:
- ⚠️ More complex API
- ⚠️ Users must understand modes
- ⚠️ Default mode needs careful choice
- ⚠️ More testing scenarios

**Risk**: Medium (API complexity)
**Benefit**: High (flexibility)

**Recommendation**: **Good candidate for Phase 2, after Option A**

**Success Criteria**:
- API parameter well-documented
- Default mode is sensible ("auto"?)
- All three modes work correctly

### Option C: Keep Static Selection (Recommend Initially)

**Decision**: Keep env var at startup

**Rationale**:
- Phase 1 needs to prove extraction works first
- Dynamic selection adds complexity
- Can add later if needed

**Recommendation**: **Phase 1 keeps static, Phase 2 adds Option A, Phase 2.1 adds Option B**

**Success Criteria**: N/A (Phase 1 approach)

### Decision for Phase 2

**Recommendation**: **Implement Option A (health-checked fallback) first**

**Rationale**:
- Improves reliability significantly
- Relatively low complexity
- Good foundation for Option B later
- Measurable benefit (training succeeds instead of fails)

**Then**: **Add Option B (user-selectable) if needed**

**Implementation Order**:
1. Phase 2.0: Health-checked fallback (Option A)
2. Phase 2.1: User-selectable mode (Option B)

**Success Criteria**:
- Fallback works transparently
- < 100ms health check latency
- Clear documentation of behavior

---

## Improvement 4: Progress Streaming

### Problem

Phase 1 preserves polling-based progress for host service:
- Backend polls every 2s
- Up to 2s latency for progress updates
- Works fine but not real-time

**Question**: Should we provide real-time progress streaming?

### Current System (Phase 1)

**Host Service Progress**:
```
Training loop
  ↓
Calls progress_callback
  ↓
session.update_progress(epoch, batch, metrics)
  ↓
Stored in session state
  ↓
Backend polls GET /status every 2s
  ↓
Returns session.get_progress_dict()
  ↓
Backend updates operation status
  ↓
User polls /operations/{id}
```

**Latency**: Up to 2s for progress to reach user

### Option A: WebSocket-Based Progress Streaming

**Design**: Host service streams progress to backend via WebSocket

**Flow**:
```
Backend starts training
  ↓
Opens WebSocket: ws://host/training/progress/{session_id}
  ↓
Training loop emits progress
  ↓
Sent via WebSocket immediately
  ↓
Backend receives and updates operation
  ↓
User polls /operations/{id} (or also WebSocket)
```

**Benefits**:
- ✅ Real-time progress (< 100ms latency)
- ✅ No polling overhead
- ✅ Better user experience (live updates)
- ✅ Can stream detailed metrics

**Costs**:
- ⚠️ Significant infrastructure complexity
- ⚠️ WebSocket management (connection, reconnect)
- ⚠️ Backend needs WebSocket client
- ⚠️ More failure modes
- ⚠️ Harder to debug

**Implementation Requirements**:
1. Host service: WebSocket server for progress streaming
2. Backend: WebSocket client in HostSessionManager
3. Backend: Fallback to polling if WebSocket fails
4. Testing: Connection failures, reconnect logic
5. Infrastructure: WebSocket support in deployment

**Risk**: High (significant complexity)
**Benefit**: Medium (better UX, but polling works)

**Recommendation**: **Only if building real-time training dashboard**

**Success Criteria**:
- Progress latency < 100ms
- WebSocket reliability > 99.9%
- Graceful fallback to polling

### Option B: Server-Sent Events (SSE)

**Design**: Backend subscribes to SSE stream from host service

**Flow**:
```
Backend starts training
  ↓
Subscribes to: GET /training/progress/{session_id} (SSE)
  ↓
Training loop emits progress
  ↓
Sent as SSE events
  ↓
Backend receives and updates operation
```

**Benefits**:
- ✅ Real-time progress
- ✅ Simpler than WebSocket (HTTP-based)
- ✅ Better browser support
- ✅ Automatic reconnect

**Costs**:
- ⚠️ One-way only (backend → host)
- ⚠️ Still requires connection management
- ⚠️ More complex than polling

**Risk**: Medium (simpler than WebSocket)
**Benefit**: Medium (real-time progress)

**Recommendation**: **Better than WebSocket if real-time needed**

**Success Criteria**:
- Progress latency < 500ms
- Reliable reconnect
- Fallback to polling

### Option C: Keep Polling (Recommend)

**Decision**: Accept 2s latency for host service progress

**Rationale**:
- Training runs for hours - 2s is negligible
- Polling is simple and reliable
- Real-time progress nice-to-have, not required
- Can add later if building dashboard

**Recommendation**: **Keep Phase 1 polling unless building real-time UI**

**Success Criteria**: N/A (no change)

### Decision for Phase 2

**Recommendation**: **Option C - Keep polling**

**Rationale**:
- 2s latency is acceptable for training (hours-long process)
- Polling is simple and reliable
- Real-time streaming adds significant complexity
- No user complaints about current latency

**Trigger to reconsider**: Building real-time training dashboard

**If reconsidered**: Choose Option B (SSE) over Option A (WebSocket) for simplicity

---

## Improvement 5: Remote Model Transfer

### Problem

Phase 1 assumes backend and host service run on the same machine (shared filesystem):

**Current**:
```
Host service trains model
  ↓
Saves to models/ directory (filesystem)
  ↓
Backend reads from same models/ directory
  ↓
Works!
```

**Limitation**: If host service on remote machine, filesystem not shared

**Example Remote Deployment**:
- Backend: AWS EC2 instance A
- Host service: AWS EC2 GPU instance B
- No shared filesystem between them

**Question**: How to transfer trained models from remote host service to backend?

### Option A: HTTP POST Model to Backend

**Design**: Host service uploads model to backend via HTTP

**Flow**:
```
Host service completes training
  ↓
Serializes model (torch.save to bytes)
  ↓
POST /api/v1/models/upload
  Body: {
    "model_data": base64(model_bytes),
    "metadata": {...}
  }
  ↓
Backend saves to models/ directory
  ↓
Returns model_path
```

**Benefits**:
- ✅ Works for any deployment (same machine or remote)
- ✅ No shared filesystem needed
- ✅ Backend controls model storage location

**Costs**:
- ⚠️ Model transfer over network (can be large: 10-100MB)
- ⚠️ Increased training latency (upload time)
- ⚠️ Network failure handling
- ⚠️ Backend needs upload endpoint

**Implementation Requirements**:
1. Backend: New endpoint `POST /api/v1/models/upload`
2. Backend: Handle large file uploads (streaming)
3. Host service: Serialize model to bytes
4. Host service: Retry logic for failed uploads
5. Compression: gzip model bytes before transfer

**Risk**: Low (straightforward HTTP upload)
**Benefit**: High (enables distributed deployment)

**Recommendation**: **Implement in Phase 2 for distributed deployment**

### Option B: S3/Cloud Storage

**Design**: Both services use shared cloud storage

**Flow**:
```
Host service completes training
  ↓
Uploads model to S3: s3://models/strategy_name/...
  ↓
Returns S3 path to backend
  ↓
Backend downloads from S3 when needed
```

**Benefits**:
- ✅ Works for distributed deployment
- ✅ Durable storage (backups, versioning)
- ✅ Scalable (multiple host services)

**Costs**:
- ⚠️ Cloud storage dependency
- ⚠️ S3 costs (storage + bandwidth)
- ⚠️ More complex configuration (credentials)
- ⚠️ Network latency for uploads/downloads

**Risk**: Medium (new infrastructure dependency)
**Benefit**: High (production-grade solution)

**Recommendation**: **Consider for production distributed deployment**

### Option C: Keep Shared Filesystem Requirement

**Decision**: Document that backend and host service must share filesystem

**Deployment Options**:
- Same machine (Phase 1)
- NFS/network filesystem
- Docker volume mounts

**Benefits**:
- ✅ Simplest solution
- ✅ No code changes needed
- ✅ Fast (no network transfer)

**Costs**:
- ❌ Limits deployment flexibility
- ⚠️ NFS can be complex to setup
- ⚠️ Network filesystem has failure modes

**Recommendation**: **Phase 1 approach, adequate for many deployments**

### Decision for Phase 2

**Recommendation**: **Implement Option A (HTTP upload) for flexibility**

**Rationale**:
- Enables distributed deployment
- Relatively simple to implement
- No infrastructure dependencies (Option B)
- More flexible than shared filesystem (Option C)

**Implementation Priority**: Medium (only needed for remote deployment)

**Success Criteria**:
- Model upload works reliably
- Handles models up to 500MB
- Upload time < 30s for typical model (~50MB)
- Graceful failure handling
- Works with shared filesystem (backward compatible)

---

## Improvement 6: Performance Optimizations

### Problem

Phase 1 focuses on correctness and eliminating duplication. Phase 2 can explore performance optimizations.

### Potential Optimizations

#### 5.1: Pipeline Method Batching

**Observation**: Pipeline methods process one symbol at a time

**Optimization**: Batch operations across symbols

**Example**:
```python
# Current (Phase 1)
for symbol in symbols:
    data = load_price_data(symbol)  # Sequential

# Optimized (Phase 2)
all_data = load_price_data_batch(symbols)  # Parallel
```

**Benefit**: Faster multi-symbol training
**Risk**: Low (pure optimization)
**Effort**: Medium (refactor pipeline methods)

**Recommendation**: **Profile first, optimize if bottleneck found**

#### 5.2: Caching Device Capabilities

**Observation**: DeviceManager detects device every time

**Optimization**: Cache detection result

**Benefit**: Faster pipeline initialization
**Risk**: Very low
**Effort**: Trivial

**Recommendation**: **Do this in Phase 1 actually** (safe optimization)

#### 5.3: Indicator Calculation Caching

**Observation**: Same indicators recalculated for same data

**Optimization**: Cache indicator results keyed by (symbol, timeframe, config)

**Benefit**: Faster re-training
**Risk**: Medium (cache invalidation complexity)
**Effort**: High

**Recommendation**: **Phase 2 or later, only if re-training is common**

### Decision for Phase 2

**Recommendation**: **Profile first, then optimize based on data**

**Approach**:
1. Run comprehensive profiling on Phase 1 implementation
2. Identify actual bottlenecks (not assumed)
3. Optimize only top 3 bottlenecks
4. Measure improvement
5. Stop when < 5% gain per optimization

**Success Criteria**:
- 10%+ total performance improvement
- No regression in correctness
- Added complexity justified by gains

---

## Phase 2 Implementation Priority

**Recommended Order**:

1. **Dynamic Mode Selection** (Option A - health-checked fallback)
   - **Why first**: Improves reliability significantly
   - **Benefit**: Training succeeds instead of fails
   - **Risk**: Medium, well-scoped
   - **Effort**: 1-2 weeks

2. **Performance Profiling & Optimization**
   - **Why second**: Understand real bottlenecks
   - **Benefit**: Data-driven improvements
   - **Risk**: Low (measure first)
   - **Effort**: 1 week profiling, 2-3 weeks optimization

3. **User-Selectable Mode** (Option B from improvement 3)
   - **Why third**: Builds on health checking
   - **Benefit**: User flexibility
   - **Risk**: Low (well-understood)
   - **Effort**: 1 week

4. **Remote Model Transfer** (Option A - HTTP upload) **IF NEEDED**
   - **Why conditional**: Only for distributed deployment
   - **Benefit**: Enables remote GPU servers
   - **Risk**: Low (straightforward)
   - **Effort**: 1-2 weeks

5. **Cancellation Improvement** (Option A - token passing) **IF NEEDED**
   - **Why conditional**: Only if users complain
   - **Benefit**: Faster cancellation
   - **Risk**: Medium
   - **Effort**: 2 weeks

6. **Async Harmonization** - **SKIP unless maintenance burden**
   - **Why last**: Aesthetic, not functional
   - **Benefit**: Code consistency
   - **Risk**: Medium
   - **Effort**: 1-2 weeks

7. **Progress Streaming** - **SKIP unless building dashboard**
   - **Why conditional**: Only for real-time UI
   - **Benefit**: Better UX
   - **Risk**: High
   - **Effort**: 3-4 weeks

---

## Phase 2 Success Criteria

Phase 2 is successful when:

1. ✅ **Measurable Improvement**: Each change provides measurable benefit
2. ✅ **No Regression**: Phase 1 functionality remains intact
3. ✅ **Justified Complexity**: Added complexity justified by benefit
4. ✅ **Production Stable**: All improvements stable in production
5. ✅ **User Feedback**: Positive feedback on improvements (if user-facing)

---

## When NOT to Do Phase 2

**Don't start Phase 2 if**:
- Phase 1 has known bugs
- Phase 1 not stable in production
- No clear problem being solved
- Doing it "because we can" (not "because we should")

**Remember**: Phase 1 already achieves the primary goal (eliminate duplication). Phase 2 is optional refinement.

---

**Status**: Phase 2 Design - Waiting for Phase 1 Completion
**Next**: Phase 1 Implementation
