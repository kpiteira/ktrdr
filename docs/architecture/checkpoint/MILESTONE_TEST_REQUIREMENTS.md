# Milestone Test Requirements Framework

**Purpose:** Provide a systematic approach for identifying what integration and smoke tests each task needs, based on the type of work being done.

**Key Insight:** Unit tests verify component behavior in isolation. Integration/smoke tests verify that components are actually connected and working together. Every task type has specific failure modes that require specific verification approaches.

---

## How to Use This Document

For each task in a milestone:

1. **Identify the task category** (see Section 1)
2. **Look up the failure modes** for that category (see Section 2)
3. **Apply the verification patterns** (see Section 3)
4. **Add the appropriate tests** to the task specification

---

## Section 1: Task Category Identification

Read the task description and identify which category or categories apply.

### Category: Persistence
**Indicators in task description:**
- Creates/modifies database tables, models, or migrations
- Creates/modifies repositories
- Service that stores or retrieves data
- Words: "persist", "store", "save", "database", "repository"

**Example tasks:**
- "Create operations table and migration"
- "Add repository for checkpoints"
- "Refactor service to use repository"

### Category: Dependency Injection / Wiring
**Indicators in task description:**
- Creates factory functions (`get_X_service()`)
- Service accepts dependencies in constructor
- Uses dependency injection patterns
- Words: "inject", "factory", "singleton", "initialize"

**Example tasks:**
- "Create OperationsService with repository injection"
- "Add get_checkpoint_service() factory"

### Category: State Machine
**Indicators in task description:**
- Status/state fields and transitions
- Workflow stages
- Lifecycle management
- Words: "status", "state", "transition", "phase", "stage"

**Example tasks:**
- "Add operation status transitions"
- "Implement session state machine"
- "Handle cancelled state"

### Category: Cross-Component Integration
**Indicators in task description:**
- One component calling another
- Data flowing between services
- Event/message passing
- Words: "calls", "integrates with", "sends to", "receives from"

**Example tasks:**
- "Worker reports completion to backend"
- "Training service triggers backtest service"

### Category: Background/Async Operations
**Indicators in task description:**
- Background tasks or workers
- Async operations with callbacks
- Long-running processes
- Words: "background", "async", "worker", "task", "queue"

**Example tasks:**
- "Add orphan detection background task"
- "Implement health check loop"

### Category: External Integration
**Indicators in task description:**
- Third-party APIs or services
- External systems (IB Gateway, etc.)
- Network calls to external endpoints
- Words: "external", "API", "gateway", "third-party"

**Example tasks:**
- "Connect to IB Gateway"
- "Fetch market data from provider"

### Category: Configuration
**Indicators in task description:**
- Environment variables
- Settings files
- Feature flags
- Words: "config", "setting", "environment", "flag"

**Example tasks:**
- "Add checkpoint interval configuration"
- "Configure worker timeouts via env"

### Category: API Endpoints
**Indicators in task description:**
- REST endpoints
- Request/response handling
- Validation and error responses
- Words: "endpoint", "route", "API", "request", "response"

**Example tasks:**
- "Add GET /checkpoints/{id} endpoint"
- "Update worker registration endpoint"

---

## Section 2: Failure Modes by Category

Each category has specific ways things can go wrong. Understanding these helps you design tests that catch them.

### Persistence Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Not wired** | Repository not injected into service | Data in memory only, lost on restart |
| **Wrong connection** | Using wrong database/table | Data written to wrong location |
| **Transaction issues** | Commits not happening | Data appears saved but isn't |
| **Schema mismatch** | Code and DB schema out of sync | Runtime errors or silent data loss |

### Dependency Injection Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Missing injection** | Factory doesn't provide dependency | NoneType errors or silent failures |
| **Wrong type** | Wrong implementation injected | Unexpected behavior |
| **Stale singleton** | Old instance used after config change | Using outdated configuration |

### State Machine Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Missing transition** | Valid state change not handled | Operations stuck or error |
| **Invalid transition allowed** | Should-be-blocked transition succeeds | Data corruption |
| **State/data desync** | State says X but data says Y | Inconsistent behavior |
| **Lost transition** | State change not persisted | State resets on restart |

### Cross-Component Integration Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Contract mismatch** | Sender/receiver expect different data | Runtime errors or silent drops |
| **Timing issues** | Components not ready when called | Race conditions |
| **Missing error propagation** | Errors not communicated | Silent failures |
| **Circular dependencies** | A needs B needs A | Deadlock or startup failure |

### Background/Async Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Never starts** | Background task not initiated | Feature doesn't work |
| **Never stops** | Task continues after should stop | Resource leak |
| **Orphaned work** | Task dies, work left incomplete | Stuck operations |
| **Race conditions** | Concurrent access issues | Intermittent failures |

### External Integration Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Connection failure** | Can't reach external service | Errors or hangs |
| **Auth failure** | Wrong credentials | 401/403 errors |
| **Response parsing** | Unexpected response format | Parse errors |
| **Timeout handling** | No timeout or wrong timeout | Hangs or premature failures |

