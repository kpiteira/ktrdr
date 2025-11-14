# Using Observability Tools TODAY (With Current Implementation)

**Created**: 2025-11-11
**Status**: Practical guide for using what you have NOW
**Audience**: Developers debugging issues right now

---

## 🎯 What This Document Is

You have Jaeger, Prometheus, and Grafana running. **What can you actually do with them RIGHT NOW** (before Phase 6)?

This is a practical guide for debugging with **only auto-instrumentation** (HTTP spans, logs with trace IDs).

---

## 🔧 Quick Access

```bash
# Open all tools
open http://localhost:16686  # Jaeger UI (traces)
open http://localhost:9090   # Prometheus UI (metrics)
open http://localhost:3000   # Grafana UI (dashboards)

# Check if tools are running
curl http://localhost:16686/api/services  # Jaeger
curl http://localhost:9090/-/healthy      # Prometheus
curl http://localhost:3000/api/health     # Grafana
```

---

## 📊 What Auto-Instrumentation Actually Gives You

### ✅ You CAN Answer

1. **"Did the API receive the request?"**
   - Jaeger → Search for service=ktrdr-api
   - Look for span: `POST /api/v1/training/start`
   - If no span → Request never reached backend

2. **"Did the API call the host service?"**
   - Open trace → Look for child span
   - Span name: `POST http://localhost:5001/...`
   - If no child span → API didn't try to call
   - If span exists with error → Connection failed

3. **"What was the HTTP status code?"**
   - Check span attributes: `http.status_code`
   - 200 = success, 404 = not found, 500 = server error

4. **"How long did the HTTP request take?"**
   - Look at span duration
   - Waterfall view shows time breakdown

5. **"Are logs correlated with traces?"**
   - Check logs for `otelTraceID` field
   - Copy trace ID → Search Jaeger for that trace

### ❌ You CANNOT Answer (Need Phase 6)

1. "Which worker was selected?" → No visibility (HTTP only)
2. "Why did worker selection fail?" → No visibility
3. "Which phase of training failed?" → Only see total HTTP duration
4. "What were the operation parameters?" → Not captured in spans

---

## 🔍 Debugging Scenarios (With Current Implementation)

### Scenario 1: "Training command not working"

**Steps**:

1. **Check if API received the request**:
   ```bash
   # Open Jaeger
   open http://localhost:16686

   # Search for:
   # - Service: ktrdr-api
   # - Operation: POST /api/v1/training/start
   # - Time range: Last 1 hour
   ```

2. **If NO traces found**:
   - API never received request
   - Check: Is API running? `curl http://localhost:8000/health`
   - Check: CLI configured with correct API URL?

3. **If trace EXISTS**:
   - Click trace → Open timeline view
   - Check HTTP status code: `http.status_code` attribute
   - If 500: Check backend logs for error details
   - If 200: Request succeeded! Issue is elsewhere

---

### Scenario 2: "Data download failed"

**Steps**:

1. **Find the trace**:
   ```bash
   # Jaeger search:
   # - Service: ktrdr-api
   # - Operation: POST /api/v1/data/load
   # - Status: Error (red)
   ```

2. **Check for child spans**:
   - Look for: `POST http://localhost:5001/download_historical_data`
   - **If child span MISSING** → API didn't try to call host service
     - Check: `USE_IB_HOST_SERVICE` env var set?
     - Check: API routing configuration

   - **If child span EXISTS with ERROR**:
     - Check error attribute: `error.type`
     - `ConnectionRefusedError` → Host service not running
     - `TimeoutError` → Host service too slow
     - Check: `lsof -i :5001` → Is host service up?

3. **Check logs for details**:
   - Copy trace ID from Jaeger
   - Search logs: `grep <trace_id> api_logs.txt`
   - Logs have full error message and stack trace

---

### Scenario 3: "Operation is slow"

**Steps**:

1. **Find the trace**:
   ```bash
   # Jaeger search:
   # - Service: ktrdr-api
   # - Sort by: Duration (longest first)
   # - Time range: Last 1 hour
   ```

2. **Open timeline view**:
   - See waterfall chart of spans
   - Identify longest span

3. **Analyze bottleneck**:
   - If main span is long → Overall operation slow
   - If child span is long → External call slow

   Example:
   ```
   POST /api/v1/data/load (15.2s)
   └─ POST http://localhost:5001/... (15.1s)  ← Bottleneck!
   ```

   **Conclusion**: IB Host Service is slow (15s), not API

4. **What you CAN'T see** (need Phase 6):
   - Which part of the host service is slow?
   - Data loading? Processing? Saving?
   - → Need phase-level spans inside host service

---

### Scenario 4: "Worker not receiving operations"

**Current Limitations** ⚠️:

With only auto-instrumentation, you can see:
- ✅ API → Worker HTTP call (if it happens)
- ✅ HTTP status code from worker

You CANNOT see:
- ❌ Worker selection logic
- ❌ Why a worker wasn't selected
- ❌ Worker registry state

**Workaround** (Manual checking):
```bash
# Check worker health manually
curl http://localhost:5003/health  # Backtest worker
curl http://localhost:5004/health  # Training worker

# Check worker registration
curl http://localhost:8000/api/v1/workers | jq
```

**Better Solution**: Implement Phase 6 Task 6.1 (Worker Registry spans)

---

## 📈 Using Prometheus (Current State)

### What Metrics Are Available NOW

1. **HTTP Request Metrics** (auto-instrumented):
   ```promql
   # Request rate
   rate(http_server_duration_milliseconds_count[5m])

   # Average duration
   rate(http_server_duration_milliseconds_sum[5m]) /
   rate(http_server_duration_milliseconds_count[5m])

   # Requests by status code
   sum by (http_status_code) (rate(http_server_duration_milliseconds_count[5m]))
   ```

