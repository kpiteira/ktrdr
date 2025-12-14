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

## Task 2.4 Completed

Indicator/symbol discovery tools were already implemented prior to M2.

### Existing Implementation

| Handler | Location | Behavior |
|---------|----------|----------|
| `_handle_get_available_indicators` | `executor.py:380` | Calls real API via `get_indicators_from_api()` |
| `_handle_get_available_symbols` | `executor.py:388` | Calls real API via `get_symbols_from_api()` |

Tests: `test_get_indicators_calls_api`, `test_get_symbols_calls_api`

---

## Gotchas for Task 2.5+

1. **ToolExecutor state tracking** - `last_saved_strategy_name` and `last_saved_strategy_path` are set when `save_strategy_config` succeeds.

2. **Logger style** - Use f-string formatting with `ktrdr.get_logger`, NOT structlog-style keyword args.

3. **OperationMetadata type ignore** - Use `# type: ignore[call-arg]` when creating OperationMetadata with only `parameters`.
