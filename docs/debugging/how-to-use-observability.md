# How to Actually Use KTRDR Telemetry

**Created**: 2025-11-11
**Audience**: Developers & Claude Code Agent
**Goal**: Make observability tools actually useful for debugging

---

## 🎯 The Problem You Identified

> "We have OTEL, Prometheus and Grafana, everything hopefully connected, BUT no idea how to properly use or configure these tools."

**You're absolutely right!** You have:
- ✅ Infrastructure running (Jaeger, Prometheus, Grafana)
- ✅ Auto-instrumentation (HTTP requests, logs with trace IDs)
- ✅ Basic dashboard (HTTP metrics)

But you **can't answer** your design questions:
- ❌ "Which worker was selected?"
- ❌ "Why is load balancing not working?"
- ❌ "Where exactly did training fail?"

---

## 🔍 Root Cause Analysis

### What You Have (Auto-Instrumentation)

```
HTTP Request Flow (Auto-Captured):

CLI → POST /api/v1/training/start → POST http://worker:5004/training/start
        │                               │
        └─ Span 1: FastAPI             └─ Span 2: httpx client
```

**What Auto-Instrumentation Tells You**:
- ✅ HTTP method, path, status code
- ✅ Request duration
- ✅ Connection errors (if host service down)

**What Auto-Instrumentation DOESN'T Tell You**:
- ❌ Which worker was selected (business logic)
- ❌ Why worker selection failed (business logic)
- ❌ What's happening inside the worker (business logic)
- ❌ Where training failed - data load? model init? training loop? (business logic)

### The Gap: Business Logic Instrumentation

**You only have HTTP boundaries**, not **decision points** or **execution phases**.

---

## 💡 The Solution: Phase 6

I've created a complete implementation plan: **[PHASE6_ACTIONABLE_OBSERVABILITY.md](PHASE6_ACTIONABLE_OBSERVABILITY.md)**

### Three High-Value Instrumentation Points

#### 1. Worker Selection (Backend)
```python
# Current: NO visibility
def select_worker():
    return some_worker

# After Phase 6: FULL visibility
with tracer.start_as_current_span("worker_registry.select_worker") as span:
    span.set_attribute("total_workers", 5)
    span.set_attribute("available_workers", 0)  # ← AHA! All busy!
    span.set_attribute("selection_status", "no_workers_available")
```

**Now you can**:
- Query Jaeger: "Show me traces where `selection_status=no_workers_available`"
- See instantly when and why no workers were available

---

#### 2. Operation Lifecycle (Backend)
```python
# Current: NO metrics
async def start_training():
    # Just logs, no metrics
    pass

# After Phase 6: Metrics + Spans
operation_duration.record(
    duration_ms,
    attributes={
        "operation_type": "training",
        "status": "completed",
        "symbol": "AAPL"
    }
)
```

**Now you can**:
- PromQL: `histogram_quantile(0.95, rate(ktrdr_operation_duration_ms[5m])) by (operation_type)`
- See P95 duration for training vs. backtesting vs. data load

---

#### 3. Worker Execution Phases (Workers)
```python
# Current: Single HTTP span
POST /training/start (duration: 24min)

# After Phase 6: Phase breakdown
with tracer.start_as_current_span("worker.training.execute"):
    with tracer.start_as_current_span("worker.training.load_data"):
        # 45s - THIS is slow!
    with tracer.start_as_current_span("worker.training.train_loop"):
        # 23min - Normal
    with tracer.start_as_current_span("worker.training.save_model"):
        # 10s - Normal
```

**Now you can**:
- See in Jaeger timeline: "Aha! Data loading is taking 45s, that's the bottleneck"
- Check attributes: `model.device=cpu` → "Oh, GPU not being used!"

---

## 📊 Concrete Examples: Before vs. After

### Example 1: "Training failed, help!"

**Before Phase 6** (Current):
```
User: "Training failed"

You/Claude: "Can you check the logs?"
User: [pastes logs]
You/Claude: "Hmm, check if worker is running"
User: "Yes it's running"
You/Claude: "Check GPU?"
User: "GPU is fine"
... 10 messages later ...
You/Claude: "Oh, data file is missing!"
```

