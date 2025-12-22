# Milestone 7: Budget & Observability

**Branch**: `feature/agent-mvp`
**Builds On**: M6 (Cancellation & Error Handling)
**Capability**: Cost control and full visibility into cycle execution

---

## Why This Milestone

Makes the system production-ready with cost controls and monitoring. Budget enforcement prevents runaway spending. Observability enables debugging and optimization.

---

## E2E Test

```bash
# Test budget enforcement
# Set budget to $0.01 in config
AGENT_DAILY_BUDGET=0.01 docker-compose up -d

ktrdr agent trigger
# Expected: {"triggered": false, "reason": "budget_exhausted"}

# Check budget status
ktrdr agent budget
# Expected: Shows daily limit, spend, remaining

# Run a cycle and check traces
ktrdr agent trigger
# Wait for completion

# Check Jaeger traces
curl -s "http://localhost:16686/api/traces?service=ktrdr-backend&limit=1" | jq '.data[0].spans | length'
# Expected: Multiple spans for agent phases

# Check Prometheus metrics
curl -s http://localhost:8000/metrics | grep agent_
# Expected: agent_cycles_total, agent_phase_duration_seconds, etc.
```

---

## Task 7.1: Add Budget Tracking

**File(s)**: `ktrdr/agents/budget.py`
**Type**: CODING

**Description**: Create budget tracker that persists daily spend to file.

**Implementation Notes**:
```python
# ktrdr/agents/budget.py
"""Budget tracking for agent operations."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktrdr import get_logger

logger = get_logger(__name__)


class BudgetTracker:
    """Tracks and enforces daily budget for agent operations.

    Budget is stored in a JSON file per day:
    - data/budget/2025-12-13.json

    Each file contains:
    {
        "date": "2025-12-13",
        "limit": 5.00,
        "spend": [
            {"amount": 0.065, "operation_id": "op_...", "timestamp": "..."},
            ...
        ],
        "total_spend": 0.15
    }
    """

    def __init__(
        self,
        daily_limit: float | None = None,
        data_dir: str | None = None,
    ):
        self.daily_limit = daily_limit or float(os.getenv("AGENT_DAILY_BUDGET", "5.0"))
        self.data_dir = Path(data_dir or os.getenv("AGENT_BUDGET_DIR", "data/budget"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_today_file(self) -> Path:
        """Get path to today's budget file."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"{today}.json"

    def _load_today(self) -> dict[str, Any]:
        """Load today's budget data."""
        path = self._get_today_file()
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "limit": self.daily_limit,
            "spend": [],
            "total_spend": 0.0,
        }

    def _save_today(self, data: dict[str, Any]):
        """Save today's budget data."""
        path = self._get_today_file()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_today_spend(self) -> float:
        """Get total spend for today."""
        data = self._load_today()
        return data.get("total_spend", 0.0)

    def get_remaining(self) -> float:
        """Get remaining budget for today."""
        return max(0, self.daily_limit - self.get_today_spend())

    def can_spend(self, estimated_amount: float = 0.15) -> tuple[bool, str]:
        """Check if we can afford estimated spend.

        Args:
            estimated_amount: Estimated cost ($0.15 per cycle default).

        Returns:
            Tuple of (can_spend, reason).
        """
        remaining = self.get_remaining()
        if remaining < estimated_amount:
            return False, f"budget_exhausted (${remaining:.2f} remaining, need ${estimated_amount:.2f})"
        return True, "ok"

    def record_spend(self, amount: float, operation_id: str):
        """Record a spend event.

        Args:
            amount: Amount spent in dollars.
            operation_id: Operation that incurred the spend.
        """
        data = self._load_today()
        data["spend"].append({
            "amount": amount,
            "operation_id": operation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        data["total_spend"] = sum(s["amount"] for s in data["spend"])
        self._save_today(data)

        logger.info(
            "Budget spend recorded",
            amount=amount,
            operation_id=operation_id,
            total_spend=data["total_spend"],
            remaining=self.daily_limit - data["total_spend"],
        )

    def get_status(self) -> dict[str, Any]:
        """Get full budget status.

        Returns:
            Dict with limit, spend, remaining, cycle estimates.
        """
        data = self._load_today()
        total_spend = data.get("total_spend", 0.0)
        remaining = max(0, self.daily_limit - total_spend)
        cycles_affordable = int(remaining / 0.15) if remaining > 0 else 0

        return {
            "date": data.get("date"),
            "daily_limit": self.daily_limit,
            "today_spend": total_spend,
            "remaining": remaining,
            "cycles_affordable": cycles_affordable,
            "spend_events": len(data.get("spend", [])),
        }


# Singleton
_budget_tracker: BudgetTracker | None = None


def get_budget_tracker() -> BudgetTracker:
    """Get the budget tracker singleton."""
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = BudgetTracker()
    return _budget_tracker
```

