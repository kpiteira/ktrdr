# Phase 4: Polish (Budget, Observability, Robustness)

**Goal**: Production-ready agent with budget enforcement, metrics, and robust error handling

**Prerequisite**: Phase 3 complete (full real cycle working)
**Branch**: `feature/agent-mvp`

---

## Overview

Phase 4 adds polish for production use:
1. **Budget enforcement** - Track tokens, prevent overspending
2. **Observability** - Traces, metrics, dashboard
3. **Error handling** - Robust handling of edge cases
4. **CLI polish** - Better status display

---

## Task 4.1: Implement budget tracking

Track token usage per invocation and daily budget.

**File**: `ktrdr/agents/budget.py` (new file)

```python
"""
Agent budget tracking and enforcement.

Tracks token usage per invocation and enforces daily spending limits.
Uses file-based storage for simplicity (persists across restarts).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktrdr import get_logger

logger = get_logger(__name__)

# Default budget (can be overridden via environment)
DEFAULT_DAILY_TOKEN_BUDGET = 500_000  # ~$15/day at Opus pricing
BUDGET_FILE = Path("data/agent_budget.json")


def get_budget_status() -> dict[str, Any]:
    """Get current budget status.

    Returns:
        Dict with:
        - daily_budget: int - daily token limit
        - tokens_used_today: int - tokens used so far today
        - tokens_remaining: int - tokens available
        - budget_available: bool - whether budget is available
        - reset_date: str - when budget was last reset (ISO format)
    """
    import os

    daily_budget = int(os.getenv("AGENT_DAILY_TOKEN_BUDGET", DEFAULT_DAILY_TOKEN_BUDGET))
    budget_data = _load_budget_data()

    # Check if we need to reset (new day)
    today = datetime.now(timezone.utc).date().isoformat()
    if budget_data.get("reset_date") != today:
        budget_data = {"reset_date": today, "tokens_used": 0, "invocations": []}
        _save_budget_data(budget_data)

    tokens_used = budget_data.get("tokens_used", 0)
    tokens_remaining = max(0, daily_budget - tokens_used)

    return {
        "daily_budget": daily_budget,
        "tokens_used_today": tokens_used,
        "tokens_remaining": tokens_remaining,
        "budget_available": tokens_remaining > 0,
        "reset_date": budget_data.get("reset_date"),
        "invocations_today": len(budget_data.get("invocations", [])),
    }


def check_budget_available(estimated_tokens: int = 10_000) -> tuple[bool, str]:
    """Check if budget is available for an invocation.

    Args:
        estimated_tokens: Estimated tokens for the invocation (default 10k)

    Returns:
        Tuple of (available: bool, reason: str)
    """
    status = get_budget_status()

    if not status["budget_available"]:
        return False, f"Daily budget exhausted ({status['tokens_used_today']} used of {status['daily_budget']})"

    if status["tokens_remaining"] < estimated_tokens:
        return False, f"Insufficient budget ({status['tokens_remaining']} remaining, need {estimated_tokens})"

    return True, "budget_available"


def record_token_usage(
    input_tokens: int,
    output_tokens: int,
    operation_id: str | None = None,
    phase: str | None = None,
) -> None:
    """Record token usage for an invocation.

    Args:
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        operation_id: Optional operation ID for tracking
        phase: Optional phase name (design, assessment)
    """
    budget_data = _load_budget_data()

    # Ensure today's data
    today = datetime.now(timezone.utc).date().isoformat()
    if budget_data.get("reset_date") != today:
        budget_data = {"reset_date": today, "tokens_used": 0, "invocations": []}

    total_tokens = input_tokens + output_tokens
    budget_data["tokens_used"] = budget_data.get("tokens_used", 0) + total_tokens

    # Record invocation details
    invocations = budget_data.get("invocations", [])
    invocations.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "operation_id": operation_id,
        "phase": phase,
    })
    budget_data["invocations"] = invocations

    _save_budget_data(budget_data)

    logger.info(
        f"Recorded token usage: {total_tokens} tokens "
        f"(daily total: {budget_data['tokens_used']})"
    )


def _load_budget_data() -> dict[str, Any]:
    """Load budget data from file."""
    if not BUDGET_FILE.exists():
        return {}

    try:
        with open(BUDGET_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load budget data: {e}")
        return {}


def _save_budget_data(data: dict[str, Any]) -> None:
    """Save budget data to file."""
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BUDGET_FILE, "w") as f:
        json.dump(data, f, indent=2)
```

