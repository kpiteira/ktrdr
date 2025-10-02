# Unified CLI Operations Pattern - Design Document

## Executive Summary

This document outlines the design for unifying the CLI command patterns across data loading, dummy operations, and model training commands. Currently, these commands exhibit inconsistent architectures: `dummy_commands.py` and `data_commands.py` follow a working pattern, while `async_model_commands.py` uses a different approach with custom clients and polling logic. This inconsistency leads to bugs (broken cancellation), code duplication, and poor maintainability.

**Core Problem**: We're reinventing the wheel for each async operation instead of having a single, reusable mechanism.

**Solution**: Create a generic async operation executor that knows nothing about specific domains (training, data loading, etc.) and inject domain-specific knowledge through lightweight adapters.

**Goals**:
- Establish a single, shared pattern for all async CLI operations
- Fix broken cancellation in training commands
- Enable consistent user experience across all operations
- Reduce code duplication by extracting common patterns
- Make it trivial to add new async operations
- **Initial scope: Migrate Training + Dummy commands** (prove the pattern works)

**Non-Goals**:
- Rewrite synchronous CLI commands (those not using operations API)
- Change the operations API itself
- Modify the backend services
- Create a complex framework (keep it simple)
- **Migrate data loading command in this iteration** (deferred to future work)

---

## Current State Analysis

### The Problem: Three Different Implementations of the Same Thing

We have three commands that all do fundamentally the same thing:
1. Make an HTTP request to start an async operation
2. Poll the operations API for status updates
3. Display progress to the user
4. Handle cancellation when the user presses Ctrl+C
5. Display final results when complete

Yet each command implements this differently, leading to:
- **Broken functionality**: Training command's cancellation doesn't work
- **Code duplication**: ~800 lines of nearly identical polling/cancellation logic
- **Inconsistent UX**: Different progress displays, different error messages
- **Maintenance burden**: Bug fixes must be applied to three places
- **Onboarding friction**: New developers see three patterns, don't know which to follow

### Working Pattern: dummy_commands.py & data_commands.py

These commands follow a similar pattern:

**What they do right**:
1. Use a singleton API client (`KtrdrApiClient`) that manages HTTP connections
2. Setup async signal handlers to catch Ctrl+C
3. Poll the operations API at `/api/v1/operations/{id}` for status
4. Use `EnhancedCLIProgressDisplay` for consistent progress bars
5. Call `/api/v1/operations/{id}/cancel` when user cancels

**What they do wrong**:
- Each command duplicates the entire polling loop (~150 lines)
- Each command duplicates the signal handling setup (~30 lines)
- Each command duplicates the progress display logic (~50 lines)
- Adding a new async operation requires copying 200+ lines of boilerplate

**Example of the duplication**:
Both commands have nearly identical code for:
```
Setup signal handler → Start operation → Get operation_id →
Poll in loop → Check for cancellation → Update progress →
Check if finished → Display results
```

### Broken Pattern: async_model_commands.py

The training command diverged from the working pattern and exhibits several anti-patterns:

**Architectural Problems**:
1. **Wrong HTTP Client**: Uses `AsyncCLIClient` instead of `KtrdrApiClient`
   - These are two completely different HTTP client implementations
   - `AsyncCLIClient` is missing the `cancel_operation()` method
   - Creates confusion about which client to use

2. **Bypasses Operations API**: Calls training-specific endpoints instead of standard operations endpoints
   - The backend DOES return an operation_id
   - But the CLI ignores it and calls `/trainings/{id}/performance` directly
   - Misses out on standard progress information in operations API

3. **Custom Everything**: Reimplements polling, progress calculation, cancellation
   - Custom polling loop with different timing
   - Manual progress percentage calculation
   - Different error handling than other commands

4. **Broken Cancellation**: The most visible symptom
   - Tries to call `cli.cancel_operation()` but method doesn't exist
   - Results in "API request failed: Unknown error"
   - Backend training continues running even after user presses Ctrl+C

**Why It Matters**:
Users expect Ctrl+C to stop what they started. When it doesn't work, it erodes trust in the tool and wastes GPU resources on unwanted training runs.

---

## Root Cause Analysis

### Historical Context

The divergence likely happened because:

1. **Timeline**: Training command predates the operations API pattern
   - Operations API was added later to support async operations
   - Training command was already working (sort of) so wasn't refactored
   - New commands (dummy, data) were built using the newer pattern

2. **Knowledge Silos**: Different developers worked on different commands
   - No shared understanding of the "right way" to do async operations
   - No code review caught the duplication
   - No refactoring initiative unified the approaches

3. **No Abstraction**: Common patterns weren't extracted
   - Easy to copy-paste working code
   - Hard to justify "big refactoring" for working code
   - Technical debt accumulated

### The Deeper Problem: Missing Abstraction

Looking at our three commands, we can identify two distinct concerns:

**Generic Concerns** (same for all async operations):
- Managing HTTP client lifecycle
- Sending HTTP requests with retries
- Setting up signal handlers for Ctrl+C
- Polling an operation until completion
- Displaying progress bars
- Handling cancellation
- Error handling and user feedback

**Domain-Specific Concerns** (unique to each operation):
- Which endpoint to call to start the operation
- What parameters to send in the request
- How to parse the response to get operation_id
- How to display final results (training metrics vs. data summary vs. dummy output)

**Current Architecture**: These concerns are mixed together in each command, making it impossible to reuse the generic parts.

**Desired Architecture**: Separate generic infrastructure from domain-specific logic through a clear interface.

---

## Proposed Design

### Design Philosophy

**Principle 1: Separation of Concerns**
Split the "what" (domain logic) from the "how" (infrastructure logic). The executor knows how to run any async operation; adapters know what makes each operation unique.

**Principle 2: Inversion of Control**
The generic executor is in control of the flow. It asks adapters for domain-specific information when needed but never gives up control. This ensures consistency.

**Principle 3: Open/Closed Principle**
The executor is closed for modification—we never change it when adding new operations. It's open for extension—new operations are added by creating new adapters.

**Principle 4: Single Responsibility**
Each component has exactly one reason to change:
- Executor changes only if async operation mechanics change
- Adapters change only if their specific domain changes

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Command Layer                        │
│                 (train, data, dummy, ...)                    │
│                                                              │
│  Responsibility:                                             │
│  • Parse command-line arguments                              │
│  • Validate user inputs                                      │
│  • Create appropriate OperationAdapter                       │
│  • Invoke AsyncOperationExecutor                             │
│  • Handle top-level errors                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Creates and passes
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              AsyncOperationExecutor (NEW)                    │
│                   (GENERIC - Zero Domain Knowledge)          │
│                                                              │
│  Responsibility:                                             │
│  • Manage HTTP client lifecycle (create, reuse, cleanup)    │
│  • Setup and teardown signal handlers (Ctrl+C)              │
│  • Execute operation start through adapter                   │
│  • Poll operations API until completion                      │
│  • Integrate with EnhancedCLIProgressDisplay                │
│  • Detect and handle cancellation requests                   │
│  • Coordinate error handling and recovery                    │
│  • Invoke adapter for result display                         │
│                                                              │
│  Key Methods:                                                │
│  • execute_operation(adapter, console, options)              │
│  • _poll_until_complete(operation_id)                       │
│  • _handle_cancellation(operation_id)                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Delegates domain-specific
                     │ decisions via adapter interface
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         OperationAdapter (Abstract Interface)                │
│                                                              │
│  Defines the contract between executor and domain logic:     │
│  • How to start this operation (endpoint + payload)          │
│  • How to parse the start response (extract operation_id)    │
│  • How to display final results (domain-specific format)     │
│  • Optional: Custom progress interpretation                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Implemented by
                     │
        ┌────────────┴────────────┬─────────────┐
        ▼                         ▼             ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Training         │  │ DataLoad         │  │ Dummy            │
│ OperationAdapter │  │ OperationAdapter │  │ OperationAdapter │
│                  │  │                  │  │                  │
│ Knows:           │  │ Knows:           │  │ Knows:           │
│ • Training       │  │ • Data loading   │  │ • Dummy task     │
│   endpoints      │  │   endpoints      │  │   endpoints      │
│ • Model params   │  │ • Data params    │  │ • Task params    │
│ • Metrics        │  │ • Data summary   │  │ • Iteration info │
│   display        │  │   display        │  │   display        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Component Responsibilities