**After Phase 6**:
```
User: "Training failed, operation op_training_123"

You/Claude: "Let me check Jaeger..."
[Queries: http://localhost:16686/api/traces?tag=operation.id:op_training_123]

You/Claude: "Found it! Looking at the trace:
- Worker selected: training-worker-cpu-01
- Failed at: worker.training.load_data span
- Error type: FileNotFoundError
- Missing file: /app/data/AAPL_1d.parquet

**Root cause**: Worker can't access data directory. Check docker volume mounts.

**Fix**: Add to docker-compose.yml:
```yaml
volumes:
  - ../data:/app/data:ro
```

**DIAGNOSIS IN FIRST RESPONSE** (not 10 messages later)
```

---

### Example 2: "Why is load balancing not working?"

**Before Phase 6** (Current):
```
User: "All operations going to one worker"

You/Claude: "Let me check the worker registry code"
[Reads code...]
You/Claude: "Code looks fine. Can you check worker health endpoints?"
User: [Checks manually]
User: "All workers show AVAILABLE"
You/Claude: "Hmm, check backend logs?"
... debugging continues ...
```

**After Phase 6**:
```
User: "All operations going to one worker"

You/Claude: "Let me check Grafana Worker Health dashboard..."
[Opens: http://localhost:3000/d/ktrdr-workers]

You/Claude: "I see the issue:
- Dashboard shows: 5 registered workers
- But Prometheus shows: available_workers=1 for last 2 hours
- Checking Jaeger traces...
- All have: selection_status='success', selected_worker_id='worker-gpu-01'

**Root cause**: Only worker-gpu-01 has GPU capability, but all training ops require GPU.

**Fix**: Either:
1. Add more GPU workers, OR
2. Make training ops fall back to CPU workers when GPU busy

Current config is correct, you just need more GPU workers for the load!"
```

---

### Example 3: "Training is slow"

**Before Phase 6** (Current):
```
User: "Training takes 30 minutes, seems slow"

You/Claude: "That's subjective. What's your baseline?"
User: "Not sure, just feels slow"
You/Claude: "Check GPU utilization?"
User: [Checks] "80%"
You/Claude: "That's normal. Maybe try larger batch size?"
... trial and error continues ...
```

**After Phase 6**:
```
User: "Training takes 30 minutes, seems slow"

You/Claude: "Let me check Jaeger timeline for a recent training operation..."
[Opens trace, sees phase breakdown:]

```
Training Operation (30min total):
├─ Data load: 58s      ← SLOW! (Expected: <30s)
├─ Model init: 5s      ← Normal
├─ Train loop: 28min   ← Normal (depends on epochs)
└─ Save model: 12s     ← Normal
```

**Root cause**: Data loading is 2x slower than expected.

Checking span attributes:
- data.rows: 1,000,000
- data.source: "network" (should be local cache!)

**Fix**: Data not cached locally. Check DataRepository cache configuration.
Enable cache: USE_DATA_CACHE=true in .env"
```

---

## 🚀 Quick Start: Most Valuable Improvements

Based on your design questions, here's the **minimum** you should implement:

### Priority 1: Worker Selection Visibility (2 hours)
**Answers**: "Which worker? Why no workers?"

Add spans to `WorkerRegistry.select_worker()`:
- `selected_worker_id`
- `available_workers` vs `total_workers`
- `selection_status` (success / no_workers_available / no_capable_workers)

### Priority 2: Worker Execution Phases (4 hours)
**Answers**: "Where did it fail? Which phase is slow?"

Add spans to worker execution:
- `worker.training.load_data`
- `worker.training.init_model`
- `worker.training.train_loop`
- `worker.training.save_model`

Each with attributes like `data.rows`, `model.device`, `training.epochs_completed`

### Priority 3: Query Documentation (2 hours)
**Answers**: "How do I actually query this stuff?"

Write docs/debugging/observability-queries.md with:
- Common scenarios ("Worker not selected" → Jaeger query)
- PromQL examples
- Grafana dashboard links

**Total: 8 hours for MASSIVE debugging improvement**

---

## 🤖 Agent Integration: How Claude Code Can Help

### Current State (Without Phase 6)
```
User: "Training failed"
Claude: "Can you share the logs?"
... back and forth debugging ...
```

### After Phase 6
```
User: "Training failed, op ID: op_training_123"

Claude: "Let me check the trace..."
[Uses curl to query Jaeger API]
[Analyzes trace structure]
[Identifies exact failure point]

Claude: "**Root cause**: CUDA OOM in train_loop span. Batch size (512) too large.
**Fix**: Reduce to 256.
**Prevention**: Add memory check before training starts."

[Diagnosis in FIRST response, with fix!]
```