**Unit Tests** (`tests/unit/agent_tests/test_budget.py`):
- [ ] Test: Spend tracked per day
- [ ] Test: New day resets spend
- [ ] Test: can_spend returns False when exhausted
- [ ] Test: record_spend updates total
- [ ] Test: Persisted to file

**Acceptance Criteria**:
- [ ] Spend tracked per day
- [ ] Persisted to file (survives restart within day)
- [ ] Configurable daily limit via AGENT_DAILY_BUDGET env

---

## Task 7.2: Add Budget Check to Trigger

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Check budget before allowing trigger.

**Implementation Notes**:
```python
from ktrdr.agents.budget import get_budget_tracker

class AgentService:
    def __init__(self, ...):
        # ... existing init ...
        self.budget = get_budget_tracker()

    async def trigger(self) -> dict[str, Any]:
        """Start a new research cycle."""
        # Check budget first
        can_spend, reason = self.budget.can_spend()
        if not can_spend:
            logger.warning("Budget exhausted", reason=reason)
            return {
                "triggered": False,
                "reason": "budget_exhausted",
                "message": f"Daily budget exhausted: {reason}",
            }

        # Check for active cycle
        # ... rest of trigger logic ...

    async def _run_worker(self, operation_id: str, worker: AgentResearchWorker):
        """Run worker and record spend after completion."""
        try:
            result = await worker.run(operation_id)
            await self.ops.complete_operation(operation_id, result)

            # Record token spend
            total_tokens = result.get("total_tokens", 0)
            estimated_cost = self._estimate_cost(total_tokens)
            self.budget.record_spend(estimated_cost, operation_id)

        except asyncio.CancelledError:
            # ... cancellation handling ...
        except Exception as e:
            # ... error handling ...

    def _estimate_cost(self, total_tokens: int) -> float:
        """Estimate cost in dollars from token count.

        Claude Opus pricing (approximate):
        - Input: $15 / 1M tokens
        - Output: $75 / 1M tokens
        - Assuming 60% input, 40% output
        """
        avg_price_per_token = (0.6 * 15 + 0.4 * 75) / 1_000_000
        return total_tokens * avg_price_per_token
```

**Unit Tests**:
- [ ] Test: Trigger rejected when budget exhausted
- [ ] Test: Returns 429 status code for budget errors
- [ ] Test: Spend recorded after successful cycle
- [ ] Test: Cost estimation reasonable

**Acceptance Criteria**:
- [ ] 429 returned if budget exhausted
- [ ] Clear reason in response
- [ ] Spend recorded after cycle completes

---

## Task 7.3: Add Budget CLI and API

**File(s)**: `ktrdr/cli/agent_commands.py`, `ktrdr/api/endpoints/agent.py`
**Type**: CODING

**Description**: Add budget status endpoint and CLI command.

**Implementation Notes**:

In `ktrdr/api/endpoints/agent.py`:
```python
from ktrdr.agents.budget import get_budget_tracker

@router.get("/budget")
async def get_budget():
    """Get current budget status."""
    tracker = get_budget_tracker()
    return tracker.get_status()
```

