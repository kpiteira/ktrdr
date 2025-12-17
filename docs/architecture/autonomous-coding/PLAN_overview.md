# Sandbox & Orchestrator: Implementation Plan Overview

**Created:** 2025-12-17
**Source Documents:**

- [DESIGN.md](DESIGN.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [VALIDATION.md](VALIDATION.md)

---

## Milestone Summary

| Milestone | Capability | Deliverables | Est. Tasks | Validation |
|-----------|------------|--------------|------------|------------|
| **M1** | Sandbox works | Dockerfile, compose, scripts | 7 | Manual E2E |
| **M2** | Single task + telemetry | Orchestrator CLI, task runner, OTel | 9 | Hand-crafted task |
| **M3** | Task loop + resume | State persistence, run/resume | 7 | Hand-crafted 3-task milestone |
| **GATE** | Design real feature | /kdesign "Orchestrator Enhancements" | — | — |
| **M4** | Escalation + loops | Human input, loop detection | 8 | Real feature M1 |
| **M5** | E2E + dashboard | E2E runner, Grafana dashboard | 9 | Real feature + E2E |

**Total:** ~40 tasks across 5 milestones

---

## Data Model

### Shared Resources (Read-Only)

```
~/Documents/ktrdr-shared/
└── data/                    # Market CSVs (consolidated from "Data Backup")
```

### Environment-Local Resources

Each environment (main workspace, sandbox, production) has its own:
- `models/` — Trained models
- `strategies/` — Generated strategies
- `logs/` — Runtime logs
- `.env` — Secrets

### Sandbox Volume Structure

```yaml
volumes:
  sandbox-workspace:    # /workspace - git clone, reset via git clean
  sandbox-models:       # /env/models - persists across resets
  sandbox-strategies:   # /env/strategies - persists across resets
  sandbox-logs:         # /env/logs - cleared on reset
```

### Reset Behavior

| Resource | On Reset | Rationale |
|----------|----------|-----------|
| `/workspace` | **Clear** | Clean code slate |
| `/shared/data` | Unchanged | Read-only mount |
| `/env/models` | **Keep** | Don't retrain |
| `/env/strategies` | **Keep** | Don't regenerate |
| `/env/logs` | **Clear** | Clean debugging |

---

## Validation Strategy

### The Bootstrap Problem

We can't /kdesign the validation mini-feature until the orchestrator exists. Solution:

1. **M1-M3**: Validate with hand-crafted test plans
2. **GATE**: Design "Orchestrator Enhancements" with /kdesign (orchestrator exists now)
3. **M4-M5**: Validate with real feature
4. **META**: Orchestrator runs on its own enhancement feature

### Hand-Crafted Test Plans

Located in `orchestrator/test_plans/`:

| Plan | Purpose | Milestone |
|------|---------|-----------|
| `hello_world.md` | Single trivial task | M2 dev |
| `health_check.md` | Real 3-task mini milestone | M2/M3 validation |
| `three_tasks_clean.md` | Multi-task, no ambiguity | M3 dev |
| `ambiguous_task.md` | Triggers "needs human" | M4 dev |
| `doomed_to_fail.md` | Fails 3x (loop detection) | M4 dev |
| `e2e_will_pass.md` | Tasks + passing E2E | M5 dev |
| `e2e_will_fail_fixable.md` | Tasks + failing E2E Claude can fix | M5 dev |

### Validation Gates

| Milestone | Must Pass Before Moving On |
|-----------|---------------------------|
| M1 | Sandbox E2E scenario passes manually |
| M2 | `health_check.md` Task 1 executes successfully |
| M3 | Full `health_check.md` (3 tasks) runs to completion |
| M4 | Real feature milestone with escalation handled |
| M5 | Real feature with E2E pass (including fix flow) |

---

## Key Decisions (from Validation)

1. **Loop Detection Over Cost Limits** — Detect loops via attempt counting (MAX_TASK_ATTEMPTS=3, MAX_E2E_FIX_ATTEMPTS=5), not cost caps
2. **Long API Retry Backoff** — 30s → 60s → 120s → 300s → 600s before giving up
3. **Simple Lock File** — PID-based, check if process exists
4. **--max-turns as Stuck Detection** — 50 turns backstop for MVP
5. **Telemetry From Day One** — Every milestone adds telemetry for its functionality
6. **No Fork (MVP)** — Clone from main repo directly, fork workflow is future

---

## File Structure (Final)

```
ktrdr/
├── deploy/
│   ├── environments/
│   │   └── sandbox/
│   │       └── docker-compose.yml
│   ├── docker/
│   │   └── sandbox/
│   │       ├── Dockerfile
│   │       └── entrypoint.sh
│   └── shared/grafana/dashboards/
│       └── orchestrator.json          # M5
│
├── scripts/
│   ├── sandbox-init.sh
│   ├── sandbox-reset.sh
│   ├── sandbox-shell.sh
│   └── sandbox-claude.sh
│
├── orchestrator/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── plan_parser.py
│   ├── sandbox.py
│   ├── task_runner.py
│   ├── state.py
│   ├── lock.py
│   ├── escalation.py
│   ├── loop_detector.py
│   ├── e2e_runner.py
│   ├── telemetry.py
│   └── test_plans/
│       ├── hello_world.md
│       ├── health_check.md
│       ├── three_tasks_clean.md
│       ├── ambiguous_task.md
│       ├── doomed_to_fail.md
│       ├── e2e_will_pass.md
│       └── e2e_will_fail_fixable.md
│
└── state/                             # Orchestrator state files
    └── {milestone}_state.json
```

---

## Milestone Plan Files

- [M1: Sandbox Works](PLAN_M1_sandbox.md)
- [M2: Single Task + Telemetry](PLAN_M2_single_task.md)
- [M3: Task Loop + Resume](PLAN_M3_task_loop.md)
- [M4: Escalation + Loop Detection](PLAN_M4_escalation.md)
- [M5: E2E + Dashboard](PLAN_M5_e2e.md)

---

## Prerequisites

Before starting M1:

1. **Track .claude/ in git** — Currently untracked, needs to be committed
2. **Consolidate data** — Move `~/Documents/Data Backup/` to `~/Documents/ktrdr-shared/data/`
3. **Verify Docker** — Ensure Docker Desktop is running and has enough resources

---

## Success Metrics (from Design)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Sandbox reset time | < 30 seconds | Timed in reset script |
| False escalation rate | < 20% | Manual review |
| Missed escalation rate | < 5% | Post-hoc review |
| E2E test reliability | > 90% pass on valid code | Telemetry |
| Cost per milestone | Track (no target) | Grafana dashboard |
