# KTRDR Sandbox & Orchestrator: Design Handoff

## Context

Karl has built a highly effective development workflow using Claude Code with four phases:
- `/kdesign` - Interactive design and architecture
- `/kdesign-validate` - Scenario tracing and gap analysis  
- `/kdesign-impl-plan` - Vertical milestone planning
- `/ktask` - TDD implementation

The design and validation phases are interactive (good). The implementation phase runs mostly autonomously with occasional questions (also good). 

**Goal**: Automate the implementation phase further by:
1. Creating a sandbox where Claude Code can run with full permissions safely
2. Building an orchestrator that manages the task-by-task implementation loop

---

## Part 1: Sandbox Environment

### Purpose

Allow Claude Code to run with full permissions without risk of:
- Modifying/deleting files outside the project
- Corrupting Karl's local development environment
- Breaking git state on the real repository

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Karl's Mac                                                     │
│                                                                 │
│  ┌─────────────────────┐                                        │
│  │ Orchestrator        │  (Python, runs on Mac)                 │
│  │ - Reads impl plans  │                                        │
│  │ - Manages tasks     │                                        │
│  │ - Escalates issues  │                                        │
│  └──────────┬──────────┘                                        │
│             │                                                   │
│             ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Sandbox Container                                          ││
│  │                                                             ││
│  │  ┌─────────────┐     ┌────────────────────────────────────┐ ││
│  │  │ Claude Code │────▶│ /workspace                         │ ││
│  │  │ (CLI)       │     │ - Full clone of ktrdr repo         │ ││
│  │  │             │     │ - .claude/ copied in               │ ││
│  │  │             │     │ - Can modify anything              │ ││
│  │  └─────────────┘     └────────────────────────────────────┘ ││
│  │        │                                                    ││
│  │        │ docker socket                                      ││
│  │        ▼                                                    ││
│  │  ┌────────────────────────────────────────────────────────┐ ││
│  │  │ KTRDR Services (via docker compose)                    │ ││
│  │  │ db, backend, workers, jaeger, prometheus, grafana      │ ││
│  │  └────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────┐                                        │
│  │ Real ktrdr repo     │  (untouched by sandbox)                │
│  └─────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Sandbox Container Requirements

**Base image**: Ubuntu 24.04 or similar with:
- Python 3.11+ with pip/uv
- Node.js (for Claude Code CLI)
- Git
- Docker CLI (client only, daemon runs on Mac)
- curl, jq, make, standard dev tools

**Claude Code CLI**: 
- Install via npm: `npm install -g @anthropic-ai/claude-code`
- Needs ANTHROPIC_API_KEY environment variable

**Mounted volumes**:
- `/var/run/docker.sock` from Mac (enables docker compose commands)
- Optionally: shared cache volumes for faster builds

**Network**:
- Can reach Docker network (for ktrdr services)
- Can reach internet (for Anthropic API, package managers)
- Host ports exposed as needed for debugging

### Workspace Setup

On sandbox initialization:

