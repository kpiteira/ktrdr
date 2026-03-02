---
design: docs/designs/sdk-evolution-researchers/DESIGN.md
architecture: docs/designs/sdk-evolution-researchers/ARCHITECTURE.md
---

# Milestone 4: Assessment Agent Worker

## User Value

**You can trigger an assessment agent that reasons deeply about strategy results — querying additional data via MCP, reading experiment history, and producing structured analysis with actionable hypotheses.**

After M4, you POST a strategy + its training/backtest metrics to the assessment agent and it:
- Reads the strategy YAML to understand what was designed
- Analyzes training metrics (loss curves, accuracy) via MCP if needed
- Analyzes backtest metrics (Sharpe, drawdown, trade count)
- Reads experiment history from filesystem to identify patterns across experiments
- Reads hypotheses to check if any were validated or refuted
- Produces a structured verdict with strengths, weaknesses, suggestions, and new hypotheses
- Saves the assessment atomically via MCP (`save_assessment`)
- Updates experiment memory with new learnings

The current assessment agent gets pre-loaded metrics and produces templated output. The new agent can reason about context it discovers, producing richer and more actionable analysis. Usable standalone — feed it any strategy + results.

## E2E Validation

### Test: Assessment Agent Analyzes Strategy Results

**Purpose**: Verify the assessment agent receives strategy + metrics, reasons about them via Claude Code's agentic loop, and produces a structured assessment with memory updates.

**Duration**: ~1-3 minutes

**Prerequisites**: Backend running, assessment-agent-1 container running, at least one strategy file exists in `/app/strategies/`

**Test Steps**:

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Verify assessment-agent-1 is healthy | GET `/health` returns 200 | Health response |
| 2 | Verify registered with backend | GET `/api/v1/workers` includes AGENT_ASSESSMENT type | Worker in list |
| 3 | POST `/assessments/start` with strategy_name, training_metrics (accuracy: 0.72, loss: 0.31), backtest_results (sharpe: 1.2, max_dd: 0.15, total_trades: 145) | Returns operation_id, status=started | Response JSON |
| 4 | Poll operation until complete (timeout: 3 min) | Status: started → running → completed | Status progression |
| 5 | Check result_summary | Contains verdict, strengths, weaknesses, suggestions | Structured fields |
| 6 | Verify verdict is meaningful | Verdict is "promising", "neutral", or "poor" — not empty or generic | Enum value |
| 7 | Check assessment file exists | `save_assessment` MCP tool was called, JSON file created | File on disk |
| 8 | Verify suggestions are specific to the strategy | Suggestions reference actual metrics or indicators | Content analysis |
| 9 | Check experiment memory updated | New experiment record in `/app/memory/experiments/` | File exists with strategy_name |

**Success Criteria**:
- [ ] Assessment agent accepts strategy + metrics
- [ ] Claude Code's agentic loop runs (MCP tool calls visible in transcript)
- [ ] Structured assessment saved via `save_assessment` MCP tool
- [ ] Verdict is one of the valid enum values
- [ ] Suggestions are specific (reference actual metrics, not generic advice)
- [ ] Experiment memory updated with new record
- [ ] Hypotheses updated (new ones generated or existing ones marked tested)

---

## Task 4.1: Create AssessmentAgentWorker (WorkerAPIBase)

**File(s)**: `ktrdr/agents/workers/assessment_agent_worker.py` (NEW)
**Type**: CODING
**Architectural Pattern**: D2 (containerized workers), WorkerAPIBase contract

**Description**:
New worker inheriting `WorkerAPIBase` with `worker_type=AGENT_ASSESSMENT`. Implements:
- `POST /assessments/start` endpoint accepting `{task_id, strategy_name, strategy_config, training_metrics, backtest_results, experiment_history}`
- Background task that invokes `AgentRuntime.invoke()` with assessment prompt + metrics
- Result extraction from transcript (find `save_assessment` tool call)
- Reports completion via `complete_operation(result_summary={verdict, strengths, weaknesses, suggestions, assessment_path})`

**Implementation Notes**:
- Follow same WorkerAPIBase pattern as DesignAgentWorker (M3)
- The assessment agent gets more structured input than the design agent (metrics dict, not free-form brief)
- Result extraction: find `mcp__ktrdr__save_assessment` tool call in transcript
- Include experiment_history as optional context in the user prompt (not system prompt)

**Tests**:
- Unit: `tests/unit/agents/workers/test_assessment_agent_worker.py`
  - [ ] Start endpoint creates operation
  - [ ] Result extraction finds assessment from transcript
  - [ ] Operation completed with structured result_summary
  - [ ] Operation failed on timeout/error

**Acceptance Criteria**:
- [ ] Worker follows WorkerAPIBase contract
- [ ] Invokes AgentRuntime with assessment prompt + metrics
- [ ] Extracts structured assessment from transcript
- [ ] Reports completion with verdict, strengths, weaknesses, suggestions

---

## Task 4.2: Write assessment agent system prompt

**File(s)**: `ktrdr/agents/prompts/assessment_sdk.py` (NEW)
**Type**: CODING
**Architectural Pattern**: D7 (slim prompt + MCP discovery)