### How to Enable This

**Add to CLAUDE.md** (I've drafted this in Phase 6 doc):
1. **Debugging section** with query patterns
2. **When to suggest checking Jaeger/Prometheus**
3. **Example interactions** showing agent using traces

**Result**: Claude Code becomes a **debugging assistant** that uses traces instead of guessing.

---

## 📈 ROI: Is Phase 6 Worth It?

### Time Investment
- **Quick Win**: 8-10 hours (core instrumentation + docs)
- **Full Phase 6**: 20 hours (add dashboards, `/debug` command)

### Time Saved
**Every debugging session** currently takes:
- 5-10 messages back and forth
- 30-60 minutes elapsed time
- Trial and error fixes

**After Phase 6**:
- 1-2 messages (query trace, identify root cause)
- 5-10 minutes elapsed time
- Targeted fix immediately

**If you debug 1 issue per week**: Phase 6 pays for itself in 3-4 weeks.
**If you debug more**: Even faster ROI.

---

## 🎯 Decision Time

### Option 1: Full Phase 6 (~20h)
**Includes**: All instrumentation + Grafana dashboards + `/debug` command
**Best for**: Production systems, multiple developers

### Option 2: Quick Win (~10h)
**Includes**: Core instrumentation (worker selection, execution phases) + query docs
**Best for**: Immediate debugging value, add dashboards later

### Option 3: Minimal (~4h)
**Includes**: Just worker selection spans + basic docs
**Best for**: Testing if this approach works before full investment

---

## 📝 My Recommendations

### Short-term (This Week)
1. **Read** [PHASE6_ACTIONABLE_OBSERVABILITY.md](PHASE6_ACTIONABLE_OBSERVABILITY.md) (full implementation plan)
2. **Discuss** which debugging scenarios are most painful right now
3. **Prioritize** which spans/metrics would help most
4. **Implement** Quick Win path (Tasks 6.1, 6.3, 6.5, 6.6)

### Medium-term (Next Week)
1. **Validate** that instrumented spans answer your questions
2. **Add** custom metrics if needed (operation duration, failure rate)
3. **Create** 1-2 purpose-built Grafana dashboards
4. **Document** query patterns for your team

### Long-term (Next Month)
1. **Train** team on using Jaeger/Grafana for debugging
2. **Expand** instrumentation to other critical paths (data acquisition, backtesting)
3. **Build** alerting on key metrics (failure rate, worker availability)
4. **Integrate** with incident response workflow

---

## 🤔 Questions for You

To help refine Phase 6, please think about:

1. **Which debugging scenarios are most painful?**
   - Worker selection failures?
   - Training failures?
   - Slow operations?
   - Data loading issues?

2. **What would make these tools most useful?**
   - Just Jaeger traces + docs?
   - Need Grafana dashboards for visual overview?
   - Want `/debug` slash command for Claude Code?

3. **How much time can you invest?**
   - 4h (minimal spans)
   - 10h (quick win)
   - 20h (full Phase 6)

4. **What other business logic needs visibility?**
   - Data acquisition flows?
   - Backtesting execution?
   - Strategy execution?

---

## 📚 Resources

**Implementation Plan**: [PHASE6_ACTIONABLE_OBSERVABILITY.md](PHASE6_ACTIONABLE_OBSERVABILITY.md)

**What You Have Now**:
- [DESIGN.md](DESIGN.md) - Why OTEL, design decisions
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical architecture
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Phases 1-5 (completed)
- [Validation docs](PHASE*_VALIDATION.md) - Validation for each phase

**What's Next**:
- [PHASE6_ACTIONABLE_OBSERVABILITY.md](PHASE6_ACTIONABLE_OBSERVABILITY.md) - Make it useful!

---

## 🎉 Bottom Line

**You've built 80% of an amazing observability system!**

The last 20% is **instrumenting business logic** so you can actually answer questions like:
- "Which worker was selected?" → Add span attribute
- "Where did training fail?" → Add phase spans
- "Why is it slow?" → Check span durations

**Phase 6 transforms your telemetry from "installed" to "indispensable".**

Let's discuss next steps! 🚀

---

**Document End**
