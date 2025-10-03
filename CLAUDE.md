# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# KTRDR Development Guide

## 🎯 PRIME DIRECTIVE: Think Before You Code

**STOP AND THINK**: Before writing any code, you MUST:

1. Understand the root cause of the problem
2. Consider architectural implications
3. Propose the solution approach and get confirmation
4. Only then implement

## 🚫 ANTI-PATTERNS TO AVOID

### The "Quick Fix" Trap

❌ **DON'T**: Add try/except blocks to suppress errors
✅ **DO**: Understand why the error occurs and fix the root cause

❌ **DON'T**: Add new parameters/flags to work around issues  
✅ **DO**: Refactor the design if current structure doesn't support the need

❌ **DON'T**: Copy-paste similar code with slight modifications
✅ **DO**: Extract common patterns into reusable functions/classes

❌ **DON'T**: Add "bandaid" fixes that make code work but harder to understand
✅ **DO**: Take time to implement clean, maintainable solutions

## 🏗️ ARCHITECTURAL PRINCIPLES

### 1. Separation of Concerns

- Each module has ONE clear responsibility
- Dependencies flow in one direction: UI → API → Core → Data
- No circular dependencies or tight coupling

### 2. Host Service Architecture

KTRDR uses **Host Services** to bypass Docker limitations for components requiring direct system access:

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Container (Port 8000)                                │
│  ├─ API Layer (FastAPI)                                     │
│  ├─ Service Orchestrators (DataManager, TrainingManager)    │
│  └─ Business Logic                                          │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         │ HTTP                               │ HTTP
         ▼                                    ▼
┌──────────────────────┐           ┌──────────────────────┐
│ IB Host Service      │           │ Training Host Service│
│ (Port 5001)          │           │ (Port 5002)          │
│ - Direct IB Gateway  │           │ - GPU Access (CUDA)  │
│ - No Docker network  │           │ - Native Performance │
└──────────────────────┘           └──────────────────────┘
         │                                    │
         ▼                                    ▼
   IB Gateway                          PyTorch + GPU
   (Port 4002)
```

**Key Pattern**: Service Orchestrators use adapters to route operations either locally (in-process) or to host services (HTTP), controlled by environment variables.

### 3. Service Orchestrator Pattern

All managers (DataManager, TrainingManager) inherit from `ServiceOrchestrator`:

- Unified async operation handling
- Progress tracking with `GenericProgressManager`
- Cancellation support via `CancellationToken`
- Environment-based adapter routing
- Automatic host service failover

### 4. Data Flow Clarity

```
IB Gateway → IB Host Service → Data Manager → Indicators → Fuzzy → Neural → Decisions
                                     ↓            ↓           ↓        ↓         ↓
                                  Storage    Calculations  Members  Models   Signals
```

### 5. Error Handling Philosophy

- Errors should bubble up with context
- Handle errors at the appropriate level
- Never silently swallow exceptions
- Always log before re-raising

## 🔍 BEFORE MAKING CHANGES

### 1. Understand the Current Code

```python
# Ask yourself:
# - What is this module's responsibility?
# - Who calls this code and why?
# - What assumptions does it make?
# - What would break if I change this?
```

### 2. Trace the Full Flow

Before modifying any function:

- Find all callers (grep/search)
- Understand the data flow
- Check for side effects
- Review related tests

### 3. Consider Architectural Impact

- Will this change make the code more or less maintainable?
- Does it align with existing patterns?
- Should we refactor instead of patching?

## 📝 IMPLEMENTATION CHECKLIST

When implementing features:

1. **Design First**
   - [ ] Write a brief design comment explaining the approach
   - [ ] Identify which modules will be affected
   - [ ] Consider edge cases and error scenarios

2. **Code Quality**
   - [ ] Follow existing patterns in the codebase
   - [ ] Add type hints for all parameters and returns
   - [ ] Write clear docstrings explaining "why", not just "what"
   - [ ] Keep functions focused and under 50 lines

3. **Testing**
   - [ ] Write tests BEFORE implementing
   - [ ] Test both happy path and error cases
   - [ ] Run existing tests to ensure no regression

4. **Integration**
   - [ ] Trace through the full execution path
   - [ ] Verify error handling at each level
   - [ ] Check logs make sense for debugging

## 🛑 WHEN TO STOP AND ASK

You MUST stop and ask for clarification when:

- The fix requires changing core architectural patterns
- You're adding the 3rd try/except block to make something work
- The solution feels like a "hack" or "workaround"
- You need to modify more than 3 files for a "simple" fix
- You're copy-pasting code blocks
- You're unsure about the broader impact

## 💭 THINKING PROMPTS

Before implementing, ask yourself:

1. "What problem am I actually solving?"
2. "Is this the simplest solution that could work?"
3. "Will someone understand this code in 6 months?"
4. "Am I fixing the symptom or the cause?"
5. "Is there a pattern in the codebase I should follow?"

## 🎨 CODE STYLE BEYOND FORMATTING

### Clarity Over Cleverness

```python
# ❌ Clever but unclear
result = [x for x in data if all(f(x) for f in filters)] if filters else data