#### AsyncOperationExecutor

**What It Knows**:
- How to make HTTP requests with retries and error handling
- The operations API contract: `/operations/{id}`, `/operations/{id}/cancel`
- How to poll for operation status at appropriate intervals
- How to interpret operation status: running, completed, failed, cancelled
- How to setup async signal handlers for graceful cancellation
- **How to create and manage Rich Progress bar (INVARIANT)**
- How to update progress display during polling
- How to display percentage completion and elapsed time

**What It Doesn't Know**:
- Anything about training, data loading, or any specific operation type
- What parameters to send when starting operations
- What endpoints to call (delegates to adapter)
- How to interpret domain-specific results
- **How to format domain-specific progress messages (VARIANT - delegates to callback)**
- Business logic of any kind

**Lifecycle**:
1. Receives an adapter, console, optional progress formatter callback, and display preferences
2. Creates and manages HTTP client (async context manager)
3. **Creates Rich Progress bar context (if show_progress=True)**
4. Registers signal handler for Ctrl+C
5. Asks adapter for start endpoint and payload
6. Makes HTTP POST to start the operation
7. Extracts operation_id from response (via adapter)
8. Enters polling loop until completion or cancellation
9. **On each poll: fetches status, formats message (via callback), updates progress bar**
10. On cancellation: sends cancel request, waits for acknowledgment
11. On completion: asks adapter to display results
12. Cleans up signal handler, progress bar, and HTTP client
13. Returns success/failure to caller

**Progress Display Architecture (INVARIANT/VARIANT Separation)**:
- **INVARIANT (Executor)**: Creates Rich Progress bar, manages lifecycle, updates percentage/elapsed time
- **VARIANT (Command/Adapter)**: Provides optional `progress_callback(operation_data: dict) -> str` to format domain-specific messages
- **Default**: If no callback provided, shows generic "Status: {status} - {current_step}"
- **Custom**: Callbacks can add domain details (e.g., "Epoch 5/10, Batch 120/500, GPU: 85%")

**Error Handling Strategy**:
- Connection errors: Retry with exponential backoff
- HTTP 4xx errors: Don't retry, report to user immediately
- HTTP 5xx errors: Retry limited times, then fail
- Polling errors: Log warning, continue polling (transient issues)
- Cancellation errors: Best effort, don't block on cancel failures

#### OperationAdapter (Abstract Interface)

**Purpose**: Define the contract between generic infrastructure and domain-specific logic.

**Interface Methods**:

1. **get_start_endpoint() → str**
   - Returns the HTTP endpoint to start this operation
   - Example: "/api/v1/trainings/start" for training
   - Example: "/api/v1/data/load" for data loading
   - Pure data, no logic

2. **get_start_payload() → dict**
   - Returns the JSON payload for the start request
   - Adapter constructs this from parameters passed to its constructor
   - Knows what the backend API expects for this operation
   - Example for training: `{"strategy_name": "...", "symbols": [...], ...}`

3. **parse_start_response(response: dict) → str**
   - Extracts the operation_id from the start response
   - Handles different response formats if needed
   - Returns the operation_id that will be used for polling
   - Most implementations: `return response["data"]["operation_id"]`

4. **display_results(final_status: dict, console: Console, http_client: AsyncClient) → None**
   - Called when operation completes successfully
   - Receives the final operation status from `/operations/{id}`
   - May fetch additional data (e.g., training performance metrics)
   - Has access to HTTP client for making additional requests
   - Formats and prints results using Rich console
   - Domain-specific display logic lives here

5. **adapt_progress(status: dict) → GenericProgressState** (optional)
   - Allows custom interpretation of progress information
   - Default implementation works for most operations
   - Override when operation has special progress semantics
   - Example: Training might expose epoch/batch information

**Design Note**: This is a minimal interface with just four required methods. Most adapters will be <100 lines of simple, declarative code.

#### Concrete Adapters

Each adapter is a lightweight class that encapsulates domain knowledge:

**TrainingOperationAdapter**:
- Constructed with: strategy_name, symbols, timeframes, date range, options
- Knows the training API contract
- Fetches detailed training metrics after completion
- Displays: accuracy, precision, recall, F1 score, training time, model size
- Handles training-specific error messages