In `ktrdr/cli/agent_commands.py`:
```python
@agent_group.command("budget")
def show_budget():
    """Show budget status."""
    url = f"{get_api_url()}/agent/budget"

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        click.echo("Agent Budget Status")
        click.echo("=" * 30)
        click.echo(f"Date: {data['date']}")
        click.echo(f"Daily Limit: ${data['daily_limit']:.2f}")
        click.echo(f"Today's Spend: ${data['today_spend']:.2f}")
        click.echo(f"Remaining: ${data['remaining']:.2f}")
        click.echo(f"Cycles Affordable: ~{data['cycles_affordable']}")

    except requests.RequestException as e:
        click.echo(f"Error: {e}", err=True)
```

**Acceptance Criteria**:
- [ ] `GET /agent/budget` returns status
- [ ] `ktrdr agent budget` shows formatted output
- [ ] Shows remaining cycles estimate

---

## Task 7.4: Add Prometheus Metrics

**File(s)**: `ktrdr/agents/metrics.py`, `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Add Prometheus metrics for agent system.

**Implementation Notes**:
```python
# ktrdr/agents/metrics.py
"""Prometheus metrics for agent system."""

from prometheus_client import Counter, Histogram


# Cycle metrics
agent_cycles_total = Counter(
    "agent_cycles_total",
    "Total research cycles",
    ["outcome"],  # completed, failed, cancelled
)

agent_cycle_duration_seconds = Histogram(
    "agent_cycle_duration_seconds",
    "Research cycle duration",
    buckets=[60, 300, 600, 900, 1200, 1800, 3600],
)

# Phase metrics
agent_phase_duration_seconds = Histogram(
    "agent_phase_duration_seconds",
    "Phase duration within cycle",
    ["phase"],  # designing, training, backtesting, assessing
    buckets=[10, 30, 60, 120, 300, 600],
)

# Gate metrics
agent_gate_results_total = Counter(
    "agent_gate_results_total",
    "Gate evaluation results",
    ["gate", "result"],  # gate: training/backtest, result: pass/fail
)

# Token metrics
agent_tokens_total = Counter(
    "agent_tokens_total",
    "Token usage by phase",
    ["phase"],  # design, assessment
)

# Budget metrics
agent_budget_spend_total = Counter(
    "agent_budget_spend_total",
    "Total budget spent (dollars)",
)
```

In `research_worker.py`:
```python
from ktrdr.agents.metrics import (
    agent_cycles_total,
    agent_cycle_duration_seconds,
    agent_phase_duration_seconds,
    agent_gate_results_total,
    agent_tokens_total,
)
import time

class AgentResearchWorker:
    async def run(self, operation_id: str) -> dict[str, Any]:
        start_time = time.time()

        try:
            # Design phase with timing
            phase_start = time.time()
            await self._update_phase(operation_id, "designing")
            design_result = await self._run_child(...)
            agent_phase_duration_seconds.labels(phase="designing").observe(
                time.time() - phase_start
            )
            agent_tokens_total.labels(phase="design").inc(
                design_result.get("input_tokens", 0) + design_result.get("output_tokens", 0)
            )

            # Training phase with timing and gate
            phase_start = time.time()
            await self._update_phase(operation_id, "training")
            training_result = await self._run_child(...)
            agent_phase_duration_seconds.labels(phase="training").observe(
                time.time() - phase_start
            )

            passed, reason = check_training_gate(training_result)
            agent_gate_results_total.labels(
                gate="training",
                result="pass" if passed else "fail"
            ).inc()

            # ... similar for other phases ...

            # Success
            agent_cycles_total.labels(outcome="completed").inc()
            agent_cycle_duration_seconds.observe(time.time() - start_time)
            return result

        except GateError:
            agent_cycles_total.labels(outcome="failed").inc()
            raise
        except asyncio.CancelledError:
            agent_cycles_total.labels(outcome="cancelled").inc()
            raise
        except Exception:
            agent_cycles_total.labels(outcome="failed").inc()
            raise
