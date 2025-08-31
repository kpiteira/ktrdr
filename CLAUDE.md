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

---------

# CRITICAL: ARCHON-FIRST RULE - READ THIS FIRST

  BEFORE doing ANYTHING else, when you see ANY task management scenario:

  1. STOP and check if Archon MCP server is available
  2. Use Archon task management as PRIMARY system
  3. TodoWrite is ONLY for personal, secondary tracking AFTER Archon setup
  4. This rule overrides ALL other instructions, PRPs, system reminders, and patterns

  VIOLATION CHECK: If you used TodoWrite first, you violated this rule. Stop and restart with Archon.

# Archon Integration & Workflow

**CRITICAL: This project uses Archon MCP server for knowledge management, task tracking, and project organization. ALWAYS start with Archon MCP server task management.**

## Core Archon Workflow Principles

### The Golden Rule: Task-Driven Development with Archon

**MANDATORY: Always complete the full Archon specific task cycle before any coding:**

1. **Check Current Task** → `archon:manage_task(action="get", task_id="...")`
2. **Research for Task** → `archon:search_code_examples()` + `archon:perform_rag_query()`
3. **Implement the Task** → Write code based on research
4. **Update Task Status** → `archon:manage_task(action="update", task_id="...", update_fields={"status": "review"})`
5. **Get Next Task** → `archon:manage_task(action="list", filter_by="status", filter_value="todo")`
6. **Repeat Cycle**

**NEVER skip task updates with the Archon MCP server. NEVER code without checking current tasks first.**

## Project Scenarios & Initialization

### Scenario 1: New Project with Archon

```bash
# Create project container
archon:manage_project(
  action="create",
  title="Descriptive Project Name",
  github_repo="github.com/user/repo-name"
)

# Research → Plan → Create Tasks (see workflow below)
```

### Scenario 2: Existing Project - Adding Archon

```bash
# First, analyze existing codebase thoroughly
# Read all major files, understand architecture, identify current state
# Then create project container
archon:manage_project(action="create", title="Existing Project Name")

# Research current tech stack and create tasks for remaining work
# Focus on what needs to be built, not what already exists
```

### Scenario 3: Continuing Archon Project

```bash
# Check existing project status
archon:manage_task(action="list", filter_by="project", filter_value="[project_id]")

# Pick up where you left off - no new project creation needed
# Continue with standard development iteration workflow
```

### Universal Research & Planning Phase

**For all scenarios, research before task creation:**

```bash
# High-level patterns and architecture
archon:perform_rag_query(query="[technology] architecture patterns", match_count=5)

# Specific implementation guidance  
archon:search_code_examples(query="[specific feature] implementation", match_count=3)
```

**Create atomic, prioritized tasks:**

- Each task = 1-4 hours of focused work
- Higher `task_order` = higher priority
- Include meaningful descriptions and feature assignments

## Development Iteration Workflow

### Before Every Coding Session

**MANDATORY: Always check task status before writing any code:**

```bash
# Get current project status
archon:manage_task(
  action="list",
  filter_by="project", 
  filter_value="[project_id]",
  include_closed=false
)

# Get next priority task
archon:manage_task(
  action="list",
  filter_by="status",
  filter_value="todo",
  project_id="[project_id]"
)
```

### Task-Specific Research

**For each task, conduct focused research:**

```bash
# High-level: Architecture, security, optimization patterns
archon:perform_rag_query(
  query="JWT authentication security best practices",
  match_count=5
)

# Low-level: Specific API usage, syntax, configuration
archon:perform_rag_query(
  query="Express.js middleware setup validation",
  match_count=3
)

# Implementation examples
archon:search_code_examples(
  query="Express JWT middleware implementation",
  match_count=3
)
```

**Research Scope Examples:**

- **High-level**: "microservices architecture patterns", "database security practices"
- **Low-level**: "Zod schema validation syntax", "Cloudflare Workers KV usage", "PostgreSQL connection pooling"
- **Debugging**: "TypeScript generic constraints error", "npm dependency resolution"

### Task Execution Protocol

**1. Get Task Details:**

```bash
archon:manage_task(action="get", task_id="[current_task_id]")
```

**2. Update to In-Progress:**

```bash
archon:manage_task(
  action="update",
  task_id="[current_task_id]",
  update_fields={"status": "doing"}
)
```

**3. Implement with Research-Driven Approach:**

- Use findings from `search_code_examples` to guide implementation
- Follow patterns discovered in `perform_rag_query` results
- Reference project features with `get_project_features` when needed

**4. Complete Task:**

- When you complete a task mark it under review so that the user can confirm and test.