**DataLoadOperationAdapter**:
- Constructed with: symbol, timeframe, date range, mode, options
- Knows the data loading API contract
- Displays: data points loaded, date range, validation results
- Handles data-specific errors (missing data, gaps, invalid symbols)

**DummyOperationAdapter**:
- Constructed with: duration, iterations
- Simplest adapter, used for testing and examples
- Displays: iterations completed, total time
- Demonstrates the pattern for new developers

**Adding New Operations**:
When we want to add a new async operation (e.g., backtesting), we:
1. Create a new adapter class (e.g., `BacktestOperationAdapter`)
2. Implement the four interface methods
3. Use it with the existing `AsyncOperationExecutor`
4. Zero changes to infrastructure code

---

## Detailed Component Design

### AsyncOperationExecutor

**Initialization**:
The executor is initialized with infrastructure configuration:
- Base URL of the API server (e.g., "http://localhost:8000")
- Default timeout for HTTP requests (e.g., 30 seconds)
- Retry configuration (max attempts, backoff strategy)

It does NOT know what operation it will execute—that comes later via the adapter parameter.

**HTTP Client Management**:
The executor creates a single `httpx.AsyncClient` instance that is reused for all requests during the operation. This provides:
- Connection pooling for performance
- Consistent timeout handling
- Proper async context management
- Automatic cleanup on completion or error

The client lifecycle is:
1. Created when `execute_operation()` is called
2. Reused for: start request, status polls, cancel request
3. Cleaned up in the `finally` block, even on errors

**Signal Handling**:
When the user presses Ctrl+C, we want graceful shutdown:

1. **Registration**: At the start of `execute_operation()`, register a handler with the event loop
   - Uses `asyncio.get_running_loop().add_signal_handler(signal.SIGINT, handler)`
   - Handler sets a `self.cancelled = True` flag
   - Handler also prints user-friendly "Cancellation requested..." message

2. **Detection**: The polling loop checks `self.cancelled` before each status poll
   - If True, immediately exit the polling loop
   - Send cancellation request to backend: `POST /operations/{id}/cancel`
   - Don't wait indefinitely for cancel acknowledgment (timeout after 5 seconds)

3. **Cleanup**: Always unregister the signal handler in the `finally` block
   - Prevents multiple handlers accumulating
   - Restores default Ctrl+C behavior after operation

**Polling Loop**:
This is the heart of the executor and implements a standardized pattern:

```
Initialize progress display (if requested)
Start time tracking for ETA calculation

LOOP:
    1. Check if user cancelled (Ctrl+C)
       → If yes: send cancel request, exit loop

    2. Fetch operation status: GET /operations/{operation_id}
       → If request fails: log warning, retry after delay

    3. Extract status field: "running", "completed", "failed", "cancelled"

    4. Update progress display (if enabled)
       → Convert status to GenericProgressState (via adapter if custom)
       → Call progress_display.update_progress(state)

    5. Check if terminal state reached
       → If "completed": exit loop, return final status
       → If "failed": exit loop, return final status
       → If "cancelled": exit loop, return final status

    6. Sleep for poll interval (300ms for responsive display)

END LOOP
```

**Polling Interval Strategy**:
- Fast polling (300ms) for responsive progress updates
- Operations API is designed to handle this frequency
- No thundering herd problem (single client per command)
- User sees smooth progress bar updates
- Backend is polled ~3 times per second

**Progress Display Integration**:
The executor integrates with `EnhancedCLIProgressDisplay` which already exists:

1. **Startup**: Call `display.start_operation(name, total_steps, context)`
   - Operation name comes from adapter's domain
   - Total steps from progress.total_steps
   - Context can include operation_id, start time, etc.

2. **Updates**: Call `display.update_progress(state)` on each poll
   - State is a `GenericProgressState` object
   - Contains: percentage, current/total steps, message, timing info
   - Display calculates ETA based on progress rate

3. **Completion**: Call `display.complete_operation(success, summary)`
   - Finalizes the progress bar
   - Shows checkmark for success, X for failure
   - Optional summary message

**Cancellation Flow**:
When cancellation is detected (Ctrl+C pressed):

