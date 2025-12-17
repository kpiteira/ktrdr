# Design Validation: Sandbox & Orchestrator

**Date:** 2025-12-16
**Documents Validated:**
- Design: [DESIGN.md](DESIGN.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Scope: Full MVP (Phases 1-5)

---

## Validation Summary

**Scenarios Validated:** 8 scenarios traced
**Critical Gaps Found:** 4 (all resolved)
**Interface Contracts:** Defined for LoopDetector, API retry, Lock file, Configuration

---

## Key Decisions Made

These decisions came from our validation conversation and should inform implementation:

### Decision 1: Loop Detection Over Cost Limits

**Context:** Original concern was runaway costs from Claude looping.

**Decision:** Detect loops via attempt counting and error similarity, not cost caps.

**Rationale:** Karl uses Claude Max ($100/month) so per-API-call billing isn't the concern. The real risk is the system burning time/usage without making progress. Loop detection catches this directly.

**Implementation:**
- `MAX_TASK_ATTEMPTS = 3` — Same task fails 3 times → stop
- `MAX_E2E_FIX_ATTEMPTS = 5` — E2E fix cycle 5 times → stop (catches oscillations)
- Error similarity matching (>80%) to detect "same error, different words"
- All limits configurable for tuning

---

### Decision 2: Long API Retry Backoff

**Context:** Anthropic API outages happen and can last 10-30 minutes.

**Decision:** Exponential backoff with delays: 30s → 60s → 120s → 300s → 600s (total ~18 min before giving up).

**Rationale:** Short retries (seconds) don't help with real outages. Better to wait longer and recover automatically than escalate for temporary issues.

**Trade-off accepted:** A stuck API means ~18 minutes before human notification. Acceptable given outages are temporary.

---

### Decision 3: Simple Lock File for Concurrency

**Context:** Two orchestrator processes on same milestone would corrupt state.

**Decision:** Simple PID-based lock file. Check if PID exists, acquire if stale.

**Rationale:** Concurrent launch is unlikely (user error). Simple solution is sufficient. No need for robust distributed locking.

---

### Decision 4: `--max-turns` as Stuck Detection (MVP)

**Context:** How to detect Claude is stuck vs. legitimately working on a hard task?

**Decision:** Use `--max-turns 50` as the backstop for MVP. Don't implement activity monitoring.

**Rationale:** Activity monitoring (streaming output, parsing progress) adds complexity. 50 turns is a reasonable upper bound. If Claude uses all 50 and fails, that's the signal to escalate.

**Future:** Revisit streaming/activity monitoring in v2 if needed.

---

### Decision 5: Telemetry From Day One

**Context:** Should telemetry be a final polish phase or woven in?

**Decision:** Telemetry is acceptance criteria for every milestone after sandbox setup.

**Rationale:** Observability built-in is better than bolted-on. Each milestone adds telemetry for its functionality, with documentation on how to view it.

---

## Scenarios Traced

### Happy Paths
1. **Full Milestone Completion** — All tasks succeed, E2E passes (validated by design doc)
2. **Human Guidance Flow** — Task needs input → Karl provides → continues (validated)
3. **E2E Diagnose-and-Fix** — E2E fails → Claude fixes → re-run passes (validated)

### Error Paths
4. **Anthropic API Outage** — 503s repeatedly → long backoff → recover or escalate
   - Gap found: Original backoff too short
   - Resolution: 30s → 10m backoff schedule

5. **Task Stuck Detection** — Claude produces nothing for extended period
   - Resolution: Use `--max-turns` as backstop for MVP

### Edge Cases
6. **Human Guidance Doesn't Help** — Guidance provided, retry fails same way
   - Handled by: `MAX_TASK_ATTEMPTS = 3`

7. **Concurrent Orchestrator Launch** — Two processes, same milestone
   - Gap found: No concurrency protection
   - Resolution: Simple PID lock file

8. **E2E Fix Creates New Bug** — Fix A → breaks B → fix B → breaks A (oscillation)
   - Gap found: Simple "same error 3x" misses oscillations
   - Resolution: Hard cap of 5 total E2E attempts

### Critical Safety
9. **Runaway Cost Prevention** — Claude loops, burning usage without progress
   - Gap found: No loop detection in original design
   - Resolution: LoopDetector component with attempt limits and error similarity

---

## Scenarios Added by Karl

These scenarios weren't in the initial enumeration but proved important:

1. **Runaway cost/infinite loop** — "The orchestrator or Claude Code going on a frenzy and spending all my money." This reframed the entire cost discussion from "limits" to "loop detection."

---

## Remaining Open Questions

To be resolved during implementation:

1. **Detection tuning**: What keyword patterns best detect "needs human"? (from original design doc)
2. **Error similarity threshold**: Is 80% the right threshold? May need tuning based on real errors.
3. **Timeout values**: Exact timeout for `docker exec` invocations (10 min proposed, may adjust).

---

## Recommended Milestone Structure

| Milestone | Deliverable | Telemetry | E2E Testable |
|-----------|-------------|-----------|--------------|
| **M1** | Sandbox | — | Claude runs isolated, resets clean |
| **M2** | Single task | Task traces, basic metrics | One task executes, trace in Jaeger |
| **M3** | Task loop + state | Milestone traces, histograms | Full milestone, resume, trace hierarchy |
| **M4** | Escalation + loops | Escalation spans, loop metrics | Human input works, loops detected |
| **M5** | E2E + dashboard | E2E traces, Grafana dashboard | E2E runs/fixes, dashboard shows all |

### Milestone Details

#### M1: Sandbox Works
- `deploy/sandbox/Dockerfile`
- `deploy/docker-compose.sandbox.yml`
- `scripts/sandbox-{init,reset,claude}.sh`
- **Test:** Claude runs in sandbox, reset works

#### M2: Single Task + Telemetry Foundation
- `orchestrator/{models,sandbox,task_runner,cli,plan_parser,telemetry}.py`
- Traces: `orchestrator.task` span
- Metrics: `tasks_total`, `tokens_total`, `cost_usd_total`
- **Test:** Task executes, trace visible in Jaeger

#### M3: Task Loop + State + Milestone Tracing
- `orchestrator/{state,lock}.py`
- CLI commands: `run`, `resume`
- Traces: `orchestrator.milestone` parent span
- Metrics: `task_duration_seconds` histogram
- **Test:** Full milestone runs, resume works, trace hierarchy visible

#### M4: Escalation + Loop Detection
- `orchestrator/{escalation,loop_detector}.py`
- macOS notifications
- Traces: `orchestrator.escalation`, `orchestrator.loop_detected`
- Metrics: `escalations_total`, `loops_detected_total`
- **Test:** Human input flow works, loops stop execution

#### M5: E2E Integration + Full Dashboard
- `orchestrator/e2e_runner.py`
- `deploy/shared/grafana/dashboards/orchestrator.json`
- Traces: `orchestrator.e2e_test`, `orchestrator.e2e_fix`
- Metrics: `e2e_tests_total`, `e2e_fix_attempts_total`
- **Test:** E2E runs, fixes work, Grafana dashboard complete

---

## Interface Contracts

### LoopDetector

```python
@dataclass
class LoopDetectorConfig:
    max_task_attempts: int = 3
    max_e2e_fix_attempts: int = 5
    error_similarity_threshold: float = 0.8

class LoopDetector:
    def record_task_failure(self, task_id: str, error: str) -> None: ...
    def record_e2e_failure(self, error: str) -> None: ...
    def should_stop_task(self, task_id: str) -> tuple[bool, str]: ...
    def should_stop_e2e(self) -> tuple[bool, str]: ...
    def reset_e2e(self) -> None: ...
```

### API Error Handling

```python
API_RETRY_DELAYS = [30, 60, 120, 300, 600]  # seconds

def is_api_error(result: ClaudeResult) -> bool:
    """Distinguish API errors (retry) from task errors (diagnose)."""
    api_patterns = ["503", "rate limit", "overloaded", "unavailable"]
    return result.is_error and any(p in result.result.lower() for p in api_patterns)
```

### Lock File

```python
class MilestoneLock:
    def acquire(self) -> bool:
        """Try to acquire. Returns False if already held by running process."""
    def release(self) -> None:
        """Release the lock."""
```

### Configuration

```python
@dataclass
class OrchestratorConfig:
    # Claude Code
    max_turns: int = 50
    task_timeout_seconds: int = 600

    # Loop detection (configurable for tuning)
    max_task_attempts: int = 3
    max_e2e_fix_attempts: int = 5
    error_similarity_threshold: float = 0.8

    # API retry
    api_retry_delays: list[int] = [30, 60, 120, 300, 600]
```

### Updated State Structure

```python
@dataclass
class OrchestratorState:
    milestone_id: str
    plan_path: str
    started_at: datetime
    current_task_index: int
    completed_tasks: list[str]
    failed_tasks: list[str]
    task_results: dict[str, TaskResult]

    # Loop detection state
    task_attempt_counts: dict[str, int]
    task_errors: dict[str, list[str]]
    e2e_attempt_count: int
    e2e_errors: list[str]

    e2e_status: str | None
```

---

## Telemetry Reference

### Trace Hierarchy

```
orchestrator.milestone (M4)
├── orchestrator.sandbox_reset
│   └── duration_seconds
├── orchestrator.task (4.1)
│   └── task.id, claude.tokens, claude.cost_usd, task.status
├── orchestrator.task (4.2)
│   └── ...
├── orchestrator.escalation (if needed)
│   └── question, wait_seconds, response
├── orchestrator.e2e_test
│   └── status, diagnosis
├── orchestrator.e2e_fix (if needed)
│   └── fix_description
└── milestone.total_cost_usd, tasks_completed, tasks_failed
```

### Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `orchestrator_tasks_total` | Counter | milestone, status | Task outcomes |
| `orchestrator_tokens_total` | Counter | milestone | Token usage |
| `orchestrator_cost_usd_total` | Counter | milestone | Cost tracking |
| `orchestrator_escalations_total` | Counter | milestone | Human input frequency |
| `orchestrator_loops_detected_total` | Counter | type | Loop detection events |
| `orchestrator_e2e_tests_total` | Counter | milestone, status | E2E outcomes |
| `orchestrator_task_duration_seconds` | Histogram | milestone | Task timing |

### Grafana Dashboard Panels

1. **Cost Over Time** — `sum(increase(orchestrator_cost_usd_total[1d])) by (milestone)`
2. **Task Success Rate** — `sum(rate(orchestrator_tasks_total{status="completed"})) / sum(rate(orchestrator_tasks_total))`
3. **Escalation Frequency** — `sum(orchestrator_escalations_total) by (milestone)`
4. **Task Duration P95** — `histogram_quantile(0.95, orchestrator_task_duration_seconds)`
5. **E2E Pass Rate** — `sum(orchestrator_e2e_tests_total{status="passed"}) / sum(orchestrator_e2e_tests_total)`
6. **Loop Detection Events** — `sum(orchestrator_loops_detected_total) by (type)`

---

## Validation Outcome

**Result: PASSED** — Design is ready for implementation planning.

All critical gaps have been resolved with concrete decisions. The milestone structure provides a clear vertical-slice implementation path with telemetry woven throughout.

Next step: Create implementation plan following this milestone structure.