**Test file**: `tests/unit/agents/test_budget.py`

```python
import pytest
import json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone

from ktrdr.agents.budget import (
    get_budget_status,
    check_budget_available,
    record_token_usage,
)


class TestBudget:
    """Tests for budget tracking."""

    @pytest.fixture
    def temp_budget_file(self, tmp_path):
        """Use temp file for budget data."""
        budget_file = tmp_path / "agent_budget.json"
        with patch("ktrdr.agents.budget.BUDGET_FILE", budget_file):
            yield budget_file

    def test_get_budget_status_new_day(self, temp_budget_file):
        """Should reset budget on new day."""
        # Write yesterday's data
        yesterday = "2024-01-01"
        temp_budget_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_budget_file, "w") as f:
            json.dump({"reset_date": yesterday, "tokens_used": 100000}, f)

        with patch("ktrdr.agents.budget.BUDGET_FILE", temp_budget_file):
            status = get_budget_status()

        # Should have reset
        assert status["tokens_used_today"] == 0
        assert status["budget_available"] is True

    def test_check_budget_exhausted(self, temp_budget_file):
        """Should reject when budget exhausted."""
        today = datetime.now(timezone.utc).date().isoformat()
        temp_budget_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_budget_file, "w") as f:
            json.dump({"reset_date": today, "tokens_used": 500_000}, f)

        with patch("ktrdr.agents.budget.BUDGET_FILE", temp_budget_file):
            available, reason = check_budget_available()

        assert available is False
        assert "exhausted" in reason

    def test_record_token_usage(self, temp_budget_file):
        """Should accumulate token usage."""
        temp_budget_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("ktrdr.agents.budget.BUDGET_FILE", temp_budget_file):
            record_token_usage(input_tokens=1000, output_tokens=500)
            record_token_usage(input_tokens=2000, output_tokens=1000)

            status = get_budget_status()

        assert status["tokens_used_today"] == 4500  # 1000+500+2000+1000
        assert status["invocations_today"] == 2
```

---

## Task 4.2: Wire budget into AgentService

**File**: `ktrdr/api/services/agent_service.py`

Add budget check to trigger:

```python
async def trigger(self) -> dict[str, Any]:
    """Start a new research cycle.

    Returns:
        Dict with triggered status and operation_id or rejection reason.
    """
    from ktrdr.agents.budget import check_budget_available, get_budget_status

    # Check budget first
    budget_ok, budget_reason = check_budget_available()
    if not budget_ok:
        budget_status = get_budget_status()
        return {
            "triggered": False,
            "reason": "budget_exhausted",
            "message": budget_reason,
            "tokens_used_today": budget_status["tokens_used_today"],
            "tokens_remaining": budget_status["tokens_remaining"],
        }

    # Check for active cycle
    active = await self._get_active_operation()
    if active:
        return {
            "triggered": False,
            "reason": "active_operation_exists",
            "operation_id": active.operation_id,
        }

    # Create and start operation
    # ... rest of existing trigger code
```

Also record token usage after each invocation:

```python
async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
    """Run Claude to design a strategy."""
    from ktrdr.agents.budget import record_token_usage

    # ... existing design phase code ...

    result = await self._invoker.invoke(prompt)

    # Record token usage
    record_token_usage(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        operation_id=operation_id,
        phase="design",
    )

    # ... rest of method


async def _run_assessment_phase(self, ...) -> dict[str, Any]:
    """Run Claude to assess the results."""
    from ktrdr.agents.budget import record_token_usage

    # ... existing assessment phase code ...

    result = await invoker.invoke(prompt)

    # Record token usage
    record_token_usage(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        operation_id=operation_id,
        phase="assessment",
    )

    # ... rest of method
```

