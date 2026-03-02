---
design: docs/designs/sdk-evolution-researchers/DESIGN.md
architecture: docs/designs/sdk-evolution-researchers/ARCHITECTURE.md
---

# Milestone 5: Evolution Integration + Cleanup

## User Value

**`ktrdr evolve start` runs with the new Claude Code agents end-to-end — smarter agents that explore and iterate, on subscription pricing, with the backend as a pure dispatcher.**

After M5, running an evolution experiment uses the containerized design and assessment agents from M3/M4. Each researcher in the population gets a Claude Code session that autonomously explores indicators, designs strategies, and validates iteratively. Assessment agents reason deeply about results and generate hypotheses that feed back into the next generation.

This is the milestone where you run a real evolution experiment and see if the agentic loop improvement translates to better, more diverse strategies — the original problem (all 3 researchers designing the same strategy) should be solved because agents now discover context themselves rather than receiving an overwhelming pre-loaded prompt.

The old AnthropicInvoker code is removed. Backend is now a pure dispatcher.

## E2E Validation

### Test: Full Evolution Generation With Containerized Agents

**Purpose**: Verify `ktrdr evolve start` triggers containerized design and assessment agents, producing diverse strategies with real fitness scores.

**Duration**: ~10-15 minutes (3 researchers × full pipeline)

**Prerequisites**: Backend + all workers running (training, backtest, design-agent, assessment-agent), EURUSD data available, auth credentials mounted

**Test Steps**:

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Verify all worker types registered | GET `/api/v1/workers` includes training, backtesting, AGENT_DESIGN, AGENT_ASSESSMENT | All 4 types present |
| 2 | Start evolution: `ktrdr evolve start --population 3 --generations 1` | Run starts, returns run_id | CLI output |
| 3 | Monitor progress: `ktrdr evolve status` | Shows researchers progressing through phases | Status output |
| 4 | Wait for completion (timeout: 15 min) | All 3 researchers complete or fail | Status shows generation complete |
| 5 | Check run directory: `data/evolution/run_*/generation_00/` | population.yaml, operations.yaml, results.yaml exist | Files on disk |
| 6 | Verify at least 2 of 3 researchers completed | results.yaml has fitness scores (not all MINIMUM_FITNESS) | Fitness values > -999 |
| 7 | Check strategy diversity | At least 2 distinct strategy names in results | Strategy names differ |
| 8 | Verify design agents used MCP | Backend logs show AGENT_DESIGN operations dispatched to container workers | Log entries |
| 9 | Verify assessment agents used MCP | Backend logs show AGENT_ASSESSMENT operations dispatched to container workers | Log entries |
| 10 | Run report: `ktrdr evolve report` | Report shows fitness scores, strategy names, generation stats | CLI output |

**Success Criteria**:
- [ ] Evolution harness triggers containerized agents (not in-process AnthropicInvoker)
- [ ] Design agents produce diverse strategies (not identical — the original problem)
- [ ] Assessment agents produce structured verdicts
- [ ] Fitness scores are real (computed from actual backtest results)
- [ ] Strategy diversity: at least 2 distinct strategies out of 3 researchers
- [ ] No budget tracking errors (subscription model, not API cost)
- [ ] Full pipeline: design → train → backtest → assess for each researcher

### Regression: Existing Evolution Tests Still Pass

The existing `evolution/single-generation.md` E2E test should also pass (it tests CLI, state files, operations tracking). Containerized agents should be transparent to the harness.

---

## Task 5.1: Update research orchestrator to dispatch to container workers

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING
**Architectural Pattern**: D2 (containerized workers), state machine dispatch

**Description**:
Update `AgentResearchWorker` to dispatch design and assessment operations to container workers via HTTP instead of calling AnthropicInvoker in-process.

Currently:
- `_handle_designing_phase()` → creates `AgentDesignWorker` instance, calls `run()` in-process
- `_handle_assessing_phase()` → creates `AgentAssessmentWorker` instance, calls `run()` in-process

New:
- `_handle_designing_phase()` → POST to design agent container via backend API (same pattern as training/backtest dispatch)
- `_handle_assessing_phase()` → POST to assessment agent container via backend API

The research orchestrator already dispatches training and backtest operations via HTTP. Design and assessment should follow the same pattern.

**Implementation Notes**:
- Read how `_start_training()` and `_start_backtest()` dispatch via HTTP — follow the same pattern
- The backend's worker selection (LRU round-robin) picks which container gets the work
- Operations are tracked via OperationsService — same polling pattern as training/backtest
- The orchestrator's state machine doesn't change — only the dispatch mechanism

**Tests**:
- Unit: Update existing research_worker tests
  - [ ] Design phase dispatches via HTTP (not in-process)
  - [ ] Assessment phase dispatches via HTTP (not in-process)
  - [ ] Operation polling works for agent operations (same as training/backtest)
  - [ ] Failure handling: container worker fails → research marked failed

**Acceptance Criteria**:
- [ ] Research orchestrator dispatches to container workers
- [ ] Same HTTP dispatch pattern as training/backtest
- [ ] Operation tracking works end-to-end
- [ ] No direct AnthropicInvoker usage in research worker

---

## Task 5.2: Update worker registry and backend dispatch for agent types

