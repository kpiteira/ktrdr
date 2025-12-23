# KDesign Command Improvements

**Purpose:** Improve the kdesign commands to systematically identify and require appropriate integration/smoke tests based on task type analysis.

**Key Insight:** The M1 persistence bug wasn't special - it was an instance of a general problem: unit tests verify component behavior, but don't verify that components are wired together correctly. Different task types have different failure modes that require different verification approaches.

---

## The Core Problem

Current kdesign commands do a great job of:

- Designing components and their interfaces
- Validating scenarios through walk-throughs
- Breaking work into vertical milestones
- Specifying unit tests per task

But they don't systematically:

- Categorize tasks by type
- Identify failure modes specific to each type
- Require appropriate integration/smoke tests based on type

---

## Proposed Solution: Task Type Analysis

Add a **Task Type Analysis** step to `/kdesign-impl-plan` that:

1. Categorizes each task
2. Looks up failure modes for that category
3. Specifies appropriate integration/smoke tests

---

## Changes to `/kdesign-impl-plan`

### New Section: Task Type Categories

Add this reference section to the command documentation:

```markdown
## Task Type Categories

When generating tasks, classify each by type to determine required tests.

### Categories and Indicators

| Category | Indicators in Task Description |
|----------|-------------------------------|
| Persistence | DB, repository, store, save, table, migration |
| Wiring/DI | Factory, inject, singleton, get_X_service() |
| State Machine | Status, state, transition, phase, workflow |
| Cross-Component | Calls, integrates, sends to, receives from |
| Background/Async | Background task, worker, queue, async loop |
| External | Third-party API, gateway, external service |
| Configuration | Env var, config, setting, flag |
| API Endpoint | Endpoint, route, request, response |

Tasks often belong to multiple categories. Apply tests for all that match.
```

### New Step: Test Requirement Analysis

Add between Step 4 (Expand Tasks) and Step 5 (Review):

```markdown
### Step 4.5: Test Requirement Analysis

For each task, Claude performs this analysis:

**1. Identify Categories**

Read the task description and identify which categories apply.

Example for "Refactor OperationsService to Use Repository":
- Persistence (uses repository)
- Wiring/DI (factory provides repository)
- State Machine (operation status)

**2. Look Up Failure Modes**

For each category, consult the failure mode table:

| Category | Key Failure Modes |
|----------|------------------|
| Persistence | Not wired, wrong connection, transaction issues |
| Wiring/DI | Missing injection, wrong type, stale singleton |
| State Machine | Missing transition, invalid allowed, not persisted |
| Cross-Component | Contract mismatch, timing issues, error not propagated |
| Background/Async | Never starts, never stops, orphaned work, races |
| External | Connection, auth, parsing, timeout |
| Configuration | Missing required, wrong type, invalid value |
| API Endpoint | Missing validation, wrong status, state not changed |

**3. Require Appropriate Tests**

For each failure mode, add the corresponding test type to the task:

| Failure Mode | Test Type | Pattern |
|--------------|-----------|---------|
| Not wired | Wiring test | `assert get_{service}()._{dependency} is not None` |
| Missing transition | State coverage | Parameterized test for all `{from_state}` → `{to_state}` |
| Contract mismatch | Contract test | Capture calls between `{component_a}` and `{component_b}` |
| Never starts | Lifecycle test | `assert {task} is not None and not {task}.done()` |
| Connection failure | Connection test | Health check + error handling for `{external_service}` |
| Missing validation | Validation test | Test that `{endpoint}` returns 422 for invalid input |
| State not changed | DB verification | Query `{table}` directly after operation |

**4. Add Smoke Test**

For each task touching infrastructure, add a smoke test command.

**Template patterns** (substitute `{placeholders}` with actual names):

| Category | Smoke Test Pattern |
|----------|-------------------|
| Persistence | `psql -c "SELECT * FROM {table_name} LIMIT 1"` |
| Wiring/DI | Python: `get_{service_name}()._{dependency_name} is not None` |
| Background | `docker compose logs \| grep "{task_log_message}"` |
| Configuration | `env \| grep {ENV_VAR_NAME}` |

**Example** for OperationsService persistence task:
    psql -c "SELECT operation_id, status FROM operations LIMIT 1"
```