---

## Task 4.3: Add agent metrics

**File**: `ktrdr/monitoring/metrics.py`

Add agent-specific metrics:

```python
# Agent metrics
agent_cycles_total = Counter(
    "ktrdr_agent_cycles_total",
    "Total agent research cycles",
    ["outcome"],  # completed, failed, cancelled
)

agent_cycle_duration_seconds = Histogram(
    "ktrdr_agent_cycle_duration_seconds",
    "Agent cycle duration distribution",
    ["outcome"],
    buckets=[60, 120, 300, 600, 1200, 1800, 3600, 7200],  # 1min to 2hr
)

agent_phase_duration_seconds = Histogram(
    "ktrdr_agent_phase_duration_seconds",
    "Agent phase duration distribution",
    ["phase"],  # designing, training, backtesting, assessing
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800],
)

agent_tokens_total = Counter(
    "ktrdr_agent_tokens_total",
    "Total tokens used by agent",
    ["token_type"],  # input, output
)

agent_gate_results = Counter(
    "ktrdr_agent_gate_results",
    "Quality gate results",
    ["gate", "result"],  # gate: training/backtest, result: passed/failed
)
```

---

## Task 4.4: Wire metrics into AgentService

**File**: `ktrdr/api/services/agent_service.py`

Add metrics recording:

```python
import time
from ktrdr.monitoring.metrics import (
    agent_cycles_total,
    agent_cycle_duration_seconds,
    agent_phase_duration_seconds,
    agent_tokens_total,
    agent_gate_results,
)


async def _run_research_cycle(self, operation_id: str) -> None:
    """Execute a research cycle with metrics."""
    cycle_start = time.time()
    outcome = "failed"  # Default, updated on success/cancel

    try:
        # Phase 1: Design
        phase_start = time.time()
        await self._update_phase(operation_id, "designing")
        design_result = await self._run_design_phase(operation_id)
        agent_phase_duration_seconds.labels(phase="designing").observe(
            time.time() - phase_start
        )

        if not design_result.get("success"):
            await self._ops.fail_operation(...)
            return

        # Record tokens
        if "input_tokens" in design_result:
            agent_tokens_total.labels(token_type="input").inc(
                design_result["input_tokens"]
            )
            agent_tokens_total.labels(token_type="output").inc(
                design_result["output_tokens"]
            )

        # Phase 2: Training
        phase_start = time.time()
        await self._update_phase(operation_id, "training")
        train_result = await self._run_training_phase(...)
        agent_phase_duration_seconds.labels(phase="training").observe(
            time.time() - phase_start
        )

        if not train_result.get("success"):
            await self._ops.fail_operation(...)
            return

        # Check training gate and record result
        gate_passed, gate_reason = self._check_training_gate(train_result)
        agent_gate_results.labels(
            gate="training",
            result="passed" if gate_passed else "failed"
        ).inc()

        if not gate_passed:
            await self._ops.fail_operation(...)
            return

        # Phase 3: Backtest (similar pattern)
        phase_start = time.time()
        await self._update_phase(operation_id, "backtesting")
        backtest_result = await self._run_backtest_phase(...)
        agent_phase_duration_seconds.labels(phase="backtesting").observe(
            time.time() - phase_start
        )

        # ... backtest gate check with metrics ...

        # Phase 4: Assessment
        phase_start = time.time()
        await self._update_phase(operation_id, "assessing")
        assessment = await self._run_assessment_phase(...)
        agent_phase_duration_seconds.labels(phase="assessing").observe(
            time.time() - phase_start
        )

        # Success!
        outcome = "completed"
        await self._ops.complete_operation(...)

    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except Exception as e:
        outcome = "failed"
        raise
    finally:
        # Record cycle metrics
        duration = time.time() - cycle_start
        agent_cycles_total.labels(outcome=outcome).inc()
        agent_cycle_duration_seconds.labels(outcome=outcome).observe(duration)
```

