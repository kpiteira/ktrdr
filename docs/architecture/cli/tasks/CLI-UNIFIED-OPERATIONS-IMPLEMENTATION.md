# CLI Unified Operations Pattern - Implementation Plan

**Parent Design**: [Unified CLI Operations Design](../unified_cli_operations_design.md)
**Status**: Ready for Implementation
**Version**: 2.0
**Date**: 2025-09-30

---

## Overview

This document breaks down the implementation of the unified CLI operations pattern into discrete, testable tasks following the adapter pattern approved in design document v2.0.

**Key Architecture Components**:
- `AsyncOperationExecutor`: Generic infrastructure (HTTP, polling, signals, progress)
- `OperationAdapter`: Abstract interface defining the contract
- Concrete adapters: Domain-specific knowledge for each operation type

**Scope**: Training + Dummy commands (Data Loading deferred to future work)

**Branching Strategy**:
- **Feature Branch**: `feature/cli-unified-operations` (off `feature/training-service-orchestrator`)
- **Merge Target**: `feature/training-service-orchestrator`
- **After Merge**: Delete feature branch

**Migration Philosophy**: Incremental, non-breaking changes with continuous testing

---

## Phase 1: Foundation (Additive Only)

**Branch Setup**:
```bash
# Create feature branch off current branch
git checkout -b feature/cli-unified-operations
```

### TASK-1.1: Create AsyncOperationExecutor

**Objective**: Build the generic async operation executor with zero domain knowledge

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/operation_executor.py` (NEW)
- `tests/unit/cli/test_operation_executor.py` (NEW)

**What It Does**:
- Manages HTTP client lifecycle (create, reuse, cleanup)
- Sets up and tears down signal handlers for Ctrl+C
- Polls operations API at `/api/v1/operations/{id}` until completion
- Integrates with `EnhancedCLIProgressDisplay` for consistent progress bars
- Handles cancellation via `/api/v1/operations/{id}/cancel`
- Coordinates error handling and recovery
- Delegates domain-specific decisions to adapter interface

**What It Doesn't Know**:
- Which endpoints to call to start operations (adapter provides)
- What parameters to send (adapter provides)
- How to interpret domain-specific results (adapter handles)
- Any business logic about training, data loading, etc.

**Key Methods**:
```python
class AsyncOperationExecutor:
    async def execute_operation(
        self,
        adapter: OperationAdapter,
        console: Console,
        options: dict,
    ) -> bool:
        """Execute an async operation end-to-end."""

    async def _poll_until_complete(
        self,
        operation_id: str,
    ) -> dict | None:
        """Poll operation status until terminal state."""

    async def _handle_cancellation(
        self,
        operation_id: str,
    ) -> None:
        """Send cancellation request to backend."""
```

**Acceptance Criteria**:
- [ ] Executor polls operations API at 300ms intervals
- [ ] Signal handler registers/unregisters correctly for Ctrl+C
- [ ] Cancellation detected and sent to backend within 300ms
- [ ] Progress display integrates with `EnhancedCLIProgressDisplay`
- [ ] HTTP errors handled with appropriate retry logic
- [ ] Executor has zero domain-specific knowledge
- [ ] All unit tests pass
- [ ] Code coverage >80%

**Testing Strategy**:
- Mock adapter interface for unit tests
- Mock HTTP client for network isolation
- Test cancellation flow end-to-end
- Test error recovery and retry logic
- Test progress display integration

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
git add ktrdr/cli/operation_executor.py tests/unit/cli/test_operation_executor.py
git commit -m "feat(cli): add AsyncOperationExecutor for unified async operations"
```

---

### TASK-1.2: Create OperationAdapter Interface

**Objective**: Define the contract between executor and domain logic

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/operation_adapters.py` (NEW - interface only)
- `tests/unit/cli/test_operation_adapter_interface.py` (NEW)

**Interface Definition**:
```python
from abc import ABC, abstractmethod
from typing import Any
from httpx import AsyncClient
from rich.console import Console

class OperationAdapter(ABC):
    """
    Abstract interface for operation-specific logic.

    Separates generic async operation infrastructure from domain knowledge.
    Adapters are lightweight translators (~50-100 lines each).
    """

    @abstractmethod
    def get_start_endpoint(self) -> str:
        """Return HTTP endpoint to start this operation."""

    @abstractmethod
    def get_start_payload(self) -> dict[str, Any]:
        """Return JSON payload for start request."""

    @abstractmethod
    def parse_start_response(self, response: dict) -> str:
        """Extract operation_id from start response."""

    @abstractmethod
    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """Display final results after operation completes."""
```

**Acceptance Criteria**:
- [ ] Interface defined with 4 required methods
- [ ] Clear docstrings explaining each method's purpose
- [ ] Type hints for all parameters and returns
- [ ] Example implementation in docstring
- [ ] Unit tests verify interface contract

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/operation_adapters.py tests/unit/cli/test_operation_adapter_interface.py
git commit -m "feat(cli): add OperationAdapter interface for domain-specific logic"
```

---

## Phase 2: Create Concrete Adapters

### TASK-2.1: TrainingOperationAdapter

