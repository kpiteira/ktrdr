# M2 Handoff: Design Worker

## Task 2.1 Completed

Created `AgentDesignWorker` that uses Claude to design trading strategies.

### Files Created/Modified

| File | Change |
|------|--------|
| `ktrdr/agents/workers/design_worker.py` | New - AgentDesignWorker class |
| `ktrdr/agents/executor.py` | Added `last_saved_strategy_name/path` state tracking |
| `tests/unit/agent_tests/test_design_worker.py` | New - 10 unit tests |

---

## Task 2.2 Completed

Wired real `AgentDesignWorker` into the orchestrator, replacing stub.

### Files Modified

| File | Change |
|------|--------|
| `ktrdr/api/services/agent_service.py` | Replace `StubDesignWorker()` with `AgentDesignWorker(self.ops)` |
| `tests/unit/agent_tests/test_agent_service_new.py` | Added 5 tests for design worker wiring |

### Verification

- Real design worker is called when phase enters "designing"
- Strategy name propagates to parent metadata (already in `research_worker.py`)
- Stub workers remain for training, backtest, assessment

---

## Task 2.3 Completed

Strategy tracking in parent metadata was already implemented in M1 (`_advance_to_next_phase`).
Task 2.3 adds test coverage to verify all acceptance criteria.

### Tests Added

| Test | Verifies |
|------|----------|
| `test_stores_strategy_path_after_design` | `strategy_path` stored in parent metadata |
| `test_status_returns_strategy_name_when_active` | Status endpoint returns `strategy_name` |

### Key Finding

No implementation was needed - functionality existed from M1 Task 1.10 (polling loop pattern).

---

## Gotchas for Task 2.4+

1. **ToolExecutor state tracking** - The `ToolExecutor` now tracks `last_saved_strategy_name` and `last_saved_strategy_path`. These are set when `save_strategy_config` succeeds. The design worker reads these after the invoker completes.

2. **Logger style** - Use f-string formatting with `ktrdr.get_logger`, NOT structlog-style keyword args:
   ```python
   # Correct
   logger.info(f"Phase completed: {phase}")

   # Wrong - will cause TypeError
   logger.info("Phase completed", phase=phase)
   ```

3. **OperationMetadata type ignore** - Use `# type: ignore[call-arg]` when creating OperationMetadata with only `parameters`:
   ```python
   metadata=OperationMetadata(  # type: ignore[call-arg]
       parameters={"parent_operation_id": operation_id}
   )
   ```

### Entry Points for Task 2.2

Wire the design worker into the orchestrator:

```python
# In agent_service.py
from ktrdr.agents.workers.design_worker import AgentDesignWorker

# Replace StubDesignWorker with AgentDesignWorker
design_worker=AgentDesignWorker(self.ops)
```

The `AgentDesignWorker.run()` signature matches the stub:
- Input: `operation_id: str` (the parent AGENT_RESEARCH operation ID)
- Output: `dict` with `success`, `strategy_name`, `strategy_path`, `input_tokens`, `output_tokens`