# ✅ Clear and maintainable
def apply_filters(data: List[Any], filters: List[Callable]) -> List[Any]:
    """Apply multiple filter functions to data."""
    if not filters:
        return data
    
    filtered_data = []
    for item in data:
        if all(filter_func(item) for filter_func in filters):
            filtered_data.append(item)
    return filtered_data
```

### Explicit Over Implicit

```python
# ❌ Implicit behavior
def process_data(data, skip_validation=False):
    if not skip_validation:
        validate(data)  # What does this validate?

# ✅ Explicit behavior  
def process_data(data: pd.DataFrame, validate_schema: bool = True):
    """Process data with optional schema validation."""
    if validate_schema:
        validate_dataframe_schema(data, required_columns=['open', 'high', 'low', 'close'])
```

## 🔧 COMMON ISSUES AND ROOT CAUSES

### Issue: "Function not working in async context"

❌ **Quick Fix**: Wrap in try/except and return None
✅ **Root Cause Fix**: Ensure proper async/await chain from top to bottom

### Issue: "Data not loading correctly"

❌ **Quick Fix**: Add more retries and error suppression
✅ **Root Cause Fix**: Understand data format requirements and validate inputs

### Issue: "Frontend not updating"

❌ **Quick Fix**: Add setTimeout or force refresh
✅ **Root Cause Fix**: Trace Redux action flow and fix state management

## 🏛️ KEY ARCHITECTURAL PATTERNS

### ServiceOrchestrator Base Class

**Location**: [ktrdr/async_infrastructure/service_orchestrator.py](ktrdr/async_infrastructure/service_orchestrator.py)

All service managers inherit from ServiceOrchestrator and follow this pattern:

1. Environment-based configuration (e.g., `USE_IB_HOST_SERVICE`, `USE_TRAINING_HOST_SERVICE`)
2. Adapter initialization (local vs. host service routing)
3. Unified async operations with progress tracking
4. Cancellation token support
5. Operations service integration

**Example Pattern**:

```python
class DataManager(ServiceOrchestrator):
    def __init__(self):
        # Reads USE_IB_HOST_SERVICE env var
        self.adapter = self._initialize_adapter()

    async def load_data(self, ...):
        # Unified async pattern with progress tracking
        return await self._execute_with_progress(...)
```

### Host Service Integration

**When to use host services**:

- IB Gateway: Direct TCP connection (Docker networking issues)
- Training: GPU access (CUDA/MPS not available in container)

**Environment Variables**:

- `USE_IB_HOST_SERVICE=true` → Route data operations to [ib-host-service](ib-host-service/)
- `USE_TRAINING_HOST_SERVICE=true` → Route training to [training-host-service](training-host-service/)
- `IB_HOST_SERVICE_URL=http://localhost:5001` (default)
- `TRAINING_HOST_SERVICE_URL=http://localhost:5002` (default)

### Async Operations Pattern (CLI Commands)

**Recent Migration**: All CLI commands migrated from sync to async (commit 8d9ca93)