**Objective**: Implement adapter for training operations

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/operation_adapters.py` (MODIFY - add TrainingOperationAdapter)
- `tests/unit/cli/test_training_adapter.py` (NEW)

**What It Knows**:
- Training API endpoint: `/api/v1/trainings/start`
- Training request payload format (strategy_name, symbols, timeframes, etc.)
- How to fetch detailed training metrics: `/api/v1/trainings/{id}/performance`
- How to display training results (accuracy, precision, recall, F1, model size)

**Constructor Parameters**:
```python
TrainingOperationAdapter(
    strategy_name: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str | None,
    end_date: str | None,
    validation_split: float,
    detailed_analytics: bool,
)
```

**Acceptance Criteria**:
- [ ] Implements all 4 OperationAdapter methods
- [ ] `get_start_endpoint()` returns correct training endpoint
- [ ] `get_start_payload()` constructs valid training request
- [ ] `parse_start_response()` extracts operation_id correctly
- [ ] `display_results()` fetches and displays training metrics
- [ ] Adapter is <100 lines of code
- [ ] Unit tests cover all methods
- [ ] Integration test verifies actual API contract

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/operation_adapters.py tests/unit/cli/test_training_adapter.py
git commit -m "feat(cli): add TrainingOperationAdapter for training commands"
```

---

### TASK-2.2: DummyOperationAdapter (Reference Implementation)

**Objective**: Create simple reference adapter for testing and examples

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/operation_adapters.py` (MODIFY - add DummyOperationAdapter)
- `tests/unit/cli/test_dummy_adapter.py` (NEW)

**Purpose**:
- Simplest possible adapter implementation
- Reference for developers adding new operations
- Used for testing executor without backend dependencies

**Constructor Parameters**:
```python
DummyOperationAdapter(
    duration: int,
    iterations: int,
)
```

**Acceptance Criteria**:
- [ ] Implements all 4 OperationAdapter methods
- [ ] <50 lines of code (simplest adapter)
- [ ] Clear inline comments explaining each method
- [ ] Unit tests pass
- [ ] Can be used with executor for end-to-end testing

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/operation_adapters.py tests/unit/cli/test_dummy_adapter.py
git commit -m "feat(cli): add DummyOperationAdapter for testing and reference"
```

---

## Phase 3: Migrate Training Command

### TASK-3.1: Refactor Training Command to Use Executor

**Objective**: Rewrite `async_model_commands.py` to use new infrastructure

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/async_model_commands.py` (REWRITE)
- `tests/integration/cli/test_training_command.py` (MODIFY)

**Changes**:
- Remove `AsyncCLIClient` usage
- Remove custom signal handling code (~30 lines)
- Remove custom polling loop code (~150 lines)
- Remove custom progress display code (~50 lines)
- Create `TrainingOperationAdapter` with parameters
- Create `AsyncOperationExecutor`
- Call `executor.execute_operation(adapter, console, options)`

**Expected Code Reduction**:
- Before: ~350 lines in training command
- After: ~80 lines in training command
- Reduction: ~77% less code

**New Command Structure**:
```python
async def _train_model_async(
    strategy_name: str,
    symbols: list[str],
    timeframes: list[str],
    # ... other params
):
    # 1. Check API connection
    # 2. Display operation header
    # 3. Create adapter
    adapter = TrainingOperationAdapter(
        strategy_name=strategy_name,
        symbols=symbols,
        timeframes=timeframes,
        # ...
    )
    # 4. Create executor
    executor = AsyncOperationExecutor(base_url=API_URL)
    # 5. Execute
    success = await executor.execute_operation(adapter, console, options)
    # 6. Exit with appropriate code
    sys.exit(0 if success else 1)
```

**Acceptance Criteria**:
- [ ] Training starts successfully
- [ ] Progress displays correctly with smooth updates
- [ ] **Cancellation works (Ctrl+C stops training)**
- [ ] Final results display correctly
- [ ] No regressions in functionality
- [ ] Code reduced by >60%
- [ ] All existing training tests pass
- [ ] Integration tests verify end-to-end flow

**Manual Testing**:
```bash
# Test training command
ktrdr models train strategies/trend_momentum.yaml AAPL 1h \
  --start-date 2024-01-01 --end-date 2024-03-01

# Test cancellation
# Start training, then press Ctrl+C after a few seconds
# Verify: "Training cancellation sent successfully"
# Verify: Backend training actually stops (check logs)
```

**Commit After**:
```bash
make test-unit
make test-integration  # Verify training command
git add ktrdr/cli/async_model_commands.py tests/
git commit -m "refactor(cli): migrate training command to unified operations pattern

Fixes training cancellation bug. Training command now uses AsyncOperationExecutor
with TrainingOperationAdapter for consistent, maintainable async operation handling.

Before: Custom polling/signal handling, broken cancellation
After: Unified pattern, working cancellation, 60% less code"
```

---

### TASK-3.2: Refactor Dummy Command to Use Executor

**Objective**: Migrate dummy command to prove pattern works for multiple operations

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/dummy_commands.py` (REWRITE)
- `tests/integration/cli/test_dummy_command.py` (MODIFY)

**Changes**:
- Replace custom polling/cancellation code
- Use `AsyncOperationExecutor` with `DummyOperationAdapter`
- Maintain identical user experience

**Expected Code Reduction**:
- Before: ~200 lines
- After: ~50 lines
- Reduction: ~75% less code

**Acceptance Criteria**:
- [ ] Dummy command works identically to before
- [ ] Progress displays correctly
- [ ] Cancellation works
- [ ] All tests pass
- [ ] Code reduced by >70%

