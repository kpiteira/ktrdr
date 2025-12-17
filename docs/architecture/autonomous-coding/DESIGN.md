# Sandbox & Orchestrator: Design

## Problem Statement

The current `/ktask` implementation workflow runs Claude Code in Karl's real environment with full file system access. This creates risk (accidental file corruption, git state issues) and requires Karl to be present for the entire implementation session. The goal is to enable autonomous multi-task execution by (1) isolating Claude Code in a sandbox where it can't damage the real environment, and (2) building an orchestrator that manages the task loop, runs E2E tests via Claude Code, and escalates only when truly needed.

---

## Goals

1. **Safe autonomy**: Claude Code can run with full permissions in isolation, unable to affect the real repository or environment
2. **Task-by-task execution**: Fresh Claude Code session per task prevents context degradation and matches current workflow
3. **Intelligent E2E testing**: Claude Code interprets and executes E2E tests, not a rigid test runner
4. **Smart escalation**: Orchestrator detects uncertainty and escalates rather than making arbitrary decisions
5. **Resumability**: Orchestrator state survives stops/crashes; can resume mid-milestone
6. **Observability**: Track task duration, token usage, escalation patterns, and costs from day one
7. **Extractability**: Design boundaries that allow future extraction for use on other projects

---

## Non-Goals (Out of Scope)

1. **Real-time collaboration UI**: MVP uses terminal + macOS notifications, not a web dashboard
2. **Multi-project support now**: We'll design for it but implement only ktrdr first
3. **Advanced escalation channels**: Slack/email/SMS are future; terminal + notification for MVP
4. **CI/CD integration**: Orchestrator runs locally on Karl's Mac; GitHub Actions integration is future
5. **Parallel task execution**: Tasks run sequentially; parallelism is a future optimization
6. **GPU training in sandbox**: Sandbox is CPU-only; GPU training uses existing host service

---

## User Experience

### Scenario 1: Happy Path - Full Milestone Completion

```
$ orchestrator run M4 --notify

[14:23:01] Starting milestone M4: Backtest Integration
[14:23:01] Initializing sandbox... done (2.3s)
[14:23:04] Task 4.1: Add Backtest Service Integration
           Invoking Claude Code...
[14:25:32] Task 4.1: COMPLETED (2m 28s, 12.4k tokens, $0.08)
[14:25:33] Task 4.2: Delete BacktestWorkerAdapter
           Invoking Claude Code...
[14:26:15] Task 4.2: COMPLETED (42s, 3.2k tokens, $0.02)
...
[14:35:00] All tasks complete. Running E2E tests...
[14:35:01] Invoking Claude Code for E2E verification...
[14:36:45] E2E: PASSED (1m 44s)
[14:36:45] Milestone M4 COMPLETE

Summary:
  Tasks: 5/5 completed
  Duration: 13m 44s
  Tokens: 48.2k
  Cost: $0.31
  Escalations: 0
```

Karl receives a macOS notification: "M4 Backtest Integration completed successfully"

### Scenario 2: Claude Needs Human Input

```
[14:28:15] Task 4.3: Update Stub Workers
           Invoking Claude Code...
[14:29:42] NEEDS HUMAN INPUT

Claude's question:
  "The stubs.py file has both StubTrainingWorker and StubBacktestWorker.
   The task says to remove backtest-related stubs, but training stubs
   are also mentioned in some tests. Options:

   A) Remove only StubBacktestWorker (safer, tests may still pass)
   B) Remove both stubs (matches task intent, may break tests)
   C) Remove both but update tests to use mocks instead

   I recommend option A because it's safer. What would you prefer?"

Your response (or 'skip' to continue with recommendation):
> A, and add a TODO comment for the training stubs

[14:30:12] Resuming Task 4.3 with guidance...
[14:31:45] Task 4.3: COMPLETED (3m 30s, 8.1k tokens, $0.05)
```

### Scenario 3: E2E Test Failure with Diagnosis

```
[14:45:00] Running E2E tests...
[14:46:30] E2E: FAILED

Claude's diagnosis:
  "The backtest operation was created but returned operation_type='training'
   instead of 'backtesting'.

   Root cause: In _start_backtest(), we're passing operation_type=OperationType.TRAINING
   instead of OperationType.BACKTESTING on line 127.

   This is fixable. Shall I apply the fix?"

Apply fix? [Y/n]: y

[14:46:45] Applying fix...
[14:47:02] Fix applied. Re-running E2E...
[14:48:30] E2E: PASSED

Milestone M4 COMPLETE (with 1 fix applied)
```

### Scenario 4: Resume After Interruption

```
$ orchestrator run M4 --notify

[14:50:00] Found existing state for M4
           Last completed: Task 4.2
           Last in-progress: Task 4.3 (interrupted)

Resume from Task 4.3? [Y/n]: y

[14:50:05] Resetting sandbox to clean state...
[14:50:12] Resuming from Task 4.3...
```

---

## Key Decisions

### Decision 1: Orchestrator Runs Outside Sandbox

**Choice**: Orchestrator is a Python process on Karl's Mac, invoking Claude Code inside the Docker sandbox via `docker exec`.

**Alternatives considered**:
- Orchestrator inside sandbox: Simpler communication but can't control sandbox lifecycle, state lost on reset