**Pattern**: CLI commands use `AsyncCLIClient` for API communication:

```python
from ktrdr.cli.helpers.async_cli_client import AsyncCLIClient

async def some_command(symbol: str):
    async with AsyncCLIClient() as client:
        result = await client.post("/endpoint", json=data)
```

**Progress Display**: Use `GenericProgressManager` with `ProgressRenderer` for live updates

### Cancellation Tokens

**Global Coordinator**: [ktrdr/async_infrastructure/cancellation.py](ktrdr/async_infrastructure/cancellation.py)

All long-running operations support cancellation:

- Create tokens with `create_cancellation_token()`
- Check with `token.is_cancelled()`
- Operations service manages tokens globally
- CLI displays cancellation status

## 📚 REQUIRED READING

Before working on specific modules:

- **ServiceOrchestrator Pattern**: [ktrdr/async_infrastructure/service_orchestrator.py](ktrdr/async_infrastructure/service_orchestrator.py)
- **Data Module**: [ktrdr/data/data_manager.py](ktrdr/data/data_manager.py) - Study ServiceOrchestrator inheritance
- **Training Module**: [ktrdr/training/training_manager.py](ktrdr/training/training_manager.py) - Host service routing pattern
- **API Module**: Review FastAPI patterns in [ktrdr/api/](ktrdr/api/)
- **CLI Async Pattern**: [ktrdr/cli/helpers/async_cli_client.py](ktrdr/cli/helpers/async_cli_client.py)
- **Host Services**:
  - [ib-host-service/README.md](ib-host-service/README.md)
  - [training-host-service/README.md](training-host-service/README.md)
- **Testing**: Study existing test patterns in [tests/](tests/)

## ⚡ FINAL REMINDERS

1. **Quality > Speed**: Taking 2 hours to do it right saves 10 hours of debugging
2. **Ask Questions**: Unclear requirements lead to wrong implementations
3. **Refactor Fearlessly**: If the current design doesn't fit, change it
4. **Document Why**: Code shows "what", comments explain "why"
5. **Test Everything**: If it's not tested, it's broken

Remember: You're not just writing code, you're building a system. Every line should make the system better, not just make it work.

## ⚠️ CRITICAL: THIS PROJECT USES UV ⚠️

**NEVER run `python` or `python3` directly!** This project uses `uv` for Python dependency management.

**Always use `uv run` for Python commands:**

```bash
# Correct
uv run python script.py
uv run pytest tests/
uv run ktrdr data show AAPL 1d

# Wrong - will use system Python
python script.py
pytest tests/
```

## 🚀 COMMON DEVELOPMENT COMMANDS

### Running the System

```bash
# Start complete system (IB + Training host services + Docker)
./start_ktrdr.sh

# Start Docker development environment only
./docker_dev.sh start
./docker_dev.sh logs        # View logs
./docker_dev.sh stop        # Stop containers

# Start API server directly (no Docker)
uv run python scripts/run_api_server.py

# Start host services individually
cd ib-host-service && ./start.sh
cd training-host-service && ./start.sh
```

### CLI Usage

```bash
# The main entry point
ktrdr --help

# Data operations
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data load EURUSD 1h --start-date 2024-01-01 --end-date 2024-12-31
ktrdr data get-range AAPL 1d

# Training operations
ktrdr models train --strategy config/strategies/example.yaml
ktrdr models list
ktrdr models test model_v1.0.0 --symbol AAPL

# Operations management
ktrdr operations list
ktrdr operations status <operation-id>
ktrdr operations cancel <operation-id>

# IB Gateway integration
ktrdr ib test-connection
ktrdr ib check-status
```

## 🔥 DEVELOPMENT BEST PRACTICES

### Commit Discipline

- **NEVER commit more than 20-30 files at once** - Large commits are unmanageable
- **Make frequent, focused commits** - Each commit should represent one logical change
- **Always run tests before committing** - Use `make test-unit` to catch regressions
- **Always run linting before committing** - Use `make quality` for all quality checks

### Testing Discipline  