**Manual Testing**:
```bash
# Test dummy command
ktrdr dummy start --duration 10 --iterations 100

# Test cancellation
# Start dummy, press Ctrl+C after a few iterations
# Verify cancellation works
```

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/dummy_commands.py tests/
git commit -m "refactor(cli): migrate dummy command to unified operations pattern"
```

---

## Phase 4: Verification and Testing

### TASK-4.1: End-to-End Integration Tests

**Objective**: Verify the complete flow works end-to-end

**Branch**: `feature/cli-unified-operations`

**Files**:
- `tests/integration/cli/test_unified_operations.py` (NEW)

**Test Scenarios**:
- [ ] Training command starts and completes successfully
- [ ] Training command cancels correctly when Ctrl+C pressed
- [ ] Training command handles backend failures gracefully
- [ ] Progress updates are accurate and responsive (<500ms lag)
- [ ] Final results display correctly with all metrics
- [ ] Dummy command works end-to-end
- [ ] Dummy command cancellation works

**Commit After**:
```bash
make test-integration
git add tests/integration/cli/test_unified_operations.py
git commit -m "test(cli): add integration tests for unified operations pattern"
```

---

### TASK-4.2: Verify Epochs Configuration (Separate Issue)

**Objective**: Verify epochs from strategy YAML pass through correctly

**Note**: This was already fixed in commit `34026e9` but needs verification

**Files**:
- `ktrdr/training/training_adapter.py` (VERIFY)
- `ktrdr/api/services/training/host_session.py` (VERIFY)
- `training-host-service/services/training_service.py` (VERIFY)

**Verification Steps**:
1. Start training with strategy containing `epochs: 10`
2. Check main API logs for "Sending training_configuration to host"
3. Verify `training_configuration` contains `"epochs": 10`
4. Check host service logs for "Received training_configuration"
5. Verify progress updates correctly (10% → 20% → ... → 100%)

**Acceptance Criteria**:
- [ ] Main API sends epochs in training_configuration
- [ ] Host service receives and uses epochs value
- [ ] Progress percentage matches actual training progress
- [ ] No defaulting to 100 epochs when strategy has different value

---

### TASK-4.3: Fix Rich Progress Context Regression

**Objective**: Restore rich training progress details (epochs, batches, GPU info) in CLI display

**Context**: The unified operations pattern successfully fixed cancellation, but introduced a regression where training progress now only shows basic "Status: running" instead of detailed epoch/batch/GPU information that was previously available.

**Root Cause Analysis**:

- `TrainingProgressBridge` already creates rich context data (epoch_index, batch_number, resource_usage)
- `current_step` field contains formatted string: "Epoch 1/100 · Batch 1/45 [1/100] (0.0%)"
- However, `GenericProgressState.context` is NOT being rendered into a structured format for the CLI
- The system has `ProgressRenderer` infrastructure (see `DataProgressRenderer`) but training doesn't use it

**Correct Solution**: Create `TrainingProgressRenderer` following the proven `ProgressRenderer` pattern

**Branch**: `feature/cli-unified-operations`

**Files**:

- `ktrdr/api/services/training/training_progress_renderer.py` (NEW)
- `ktrdr/api/services/training_service.py` (MODIFY - inject renderer into GenericProgressManager)
- `ktrdr/api/models/operations.py` (MODIFY - add context field to OperationProgress) ✅ DONE
- `ktrdr/api/services/training_service.py` (MODIFY - ensure context passed to OperationProgress)
- `ktrdr/cli/async_model_commands.py` (CLEANUP - remove debug code)
- `tests/unit/api/services/training/test_training_progress_renderer.py` (NEW)
- `tests/integration/cli/test_unified_operations.py` (MODIFY - test rich progress context)

**Implementation Steps**:

1. **Create TrainingProgressRenderer** (follows DataProgressRenderer pattern):

   ```python
   # ktrdr/api/services/training/training_progress_renderer.py
   class TrainingProgressRenderer(ProgressRenderer):
       """Renders rich training progress messages from context data."""

       def render_message(self, state: GenericProgressState) -> str:
           """Format training-specific progress with epochs, batches, GPU."""
           # Extract from state.context (populated by TrainingProgressBridge)
           epoch_index = state.context.get("epoch_index", 0)
           total_epochs = state.context.get("total_epochs", 0)
           batch_number = state.context.get("batch_number", 0)
           batch_total = state.context.get("batch_total_per_epoch", 0)

           # Build rich message
           msg = state.message  # Base message from bridge
           if epoch_index > 0 and total_epochs > 0:
               msg = f"Epoch {epoch_index}/{total_epochs}"
               if batch_number > 0:
                   msg += f" · Batch {batch_number}/{batch_total}"

           # Add GPU info if available
           resource_usage = state.context.get("resource_usage", {})
           if resource_usage.get("gpu_used"):
               gpu_name = resource_usage.get("gpu_name", "GPU")
               gpu_util = resource_usage.get("gpu_utilization_percent")
               if gpu_util:
                   msg += f" 🖥️ {gpu_name}: {gpu_util:.0f}%"

           return msg
   ```

2. **Inject renderer when creating GenericProgressManager**:

   ```python
   # ktrdr/api/services/training_service.py
   from .training.training_progress_renderer import TrainingProgressRenderer

   # In _run_local_via_orchestrator() and _run_host_via_orchestrator():
   renderer = TrainingProgressRenderer()
   # Pass to GenericProgressManager constructor
   ```

3. **Ensure ServiceOrchestrator passes context to OperationProgress**:
   - Verify that when converting GenericProgressState → OperationProgress
   - The `state.context` dict is included in `OperationProgress.context`
   - This ensures CLI receives structured data, not just formatted strings

4. **Update CLI callback to use context** (already exists in format_training_progress):
   - Extract from `progress_info.get("context", {})`
   - Build rich status message for progress bar description

**Expected Progress Display**:

Before (Current - Regression):
```
Training: 45% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 00:02:30
```

After (Fixed):
```
Training: 45% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 00:02:30
Status: running (Epoch: 5/10, Batch: 120/500) 🖥️ RTX 3090: 85%
```

**Acceptance Criteria**:

- [ ] `TrainingProgressRenderer` class created following `DataProgressRenderer` pattern
- [ ] Renderer extracts epoch_index, total_epochs, batch_number from state.context
- [ ] Renderer extracts GPU info from state.context.resource_usage
- [ ] Renderer injected into GenericProgressManager for training operations
- [ ] `OperationProgress` has `context: dict[str, Any]` field ✅ DONE
- [ ] ServiceOrchestrator passes `state.context` to `OperationProgress.context`
- [ ] Training progress shows epoch numbers (e.g., "Epoch: 5/10")
- [ ] Training progress shows batch numbers (e.g., "Batch: 120/500")
- [ ] Training progress shows GPU info when available (e.g., "🖥️ RTX 3090: 85%")
- [ ] Dummy operation still works (generic progress without renderer)
- [ ] Unit tests for TrainingProgressRenderer pass
- [ ] Integration test verifies rich progress context flows correctly
- [ ] No breaking changes to existing operations
- [ ] All unit and integration tests pass
- [ ] Quality checks pass

**Testing Strategy**:

1. **Unit Tests** (`test_training_progress_renderer.py`):
   - Test renderer with epoch-only context
   - Test renderer with epoch + batch context
   - Test renderer with epoch + batch + GPU context
   - Test renderer with empty context (graceful fallback)
   - Test renderer extracts correct values from state.context

2. **Integration Tests** (`test_unified_operations.py`):
   - Test rich progress context flows from API to CLI
   - Verify `format_training_progress` callback receives populated context
   - Verify context contains: epoch_index, total_epochs, batch_number, resource_usage

3. **Manual Testing**:
   ```bash
   # Start training and verify progress display shows:
   ktrdr models train strategies/trend_momentum.yaml AAPL 1h \
     --start-date 2024-01-01 --end-date 2024-03-01

   # Expected output should include:
   # Status: running (Epoch: 5/10, Batch: 120/500) 🖥️ GPU: 85%
   ```

**Rollback Plan**:
If this introduces issues, the `context` field is optional (defaults to empty dict), so existing operations continue working. Simply revert the commit and investigate.

**Documentation Updates**:
- Update API models documentation to explain context field usage
- Add example showing how adapters can use context for rich progress
- Document best practices for progress context structure

**Commit Message**:
```
feat(training): implement TrainingProgressRenderer for rich progress display