---

## Task 4.5: Add OTEL tracing

**File**: `ktrdr/api/services/agent_service.py`

Add trace spans:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


async def _run_research_cycle(self, operation_id: str) -> None:
    """Execute a research cycle with tracing."""
    with tracer.start_as_current_span("agent.research_cycle") as cycle_span:
        cycle_span.set_attribute("operation.id", operation_id)

        try:
            # Phase 1: Design
            with tracer.start_as_current_span("agent.phase.design") as span:
                span.set_attribute("phase", "designing")
                design_result = await self._run_design_phase(operation_id)

                if design_result.get("strategy_name"):
                    span.set_attribute("strategy.name", design_result["strategy_name"])
                if "input_tokens" in design_result:
                    span.set_attribute("tokens.input", design_result["input_tokens"])
                    span.set_attribute("tokens.output", design_result["output_tokens"])

            # Phase 2: Training
            with tracer.start_as_current_span("agent.phase.training") as span:
                span.set_attribute("phase", "training")
                train_result = await self._run_training_phase(...)

                if train_result.get("accuracy"):
                    span.set_attribute("training.accuracy", train_result["accuracy"])
                if train_result.get("final_loss"):
                    span.set_attribute("training.final_loss", train_result["final_loss"])

            # Check gate
            gate_passed, gate_reason = self._check_training_gate(train_result)
            cycle_span.set_attribute("gate.training.passed", gate_passed)
            cycle_span.set_attribute("gate.training.reason", gate_reason)

            # Phase 3: Backtest
            with tracer.start_as_current_span("agent.phase.backtest") as span:
                span.set_attribute("phase", "backtesting")
                backtest_result = await self._run_backtest_phase(...)

                if backtest_result.get("win_rate"):
                    span.set_attribute("backtest.win_rate", backtest_result["win_rate"])
                if backtest_result.get("sharpe_ratio"):
                    span.set_attribute("backtest.sharpe", backtest_result["sharpe_ratio"])

            # Phase 4: Assessment
            with tracer.start_as_current_span("agent.phase.assessment") as span:
                span.set_attribute("phase", "assessing")
                assessment = await self._run_assessment_phase(...)
                span.set_attribute("assessment.verdict", assessment.get("verdict", "unknown"))

            cycle_span.set_attribute("outcome", "completed")

        except asyncio.CancelledError:
            cycle_span.set_attribute("outcome", "cancelled")
            raise
        except Exception as e:
            cycle_span.set_attribute("outcome", "failed")
            cycle_span.set_attribute("error.message", str(e))
            cycle_span.record_exception(e)
            raise
```

---

## Task 4.6: Error handling improvements

**File**: `ktrdr/api/services/agent_service.py`

Add robust error handling:

```python
class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class AnthropicTimeoutError(AgentError):
    """Anthropic API timed out."""
    pass


class TrainingServiceError(AgentError):
    """Training service unavailable or failed."""
    pass


class BacktestServiceError(AgentError):
    """Backtest service unavailable or failed."""
    pass


async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
    """Run Claude to design a strategy with error handling."""
    try:
        result = await asyncio.wait_for(
            self._invoker.invoke(prompt),
            timeout=120.0,  # 2 minute timeout
        )
    except asyncio.TimeoutError:
        logger.error("Anthropic API timed out during design phase")
        return {
            "success": False,
            "error": "anthropic_timeout",
            "message": "Claude API timed out after 120 seconds",
        }
    except Exception as e:
        logger.error(f"Design phase failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": "design_error",
            "message": str(e),
        }

    if not result.success:
        return {
            "success": False,
            "error": "anthropic_error",
            "message": result.error or "Unknown error",
        }

    return {
        "success": True,
        "strategy_name": result.tool_outputs.get("strategy_name"),
        "strategy_path": result.tool_outputs.get("strategy_path"),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }


async def _poll_training_completion(self, ...) -> dict[str, Any]:
    """Poll training with connection error handling."""
    import httpx

    consecutive_errors = 0
    max_consecutive_errors = 5

    async with httpx.AsyncClient(timeout=30.0) as client:
        for poll_count in range(max_polls):
            try:
                response = await client.get(url)
                response.raise_for_status()
                consecutive_errors = 0  # Reset on success

                # ... process response ...

            except httpx.ConnectError:
                consecutive_errors += 1
                logger.warning(
                    f"Training service connection failed "
                    f"({consecutive_errors}/{max_consecutive_errors})"
                )
                if consecutive_errors >= max_consecutive_errors:
                    return {
                        "success": False,
                        "error": "training_service_unavailable",
                        "message": "Could not connect to training service",
                    }
                await asyncio.sleep(poll_interval * 2)  # Longer wait on error
                continue

            except httpx.TimeoutException:
                logger.warning("Training status poll timed out")
                await asyncio.sleep(poll_interval)
                continue

            except Exception as e:
                logger.error(f"Unexpected error polling training: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    return {"success": False, "error": str(e)}
                await asyncio.sleep(poll_interval)
                continue

            await asyncio.sleep(poll_interval)
```

---

## Task 4.7: CLI status improvements

**File**: `ktrdr/cli/agent_commands.py`

Improve status display:

```python
async def _status_async(verbose: bool = False):
    """Get and display agent status."""
    async with AsyncCLIClient() as client:
        result = await client.get("/agent/status")

    if result.get("status") == "idle":
        console.print("\n[dim]No active research cycle[/dim]")

        # Show budget status
        budget = result.get("budget", {})
        if budget:
            used = budget.get("tokens_used_today", 0)
            remaining = budget.get("tokens_remaining", 0)
            total = budget.get("daily_budget", 0)
            pct = (used / total * 100) if total > 0 else 0

            console.print(f"\n[bold]Budget Status[/bold]")
            console.print(f"  Used today: {used:,} tokens ({pct:.1f}%)")
            console.print(f"  Remaining: {remaining:,} tokens")
        return

    # Active cycle
    op = result.get("operation", {})
    console.print(f"\n[bold green]Active Research Cycle[/bold green]")
    console.print(f"  Operation: {op.get('id', 'unknown')}")
    console.print(f"  Phase: [cyan]{op.get('phase', 'unknown')}[/cyan]")

    progress = op.get("progress", {})
    pct = progress.get("percentage", 0)
    step = progress.get("current_step", "")

    # Progress bar
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    console.print(f"  Progress: [{bar}] {pct:.0f}%")

    if step:
        console.print(f"  Step: {step}")

    if op.get("strategy_name"):
        console.print(f"  Strategy: {op['strategy_name']}")

    if verbose:
        metadata = op.get("metadata", {})
        if metadata.get("training_result"):
            train = metadata["training_result"]
            console.print(f"\n  [bold]Training Result[/bold]")
            if train.get("accuracy"):
                console.print(f"    Accuracy: {train['accuracy']:.1%}")
            if train.get("final_loss"):
                console.print(f"    Final Loss: {train['final_loss']:.4f}")

        if metadata.get("backtest_result"):
            bt = metadata["backtest_result"]
            console.print(f"\n  [bold]Backtest Result[/bold]")
            if bt.get("win_rate"):
                console.print(f"    Win Rate: {bt['win_rate']:.1%}")
            if bt.get("sharpe_ratio"):
                console.print(f"    Sharpe: {bt['sharpe_ratio']:.2f}")
```

---

## Task 4.8: Add budget endpoint to API

**File**: `ktrdr/api/endpoints/agent.py`

```python
@router.get("/budget")
async def get_budget_status():
    """Get current agent budget status.

    Returns budget information including daily limit, usage, and availability.
    """
    from ktrdr.agents.budget import get_budget_status

    status = get_budget_status()
    return {"success": True, "data": status}
```

---

## Phase 4 Verification

### Manual Test Sequence

```bash
# 1. Check budget before starting
ktrdr agent status
# Expected: Shows budget status

# 2. Run a cycle and verify metrics
ktrdr agent trigger
# Watch Grafana: http://localhost:3000

# 3. Check traces in Jaeger
# Open http://localhost:16686
# Search for service: ktrdr-backend
# Look for agent.research_cycle trace

# 4. Test budget exhaustion
# Set low budget: AGENT_DAILY_TOKEN_BUDGET=1000
# Trigger cycle, should fail with budget_exhausted

# 5. Test error handling
# Stop training service, trigger cycle
# Should fail gracefully with training_service_unavailable

# 6. Verify metrics in Prometheus
curl http://localhost:8000/metrics | grep ktrdr_agent
# Expected: agent_cycles_total, agent_phase_duration_seconds, etc.
```

### Acceptance Criteria

- [ ] Budget prevents overspending
- [ ] Token usage tracked per invocation
- [ ] Budget resets daily
- [ ] `/agent/status` shows budget info
- [ ] Cycle traces appear in Jaeger
- [ ] Metrics visible in Prometheus/Grafana
- [ ] Anthropic timeout handled gracefully
- [ ] Training service unavailable handled gracefully
- [ ] Progress bar shows in CLI status

---

## Files Created/Modified Summary

| File | Action |
|------|--------|
| `ktrdr/agents/budget.py` | Create new |
| `ktrdr/api/services/agent_service.py` | Modify - add budget, metrics, tracing |
| `ktrdr/monitoring/metrics.py` | Modify - add agent metrics |
| `ktrdr/api/endpoints/agent.py` | Modify - add /budget endpoint |
| `ktrdr/cli/agent_commands.py` | Modify - improve status display |
| `tests/unit/agents/test_budget.py` | Create new |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_DAILY_TOKEN_BUDGET` | 500000 | Daily token limit |
| `KTRDR_API_URL` | http://localhost:8000 | Backend URL for polling |

---

## Grafana Dashboard Additions

Add to existing dashboard or create `agent.json`:

```json
{
  "panels": [
    {
      "title": "Research Cycles",
      "type": "stat",
      "targets": [
        {"expr": "sum(ktrdr_agent_cycles_total)"}
      ]
    },
    {
      "title": "Cycle Outcomes",
      "type": "piechart",
      "targets": [
        {"expr": "ktrdr_agent_cycles_total", "legendFormat": "{{outcome}}"}
      ]
    },
    {
      "title": "Phase Durations",
      "type": "histogram",
      "targets": [
        {"expr": "ktrdr_agent_phase_duration_seconds_bucket", "legendFormat": "{{phase}}"}
      ]
    },
    {
      "title": "Gate Pass Rates",
      "type": "gauge",
      "targets": [
        {"expr": "sum(ktrdr_agent_gate_results{result='passed'}) / sum(ktrdr_agent_gate_results) * 100"}
      ]
    },
    {
      "title": "Token Usage",
      "type": "timeseries",
      "targets": [
        {"expr": "rate(ktrdr_agent_tokens_total[1h])", "legendFormat": "{{token_type}}"}
      ]
    }
  ]
}
```

---

## Definition of Done (MVP)

The MVP is complete when all phases pass their acceptance criteria:

1. ✅ **Phase 1**: Design-only cycle works (trigger → design → save → complete)
2. ✅ **Phase 2**: Training integration (design → train → gate check)
3. ✅ **Phase 3**: Full cycle (design → train → backtest → assess → complete)
4. ✅ **Phase 4**: Production polish (budget, metrics, tracing, error handling)

Plus:
- [ ] All tests pass
- [ ] No session database code remains
- [ ] Documentation updated
- [ ] Grafana dashboard shows agent metrics
- [ ] Traces visible in Jaeger