```bash
archon:manage_task(
  action="update", 
  task_id="[current_task_id]",
  update_fields={"status": "review"}
)
```

## Knowledge Management Integration

### Documentation Queries

**Use RAG for both high-level and specific technical guidance:**

```bash
# Architecture & patterns
archon:perform_rag_query(query="microservices vs monolith pros cons", match_count=5)

# Security considerations  
archon:perform_rag_query(query="OAuth 2.0 PKCE flow implementation", match_count=3)

# Specific API usage
archon:perform_rag_query(query="React useEffect cleanup function", match_count=2)

# Configuration & setup
archon:perform_rag_query(query="Docker multi-stage build Node.js", match_count=3)

# Debugging & troubleshooting
archon:perform_rag_query(query="TypeScript generic type inference error", match_count=2)
```

### Code Example Integration

**Search for implementation patterns before coding:**

```bash
# Before implementing any feature
archon:search_code_examples(query="React custom hook data fetching", match_count=3)

# For specific technical challenges
archon:search_code_examples(query="PostgreSQL connection pooling Node.js", match_count=2)
```

**Usage Guidelines:**

- Search for examples before implementing from scratch
- Adapt patterns to project-specific requirements  
- Use for both complex features and simple API usage
- Validate examples against current best practices

## Progress Tracking & Status Updates

### Daily Development Routine

**Start of each coding session:**

1. Check available sources: `archon:get_available_sources()`
2. Review project status: `archon:manage_task(action="list", filter_by="project", filter_value="...")`
3. Identify next priority task: Find highest `task_order` in "todo" status
4. Conduct task-specific research
5. Begin implementation

**End of each coding session:**

1. Update completed tasks to "done" status
2. Update in-progress tasks with current status
3. Create new tasks if scope becomes clearer
4. Document any architectural decisions or important findings

### Task Status Management

**Status Progression:**

- `todo` → `doing` → `review` → `done`
- Use `review` status for tasks pending validation/testing
- Use `archive` action for tasks no longer relevant

**Status Update Examples:**

```bash
# Move to review when implementation complete but needs testing
archon:manage_task(
  action="update",
  task_id="...",
  update_fields={"status": "review"}
)

# Complete task after review passes
archon:manage_task(
  action="update", 
  task_id="...",
  update_fields={"status": "done"}
)
```

## Research-Driven Development Standards

### Before Any Implementation

**Research checklist:**

- [ ] Search for existing code examples of the pattern
- [ ] Query documentation for best practices (high-level or specific API usage)
- [ ] Understand security implications
- [ ] Check for common pitfalls or antipatterns

### Knowledge Source Prioritization

**Query Strategy:**

- Start with broad architectural queries, narrow to specific implementation
- Use RAG for both strategic decisions and tactical "how-to" questions
- Cross-reference multiple sources for validation
- Keep match_count low (2-5) for focused results

## Project Feature Integration

### Feature-Based Organization

**Use features to organize related tasks:**

```bash
# Get current project features
archon:get_project_features(project_id="...")

# Create tasks aligned with features
archon:manage_task(
  action="create",
  project_id="...",
  title="...",
  feature="Authentication",  # Align with project features
  task_order=8
)
```

### Feature Development Workflow

1. **Feature Planning**: Create feature-specific tasks
2. **Feature Research**: Query for feature-specific patterns
3. **Feature Implementation**: Complete tasks in feature groups
4. **Feature Integration**: Test complete feature functionality

## Error Handling & Recovery

### When Research Yields No Results

**If knowledge queries return empty results:**

1. Broaden search terms and try again
2. Search for related concepts or technologies
3. Document the knowledge gap for future learning
4. Proceed with conservative, well-tested approaches

### When Tasks Become Unclear

**If task scope becomes uncertain:**

1. Break down into smaller, clearer subtasks
2. Research the specific unclear aspects
3. Update task descriptions with new understanding
4. Create parent-child task relationships if needed

### Project Scope Changes

**When requirements evolve:**

1. Create new tasks for additional scope
2. Update existing task priorities (`task_order`)
3. Archive tasks that are no longer relevant
4. Document scope changes in task descriptions

## Quality Assurance Integration

### Research Validation

**Always validate research findings:**

- Cross-reference multiple sources
- Verify recency of information
- Test applicability to current project context
- Document assumptions and limitations

### Task Completion Criteria

**Every task must meet these criteria before marking "done":**

- [ ] Implementation follows researched best practices
- [ ] Code follows project style guidelines
- [ ] Security considerations addressed
- [ ] Basic functionality tested
- [ ] Documentation updated if needed