Creates TrainingProgressRenderer following the ProgressRenderer pattern to
restore rich training progress details (epochs, batches, GPU) in CLI.

Changes:
- Add TrainingProgressRenderer to format training-specific progress messages
- Inject renderer into GenericProgressManager for training operations
- Ensure ServiceOrchestrator passes state.context to OperationProgress.context
- Update CLI callback to extract from progress.context

Before: "Status: running" (generic message)
After: "Epoch: 5/10 · Batch: 120/500 🖥️ RTX 3090: 85%" (rich details)

Architecture:
- Follows proven DataProgressRenderer pattern
- TrainingProgressBridge populates state.context → Renderer formats message
- Context flows: Bridge → Manager → ServiceOrchestrator → OperationProgress → CLI

Fixes: Rich progress context regression from unified operations migration
Tests: Unit tests for renderer + integration tests for context flow
```

**Estimated Time**: 3-4 hours (renderer + integration + testing)

---

## Phase 5: Cleanup and Documentation

### TASK-5.1: Remove Debug Code

**Objective**: Clean up debug logging added during investigation

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/training/training_adapter.py` (remove debug logs)
- `training-host-service/services/training_service.py` (remove debug logs)
- `training-host-service/endpoints/training.py` (remove debug logs)

**Acceptance Criteria**:
- [ ] All `logger.info("DEBUG: ...")` removed
- [ ] No temporary/exploratory code in production files
- [ ] Code quality checks pass

**Commit After**:
```bash
make quality
git add ktrdr/ training-host-service/
git commit -m "chore(cli): remove debug logging from CLI refactoring investigation"
```

---

### TASK-5.2: Update Documentation

**Objective**: Document the new pattern for future developers

**Branch**: `feature/cli-unified-operations`

**Files**:
- `docs/cli/adding-new-operations.md` (NEW)
- `docs/cli/README.md` (MODIFY)

**Content**:
- How to add a new async operation (step-by-step guide)
- Adapter pattern explanation with examples
- When to use executor vs. direct API calls
- Testing strategy for new operations

**Acceptance Criteria**:
- [ ] Step-by-step guide for adding new operations
- [ ] Example adapter with annotations
- [ ] Clear explanation of executor responsibilities
- [ ] Migration guide for existing commands (optional)