2. **Service Health**:
   ```promql
   # Is backend up?
   up{job="ktrdr-api"}
   ```

### What Metrics Are NOT Available (Need Phase 6)

- ❌ Operation-specific metrics (training duration, failure rate)
- ❌ Worker utilization
- ❌ Operation count by type
- ❌ Custom business metrics

---

## 🎨 Using Grafana (Current State)

### Current Dashboard: Operations Dashboard

**Location**: http://localhost:3000/d/ktrdr-operations

**What it shows**:
1. **HTTP Request Duration** (5m avg)
   - Average response time for API endpoints
   - Broken down by route

2. **HTTP Request Rate**
   - Requests per second
   - Good for seeing traffic patterns

3. **HTTP Status Codes Distribution**
   - Pie chart of 200 vs 500 vs 404
   - Shows error rate

4. **Service Health**
   - Is backend API up? (1 = up, 0 = down)

### What it DOESN'T show (Need Phase 6)

- ❌ Worker health
- ❌ Operation success/failure rate
- ❌ Worker selection failures
- ❌ Operation duration by type (training vs. backtesting)

---

## 🎯 Practical Debugging Workflow (TODAY)

### Step 1: Start with Grafana (Overview)
```bash
open http://localhost:3000/d/ktrdr-operations
```

**Check**:
- Service Health panel → Is backend up?
- HTTP Status Codes → High error rate (lots of 500s)?
- Request Duration → Spike in latency?

**Tells you**: "Is there a problem?" and "When did it start?"

---

### Step 2: Drill down with Jaeger (Root Cause)
```bash
open http://localhost:16686
```

**Search for**:
- Service: ktrdr-api
- Time range: When Grafana showed problem
- Status: Error (if looking for failures)

**Open trace**:
- See full request flow
- Check for missing child spans (call didn't happen)
- Check for error spans (call failed)
- Check span attributes for HTTP status codes

**Tells you**: "What exactly happened?" and "Where did it fail?"

---

### Step 3: Check Logs (Details)
```bash
# Get trace ID from Jaeger
TRACE_ID="abc123..."

# Find related logs
docker logs ktrdr-backend | grep $TRACE_ID
docker logs ktrdr-jaeger | grep $TRACE_ID
```

**Tells you**: "What was the exact error message?" and "Stack trace?"

---

## 💡 Pro Tips

### Tip 1: Use Trace ID for Correlation
When you see an error in logs:
```
2025-11-11 10:00:00 ERROR [...] otelTraceID=abc123... Training failed
```

Copy trace ID → Paste in Jaeger search → See full context

---

### Tip 2: Filter by Time Range
If issue happened at specific time:
1. Grafana → Zoom in to time range
2. Copy time range (e.g., "10:00 to 10:05")
3. Jaeger → Set same time range
4. See only relevant traces

---

### Tip 3: Compare Success vs. Failure
1. Find a **successful** operation trace
2. Find a **failed** operation trace
3. Compare side-by-side
4. Look for missing spans or different durations

---

### Tip 4: Use Tags to Filter
Jaeger search supports tags (from span attributes):
```
service="ktrdr-api"
http.method="POST"
http.status_code="500"
error=true
```

Combine filters to narrow down issues.

---

## ⚠️ Current Limitations (Honest Assessment)

### You Have Good Visibility For:
- ✅ HTTP request flow (API → Host Service)
- ✅ Connection failures
- ✅ HTTP status codes
- ✅ Request duration (total)
- ✅ Log correlation with traces

### You Have ZERO Visibility For:
- ❌ Worker selection logic
- ❌ Operation state transitions
- ❌ Execution phases (data load vs. training vs. save)
- ❌ Business metrics (operation failure rate by type)
- ❌ Worker health and utilization

### To Fix: Implement Phase 6
See: [PHASE6_ACTIONABLE_OBSERVABILITY.md](../architecture/telemetry/PHASE6_ACTIONABLE_OBSERVABILITY.md)

**Most valuable quick wins**:
1. Worker Registry spans (2h) → "Which worker?"
2. Worker execution phases (4h) → "Where did it fail?"
3. Query documentation (2h) → "How do I find this?"

---

## 🚀 Next Steps

### Today (Using What You Have)
1. **Bookmark these URLs**:
   - Jaeger: http://localhost:16686
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000/d/ktrdr-operations

2. **Try debugging something**:
   - Trigger a failure (stop host service, then try data load)
   - Find the trace in Jaeger
   - See the connection error span

3. **Get comfortable with Jaeger UI**:
   - Search for traces
   - Open timeline view
   - Check span attributes

### This Week (Improve Tools)
1. **Read**: [PHASE6_ACTIONABLE_OBSERVABILITY.md](../architecture/telemetry/PHASE6_ACTIONABLE_OBSERVABILITY.md)
2. **Discuss**: Which debugging scenarios are most painful?
3. **Implement**: Quick Win tasks (8-10 hours)
4. **Validate**: Tools now answer your questions!

---

## 📚 Related Documents

**For Understanding**:
- [HOW_TO_USE_TELEMETRY.md](../architecture/telemetry/HOW_TO_USE_TELEMETRY.md) - Overview and strategy
- [DESIGN.md](../architecture/telemetry/DESIGN.md) - Why we built this

**For Implementation**:
- [PHASE6_ACTIONABLE_OBSERVABILITY.md](../architecture/telemetry/PHASE6_ACTIONABLE_OBSERVABILITY.md) - How to make it better
- [IMPLEMENTATION_PLAN.md](../architecture/telemetry/IMPLEMENTATION_PLAN.md) - What we've built (Phases 1-5)

---

**Questions? Discuss with the team or Claude Code agent!**

---

**Document End**