**Description**:
Write the assessment agent system prompt. Defines:

1. **Role**: You are a trading strategy analyst evaluating research results
2. **Analysis rubric**: What to evaluate (Sharpe ratio quality, drawdown risk, trade frequency, consistency across metrics, indicator relevance)
3. **Output contract**: Call `save_assessment` MCP tool with structured verdict
4. **Verdict guidelines**: "promising" (Sharpe > 1, manageable drawdown, sufficient trades), "neutral" (mixed signals), "poor" (negative Sharpe or extreme drawdown or too few trades)
5. **Hypothesis generation**: Identify testable hypotheses based on what you observe

**Implementation Notes**:
- Training metrics and backtest results go in the user prompt, not system prompt
- System prompt is static across all assessments
- The agent can optionally query more data via MCP (e.g., `get_model_performance` for detailed training metrics)
- Hypothesis format should match existing `memory/hypotheses.yaml` structure

**Tests**:
- [ ] System prompt defines clear analysis rubric
- [ ] System prompt references `save_assessment` MCP tool
- [ ] Verdict categories are well-defined

**Acceptance Criteria**:
- [ ] Clear analysis rubric in system prompt
- [ ] Output contract: save_assessment MCP tool call
- [ ] Hypothesis generation guidance included

---

## Task 4.3: Memory integration (experiment records + hypotheses)

**File(s)**: `ktrdr/agents/workers/assessment_agent_worker.py`, reuse from `ktrdr/agents/memory.py`
**Type**: CODING

**Description**:
After the assessment agent completes, the worker must:
1. Save an experiment record to `/app/memory/experiments/` (YAML with strategy_name, verdict, metrics, date)
2. Extract new hypotheses from the assessment and append to `/app/memory/hypotheses.yaml`
3. If the assessment references existing hypotheses, update their status (validated/refuted/inconclusive)

This logic already exists in `ktrdr/agents/memory.py` (used by the current in-process assessment worker). Reuse it.

**Implementation Notes**:
- Read `ktrdr/agents/memory.py` to understand existing experiment record and hypothesis saving
- The memory operations happen AFTER the Claude Code session completes, in the worker's background task
- Best-effort: memory save failures should log warnings, not fail the operation
- The Claude Code session writes the assessment via MCP; the worker handles memory

**Tests**:
- [ ] Experiment record saved after successful assessment
- [ ] Hypotheses extracted and appended
- [ ] Memory save failure doesn't fail the operation
- [ ] Existing hypothesis status updated when referenced

**Acceptance Criteria**:
- [ ] Experiment records persist across assessments
- [ ] Hypotheses accumulate over time
- [ ] Memory failures are non-blocking

---

## Task 4.4: Wire assessment agent into docker-compose + unit tests

**File(s)**: `docker-compose.sandbox.yml`, `tests/unit/agents/workers/test_assessment_agent_worker.py`
**Type**: CODING

**Description**:
1. Add `assessment-agent-1` service to docker-compose using the same `ktrdr-agent:dev` image
2. Configure with `KTRDR_WORKER_TYPE=agent_assessment`, port 5020
3. Write comprehensive unit tests with mocked AgentRuntime

**Tests**:
- [ ] POST /assessments/start with valid metrics → operation created
- [ ] POST /assessments/start with missing strategy_name → 422
- [ ] Background task calls runtime.invoke() with correct assessment prompt
- [ ] Transcript with save_assessment → verdict extracted
- [ ] Memory integration called after successful assessment
- [ ] Memory integration failure → operation still succeeds (best-effort)

**Acceptance Criteria**:
- [ ] Assessment agent starts as Docker service
- [ ] Self-registers with backend as AGENT_ASSESSMENT
- [ ] Healthcheck passes
- [ ] Comprehensive unit tests with mocked runtime

---

## Task 4.5: Execute E2E Test — Assessment Agent Analyzes Results

**Type**: VALIDATION

**Description**:
Validate M4 is complete: POST strategy + metrics to assessment agent, verify structured assessment and memory updates.

**⚠️ MANDATORY: Use the E2E Agent System**

1. Invoke `e2e-test-designer` → likely architect handoff
2. Invoke `e2e-test-architect` to design test spec
3. Invoke `e2e-tester` to execute

**Key Validation**: Verify the assessment is specific to the input metrics (not generic). The verdict should match what the metrics suggest (good Sharpe + low drawdown → "promising"). Check that experiment memory was updated.

**Acceptance Criteria**:
- [ ] Assessment agent accepts strategy + metrics
- [ ] Claude Code agentic loop runs with MCP tool calls
- [ ] Structured assessment saved via save_assessment MCP tool
- [ ] Verdict appropriate for the given metrics
- [ ] Experiment record saved to memory
- [ ] M1, M2, M3 E2E tests still pass
- [ ] E2E test executed via agent

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (assessment agent analyzes results)
- [ ] M1, M2, M3 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Assessment agent registers and appears in worker list
- [ ] Memory integration works (experiment records, hypotheses)
- [ ] No regressions in existing workers