### Modify Task Template

Update the task template to include test analysis:

```markdown
## Task N.M: [Title]

**File(s):** [paths]
**Type:** CODING | RESEARCH | MIXED

**Task Categories:** [List categories that apply]

**Description:**
[What this task accomplishes]

**Implementation Notes:**
[Guidance, patterns, gotchas]

**Testing Requirements:**

*Unit Tests:*
- [ ] [Specific test cases]

*Integration Tests (based on categories):*
[For each category that applies, list required integration tests]

*Smoke Test:*
```bash
# Command to manually verify after implementation
[smoke test command]
```

**Acceptance Criteria:**
- [ ] [Functional criteria]
- [ ] [Required tests pass]
```

---

## Changes to `/kdesign-validate`

### Add to Gap Analysis Categories

The current gap analysis has categories like:
- State Machine Gaps
- Error Handling Gaps
- Data Shape Gaps
- Integration Gaps
- Concurrency Gaps

Add a new category:

```markdown
### Verification Gaps

For each component in the design, verify that the integration test approach is specified:

| Component | Type | Verification Approach | Specified? |
|-----------|------|----------------------|------------|
| OperationsService | Persistence + Wiring | Wiring test + DB query | ⬜ |
| OrphanDetector | Background + Persistence | Task lifecycle + DB query | ⬜ |
| WorkerRegistry | Cross-Component | Contract test | ⬜ |

**Red Flags:**
- Component stores data but no DB verification specified
- Component uses DI but no wiring test specified
- Component runs async but no lifecycle test specified
```

### Add to Scenario Walk-Through

When tracing scenarios, add verification checkpoints:

```markdown
### Execution Trace

| Step | Component | Action | **Verification** |
|------|-----------|--------|-----------------|
| 1 | API | POST /operations | Response test |
| 2 | Service | create_operation() | **Wiring: has repo?** |
| 3 | Repository | insert() | **DB: row exists?** |
| 4 | Background | start detection | **Lifecycle: task runs?** |
```

This surfaces verification gaps during design validation, not during implementation.

---

## Changes to `/kdesign`

### Add to Architecture Template

When drafting the architecture document, add a Verification Strategy section:

```markdown
## Verification Strategy

For each component, specify how its correctness will be verified beyond unit tests.

### [Component 1]
**Type:** [Categories]
**Unit Test Focus:** [What unit tests verify]
**Integration Test:** [What integration tests verify]
**Smoke Test:** [Quick manual check]

### [Component 2]
...
```

This forces thinking about verification during design, not after.

---

## Reference: Category → Test Mapping

Full mapping for Claude to use when generating tasks.

**Note:** All code snippets below are **templates**. Substitute placeholders like `{service}`, `{table}`, `{endpoint}` with actual names from the task being generated.

### Persistence Tasks

```markdown
**Categories:** Persistence, Wiring/DI
**Failure Modes:** Not wired, wrong connection, transaction issues, schema mismatch
**Required Tests:**
1. Wiring: `assert get_{service}()._{repository} is not None`
2. DB Verification: Query `{table}` directly after operation
3. Smoke: `psql -c "SELECT * FROM {table} LIMIT 1"`
```

### State Machine Tasks

```markdown
**Categories:** State Machine (often + Persistence)
**Failure Modes:** Missing transition, invalid transition allowed, state not persisted
**Required Tests:**
1. Transition coverage: Parameterized test for all valid transitions
2. Invalid rejection: Test that invalid transitions raise errors
3. Persistence: State changes survive cache clear / restart
4. Smoke: Check status in DB after state change
```

### Cross-Component Tasks