**File(s)**: `ktrdr/api/services/worker_registry.py`, `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**:
Ensure the backend can dispatch operations to AGENT_DESIGN and AGENT_ASSESSMENT workers:
1. Worker registry already accepts new types (from M2 task 2.4)
2. Agent service needs to create child operations of type AGENT_DESIGN and AGENT_ASSESSMENT
3. Backend needs endpoints (or routing) to forward start requests to the agent containers

**Implementation Notes**:
- Check how the agent service currently creates child operations for design/assessment
- The dispatch should use the same worker selection as training: `get_worker_registry().get_available_workers(worker_type)`
- May need new endpoints on the backend to accept and route design/assessment start requests

**Tests**:
- [ ] Backend dispatches AGENT_DESIGN operations to registered design agent workers
- [ ] Backend dispatches AGENT_ASSESSMENT operations to registered assessment agent workers
- [ ] Worker selection follows LRU pattern
- [ ] Operations tracked correctly for new types

**Acceptance Criteria**:
- [ ] Backend routes design operations to design agent containers
- [ ] Backend routes assessment operations to assessment agent containers
- [ ] Worker selection works for new types

---

## Task 5.3: Adapt BudgetTracker for subscription model

**File(s)**: `ktrdr/agents/budget.py`
**Type**: CODING

**Description**:
The current BudgetTracker tracks Anthropic API cost per researcher (~$0.40/researcher, with known 3x over-estimation). With containerized agents on subscription pricing, API cost tracking is no longer relevant for evolution.

Options:
1. Disable budget tracking for evolution operations that use container workers
2. Track turn count instead of dollar cost
3. Keep budget tracking but set a very high limit

**Implementation Notes**:
- The evolution harness checks budget before triggering researchers (`budget_exhausted` response)
- With subscription pricing, the harness should never get `budget_exhausted` for agent operations
- Training operations still incur compute cost — budget tracking may still be relevant there
- Simplest approach: if operation uses container agent workers, skip budget check

**Tests**:
- [ ] Evolution harness doesn't get budget_exhausted for container agent operations
- [ ] Training/backtest budget tracking still works if applicable
- [ ] Budget status endpoint reflects new model

**Acceptance Criteria**:
- [ ] Evolution runs aren't killed by false budget exhaustion
- [ ] Budget tracking adapted for subscription model

---

## Task 5.4: Remove old invoker code + update stub workers

**File(s)**:
- `ktrdr/agents/invoker.py` — DELETE
- `ktrdr/agents/executor.py` — DELETE
- `ktrdr/agents/tools.py` — DELETE
- `ktrdr/agents/workers/stubs.py` — UPDATE
**Type**: CODING

**Description**:
1. Remove `AnthropicAgentInvoker` (direct Anthropic API client)
2. Remove `ToolExecutor` (in-process tool call handler — replaced by MCP)
3. Remove `AGENT_TOOLS` and `DESIGN_PHASE_TOOLS` definitions (replaced by MCP server tools)
4. Update `StubDesignWorker` and `StubAssessmentWorker` to match the new container worker interface (HTTP dispatch, not in-process)

**Implementation Notes**:
- Before deleting, verify nothing else imports from these files
- Keep `ktrdr/agents/prompts.py` (current prompts) temporarily for reference, but mark deprecated
- Stub workers should now simulate HTTP dispatch: accept the same request format as container workers, sleep, return mock result
- The `anthropic` package may still be needed for tests — check before removing from dependencies

**Tests**:
- [ ] No imports remain for deleted files
- [ ] Stub workers work with new dispatch pattern
- [ ] USE_STUB_WORKERS still works for testing without real containers

**Acceptance Criteria**:
- [ ] Old invoker code deleted
- [ ] No dangling imports
- [ ] Stub workers updated for new interface
- [ ] Tests pass with stubs

---

## Task 5.5: Execute E2E Test — Full Evolution With Containerized Agents

**Type**: VALIDATION

**Description**:
Validate M5 is complete: run a full evolution generation with containerized agents and verify diverse strategies, real fitness scores, and no budget errors.

**⚠️ MANDATORY: Use the E2E Agent System**

1. Invoke `e2e-test-designer` → may extend `evolution/single-generation.md` or hand off to architect
2. Invoke `e2e-test-architect` if needed (new: containerized agent validation)
3. Invoke `e2e-tester` to execute

**Key Validations**:
- Strategies are diverse (not identical — the original problem)
- Container agents are used (check backend logs for AGENT_DESIGN/AGENT_ASSESSMENT dispatch)
- No budget exhaustion errors
- Fitness scores are real (from actual backtests)

**Acceptance Criteria**:
- [ ] `ktrdr evolve start --population 3 --generations 1` completes
- [ ] At least 2 of 3 researchers produce distinct strategies
- [ ] Design operations dispatched to container workers (not in-process)
- [ ] Assessment operations dispatched to container workers (not in-process)
- [ ] Real fitness scores (not all MINIMUM_FITNESS)
- [ ] No budget tracking errors
- [ ] `ktrdr evolve report` shows meaningful results
- [ ] All previous milestone E2E tests still pass
- [ ] E2E test executed via agent

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (full evolution generation with containerized agents)
- [ ] All previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Old invoker code deleted (no dangling imports)
- [ ] Backend is pure dispatcher (no agent logic in-process)
- [ ] Stub workers work with new interface
- [ ] No regressions in evolution harness (CLI commands still work)