### Configuration Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Missing required** | Required config not set | Startup failure or wrong defaults |
| **Wrong type** | String where int expected | Runtime errors |
| **Invalid value** | Out of range or invalid | Unexpected behavior |
| **Not reloaded** | Config change requires restart | Stale configuration |

### API Endpoint Failure Modes

| Failure Mode | Description | How It Manifests |
|--------------|-------------|------------------|
| **Missing validation** | Bad input not rejected | Data corruption or errors |
| **Wrong status code** | Success returns error or vice versa | Confusing behavior |
| **Missing auth** | Unauthenticated access allowed | Security hole |
| **Response shape wrong** | Response doesn't match contract | Client errors |

---

## Section 3: Verification Patterns by Category

For each category, here are the specific tests needed.

### Persistence Verification

**1. Wiring Test (CRITICAL - catches "not connected" bugs)**
```python
def test_service_has_repository():
    """Verify factory injects repository."""
    service = get_X_service()
    assert service._repository is not None, (
        "Repository not injected - data will not persist!"
    )
```

**2. Direct DB Verification (CRITICAL - catches "writes to wrong place" bugs)**
```python
async def test_operation_persists_to_db(db_session):
    """Verify data actually reaches database."""
    # Do operation via service
    await service.create(data)

    # Query DB DIRECTLY, not through service
    result = await db_session.execute(
        select(Model).where(Model.id == data.id)
    )
    record = result.scalar_one_or_none()

    assert record is not None, "Data not found in database!"
```

**3. Smoke Test Command**
```bash
# After task completion, verify DB state:
docker compose exec db psql -U user -d db -c "SELECT * FROM table LIMIT 5"
```

### Dependency Injection Verification

**1. Wiring Test**
```python
def test_factory_injects_all_dependencies():
    """Verify all dependencies are provided."""
    service = get_service()
    assert service._dep1 is not None
    assert service._dep2 is not None
    assert isinstance(service._dep1, ExpectedType)
```

**2. Smoke Test**
```python
# In Python REPL or test:
from module import get_service
service = get_service()
print(f"dep1: {service._dep1}")  # Should not be None
```

### State Machine Verification

**1. Transition Coverage Test**
```python
@pytest.mark.parametrize("from_state,event,to_state", [
    ("PENDING", "start", "RUNNING"),
    ("RUNNING", "complete", "COMPLETED"),
    ("RUNNING", "fail", "FAILED"),
    ("RUNNING", "cancel", "CANCELLED"),
    # ... all valid transitions
])
async def test_valid_transitions(from_state, event, to_state):
    """Verify all valid transitions work."""
    entity = create_in_state(from_state)
    await service.handle_event(entity.id, event)
    assert entity.status == to_state
```

**2. Invalid Transition Test**
```python
@pytest.mark.parametrize("from_state,event", [
    ("COMPLETED", "start"),  # Can't restart completed
    ("FAILED", "complete"),  # Can't complete failed
    # ... all invalid transitions
])
async def test_invalid_transitions_rejected(from_state, event):
    """Verify invalid transitions are blocked."""
    entity = create_in_state(from_state)
    with pytest.raises(InvalidTransitionError):
        await service.handle_event(entity.id, event)
```

**3. Persistence of State Change**
```python
async def test_state_change_persists(db_session):
    """Verify state changes survive restart."""
    entity = await service.create()
    await service.transition(entity.id, "RUNNING")

    # Query DB directly
    record = await db_session.get(Model, entity.id)
    assert record.status == "RUNNING"
```

### Cross-Component Integration Verification

**1. Contract Test**
```python
async def test_component_a_sends_correct_data_to_b():
    """Verify data contract between components."""
    # Capture what A sends
    captured = []
    mock_b = Mock(side_effect=lambda x: captured.append(x))

    a = ComponentA(b=mock_b)
    await a.do_operation()

    # Verify contract
    assert len(captured) == 1
    assert "required_field" in captured[0]
    assert isinstance(captured[0]["required_field"], ExpectedType)
```

**2. End-to-End Flow Test**
```python
async def test_full_flow_a_to_b_to_c():
    """Verify data flows correctly through all components."""
    result = await trigger_flow()

    # Verify state at each layer
    assert a_state == expected_a
    assert b_state == expected_b
    assert c_state == expected_c
```

### Background/Async Verification

**1. Task Starts Test**
```python
async def test_background_task_starts():
    """Verify background task actually starts."""
    service = await create_service()
    await service.start()

    # Task should be running
    assert service._background_task is not None
    assert not service._background_task.done()
```

**2. Task Stops Test**
```python
async def test_background_task_stops_cleanly():
    """Verify task stops when service stops."""
    service = await create_service()
    await service.start()
    await service.stop()

    # Task should be done
    assert service._background_task.done()
    # No exceptions
    service._background_task.result()  # Raises if task failed
```

**3. Work Completion Test**
```python
async def test_background_work_completes():
    """Verify background task actually does its work."""
    service = await create_service()
    await service.start()

    # Wait for one cycle
    await asyncio.sleep(service.interval + 0.1)

    # Work should be done
    assert work_was_done()
```