**Commit After**:
```bash
git add docs/cli/
git commit -m "docs(cli): add developer guide for unified operations pattern"
```

---

### TASK-5.3: Create Pull Request

**Objective**: Merge feature branch into parent branch

**Branch**: `feature/cli-unified-operations` → `feature/training-service-orchestrator`

**Pre-PR Checklist**:
- [ ] All unit tests pass: `make test-unit`
- [ ] All integration tests pass: `make test-integration`
- [ ] Code quality checks pass: `make quality`
- [ ] Manual testing completed for training and dummy commands
- [ ] All commits have clear messages
- [ ] No debug code or TODOs in production files

**Create PR**:
```bash
gh pr create \
  --base feature/training-service-orchestrator \
  --head feature/cli-unified-operations \
  --title "refactor(cli): implement unified async operations pattern with adapter architecture" \
  --body "$(cat <<'EOF'
## Summary
Implements unified async operations pattern for CLI commands using adapter architecture.

## Changes
- Created `AsyncOperationExecutor` for generic async operation handling
- Created `OperationAdapter` interface for domain-specific logic
- Implemented `TrainingOperationAdapter` and `DummyOperationAdapter`
- Migrated training command to use new pattern (fixes cancellation bug)
- Migrated dummy command to use new pattern

## Fixes
- ✅ Training cancellation now works correctly (Ctrl+C)
- ✅ Consistent progress display across operations
- ✅ Reduced code duplication by >60%

## Testing
- [x] All unit tests pass
- [x] All integration tests pass
- [x] Manual testing: training start/complete/cancel
- [x] Manual testing: dummy command
- [x] Code quality checks pass

## Migration Notes
- Data loading command NOT migrated (deferred to future work)
- Old `AsyncCLIClient` retained for compatibility
- No breaking changes to user experience

## Code Metrics
- Training command: 350 → 80 lines (77% reduction)
- Dummy command: 200 → 50 lines (75% reduction)
- New infrastructure: 400 lines (executor + adapters + tests)
- Net reduction: ~220 lines with better architecture

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**After Merge**:
```bash
# Switch back to parent branch
git checkout feature/training-service-orchestrator

# Pull merged changes
git pull origin feature/training-service-orchestrator

# Delete feature branch
git branch -d feature/cli-unified-operations
gh api repos/:owner/:repo/git/refs/heads/feature/cli-unified-operations -X DELETE
```

---

## Phase 6: Final CLI Unification and Cleanup

**Objective**: Complete CLI unification by cleaning up remaining custom code in Training and migrating Data Loading command to unified pattern. Ensure all three async CLI commands (Dummy, Training, Data Loading) are as lean as possible.

**Branch**: `feature/cli-unified-operations` (continue on same branch)

### Analysis Summary

**Current State Assessment**:

1. **Dummy Command**: ✅ PERFECT (Gold Standard)
   - 127 total lines, ~57 async implementation
   - Fully migrated, minimal custom code
   - Only appropriate domain-specific code
   - **This is the target pattern for all commands**

2. **Training Command**: ⚠️ NEEDS CLEANUP
   - 327 total lines, ~135 async implementation
   - Migrated but bloated with ~55 lines of extractable code
   - Issues: Strategy loading (~34 lines), complex progress formatter (~56 lines), validation loops (~15 lines)
   - **Target: Reduce to ~80 lines async implementation**

3. **Data Loading Command**: ❌ NOT MIGRATED - CRITICAL
   - 934 total lines, ~332 async implementation
   - Uses OLD pattern: `KtrdrApiClient`, custom signal handlers, custom polling
   - Major duplication: TWO polling loops (~157 lines), custom signal handler (~26 lines), duplicate cancellation (~50 lines)
   - **Target: Migrate completely, reduce to ~80 lines async implementation**

---

### TASK-6.1: Create Strategy Loading Helper

**Objective**: Extract strategy loading/validation logic from training command into reusable helper

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/helpers/strategy_helpers.py` (NEW)
- `ktrdr/cli/helpers/__init__.py` (NEW)
- `tests/unit/cli/helpers/test_strategy_helpers.py` (NEW)
- `tests/unit/cli/helpers/__init__.py` (NEW)

**What to Extract**:
```python
# From async_model_commands.py lines 89-158
def load_and_validate_strategy(
    strategy_file: str,
    symbol_override: Optional[str] = None,
    timeframe_override: Optional[str] = None,
) -> tuple[list[str], list[str], dict]:
    """
    Load strategy config and extract/validate symbols and timeframes.

    Returns:
        (symbols, timeframes, config) tuple

    Raises:
        ValidationError: If validation fails
        FileNotFoundError: If strategy file doesn't exist
    """
```

**Benefits**:
- Removes ~50 lines from training command
- Reusable for future commands
- Easier to test in isolation
- Cleaner training command flow

**Acceptance Criteria**:
- [ ] Helper function created with clear interface
- [ ] Handles strategy file validation
- [ ] Extracts symbols/timeframes from config
- [ ] Supports CLI overrides
- [ ] Validates symbols and timeframes
- [ ] Returns clean data structures
- [ ] Unit tests with >90% coverage
- [ ] Training command uses helper (verified working)

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/helpers/ tests/unit/cli/helpers/
git commit -m "refactor(cli): extract strategy loading into reusable helper"
```

---

### TASK-6.2: Simplify Training Progress Formatter

**Objective**: Reduce 56-line progress formatter to ~15 lines by removing excessive fallback logic

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/async_model_commands.py` (MODIFY - lines 260-315)