```

**Acceptance Criteria**:
- [ ] Metrics exported at /metrics
- [ ] Cycle counts by outcome
- [ ] Phase durations
- [ ] Gate pass/fail counts
- [ ] Token usage

---

## Task 7.5: Add OTEL Tracing

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Add OpenTelemetry spans for all phases.

**Implementation Notes**:
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class AgentResearchWorker:
    async def run(self, operation_id: str) -> dict[str, Any]:
        with tracer.start_as_current_span("agent.research_cycle") as span:
            span.set_attribute("operation.id", operation_id)
            span.set_attribute("operation.type", "agent_research")

            try:
                # Design phase
                with tracer.start_as_current_span("agent.phase.design") as design_span:
                    design_span.set_attribute("phase", "designing")
                    design_result = await self._run_child(...)
                    design_span.set_attribute("strategy_name", design_result.get("strategy_name"))
                    design_span.set_attribute("tokens", design_result.get("input_tokens", 0) + design_result.get("output_tokens", 0))

                # Training phase
                with tracer.start_as_current_span("agent.phase.training") as train_span:
                    train_span.set_attribute("phase", "training")
                    training_result = await self._run_child(...)
                    train_span.set_attribute("accuracy", training_result.get("accuracy"))

                    passed, reason = check_training_gate(training_result)
                    train_span.set_attribute("gate.passed", passed)
                    train_span.set_attribute("gate.reason", reason)

                # ... similar for other phases ...

                span.set_attribute("outcome", "completed")
                return result

            except Exception as e:
                span.set_attribute("outcome", "failed")
                span.set_attribute("error", str(e))
                span.record_exception(e)
                raise
```

**Acceptance Criteria**:
- [ ] Parent span for full cycle
- [ ] Child spans for each phase
- [ ] Spans visible in Jaeger
- [ ] operation.id attribute on all spans

---

## Task 7.6: Create Grafana Dashboard

**File(s)**: `docker/grafana/dashboards/agent.json`
**Type**: CODING

**Description**: Create Grafana dashboard for agent metrics.

**Implementation Notes**:
```json
{
  "title": "Agent Research Cycles",
  "panels": [
    {
      "title": "Cycles per Hour",
      "type": "graph",
      "targets": [
        {"expr": "rate(agent_cycles_total[1h])"}
      ]
    },
    {
      "title": "Cycle Outcomes",
      "type": "piechart",
      "targets": [
        {"expr": "sum by (outcome) (agent_cycles_total)"}
      ]
    },
    {
      "title": "Average Cycle Duration",
      "type": "stat",
      "targets": [
        {"expr": "histogram_quantile(0.5, rate(agent_cycle_duration_seconds_bucket[1h]))"}
      ]
    },
    {
      "title": "Phase Durations",
      "type": "heatmap",
      "targets": [
        {"expr": "rate(agent_phase_duration_seconds_bucket[1h])"}
      ]
    },
    {
      "title": "Gate Pass Rate",
      "type": "gauge",
      "targets": [
        {"expr": "sum(agent_gate_results_total{result=\"pass\"}) / sum(agent_gate_results_total) * 100"}
      ]
    },
    {
      "title": "Token Usage",
      "type": "graph",
      "targets": [
        {"expr": "rate(agent_tokens_total[1h])"}
      ]
    },
    {
      "title": "Daily Budget",
      "type": "gauge",
      "targets": [
        {"expr": "agent_budget_remaining_dollars"}
      ]
    }
  ]
}
```

**Acceptance Criteria**:
- [ ] Dashboard auto-provisioned
- [ ] All metrics visualized
- [ ] Time range selectable

---

## Milestone 7 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M7: Budget & Observability Verification ==="

