# CLAUDE.md - KTRDR Development Guide

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

### 2. Data Flow Clarity
```
IB Gateway → Data Manager → Indicators → Fuzzy → Neural → Decisions
                ↓               ↓           ↓        ↓         ↓
              Storage      Calculations  Members  Models   Signals
```

### 3. Error Handling Philosophy
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

## 📚 REQUIRED READING

Before working on specific modules:
- **Data Module**: Read `ktrdr/data/README.md` and understand IB integration
- **API Module**: Review FastAPI patterns in `ktrdr/api/`
- **Frontend**: Understand Redux Toolkit patterns in `frontend/src/store/`
- **Testing**: Study existing test patterns in `tests/`

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
- `uv run python script.py` (NOT `python script.py`)
- `uv run pytest` (NOT `pytest`)
- `uv run mypy ktrdr` (NOT `mypy ktrdr`)
- `uv run black ktrdr tests` (NOT `black ktrdr tests`)

## 🚨 CRITICAL: MCP DEVELOPMENT RULES 🚨

**WHEN WORKING ON MCP FEATURES, NEVER TOUCH BACKEND OR FRONTEND CONTAINERS!**

**✅ ALLOWED MCP Commands:**
- `./mcp/restart_mcp.sh` - Restart only MCP container
- `./mcp/build_mcp.sh` - Build and start only MCP container  
- `./mcp/stop_mcp.sh` - Stop only MCP container
- `docker-compose -f docker/docker-compose.yml restart --no-deps mcp`
- `docker-compose -f docker/docker-compose.yml build --no-deps mcp`
- `docker-compose -f docker/docker-compose.yml up -d --no-deps mcp`

**❌ FORBIDDEN Commands (will break backend/frontend):**
- `docker-compose --profile research up -d` (rebuilds ALL containers)
- `docker-compose build` (rebuilds ALL containers) 
- `docker-compose restart` (restarts ALL containers)
- Any command that affects backend or frontend containers

## 🔥 DEVELOPMENT BEST PRACTICES

### Commit Discipline
- **NEVER commit more than 20-30 files at once** - Large commits are unmanageable
- **Make frequent, focused commits** - Each commit should represent one logical change
- **Always run tests before committing** - Use `make test-fast` to catch regressions
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

## CRITICAL FIXES - DO NOT REMOVE

### Chart Jumping Bug Prevention (CRITICAL)

**Location**: `frontend/src/components/presentation/charts/BasicChart.tsx` lines 288-341

**Issue**: TradingView Lightweight Charts v5 automatically adjusts visible time range when indicators are added to synchronized charts, causing unwanted forward jumps in time that break user experience.

**Solution**: Preventive visibility toggle (hide/show) of first indicator after addition. Forces TradingView to recalculate correct time range without jumping.

**SEVERITY: CRITICAL** - Removing this fix will cause immediate regression

## ⚠️ CRITICAL: IB Gateway Connection Requirements

**MUST READ**: `docs/ib-connection-lessons-learned.md` for critical IB Gateway connectivity requirements.

**Key Points:**
- **Wait for "Synchronization complete"** before making API calls (minimum 2 seconds)
- **Limit retry attempts** to 3 client IDs maximum
- **Add delays** between failed connection attempts (1-2 seconds)
- **Use conservative health checks** - avoid heavy API calls in connection validation

**⚠️ WARNING**: Ignoring these requirements will corrupt IB Gateway's socket state, requiring computer reboot to fix.