1. Immediately print: "🛑 Sending cancellation to server..."
2. Send POST to `/operations/{operation_id}/cancel` with reason: "User cancelled"
3. Wait for response with 5-second timeout
4. If successful: print "✅ Cancellation sent successfully"
5. If failed: print warning but don't block (best effort)
6. Exit polling loop, return None (indicating cancellation)
7. Executor returns False to command (operation did not complete)

**Error Handling Hierarchy**:

1. **Network Errors** (can't connect to API):
   - Retry with exponential backoff: 1s, 2s, 4s, 8s
   - Max 5 retries for transient issues
   - After max retries: print clear error message
   - Suggest checking if API server is running
   - Return False (operation failed)

2. **HTTP Client Errors (4xx)**:
   - 400 Bad Request: Invalid parameters (adapter bug or user input)
   - 404 Not Found: Wrong endpoint or operation doesn't exist
   - Don't retry (not transient)
   - Print error detail from response body
   - Return False immediately

3. **HTTP Server Errors (5xx)**:
   - 500 Internal Server Error: Backend bug
   - 503 Service Unavailable: Temporary backend issue
   - Retry up to 3 times (may be transient)
   - If persistent: print error, suggest checking backend logs
   - Return False

4. **Polling Errors** (status request fails mid-operation):
   - Log warning: "Failed to get status, retrying..."
   - Don't exit polling loop (temporary network blip)
   - Continue polling with backoff
   - If errors persist: eventually timeout and fail

5. **Operation Failures** (status = "failed"):
   - Operation started but failed during execution
   - Not an infrastructure error
   - Retrieve error_message from operation status
   - Print error to user
   - Return False (operation failed)

**Return Value**:
The executor returns a simple boolean:
- `True`: Operation completed successfully
- `False`: Operation failed, was cancelled, or infrastructure error occurred

The caller (CLI command) uses this to determine exit code.

### OperationAdapter Pattern

**Design Rationale**:
Adapters are intentionally lightweight. They should feel like "configuration" rather than complex code. The adapter's job is to translate between the generic executor's expectations and the specific operation's API contract.

**Anti-Patterns to Avoid**:
- ❌ Don't put HTTP logic in adapters (executor owns HTTP)
- ❌ Don't put polling logic in adapters (executor owns polling)
- ❌ Don't put signal handling in adapters (executor owns signals)
- ❌ Don't make adapters stateful (they're just translators)

**What Adapters Should Do**:
- ✅ Translate domain parameters to API payload format
- ✅ Know the endpoint URLs for their domain
- ✅ Parse domain-specific response formats
- ✅ Format domain-specific results for display

**Typical Adapter Size**: 50-100 lines, mostly data transformation

---

## Command Implementation Pattern

With the executor and adapters, commands become thin wrappers:

**Structure of Every Async Command**:

1. **Command Function** (Typer decorator):
   - Parse and validate command-line arguments
   - Create the async wrapper function
   - Call `asyncio.run(async_wrapper())`
   - Handle top-level errors (KeyboardInterrupt, etc.)