**Current Problem**:
The formatter has two complete implementations:
1. Try to use backend-rendered message
2. Fall back to manual construction from context

**Root Cause**:
Backend `TrainingProgressRenderer` already formats rich messages. CLI shouldn't duplicate this logic.

**Solution**:
```python
def format_training_progress(operation_data: dict) -> str:
    """Format progress message - backend already does the heavy lifting."""
    status = operation_data.get("status", "unknown")
    progress_info = operation_data.get("progress") or {}

    # Use backend-rendered message (TrainingProgressRenderer output)
    rendered_message = progress_info.get("current_step", "")
    if rendered_message:
        return f"Status: {status} - {rendered_message}"

    # Minimal fallback for missing data
    return f"Status: {status}"
```

**Benefits**:
- Reduces from 56 lines to ~10 lines
- Eliminates duplicate rendering logic
- Trusts backend to do formatting (Single Responsibility)
- Easier to maintain

**Acceptance Criteria**:
- [ ] Formatter reduced to <15 lines
- [ ] Uses backend-rendered message primarily
- [ ] Minimal fallback (no complex reconstruction)
- [ ] Still displays rich progress (epochs, batches, GPU)
- [ ] Manual testing shows correct display
- [ ] No regressions in progress quality

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/async_model_commands.py
git commit -m "refactor(cli): simplify training progress formatter

Reduce from 56 lines to 10 lines by trusting backend TrainingProgressRenderer
to format messages. CLI should only display, not reconstruct."
```

---

### TASK-6.3: Clean Up Training Command

**Objective**: Apply helpers and simplifications to reduce training command to ~80 lines async implementation

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/async_model_commands.py` (MODIFY)

**Changes**:
1. Use `load_and_validate_strategy()` helper (TASK-6.1)
2. Use simplified progress formatter (TASK-6.2)
3. Consolidate parameter display into single print statement
4. Remove redundant comments and whitespace

**Expected Reduction**:
- Before: ~135 lines async implementation
- After: ~80 lines async implementation
- Reduction: ~40% cleaner code

**Acceptance Criteria**:
- [ ] Uses strategy helper function
- [ ] Uses simplified progress formatter
- [ ] Async implementation ≤85 lines
- [ ] All functionality preserved
- [ ] Training starts, progresses, completes successfully
- [ ] Cancellation works correctly
- [ ] Progress display shows rich details
- [ ] All tests pass
- [ ] Manual testing successful

**Commit After**:
```bash
make test-unit
make test-integration
git add ktrdr/cli/async_model_commands.py
git commit -m "refactor(cli): clean up training command using helpers

Reduces async implementation from 135 to 80 lines (40% reduction).
Uses strategy loading helper and simplified progress formatter."
```

---

### TASK-6.4: Create DataLoadOperationAdapter