# 1. Check budget endpoint works
echo "1. Testing budget endpoint..."
BUDGET=$(curl -s http://localhost:8000/api/v1/agent/budget)
LIMIT=$(echo $BUDGET | jq -r '.daily_limit')
SPEND=$(echo $BUDGET | jq -r '.today_spend')
REMAINING=$(echo $BUDGET | jq -r '.remaining')

if [ "$LIMIT" == "null" ]; then
    echo "   FAIL: Budget endpoint not working"
    exit 1
fi
echo "   PASS: Budget endpoint works"
echo "   Limit: \$$LIMIT, Spend: \$$SPEND, Remaining: \$$REMAINING"

# 2. Check metrics endpoint has agent metrics
echo ""
echo "2. Testing Prometheus metrics..."
METRICS=$(curl -s http://localhost:8000/metrics)

if echo "$METRICS" | grep -q "agent_cycles_total"; then
    echo "   PASS: agent_cycles_total found"
else
    echo "   WARN: agent_cycles_total not found (may need a cycle first)"
fi

if echo "$METRICS" | grep -q "agent_phase_duration_seconds"; then
    echo "   PASS: agent_phase_duration_seconds found"
else
    echo "   WARN: agent_phase_duration_seconds not found"
fi

# 3. Run a cycle and verify budget updates
echo ""
echo "3. Running cycle to test budget tracking..."
BEFORE=$(curl -s http://localhost:8000/api/v1/agent/budget | jq '.today_spend')
echo "   Spend before: \$$BEFORE"

# Trigger (use stubs for speed if no API key)
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')

if [ "$OP_ID" == "null" ]; then
    REASON=$(echo $RESULT | jq -r '.reason')
    if [ "$REASON" == "budget_exhausted" ]; then
        echo "   PASS: Budget enforcement working (exhausted)"
    else
        echo "   Could not trigger: $REASON"
    fi
else
    echo "   Cycle started: $OP_ID"

    # Wait for completion
    for i in {1..60}; do
        STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
        if [ "$(echo $STATUS | jq -r '.status')" == "idle" ]; then
            break
        fi
        sleep 2
    done

    AFTER=$(curl -s http://localhost:8000/api/v1/agent/budget | jq '.today_spend')
    echo "   Spend after: \$$AFTER"

    if [ "$AFTER" != "$BEFORE" ]; then
        echo "   PASS: Budget updated after cycle"
    else
        echo "   WARN: Budget not updated (may be using stubs)"
    fi
fi

# 4. Check Jaeger has traces
echo ""
echo "4. Checking Jaeger traces..."
TRACES=$(curl -s "http://localhost:16686/api/traces?service=ktrdr-backend&limit=5" 2>/dev/null | jq '.data | length' 2>/dev/null || echo "0")
if [ "$TRACES" -gt 0 ]; then
    echo "   PASS: Found $TRACES recent traces in Jaeger"
else
    echo "   WARN: No traces found (Jaeger may not be running)"
fi

# 5. Test CLI budget command
echo ""
echo "5. Testing CLI budget command..."
ktrdr agent budget
echo "   PASS: CLI budget works"

# 6. Test budget exhaustion
echo ""
echo "6. Testing budget exhaustion..."
# This would require setting a very low budget, skipping in automated test
echo "   SKIP: Manual test required (set AGENT_DAILY_BUDGET=0.01)"

# 7. Check Grafana dashboard exists
echo ""
echo "7. Checking Grafana..."
GRAFANA_STATUS=$(curl -s http://localhost:3000/api/health 2>/dev/null | jq -r '.database' 2>/dev/null || echo "down")
if [ "$GRAFANA_STATUS" == "ok" ]; then
    echo "   PASS: Grafana is running"
    echo "   Dashboard URL: http://localhost:3000/d/agent-research"
else
    echo "   WARN: Grafana not responding"
fi

echo ""
echo "=== M7 Complete ==="
echo ""
echo "Manual verification steps:"
echo "1. Open Grafana: http://localhost:3000"
echo "2. Find 'Agent Research Cycles' dashboard"
echo "3. Verify metrics are populated after running cycles"
echo "4. Open Jaeger: http://localhost:16686"
echo "5. Search for service=ktrdr-backend"
echo "6. Find agent.research_cycle spans"
```

---

## Files Created/Modified in M7

**New files**:
```
ktrdr/agents/budget.py
ktrdr/agents/metrics.py
docker/grafana/dashboards/agent.json
tests/unit/agent_tests/test_budget.py
```

**Modified files**:
```
ktrdr/api/endpoints/agent.py             # Add budget endpoint
ktrdr/api/services/agent_service.py      # Add budget check and recording
ktrdr/cli/agent_commands.py              # Add budget command
ktrdr/agents/workers/research_worker.py  # Add metrics and tracing
```

---

*Estimated effort: ~4-5 hours*