2. **Async Wrapper Function**:
   - Setup logging preferences (quiet, verbose)
   - Check API connection
   - Print operation header (what we're about to do)
   - Create the appropriate adapter with parameters
   - Create the executor
   - Call `executor.execute_operation(adapter, console, options)`
   - Exit with appropriate code based on result

**What's Notable**:
- Command function: ~10 lines (just Typer boilerplate)
- Async function: ~40 lines (header, adapter, executor, cleanup)
- Zero polling logic, zero signal handling, zero progress display code
- All the complexity is in the reusable executor

**Adding a New Async Operation**:
To add a new operation (e.g., backtesting):
1. Create `BacktestOperationAdapter` (~80 lines)
2. Create command function identical to pattern, just swap the adapter
3. Total new code: ~120 lines vs. ~300 lines with current approach

---

## Migration Strategy

### Philosophy: Incremental, Non-Breaking

We will migrate in phases, with each phase being:
- Independently testable
- Deployable (can ship each phase separately)
- Non-breaking (existing commands keep working)
- Reversible (can rollback if issues found)

This is the opposite of a "big bang" rewrite that breaks everything until it's done.

### Phase 1: Foundation (Additive Only)

**Branch**: `feature/cli-unified-operations` (off current branch: `feature/training-service-orchestrator`)

**Goal**: Build the new infrastructure without touching existing commands.

**Deliverables**:
1. `AsyncOperationExecutor` class with full implementation
2. `OperationAdapter` abstract base class defining the interface
3. Comprehensive unit tests for executor (>80% coverage)
4. Integration tests proving executor works end-to-end

**Success Criteria**:
- All new tests pass
- Code coverage >80% for executor
- No existing tests broken
- No existing code modified

**Risk**: Very low - purely additive

**Timeline**: 1-2 hours implementation, 1 hour testing

**Commit Strategy**: Commit after Phase 1 complete, all tests passing

### Phase 2: Create Adapters

**Branch**: Continue on `feature/cli-unified-operations`

**Goal**: Implement concrete adapters for Training and Dummy operations.

**Deliverables**:
1. `TrainingOperationAdapter` (full implementation)
2. `DummyOperationAdapter` (full implementation)
3. Unit tests for each adapter

**Success Criteria**:
- All adapter tests pass
- Adapters produce identical payloads to current commands
- No existing code modified

**Risk**: Very low - still no user-facing changes

**Timeline**: 2-3 hours implementation, 1 hour testing

**Commit Strategy**: Commit after each adapter is complete with passing tests

**Note**: DataLoadOperationAdapter is deferred to future work

### Phase 3: Migrate Training Command

**Branch**: Continue on `feature/cli-unified-operations`

**Goal**: Rewrite training command to use new infrastructure.

**Success Criteria**:
- Training starts successfully
- Progress displays correctly
- **Cancellation works (this is the fix!)**
- Final results display correctly
- All tests pass
- Code reduced by >60%

**Risk**: Medium - changes user-facing command

**Mitigation**:
- Create backup: `git stash` or separate commit before rewrite
- Test thoroughly before committing
- Manual testing with real training runs

**Timeline**: 2-3 hours implementation, 2 hours testing

**Commit Strategy**: Single commit for training command migration after all tests pass

### Phase 4: Migrate Dummy Command

**Branch**: Continue on `feature/cli-unified-operations`

**Goal**: Refactor dummy command to use new infrastructure.

**Benefits**:
- Proves pattern works for multiple operations
- Further code reduction
- Validates adapter interface design

**Risk**: Very low - dummy command is simple, pattern already proven with training

**Success Criteria**:
- Dummy command works identically to before
- Code reduced by >70%
- All tests pass

**Timeline**: 1 hour implementation, 30 minutes testing

**Commit Strategy**: Single commit for dummy command migration

**Note**: Data loading command migration is deferred to future work due to potential complexity

### Phase 5: Cleanup and Documentation

**Branch**: Continue on `feature/cli-unified-operations`

**Goal**: Polish and document the new architecture.

**Deliverables**:
- Remove any debug/exploratory code
- Update CLI documentation
- Create developer guide for adding new operations
- Final code quality checks

**Success Criteria**:
- All documentation updated
- No debug code in production
- Clear path for future operations
- All quality checks pass

**Timeline**: 2 hours

**Commit Strategy**: Final cleanup commit

---

### Phase 6: Pull Request and Merge

**Branch**: `feature/cli-unified-operations` → `feature/training-service-orchestrator`

**PR Title**: "refactor(cli): implement unified async operations pattern with adapter architecture"

**PR Description Template**:
```markdown
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

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Review Checklist**:
- [ ] All tests pass
- [ ] Code coverage >80%
- [ ] Training cancellation works
- [ ] No regressions in training or dummy commands
- [ ] Documentation complete

**Merge Target**: `feature/training-service-orchestrator`

**After Merge**: Delete feature branch `feature/cli-unified-operations`

---

## Success Criteria

### Functional Requirements

**FR-1: Unified Pattern**
All async CLI operations use the same infrastructure with adapter pattern for domain-specific logic.

**FR-2: Working Cancellation**
Users can cancel any async operation with Ctrl+C - cancellation detected immediately, request sent to backend, operation stops.

**FR-3: Consistent User Experience**
All async operations provide the same quality of UX with clear messages, smooth progress, and helpful errors.

**FR-4: Maintainability**
Code is easy to understand and modify with clear separation of concerns and isolated domain code.

**FR-5: Performance**
No degradation in user-perceived performance - commands start quickly, progress updates are responsive.

### Non-Functional Requirements

**NFR-1: Code Reduction**
Before: ~800 lines of duplicated polling/cancellation logic
After: ~300 lines in executor, <100 lines per adapter
Reduction: >60% in total code

**NFR-2: Test Coverage**
Unit tests: >80% coverage
Integration tests: All critical paths
Manual tests: Comprehensive checklist

**NFR-3: Documentation**
Architecture is well-documented with design docs, developer guides, and inline comments.

**NFR-4: Backward Compatibility**
No breaking changes to user experience - same commands, arguments, output, behavior.

**NFR-5: Extensibility**
Easy to add new async operations - create adapter (~80 lines), create command (~50 lines), total <2 hours per new operation.

---

## Risks and Mitigations

### Risk 1: Breaking Existing Functionality

**Likelihood**: Medium | **Impact**: High

**Mitigation**:
- Incremental migration (one command at a time)
- Comprehensive testing before each phase
- Backup of old implementations
- Easy rollback plan

### Risk 2: Performance Degradation

**Likelihood**: Low | **Impact**: Medium

**Mitigation**:
- Profile before and after migration
- Use same HTTP client library
- Same polling interval
- Connection pooling maintained

### Risk 3: Edge Cases Not Covered

**Likelihood**: Medium | **Impact**: Medium

**Mitigation**:
- Study old code thoroughly
- Extensive test coverage
- Beta testing with diverse scenarios
- Gradual rollout

### Risk 4: Adapter Interface Too Rigid

**Likelihood**: Low | **Impact**: Medium

**Mitigation**:
- Keep interface minimal (4 methods)
- Allow adapter customization via optional methods
- Design review before implementation

---

## Future Considerations

### Adding New Operation Types

With this architecture, adding new async operations becomes trivial - just create an adapter and command function (~2 hours total work).

### Monitoring and Observability

Consider adding operation timing metrics, success/failure rate tracking, and progress update latency monitoring.

### Advanced Progress Display

Future enhancements could include real-time logs, resource usage display, multi-step progress, and parallel operation tracking.

---

## Appendix: File Organization

```
ktrdr/
├── cli/
│   ├── operation_executor.py          # NEW - AsyncOperationExecutor
│   ├── operation_adapters.py          # NEW - Adapter classes
│   ├── async_model_commands.py        # MODIFY - use executor
│   ├── data_commands.py               # OPTIONAL - refactor later
│   ├── dummy_commands.py              # OPTIONAL - refactor later
│   └── progress_display_enhanced.py   # EXISTING - no changes
tests/
├── unit/cli/
│   ├── test_operation_executor.py     # NEW - executor tests
│   ├── test_operation_adapters.py     # NEW - adapter tests
│   └── test_training_command.py       # MODIFY - test new impl
└── integration/cli/
    └── test_async_operations.py       # NEW - end-to-end tests
docs/architecture/cli/
├── unified_cli_operations_design.md   # THIS FILE
├── tasks/CLI-UNIFIED-OPERATIONS-IMPLEMENTATION.md
├── MINIMAL-PATCH-PLAN.md
└── adding-new-operations.md           # NEW - developer guide
```

---

## Conclusion

This design solves current problems while establishing a scalable pattern:

**Current Problems Solved**:
- ✅ Broken cancellation in training command
- ✅ Code duplication across commands
- ✅ Inconsistent user experience
- ✅ Difficulty adding new operations

**Future Benefits**:
- ✅ Single source of truth for async operations
- ✅ Trivial to add new operation types
- ✅ Consistent, predictable behavior
- ✅ Easy to test and maintain
- ✅ Clear architecture for new developers

**Key Insight**: The problem wasn't that we needed better training command code—we needed to recognize that training, data loading, and dummy operations are all instances of the same pattern: async operations with progress and cancellation. By extracting that pattern into reusable infrastructure with domain knowledge injected via adapters, we get consistency, reliability, and simplicity.

---

**Document Version**: 2.0
**Date**: 2025-09-30
**Author**: Claude (with Karl)
**Status**: Ready for Review
**Changes from v1.0**: Complete redesign with generic executor and adapter pattern