**Objective**: Create adapter for data loading operations following the proven pattern

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/operation_adapters.py` (MODIFY - add DataLoadOperationAdapter)
- `tests/unit/cli/test_data_load_adapter.py` (NEW)

**Adapter Design**:
```python
class DataLoadOperationAdapter(OperationAdapter):
    """
    Adapter for data loading operations.

    Knows how to:
    - Start data loading via /api/v1/data/load
    - Parse data loading response to extract operation_id
    - Display data loading results with summary
    - Handle IB diagnosis messages
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        mode: str = "tail",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
    ):
        # Store parameters

    def get_start_endpoint(self) -> str:
        return "/data/load"

    def get_start_payload(self) -> dict[str, Any]:
        # Construct payload from parameters

    def parse_start_response(self, response: dict) -> str:
        # Extract operation_id

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        # Display bars loaded, date range, execution time
        # Handle IB diagnosis if present
        # Show summary table
```

**Key Features**:
- Handles data loading specific parameters
- Knows data loading API contract
- Displays data summary (bars loaded, date range, etc.)
- Handles IB diagnosis messages (partial loads, errors)
- Clean, ~100 lines like TrainingOperationAdapter

**Acceptance Criteria**:
- [ ] Implements all 4 required OperationAdapter methods
- [ ] Handles all data loading parameters correctly
- [ ] Constructs proper API payload
- [ ] Extracts operation_id correctly
- [ ] Displays comprehensive results summary
- [ ] Handles IB diagnosis messages
- [ ] Shows bars loaded, date range, execution time
- [ ] Adapter is <120 lines
- [ ] Unit tests cover all methods
- [ ] Mock tests verify API contract

**Commit After**:
```bash
make test-unit
git add ktrdr/cli/operation_adapters.py tests/unit/cli/test_data_load_adapter.py
git commit -m "feat(cli): add DataLoadOperationAdapter for data loading operations"
```

---

### TASK-6.5: Migrate Data Loading Command

**Objective**: Complete rewrite of data loading command using unified pattern

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/data_commands.py` (REWRITE `load_data` and `_load_data_async`)
- `tests/integration/cli/test_data_commands.py` (MODIFY)

**Current State**:
- 332 lines of async implementation
- Custom signal handling (~26 lines)
- TWO polling loops (~157 lines combined)
- Duplicate cancellation code (~50 lines)
- Custom progress integration (~33 lines)

**Target State**:
~80 lines async implementation using `AsyncOperationExecutor` and `DataLoadOperationAdapter`

**Code to DELETE**:
- All custom signal handling (lines 410-435)
- Both polling loops (lines 471-627)
- All cancellation handling code (lines 484-509, 584-606)
- Progress state creation (lines 534-546)
- Enhanced display integration

**Code to KEEP (move to adapter)**:
- `_process_data_load_response` logic → move to adapter's `display_results()`
- IB diagnosis handling → keep in adapter

**Expected Reduction**:
- Before: ~332 lines async implementation
- After: ~80 lines async implementation
- Reduction: ~76% cleaner code

**Acceptance Criteria**:
- [ ] Uses `AsyncOperationExecutor`
- [ ] Uses `DataLoadOperationAdapter`
- [ ] NO custom polling loops
- [ ] NO custom signal handling
- [ ] NO custom cancellation code
- [ ] Async implementation ≤85 lines
- [ ] Data loading works correctly (tail, backfill, full)
- [ ] Progress displays correctly
- [ ] Cancellation works (Ctrl+C)
- [ ] IB diagnosis messages still shown
- [ ] Results summary displayed correctly
- [ ] All tests pass
- [ ] Manual testing with real IB data successful

**Testing Strategy**:
1. **Unit tests**: Adapter methods in isolation
2. **Integration tests**: Full command flow with mock API
3. **Manual tests**:
   ```bash
   # Test basic load
   ktrdr data load AAPL --timeframe 1h --mode tail

   # Test with date range
   ktrdr data load MSFT --start 2024-01-01 --end 2024-06-01

   # Test cancellation (press Ctrl+C during load)
   ktrdr data load TSLA --mode full

   # Test with trading hours filter
   ktrdr data load AAPL --trading-hours --include-extended
   ```

**Commit After**:
```bash
make test-unit
make test-integration
git add ktrdr/cli/data_commands.py tests/
git commit -m "refactor(cli): migrate data loading to unified operations pattern

Complete migration of data loading command to use AsyncOperationExecutor
and DataLoadOperationAdapter. Removes 252 lines of custom code.

Before: 332 lines with custom polling/signal handling
After: 80 lines using unified pattern (76% reduction)

- Removed custom signal handling
- Removed duplicate polling loops
- Removed custom cancellation code
- Removed custom progress integration
- All functionality preserved
- IB diagnosis still works"
```

---

### TASK-6.6: Final Verification and Documentation

**Objective**: Ensure all three commands are lean, consistent, and well-documented

**Branch**: `feature/cli-unified-operations`

**Files**:
- `ktrdr/cli/dummy_commands.py` (VERIFY)
- `ktrdr/cli/async_model_commands.py` (VERIFY)
- `ktrdr/cli/data_commands.py` (VERIFY)
- `docs/cli/adding-new-operations.md` (UPDATE)
- `docs/architecture/cli/tasks/CLI-UNIFIED-OPERATIONS-IMPLEMENTATION.md` (UPDATE)

**Verification Checklist**:

**Code Metrics**:
- [ ] Dummy command: ≤60 lines async implementation
- [ ] Training command: ≤85 lines async implementation
- [ ] Data loading command: ≤85 lines async implementation
- [ ] All use `AsyncOperationExecutor`
- [ ] All use appropriate `OperationAdapter`
- [ ] NO custom polling loops in any command
- [ ] NO custom signal handling in any command
- [ ] NO custom cancellation code in any command

**Consistency Checks**:
- [ ] All three commands have same structure
- [ ] All three handle httpx logging suppression the same way
- [ ] All three use progress callbacks similarly
- [ ] All three have consistent error handling
- [ ] All three have similar parameter display patterns

**Functional Testing**:
- [ ] Dummy command: start, progress, complete, cancel
- [ ] Training command: start, progress, complete, cancel, metrics display
- [ ] Data loading command: start, progress, complete, cancel, data summary

**Quality Checks**:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code quality checks pass (`make quality`)
- [ ] No debug code remaining
- [ ] No TODOs remaining

**Documentation Updates**:
- [ ] Update `adding-new-operations.md` with all three as examples
- [ ] Document data loading adapter specifics
- [ ] Update implementation plan with Phase 6 completion
- [ ] Add "lessons learned" section

**Final Comparison Table**:
```
Command         | Before | After | Reduction | Status
----------------|--------|-------|-----------|--------
Dummy           | 57     | 57    | 0%        | ✅ Already optimal
Training        | 135    | 80    | 41%       | ✅ Cleaned up
Data Loading    | 332    | 80    | 76%       | ✅ Fully migrated
```

**Commit After**:
```bash
git add docs/
git commit -m "docs(cli): update documentation for Phase 6 completion

Final verification of all three async CLI commands (dummy, training, data loading).
All commands now use unified pattern with minimal custom code.

Code Metrics:
- Dummy: 57 lines (already optimal)
- Training: 80 lines (41% reduction)
- Data Loading: 80 lines (76% reduction)

Total reduction: ~307 lines of duplicate infrastructure code eliminated."
```

---

## Phase 6 Success Criteria

### Code Quality Metrics:
- All three commands use unified pattern
- Total async implementation: ≤220 lines (avg ~73 lines per command)
- Code duplication: <5% across all three commands
- All custom infrastructure removed

### Functional Metrics:
- All operations start successfully
- All operations show progress correctly
- All operations handle cancellation correctly
- All operations display results correctly
- No regressions in any command

### Architectural Metrics:
- Single source of truth: `AsyncOperationExecutor`
- Clear separation: infrastructure vs domain logic
- Consistent pattern across all async operations
- Easy to add new operations (<100 lines per adapter)

---

## Phase 6 Timeline

**TASK-6.1: Strategy Helper** - 2 hours
**TASK-6.2: Training Formatter** - 1 hour
**TASK-6.3: Training Cleanup** - 1 hour
**TASK-6.4: Data Adapter** - 3 hours
**TASK-6.5: Data Migration** - 4 hours
**TASK-6.6: Verification** - 2 hours

**Total**: ~13 hours for complete Phase 6

**Overall Project Total**: ~30-34 hours (Phases 1-6 combined)

---

## Testing Strategy

### Unit Tests

**Coverage Target**: >80% for all new code

**Key Test Files**:
- `test_operation_executor.py`: Executor logic isolation
- `test_operation_adapters.py`: Each adapter in isolation
- `test_training_command.py`: Command integration

**Mock Strategy**:
- Mock HTTP client for network isolation
- Mock adapter interface for executor tests
- Mock operations API responses

### Integration Tests

**Test Files**:
- `test_unified_operations.py`: Full workflow with real API

**Scenarios**:
- Successful completion flow
- Cancellation flow
- Error handling flow
- Progress accuracy

### Manual Testing Checklist

**Before Committing**:
- [ ] `ktrdr models train` starts and completes
- [ ] Progress bar updates smoothly (< 500ms lag)
- [ ] Ctrl+C cancels training immediately
- [ ] Backend training actually stops (check logs)
- [ ] Final results display all metrics correctly
- [ ] Error messages are helpful and actionable
- [ ] `--quiet` mode suppresses progress
- [ ] `--verbose` mode shows detailed logs

---

## Success Metrics

### Code Quality
- **Code Reduction**: >60% reduction in command implementation
- **Code Duplication**: <10% similarity between operations
- **Test Coverage**: >80% for executor and adapters

### Functionality
- **Cancellation Success Rate**: 100% (main fix)
- **Progress Accuracy**: Within ±2% of actual training progress
- **Response Time**: Progress updates < 500ms lag

### User Experience
- **Consistent UX**: Same progress display across all operations
- **Error Clarity**: Actionable error messages
- **Responsiveness**: Immediate feedback on user actions

---

## Migration Timeline

### Estimated Effort

**Phase 1: Foundation** (4-5 hours)
- TASK-1.1: AsyncOperationExecutor - 2-3 hours
- TASK-1.2: OperationAdapter Interface - 1 hour
- Testing - 1 hour

**Phase 2: Adapters** (3-4 hours)
- TASK-2.1: TrainingOperationAdapter - 2 hours
- TASK-2.2: DummyOperationAdapter - 1 hour
- Testing - 1 hour

**Phase 3: Migration** (5-6 hours)
- TASK-3.1: Refactor training command - 2-3 hours
- TASK-3.2: Refactor dummy command - 1-2 hours
- Testing - 2 hours

**Phase 4: Verification** (2-3 hours)
- TASK-4.1: Integration tests - 1-2 hours
- TASK-4.2: Verify epochs config - 1 hour

**Phase 5: Cleanup** (3 hours)
- TASK-5.1: Remove debug code - 30 minutes
- TASK-5.2: Documentation - 1.5 hours
- TASK-5.3: Create PR and merge - 1 hour

**Total**: ~17-21 hours for complete migration

**Scope**: Training + Dummy commands (Data Loading deferred)

---

## Risk Mitigation

### Risk: Breaking Existing Functionality

**Mitigation**:
- Incremental migration (one command at a time)
- Comprehensive test coverage before migration
- Keep backup of old implementation
- Easy rollback plan
- Gradual rollout

### Risk: Adapter Interface Too Rigid

**Mitigation**:
- Keep interface minimal (4 methods)
- Allow optional methods for customization
- Design review before implementation
- Test with multiple adapters before finalizing

### Risk: Performance Degradation

**Mitigation**:
- Profile before and after migration
- Use same HTTP client and polling intervals
- Monitor progress update latency
- Load testing with concurrent operations

---

## Rollback Plan

If critical issues are discovered:

1. **Immediate**: Revert to backed-up version
2. **Investigation**: Identify root cause in isolated environment
3. **Fix Forward**: Apply minimal patch to executor/adapter
4. **Re-migrate**: Once fix is verified with tests

**Backup Strategy**: Create `async_model_commands.py.backup` before modification

---

## Open Questions

1. ✅ **Should we migrate data/dummy commands too?**
   - **Decision**: Optional future work, not required for training fix

2. ✅ **What to do with AsyncCLIClient?**
   - **Decision**: Keep for now, add cancel_operation() method as safety net

3. ✅ **Should progress adapter be mandatory or optional?**
   - **Decision**: Optional with sensible default

4. ⏳ **Should we deprecate old async patterns?**
   - **Decision**: Pending - evaluate after migration complete

---

## Next Steps

1. Review and approve this implementation plan
2. Decide on approach:
   - **Option A**: Full refactoring (14-18 hours)
   - **Option B**: Minimal patch only (45 minutes)
   - **Option C**: Minimal patch now + full refactoring later
3. Begin implementation based on decision

---

**Document Version**: 2.0
**Status**: Ready for Implementation
**Changes from v1.0**: Aligned with approved design document v2.0 using adapter pattern instead of growing KtrdrApiClient