```markdown
**Categories:** Cross-Component (often + others)
**Failure Modes:** Contract mismatch, timing issues, errors not propagated
**Required Tests:**
1. Contract: Capture and verify data sent between components
2. End-to-end: Verify state at each layer after full flow
3. Error propagation: Verify errors surface correctly
4. Smoke: Trigger flow, check all component states
```

### Background Task

```markdown
**Categories:** Background/Async
**Failure Modes:** Never starts, never stops, orphaned work, race conditions
**Required Tests:**
1. Starts: `assert {service}._{task} is not None and not {service}._{task}.done()`
2. Stops: After stop(), `assert {service}._{task}.done()`
3. Does work: Wait for cycle, verify effect
4. Smoke: `docker compose logs | grep "{task_log_message}"`
```

### External Integration

```markdown
**Categories:** External
**Failure Modes:** Connection, auth, parsing, timeout handling
**Required Tests:**
1. Connection: `{client}.health_check()` returns OK
2. Response handling: Parse sample responses from `{external_service}` correctly
3. Error handling: Timeouts and errors raise appropriate exceptions
4. Smoke: `curl {external_endpoint}/health`
```

### Configuration Tasks

```markdown
**Categories:** Configuration
**Failure Modes:** Missing required, wrong type, invalid value
**Required Tests:**
1. Required: Startup fails without `{required_env_var}`
2. Defaults: Sensible defaults used when `{optional_env_var}` not set
3. Validation: Invalid values for `{config_field}` rejected
4. Smoke: `env | grep {ENV_VAR_PREFIX}`
```

### API Endpoint Tasks

```markdown
**Categories:** API Endpoint (often + Persistence)
**Failure Modes:** Missing validation, wrong status code, state not actually changed
**Required Tests:**
1. Happy path: `{method} {endpoint}` returns correct response for valid input
2. Validation: `{endpoint}` returns 422 for invalid input
3. State verification: Query `{table}` directly after API call
4. Smoke: `curl -X {method} {endpoint}` then query `{table}`
```

---

## Example: Applying to M1 Task 1.3

**Task:** "Refactor OperationsService to Use Repository"

**Current kdesign output:**
```markdown
## Task 1.3: Refactor OperationsService to Use Repository

**File(s):** ktrdr/api/services/operations_service.py
**Type:** CODING

**Description:** Refactor to use repository for persistence...

**Tests:**
- Unit tests with mocked repository
- Existing tests still pass

**Acceptance Criteria:**
- [ ] Service uses repository
- [ ] No behavior change for callers
```

**Improved kdesign output with test analysis:**
```markdown
## Task 1.3: Refactor OperationsService to Use Repository

**File(s):** ktrdr/api/services/operations_service.py
**Type:** CODING

**Task Categories:** Persistence, Wiring/DI, State Machine

**Description:** Refactor to use repository for persistence...

**Testing Requirements:**

*Unit Tests:*
- [ ] Service methods work with mocked repository
- [ ] Existing tests still pass

*Integration Tests:*
- [ ] **Wiring (CRITICAL):** `test_operations_service_has_repository()`
  - `assert get_operations_service()._repository is not None`
- [ ] **Persistence:** `test_operation_persists_to_db()`
  - Create operation, query DB directly, verify exists
- [ ] **State Persistence:** `test_status_change_persists()`
  - Change status, clear cache, query DB, verify changed

*Smoke Test:*
```bash
# After implementation:
docker compose exec db psql -U ktrdr -d ktrdr -c \
  "SELECT operation_id, status FROM operations LIMIT 1"
# Should see operations if service is working
```

**Acceptance Criteria:**
- [ ] Service uses repository for persistence
- [ ] Wiring test passes
- [ ] DB verification test passes
- [ ] State persistence test passes
- [ ] Smoke test shows data in DB
```

---

## Summary

The improvements add systematic test analysis to kdesign commands:

1. **Categorize** each task by type
2. **Identify** failure modes for those types
3. **Require** appropriate integration/smoke tests
4. **Verify** during design validation that verification approach is specified

This prevents "components work but aren't connected" bugs by making integration testing a first-class part of the design process, not an afterthought.