- **Run unit tests systematically** - Use `make test-unit` for fast feedback (<2s)
- **Run integration tests when needed** - Use `make test-integration` for component interaction tests
- **Never skip failing tests** - Fix or properly skip tests that don't pass
- **Test-driven development** - Write tests for new functionality
- **Proper test categorization**: Unit (fast, mocked), Integration (slower, real components), E2E (full system)

### Standard Testing Commands (Use Makefile)

```bash
# Fast development loop - run on every change
make test-unit          # Unit tests only (<2s)
make test-fast          # Alias for test-unit

# Integration testing - run when testing component interactions  
make test-integration   # Integration tests (<30s)

# Full system testing - run before major commits
make test-e2e          # End-to-end tests (<5min)

# Coverage and reporting
make test-coverage     # Unit tests with HTML coverage report

# Code quality - run before committing
make quality           # Lint + format + typecheck
make lint              # Ruff linting only  
make format            # Black formatting only
make typecheck         # MyPy type checking only

# CI simulation - matches GitHub Actions
make ci                # Run unit tests + quality checks
```

### Pre-Commit Checklist

1. `make test-unit` - All unit tests pass (<2s)
2. `make quality` - Lint, format, and type checking pass
3. Review changed files - No debug code or secrets
4. Write meaningful commit message
5. Keep commits small and focused (< 30 files)

### Test Performance Standards

- **Unit tests**: Must complete in <2 seconds total
- **Integration tests**: Should complete in <30 seconds total
- **E2E tests**: Should complete in <5 minutes total
- **Collection time**: Should be <2 seconds

## 🔍 DEBUGGING TIPS

### Host Services Not Working

```bash
# Check if services are running
lsof -i :5001  # IB Host Service
lsof -i :5002  # Training Host Service

# Test connectivity from Docker
docker exec ktrdr-backend curl http://host.docker.internal:5001/health
docker exec ktrdr-backend curl http://host.docker.internal:5002/health

# Check logs
tail -f ib-host-service/logs/ib-host-service.log
tail -f training-host-service/logs/training-host-service.log
```

### Environment Variable Issues

```bash
# Check what's set in Docker container
docker exec ktrdr-backend env | grep -E "(IB|TRAINING)"

# Common issues:
# - USE_IB_HOST_SERVICE not set → falls back to local (wrong in Docker)
# - URL wrong → connection failures
# - Service not started → timeouts
```

### Progress Not Updating

Check these in order:

1. Is `OperationsService` being used? ([ktrdr/api/services/operations_service.py](ktrdr/api/services/operations_service.py))
2. Is progress callback being passed to ServiceOrchestrator?
3. Is `GenericProgressManager` updating state?
4. Check cancellation token not triggered

### Data Loading Issues

Common root causes:

1. IB Gateway not running (port 4002)
2. IB Host Service not started or unreachable
3. Symbol format incorrect (use IB format: "AAPL" not "AAPL.US")
4. Date range outside available data
5. Timeframe not supported by data source

## 📊 API DEVELOPMENT

### API Documentation

Once server running:

- Swagger UI: <http://localhost:8000/api/v1/docs>
- ReDoc: <http://localhost:8000/api/v1/redoc>

### Adding New Endpoints

1. Create endpoint in [ktrdr/api/endpoints/](ktrdr/api/endpoints/)
2. Define Pydantic models in [ktrdr/api/models/](ktrdr/api/models/)
3. Implement business logic in [ktrdr/api/services/](ktrdr/api/services/)
4. Register router in [ktrdr/api/main.py](ktrdr/api/main.py)
5. Add tests in [tests/api/](tests/api/)

### Async Operation Pattern (for long-running tasks)

```python
from ktrdr.api.services.operations_service import OperationsService

@router.post("/long-operation")
async def start_operation(
    background_tasks: BackgroundTasks,
    operations_service: OperationsService = Depends(get_operations_service)
):
    # Register operation
    operation_id = await operations_service.register_operation(
        operation_type=OperationType.TRAINING,
        description="Training model..."
    )

    # Start background task
    background_tasks.add_task(
        run_operation,
        operation_id,
        operations_service
    )

    return {"operation_id": operation_id}
```