**Rationale**:
- Orchestrator must persist state across sandbox resets
- Orchestrator needs access to Mac resources (notifications, file system for state)
- Easier to debug Python on Mac than inside container
- Clean separation: sandbox is ephemeral, orchestrator is persistent

### Decision 2: Claude Code Executes E2E Tests

**Choice**: E2E test scenarios remain as markdown. Orchestrator passes them to Claude Code, which interprets and executes them, then reports pass/fail.

**Alternatives considered**:
- Strict YAML format with assertion DSL: Rigid, loses Claude's ability to interpret context
- Shell script per test: No intelligence, can't diagnose failures

**Rationale**:
- Claude Code already executes tests manually; this automates that
- Natural language tests are more expressive than DSLs
- Claude can diagnose failures and propose fixes
- Existing test scenarios work without modification

### Decision 3: Fresh Session Per Task

**Choice**: Each task gets a new Claude Code invocation. No session continuity between tasks.

**Alternatives considered**:
- Single session for entire milestone: Context degrades, harder to resume
- Resume previous session: Complex state management

**Rationale**:
- Matches Karl's current manual workflow
- Prevents context window exhaustion on large milestones
- Clean isolation between tasks
- Simpler resumption (just restart the task)

### Decision 4: JSON Output Mode for Parsing

**Choice**: Use `claude -p --output-format json` for all invocations. Parse structured output for status, cost, session ID.

**Alternatives considered**:
- Parse natural language output: Fragile, regex-heavy
- Stream JSON mode: More complex, not needed for task-level granularity

**Rationale**:
- Claude Code natively supports JSON output
- Includes `is_error`, `total_cost_usd`, `session_id`
- Reliable parsing without heuristics

### Decision 5: Conservative "Needs Human" Detection

**Choice**: Start with explicit structured markers in system prompt, augmented by keyword detection. Err on side of escalating too much.

**Alternatives considered**:
- Pure keyword heuristics: High false positive/negative rate
- Ask Claude to always output structured status: Adds overhead to every task

**Rationale**:
- Better to escalate unnecessarily than to proceed incorrectly
- Can tune detection thresholds based on observed patterns
- Explicit markers ("OPTIONS:", "RECOMMENDATION:") reduce ambiguity

### Decision 6: Reuse Existing Observability Stack (OTel/Jaeger/Prometheus/Grafana)

**Choice**: Emit OpenTelemetry traces and metrics to the existing KTRDR observability stack. Each milestone run is a trace with spans for tasks, Claude invocations, and E2E tests. Metrics track tokens, cost, and success rates.

**Alternatives considered**:
- Custom JSONL logging: Inconsistent with existing observability, requires separate analysis tools
- Add observability later: Lose early data, especially cost tracking

**Rationale**:
- KTRDR already has Jaeger, Prometheus, Grafana running
- Traces give hierarchical view (milestone → task → claude invocation)
- Metrics enable cost tracking and aggregation across runs
- Consistent tooling with rest of system
- Cost captured automatically from Claude's JSON output (`total_cost_usd`)

### Decision 7: GitHub Identity Isolation

**Choice**: Orchestrator uses its own GitHub identity with a fork of the repo. All changes go through Pull Requests that only Karl can merge.

**Alternatives considered**:
- Same GitHub identity: Orchestrator could push directly to main
- Branch protection only: Still same identity, less isolation

**Rationale**:
- Orchestrator can completely mess up its fork - no impact on main repo
- All changes require PR review (human gate)
- Audit trail of all orchestrator work
- Easy to abandon failed attempts (just close PR)
- Karl is only maintainer - merge gate is enforced

### Decision 8: Design for Extractability, Implement for ktrdr

**Choice**: Clear module boundaries (sandbox-core, orchestrator-core) but all code lives in ktrdr repo for now.

**Alternatives considered**:
- Separate repo from start: Premature, adds coordination overhead
- No separation: Hard to extract later

**Rationale**:
- Extraction is a goal, not a requirement
- Module boundaries make future extraction straightforward
- Single repo simplifies development and testing
- Document extraction path for future

---

## Open Questions

Resolved during design:
- ~~Orchestrator location~~ → Outside sandbox
- ~~E2E test format~~ → Markdown, Claude interprets
- ~~Claude Code CLI capabilities~~ → Researched, JSON mode works

To resolve during implementation:
1. **Detection tuning**: What keyword patterns best detect "needs human"?
2. **Timeout values**: How long to wait for tasks before considering them stuck?
3. **Reset optimization**: Is `git clean -fdx` fast enough, or do we need snapshotting?
4. **Sandbox resource limits**: Memory/CPU constraints for the container?

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Sandbox reset time | < 30 seconds | Timed in reset script |
| False escalation rate | < 20% | Manual review of escalations |
| Missed escalation rate | < 5% | Post-hoc review of mistakes |
| E2E test reliability | > 90% pass on valid code | Track in JSONL logs |
| Cost per milestone | Track, no target yet | Sum from JSONL logs |

---

## References

- [Sandbox & Orchestrator Handoff](sandbox-orchestrator-handoff.md) - Original design conversation
- [Claude Code Headless Documentation](https://code.claude.com/docs/en/headless.md) - CLI reference
- [Integration Testing Skill](.claude/skills/integration-testing/SKILL.md) - E2E test patterns
- [Test Scenarios](docs/testing/SCENARIOS.md) - Existing test library