1. **Clone repo**: `git clone <ktrdr-repo> /workspace`
2. **Copy .claude/**: From Karl's real repo (commands, skills, CLAUDE.md)
3. **Copy data files**: Instrument data needed for tests (or symlink to read-only mount)
4. **Copy config**: Any local config files needed

The workspace is ephemeral - on reset, we blow it away and re-clone.

### Key Scripts

**`sandbox-init.sh`**
```bash
# First-time setup
# - Build sandbox container image
# - Create necessary volumes
# - Clone repo into workspace
# - Copy .claude/, data, config
```

**`sandbox-reset.sh`**
```bash
# Fast reset to clean state
# - Stop any running services
# - Delete /workspace contents
# - Re-clone repo (or git clean -fdx)
# - Re-copy .claude/, data, config
# - Restart services
# Target: < 30 seconds
```

**`sandbox-shell.sh`**
```bash
# Drop into sandbox for manual work
# docker exec -it ktrdr-sandbox /bin/bash
```

**`sandbox-claude.sh`**
```bash
# Run Claude Code in sandbox with a prompt
# docker exec -it ktrdr-sandbox claude "$@"
```

### Docker Compose Addition

Add to existing compose or create `docker-compose.sandbox.yml`:

```yaml
services:
  sandbox:
    build:
      context: .
      dockerfile: docker/sandbox/Dockerfile
    container_name: ktrdr-sandbox
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - sandbox-workspace:/workspace
      # Read-only reference to real repo for copying
      - ./.claude:/reference/.claude:ro
      - ./data:/reference/data:ro
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    networks:
      - ktrdr-network
    # Keep running for exec commands
    command: ["sleep", "infinity"]
    
volumes:
  sandbox-workspace:
```

---

## Part 2: Orchestrator

### Purpose

Automate the implementation loop:
1. Read implementation plan (milestone files)
2. Execute tasks one-by-one via Claude Code in sandbox
3. Run E2E tests after each milestone
4. Escalate to Karl when:
   - Claude Code asks a question / expresses uncertainty
   - Tests fail and root cause is unclear
   - Something unexpected happens

### Design Principles

**Milestone as unit of autonomy**: The orchestrator runs a full milestone without intervention unless something goes wrong.

**Task as unit of context**: Each task gets a fresh Claude Code session. This matches Karl's current workflow and prevents context degradation.

**Root cause focus**: When E2E fails, don't just report "test failed" - have Claude Code investigate and either fix it or explain what's wrong.

**Psychological safety**: Claude Code should feel safe saying "I don't know" or "I'm not sure, the options are X, Y, Z". The orchestrator should surface these to Karl rather than pushing for false confidence.

### Core Loop

```python
def run_milestone(milestone: Milestone) -> MilestoneResult:
    for task in milestone.tasks:
        # Fresh context per task
        result = run_task(task)
        
        if result.status == "needs_human":
            # Claude Code expressed uncertainty or asked a question
            response = escalate_and_wait(
                type="question",
                context=result.question,
                options=result.options,
                recommendation=result.recommendation
            )
            # Feed response back, retry task
            result = run_task(task, human_guidance=response)
        
        if result.status == "failed":
            # Task failed - try to diagnose
            diagnosis = diagnose_failure(task, result)
            
            if diagnosis.is_fixable:
                fix_result = attempt_fix(diagnosis)
                if not fix_result.success:
                    escalate_and_wait(type="fix_failed", context=diagnosis)
            else:
                escalate_and_wait(type="task_failed", context=diagnosis)
    
    # All tasks complete - run E2E
    e2e_result = run_e2e_tests(milestone)
    
    if not e2e_result.passed:
        diagnosis = diagnose_e2e_failure(milestone, e2e_result)
        
        if diagnosis.is_fixable:
            fix_result = attempt_fix(diagnosis)
            if fix_result.success:
                # Re-run E2E after fix
                e2e_result = run_e2e_tests(milestone)
        
        if not e2e_result.passed:
            escalate_and_wait(type="e2e_failed", context=diagnosis)
    
    return MilestoneResult(status="complete", e2e_passed=True)
```

### Running Tasks via Claude Code

Each task runs as a Claude Code session with a structured prompt:

```python
def run_task(task: Task, human_guidance: str = None) -> TaskResult:
    prompt = f"""
    /ktask impl: {task.plan_file} task: {task.id}
    
    {f"Additional guidance from Karl: {human_guidance}" if human_guidance else ""}
    
    When complete, output a structured summary:
    - STATUS: complete | needs_human | failed
    - If needs_human: QUESTION: <your question> OPTIONS: <options> RECOMMENDATION: <recommendation>
    - If failed: ERROR: <what went wrong>
    - SUMMARY: <brief description of what was done>
    """
    
    result = execute_claude_code_in_sandbox(prompt)
    return parse_task_result(result)
```

### Detecting "Needs Human"

Claude Code might express uncertainty in various ways:
- Explicit: "I'm not sure whether to use approach A or B"
- Question: "Should I create a new table or add columns to existing?"
- Options: "The options seem to be X, Y, and Z. I recommend X because..."

The orchestrator should detect these patterns in Claude Code's output and escalate rather than letting Claude Code make arbitrary choices on uncertain decisions.

**Detection heuristics**:
- Contains question marks in decision context
- Phrases: "I'm not sure", "uncertain", "options are", "could go either way"
- Explicit structured output (if we train Claude Code to use it)

### E2E Test Execution

After milestone completion:

```python
def run_e2e_tests(milestone: Milestone) -> E2EResult:
    # E2E scenarios are defined in the milestone file
    for scenario in milestone.e2e_scenarios:
        # Execute the test commands
        result = execute_in_sandbox(scenario.commands)
        
        # Check success criteria
        for criterion in scenario.success_criteria:
            if not check_criterion(criterion, result):
                return E2EResult(
                    passed=False,
                    scenario=scenario.name,
                    failed_criterion=criterion,
                    logs=result.logs
                )
    
    return E2EResult(passed=True)
```

### Failure Diagnosis

When something fails, don't just stop - investigate:

```python
def diagnose_failure(context: str, error: str) -> Diagnosis:
    prompt = f"""
    A failure occurred during implementation:
    
    Context: {context}
    Error: {error}
    
    Please investigate:
    1. What is the root cause?
    2. Is this something you can fix, or does it need human decision?
    3. If fixable, what's the fix?
    4. If not fixable, what are the options and what do you recommend?
    
    Output:
    - ROOT_CAUSE: <explanation>
    - FIXABLE: yes | no
    - If yes: FIX_PLAN: <what to do>
    - If no: OPTIONS: <options> RECOMMENDATION: <recommendation>
    """
    
    result = execute_claude_code_in_sandbox(prompt)
    return parse_diagnosis(result)
```

### Escalation

When the orchestrator needs Karl's input:

```python
def escalate_and_wait(type: str, context: Any) -> str:
    # Format the escalation message
    message = format_escalation(type, context)
    
    # Notify Karl (multiple channels possible)
    send_terminal_notification(message)  # Print to orchestrator terminal
    send_desktop_notification(message)   # macOS notification
    # Optional: send_slack_message(message)
    
    # Wait for response
    # Could be: interactive terminal input, file watch, API endpoint
    response = wait_for_human_response()
    
    return response
```

### State Persistence

The orchestrator should be stoppable and resumable:

```python
@dataclass
class OrchestratorState:
    plan_path: str
    current_milestone: int
    current_task: int
    completed_tasks: list[str]
    milestone_results: dict[str, MilestoneResult]
    
    def save(self, path: str):
        # Write to JSON file
        
    @classmethod
    def load(cls, path: str) -> "OrchestratorState":
        # Read from JSON file
```

**Resume behavior**: If stopped mid-task, restart that task from the beginning (tasks should be idempotent). If stopped between tasks, continue with next task.

---

## Part 3: File Structure

```
ktrdr/
├── docker/
│   └── sandbox/
│       └── Dockerfile           # Sandbox container image
│
├── scripts/
│   ├── sandbox-init.sh          # First-time sandbox setup
│   ├── sandbox-reset.sh         # Reset sandbox to clean state
│   ├── sandbox-shell.sh         # Interactive shell in sandbox
│   └── sandbox-claude.sh        # Run Claude Code command in sandbox
│
├── orchestrator/
│   ├── __init__.py
│   ├── main.py                  # Entry point, CLI
│   ├── config.py                # Configuration management
│   ├── models.py                # Data classes (Task, Milestone, etc.)
│   ├── plan_parser.py           # Parse implementation plan files
│   ├── task_runner.py           # Execute tasks via Claude Code
│   ├── e2e_runner.py            # Execute E2E tests
│   ├── diagnosis.py             # Failure investigation
│   ├── escalation.py            # Human notification and response
│   └── state.py                 # Persistence for resume capability
│
├── docker-compose.yml           # Existing (production-like)
├── docker-compose.dev.yml       # Existing (development)
└── docker-compose.sandbox.yml   # New (sandbox environment)
```

---

## Part 4: Implementation Phases

### Phase 1: Sandbox Environment (Start Here)

**Goal**: Claude Code can run in an isolated environment with full permissions.

**Tasks**:
1. Create `docker/sandbox/Dockerfile`
2. Create `docker-compose.sandbox.yml`
3. Create `scripts/sandbox-init.sh`
4. Create `scripts/sandbox-reset.sh`
5. Create `scripts/sandbox-shell.sh`
6. Test: Can manually run Claude Code in sandbox and execute a simple task

**Validation**:
- [ ] Sandbox container builds and runs
- [ ] Can clone repo into workspace
- [ ] Can run `docker compose` commands from inside sandbox
- [ ] Can run Claude Code CLI in sandbox
- [ ] Reset script restores clean state in < 30 seconds
- [ ] Changes in sandbox don't affect real repo

### Phase 2: Minimal Orchestrator

**Goal**: Orchestrator can run a single task and report result.

**Tasks**:
1. Create basic orchestrator structure
2. Implement plan parser (read milestone files)
3. Implement task runner (execute single task via Claude Code)
4. Implement basic result parsing
5. Test: Run one task from an existing implementation plan

**Validation**:
- [ ] Can parse existing milestone files
- [ ] Can execute a task and capture output
- [ ] Can detect success/failure
- [ ] Output is logged and readable

### Phase 3: E2E Integration

**Goal**: Orchestrator runs E2E tests after tasks and detects failures.

**Tasks**:
1. Implement E2E test runner
2. Parse E2E scenarios from milestone files
3. Execute test commands and check criteria
4. Report results

**Validation**:
- [ ] Can execute E2E test scenarios
- [ ] Correctly detects pass/fail
- [ ] Captures logs for debugging

### Phase 4: Failure Handling & Escalation

**Goal**: Orchestrator investigates failures and escalates appropriately.

**Tasks**:
1. Implement diagnosis flow (ask Claude Code to investigate)
2. Implement fix attempt flow
3. Implement escalation (notification + wait for response)
4. Implement "needs human" detection from Claude Code output

**Validation**:
- [ ] Failures trigger diagnosis
- [ ] Fixable issues get fixed automatically
- [ ] Unfixable issues escalate to Karl
- [ ] Questions/uncertainty from Claude Code escalate to Karl
- [ ] Karl can provide input and orchestrator continues

### Phase 5: Full Loop & Polish

**Goal**: Orchestrator can run a full milestone autonomously.

**Tasks**:
1. Implement milestone loop
2. Implement state persistence (resume after stop)
3. Add progress logging/display
4. Add desktop notifications
5. Test end-to-end with a real milestone

**Validation**:
- [ ] Can run a full milestone without intervention (happy path)
- [ ] Can resume after being stopped
- [ ] Escalations work correctly
- [ ] E2E failures are handled appropriately

---

## Part 5: Open Questions for Claude Code

These are decisions that can be made during implementation:

1. **Claude Code invocation**: What's the best way to invoke Claude Code CLI and capture structured output? (Direct CLI? API if available? Wrapper script?)

2. **Output parsing**: How to reliably detect "needs human" vs "failed" vs "complete" from Claude Code's natural language output? (Structured markers? Post-processing prompt?)

3. **E2E test format**: The current E2E tests in milestone files are somewhat freeform. Should we standardize the format for easier parsing?

4. **Escalation UX**: What's the best way for Karl to respond to escalations? (Interactive terminal? Separate file? Simple CLI prompt?)

5. **Workspace isolation**: Should each task get a completely fresh workspace, or is git-based reset sufficient?

---

## Part 6: Reference Materials

**Existing workflow commands** (in project files):
- `kdesign.md` - Design generation
- `kdesign-validate.md` - Design validation
- `kdesign-impl-plan.md` - Implementation planning
- `ktask.md` - Task implementation
- `kworkflow.md` - Overall workflow

**Existing infrastructure**:
- `docker-compose.dev.yml` - Current development environment (attached)
- `SKILL.md` (integration-testing) - E2E test patterns (attached)

**Key paths in Karl's setup**:
- `.claude/` - Commands, skills, CLAUDE.md (not in git, needs to be copied)
- `data/` - Instrument data (not in git, needs to be copied)
- `config/` - Configuration files

---

## Summary

**What we're building**:
1. A sandbox container where Claude Code can run safely with full permissions
2. An orchestrator that automates the task → test → fix loop

**Key principles**:
- Milestone as unit of autonomy
- Task as unit of context (fresh session per task)
- Root cause focus on failures
- Psychological safety for uncertainty
- Escalate early rather than guess wrong

**Start with**: Phase 1 (Sandbox Environment) - get Claude Code running safely in isolation before building the orchestrator on top.