### External Integration Verification

**1. Connection Test**
```python
async def test_can_connect_to_external_service():
    """Verify we can reach the external service."""
    client = ExternalClient(config)
    health = await client.health_check()
    assert health.ok
```

**2. Contract Test (with mock/stub)**
```python
async def test_handles_external_response_correctly():
    """Verify we parse external responses correctly."""
    # Use recorded response or mock
    with responses.mock:
        responses.add(responses.GET, URL, json=SAMPLE_RESPONSE)
        result = await client.fetch_data()

    assert result.field == expected_value
```

**3. Error Handling Test**
```python
async def test_handles_external_timeout():
    """Verify timeout is handled gracefully."""
    with responses.mock:
        responses.add(responses.GET, URL, body=Timeout())

        with pytest.raises(ServiceUnavailableError):
            await client.fetch_data()
```

### Configuration Verification

**1. Required Config Test**
```python
def test_fails_without_required_config():
    """Verify startup fails if required config missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigurationError):
            load_config()
```

**2. Default Values Test**
```python
def test_uses_correct_defaults():
    """Verify default values are sensible."""
    config = load_config()
    assert config.timeout == 30  # Not 0 or infinity
    assert config.retry_count == 3  # Reasonable default
```

**3. Smoke Test**
```bash
# Verify config is loaded:
docker compose exec backend env | grep RELEVANT_VAR
```

### API Endpoint Verification

**1. Happy Path Test**
```python
async def test_endpoint_returns_correct_response():
    """Verify endpoint works for valid input."""
    response = await client.post("/api/endpoint", json=valid_data)
    assert response.status_code == 200
    assert response.json()["field"] == expected_value
```

**2. Validation Test**
```python
async def test_endpoint_rejects_invalid_input():
    """Verify validation catches bad input."""
    response = await client.post("/api/endpoint", json=invalid_data)
    assert response.status_code == 422  # Validation error
```

**3. State Verification (IMPORTANT)**
```python
async def test_endpoint_actually_changes_state(db_session):
    """Verify endpoint changes underlying state, not just returns success."""
    response = await client.post("/api/create", json=data)
    assert response.status_code == 200

    # Verify DB directly - don't trust the response!
    record = await db_session.get(Model, response.json()["id"])
    assert record is not None
```

---

## Section 4: Applying to Milestones

### Step-by-Step Process

For each task in a milestone:

1. **Read the task description**
2. **Identify categories** that apply (often multiple)
3. **List failure modes** for each category
4. **Select verification patterns** that catch those failures
5. **Write the specific tests** for this task
6. **Add smoke test command** where applicable

### Example: Task "Refactor OperationsService to Use Repository"

**Step 1-2: Categories identified:**
- Persistence (uses repository)
- Dependency Injection (service accepts repository)
- State Machine (operation status)

**Step 3: Failure modes:**
- Persistence: Not wired, transaction issues
- DI: Missing injection, wrong type
- State: State changes not persisted

**Step 4-5: Tests needed:**
```python
# Wiring (catches the M1 bug!)
def test_operations_service_has_repository():
    service = get_operations_service()
    assert service._repository is not None

# Persistence
async def test_operation_persists_to_db(db_session):
    await service.create_operation(...)
    record = await db_session.get(OperationRecord, op_id)
    assert record is not None

# State persistence
async def test_status_change_persists(db_session):
    await service.update_status(op_id, "RUNNING")
    record = await db_session.get(OperationRecord, op_id)
    assert record.status == "running"
```

**Step 6: Smoke test:**
```bash
# Create operation, then:
docker compose exec db psql -U ktrdr -d ktrdr -c \
    "SELECT operation_id, status FROM operations ORDER BY created_at DESC LIMIT 1"
```

---

## Section 5: When No Integration Test Is Needed

Not every task needs integration tests. Skip them when:

- **Pure refactoring** - No behavior change, existing tests cover it
- **Documentation only** - No code changes
- **Pure unit logic** - Self-contained calculation with no external dependencies
- **Test-only changes** - Adding tests to existing code

**But be careful:** If you find yourself saying "this is just a simple change," ask:
- Does it touch persistence? → Need DB verification
- Does it add/modify a factory function? → Need wiring test
- Does it change state transitions? → Need transition tests
- Does it cross component boundaries? → Need integration test

---

## Quick Reference Card

| Category | Key Test | Smoke Command |
|----------|----------|---------------|
| Persistence | Query DB directly after operation | `psql -c "SELECT * FROM table"` |
| Wiring/DI | Assert dependency is not None | Python REPL: `service._dep` |
| State Machine | Test all transitions + persistence | Check status in DB |
| Cross-Component | End-to-end flow test | Trigger flow, check all states |
| Background | Task starts, stops, does work | Check logs for task activity |
| External | Connection + error handling | `curl` to external endpoint |
| Config | Required config + defaults | `env \| grep CONFIG` |
| API | Response + underlying state | Call API, then check DB |
