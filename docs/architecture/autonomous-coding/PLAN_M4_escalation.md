---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Milestone 4: Escalation + Loop Detection

**Branch:** `feature/orchestrator-m4-escalation`
**Builds on:** M3 (task loop works)
**Estimated Tasks:** 11

---

## Capability

Orchestrator detects when Claude needs human input, presents the question with options, waits for response, and resumes. Loop detection prevents runaway execution by stopping after repeated failures.

---

## GATE: Before Starting M4

**Pause here to design the real validation feature:**

```bash
# Use the working orchestrator from M3 to help design
# "Orchestrator Enhancements" with /kdesign workflow

# This gives us a real feature with:
# - Tasks that might trigger "needs human" (design decisions)
# - Multiple tasks for loop detection testing
# - E2E tests for M5 validation
```

---

## E2E Test Scenario

```bash
# Scenario A: Human input needed
# 1. Run ambiguous task
uv run orchestrator run orchestrator/test_plans/ambiguous_task.md

# Expected:
# [timestamp] Task 1.1: Implement caching
#             Invoking Claude Code...
# [timestamp] NEEDS HUMAN INPUT
#
# Claude's question:
#   "The task says to add caching but doesn't specify the type.
#
#    OPTIONS:
#    A) Redis (distributed, persistent)
#    B) In-memory (fast, local only)
#    C) File-based (simple, persistent)
#
#    RECOMMENDATION: B for simplicity
#
#    What would you prefer?"
#
# Your response (or 'skip' for recommendation): B
#
# [timestamp] Resuming Task 1.1 with guidance...
# [timestamp] Task 1.1: COMPLETED

# 2. Verify trace includes escalation
open http://localhost:16686
# Expect: orchestrator.escalation span with question, wait_seconds, response

# 3. Verify escalation metric
curl -s "http://localhost:9090/api/v1/query?query=orchestrator_escalations_total" | jq

# ---

# Scenario B: Loop detection (task fails repeatedly)
uv run orchestrator run orchestrator/test_plans/doomed_to_fail.md

# Expected after 3 attempts:
# [timestamp] Task 1.1: Impossible task
#             Invoking Claude Code...
# [timestamp] Task 1.1: FAILED (attempt 1/3)
# [timestamp] Retrying Task 1.1...
# [timestamp] Task 1.1: FAILED (attempt 2/3)
# [timestamp] Retrying Task 1.1...
# [timestamp] Task 1.1: FAILED (attempt 3/3)
# [timestamp] LOOP DETECTED: Task 1.1 failed 3 times with similar errors
# [timestamp] Stopping to prevent resource waste.
#
# Error similarity: 87%
# Please investigate and provide guidance.

# 4. Verify loop detection metric
curl -s "http://localhost:9090/api/v1/query?query=orchestrator_loops_detected_total" | jq

# ---

# Scenario C: Human guidance doesn't help
# 1. Run task that needs guidance
# 2. Provide guidance
# 3. Task still fails
# 4. After 3 total attempts (including with guidance), loop detected
```

---

## Tasks

### Task 4.1: Create Escalation Handler

**File:** `orchestrator/escalation.py`
**Type:** CODING

**Description:**
Detect "needs human" in Claude output, extract question/options, present to user.

**Implementation Notes:**

```python
import re
from dataclasses import dataclass

@dataclass
class EscalationInfo:
    task_id: str
    question: str
    options: list[str] | None
    recommendation: str | None
    raw_output: str

def detect_needs_human(output: str) -> bool:
    """Detect if Claude is expressing uncertainty."""
    # Explicit markers (highest priority)
    if "STATUS: needs_human" in output:
        return True
    if "NEEDS_HUMAN:" in output or "OPTIONS:" in output:
        return True

    # Question patterns
    question_patterns = [
        r"should I\s+",
        r"would you prefer",
        r"I'm not sure whether",
        r"I'm uncertain",
        r"the options (are|seem to be)",
        r"I recommend .+ but",
        r"could go either way",
        r"what would you like",
        r"do you want me to",
    ]
    for pattern in question_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            return True

    return False

def extract_escalation_info(task_id: str, output: str) -> EscalationInfo:
    """Extract question, options, recommendation from output."""

    # Try structured format first
    question_match = re.search(r"QUESTION:\s*(.+?)(?=OPTIONS:|RECOMMENDATION:|$)", output, re.DOTALL)
    options_match = re.search(r"OPTIONS:\s*(.+?)(?=RECOMMENDATION:|$)", output, re.DOTALL)
    rec_match = re.search(r"RECOMMENDATION:\s*(.+?)$", output, re.DOTALL)

    question = question_match.group(1).strip() if question_match else _extract_question_heuristic(output)
    options = _parse_options(options_match.group(1)) if options_match else None
    recommendation = rec_match.group(1).strip() if rec_match else None

    return EscalationInfo(
        task_id=task_id,
        question=question,
        options=options,
        recommendation=recommendation,
        raw_output=output,
    )

def _extract_question_heuristic(output: str) -> str:
    """Extract question using heuristics when no structured format."""
    # Find sentences ending with ?
    questions = re.findall(r"[^.!?]*\?", output)
    if questions:
        return questions[-1].strip()

    # Find "I'm not sure..." type statements
    uncertainty = re.search(r"(I'm not sure|I'm uncertain|I recommend).+?[.!]", output, re.IGNORECASE)
    if uncertainty:
        return uncertainty.group(0)

    return "Claude expressed uncertainty. Please review the output."

def _parse_options(options_text: str) -> list[str]:
    """Parse options from text."""
    # Try lettered options: A) ..., B) ...
    lettered = re.findall(r"[A-Z]\)\s*(.+?)(?=[A-Z]\)|$)", options_text, re.DOTALL)
    if lettered:
        return [opt.strip() for opt in lettered]

    # Try numbered: 1. ..., 2. ...
    numbered = re.findall(r"\d+[.)]\s*(.+?)(?=\d+[.)]|$)", options_text, re.DOTALL)
    if numbered:
        return [opt.strip() for opt in numbered]

    # Try bullet points
    bullets = re.findall(r"[-*]\s*(.+?)(?=[-*]|$)", options_text, re.DOTALL)
    if bullets:
        return [opt.strip() for opt in bullets]

    return [options_text.strip()]
```

**Acceptance Criteria:**

- [ ] Detects explicit STATUS: needs_human
- [ ] Detects question patterns in natural language
- [ ] Extracts structured QUESTION/OPTIONS/RECOMMENDATION
- [ ] Falls back to heuristics for unstructured output
- [ ] Unit tests cover various formats

---

### Task 4.2: Create User Input Handler

**File:** `orchestrator/escalation.py`
**Type:** CODING

**Description:**
Present escalation to user and wait for input.

**Implementation Notes:**

```python
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

async def escalate_and_wait(
    info: EscalationInfo,
    tracer: trace.Tracer,
    notify: bool = True,
) -> str:
    """Present question to user and wait for response."""

    with tracer.start_as_current_span("orchestrator.escalation") as span:
        span.set_attribute("task.id", info.task_id)
        span.set_attribute("escalation.question", info.question[:200])

        start_time = time.time()

        # Send notification
        if notify:
            send_notification(
                title="Orchestrator needs input",
                message=f"Task {info.task_id}: {info.question[:50]}..."
            )

        # Display formatted question
        console.print()
        console.print(Panel(
            f"[bold]Claude's question:[/bold]\n\n{info.question}",
            title=f"Task {info.task_id} - NEEDS HUMAN INPUT",
            border_style="yellow",
        ))

        if info.options:
            console.print("\n[bold]Options:[/bold]")
            for i, opt in enumerate(info.options):
                console.print(f"  {chr(65+i)}) {opt}")

        if info.recommendation:
            console.print(f"\n[bold]Recommendation:[/bold] {info.recommendation}")

        # Get input
        console.print()
        response = Prompt.ask(
            "Your response (or 'skip' for recommendation)",
            default="skip" if info.recommendation else None,
        )

        if response.lower() == "skip" and info.recommendation:
            response = info.recommendation

        wait_seconds = time.time() - start_time
        span.set_attribute("escalation.wait_seconds", wait_seconds)
        span.set_attribute("escalation.response", response[:200])

        # Update metrics
        escalations_counter.add(1, {"task_id": info.task_id})

        return response
```

**Acceptance Criteria:**

- [ ] Displays formatted question with Rich
- [ ] Shows options if present
- [ ] Shows recommendation if present
- [ ] 'skip' uses recommendation
- [ ] Records wait time in trace
- [ ] Sends notification

---

### Task 4.3: Create Loop Detector

**File:** `orchestrator/loop_detector.py`
**Type:** CODING

**Description:**
Track failures and detect loops via attempt counting and error similarity.

**Implementation Notes:**

```python
from dataclasses import dataclass
from difflib import SequenceMatcher

@dataclass
class LoopDetectorConfig:
    max_task_attempts: int = 3
    max_e2e_fix_attempts: int = 5
    error_similarity_threshold: float = 0.8

class LoopDetector:
    def __init__(self, config: LoopDetectorConfig, state: OrchestratorState):
        self.config = config
        self.state = state

    def record_task_failure(self, task_id: str, error: str) -> None:
        """Record a task failure."""
        if task_id not in self.state.task_attempt_counts:
            self.state.task_attempt_counts[task_id] = 0
            self.state.task_errors[task_id] = []

        self.state.task_attempt_counts[task_id] += 1
        self.state.task_errors[task_id].append(error)

    def record_e2e_failure(self, error: str) -> None:
        """Record an E2E test failure."""
        self.state.e2e_attempt_count += 1
        self.state.e2e_errors.append(error)

    def should_stop_task(self, task_id: str) -> tuple[bool, str]:
        """Check if we should stop retrying this task."""
        attempts = self.state.task_attempt_counts.get(task_id, 0)

        if attempts >= self.config.max_task_attempts:
            errors = self.state.task_errors.get(task_id, [])
            similarity = self._compute_error_similarity(errors)

            return True, (
                f"Task {task_id} failed {attempts} times. "
                f"Error similarity: {similarity:.0%}. "
                "Stopping to prevent resource waste."
            )

        return False, ""

    def should_stop_e2e(self) -> tuple[bool, str]:
        """Check if we should stop E2E fix attempts."""
        if self.state.e2e_attempt_count >= self.config.max_e2e_fix_attempts:
            return True, (
                f"E2E tests failed {self.state.e2e_attempt_count} times. "
                "Possible oscillation detected. Stopping."
            )

        # Check for oscillation (A breaks B, fix B breaks A)
        if len(self.state.e2e_errors) >= 3:
            if self._detect_oscillation(self.state.e2e_errors):
                return True, "E2E fix oscillation detected. Manual intervention needed."

        return False, ""

    def reset_e2e(self) -> None:
        """Reset E2E counters (for new milestone run)."""
        self.state.e2e_attempt_count = 0
        self.state.e2e_errors = []

    def _compute_error_similarity(self, errors: list[str]) -> float:
        """Compute average similarity between consecutive errors."""
        if len(errors) < 2:
            return 0.0

        similarities = []
        for i in range(1, len(errors)):
            ratio = SequenceMatcher(None, errors[i-1], errors[i]).ratio()
            similarities.append(ratio)

        return sum(similarities) / len(similarities)

    def _detect_oscillation(self, errors: list[str]) -> bool:
        """Detect A-B-A pattern in errors."""
        if len(errors) < 3:
            return False

        # Check if error[0] is similar to error[2] (A-B-A pattern)
        similarity = SequenceMatcher(None, errors[-3], errors[-1]).ratio()
        return similarity > self.config.error_similarity_threshold
```

**Acceptance Criteria:**

- [ ] Counts task attempts per task
- [ ] Detects repeated failures
- [ ] Computes error similarity
- [ ] Detects E2E oscillation (A-B-A pattern)
- [ ] Configurable thresholds
- [ ] Unit tests for all scenarios

---

### Task 4.4: Integrate Escalation into Task Runner

**File:** `orchestrator/task_runner.py`
**Type:** CODING

**Description:**
Update task runner to detect needs_human and trigger escalation.

**Implementation Notes:**

```python
async def run_task_with_escalation(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
    loop_detector: LoopDetector,
    notify: bool = True,
) -> TaskResult:
    """Execute task with escalation and retry support."""

    guidance = None

    while True:
        # Check loop detection
        should_stop, reason = loop_detector.should_stop_task(task.id)
        if should_stop:
            with tracer.start_as_current_span("orchestrator.loop_detected") as span:
                span.set_attribute("task.id", task.id)
                span.set_attribute("reason", reason)
                loops_counter.add(1, {"type": "task"})

            console.print(f"[bold red]LOOP DETECTED:[/bold] {reason}")
            return TaskResult(
                task_id=task.id,
                status="failed",
                error=reason,
                # ... other fields
            )

        result = await run_task(task, sandbox, config, guidance)

        if result.status == "completed":
            return result

        elif result.status == "needs_human":
            # Extract and present question
            info = extract_escalation_info(task.id, result.output)
            response = await escalate_and_wait(info, tracer, notify)
            guidance = response
            # Loop continues with guidance

        elif result.status == "failed":
            loop_detector.record_task_failure(task.id, result.error or "Unknown error")

            attempts = loop_detector.state.task_attempt_counts.get(task.id, 0)
            max_attempts = loop_detector.config.max_task_attempts

            console.print(f"Task {task.id}: [bold red]FAILED[/bold] (attempt {attempts}/{max_attempts})")

            if attempts < max_attempts:
                console.print("Retrying...")
                # Loop continues
            # else loop detection will catch it next iteration
```

**Acceptance Criteria:**

- [ ] Detects needs_human and triggers escalation
- [ ] Retries task with human guidance
- [ ] Respects loop detection limits
- [ ] Records loop detection events

---

### Task 4.5: Integrate Loop Detection into Milestone Runner

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Update milestone runner to use loop detector.

**Implementation Notes:**

- Create LoopDetector at milestone start
- Pass to task runner
- Check should_stop_task before each attempt
- Save loop state to OrchestratorState

**Acceptance Criteria:**

- [ ] Loop detector initialized per milestone
- [ ] State persisted for resume
- [ ] Milestone stops on loop detection

---

### Task 4.6: Add Escalation Metrics

**File:** `orchestrator/telemetry.py`
**Type:** CODING

**Description:**
Add metrics for escalations and loop detection.

**Implementation Notes:**

```python
escalations_counter: metrics.Counter
loops_counter: metrics.Counter

def create_metrics(meter: metrics.Meter):
    global escalations_counter, loops_counter
    # ... existing ...

    escalations_counter = meter.create_counter(
        "orchestrator_escalations_total",
        description="Total escalations to human",
    )

    loops_counter = meter.create_counter(
        "orchestrator_loops_detected_total",
        description="Total loops detected",
    )
```

**Acceptance Criteria:**

- [ ] Escalation counter increments
- [ ] Loop counter increments with type label
- [ ] Queryable in Prometheus

---

### Task 4.7: Create Ambiguous Task Test Plan

**File:** `orchestrator/test_plans/ambiguous_task.md`
**Type:** CODING

**Description:**
Test plan designed to trigger "needs human" escalation.

**Content:**

```markdown
# Test Milestone: Ambiguous Task

## Task 1.1: Implement caching

**File:** `orchestrator/cache.py`
**Type:** CODING

**Description:**
Add caching to improve performance.

(Note: Intentionally vague - no specification of cache type,
eviction policy, or scope. Should trigger uncertainty.)

**Acceptance Criteria:**
- [ ] Caching is implemented
- [ ] Performance is improved
```

**Acceptance Criteria:**

- [ ] Task is genuinely ambiguous
- [ ] Running it triggers needs_human
- [ ] Claude provides reasonable options

---

### Task 4.8: Create Doomed Task Test Plan

**File:** `orchestrator/test_plans/doomed_to_fail.md`
**Type:** CODING

**Description:**
Test plan designed to fail repeatedly for loop detection testing.

**Content:**

```markdown
# Test Milestone: Doomed to Fail

## Task 1.1: Impossible task

**File:** `orchestrator/impossible.py`
**Type:** CODING

**Description:**
Create a file that simultaneously:
1. Has exactly 100 lines
2. Has exactly 50 lines
3. Contains no newlines

(This is intentionally impossible to satisfy all criteria)

**Acceptance Criteria:**
- [ ] File has exactly 100 lines
- [ ] File has exactly 50 lines
- [ ] File contains no newline characters
```

**Acceptance Criteria:**

- [ ] Task is genuinely impossible
- [ ] Fails consistently with similar errors
- [ ] Triggers loop detection after 3 attempts

---

### Task 4.9: Create LLM Output Interpreter

**File:** `orchestrator/llm_interpreter.py`
**Type:** CODING

**Description:**
Create a module that uses Claude Code CLI with Haiku 4.5 to interpret task output, replacing fragile regex-based detection with semantic understanding.

**Implementation Notes:**

```python
import json
import subprocess
from dataclasses import dataclass

@dataclass
class InterpretationResult:
    """Result of LLM interpretation of task output."""
    needs_human: bool
    question: str | None
    options: list[str] | None
    recommendation: str | None
    task_completed: bool
    task_failed: bool
    error_message: str | None

INTERPRETATION_PROMPT = """Analyze this Claude Code output and return ONLY valid JSON (no markdown, no explanation):

{{
  "needs_human": true or false,
  "question": "the question being asked" or null,
  "options": ["option A", "option B"] or null,
  "recommendation": "recommended choice" or null,
  "task_completed": true or false,
  "task_failed": true or false,
  "error_message": "error details" or null
}}

Output to analyze:
{output}
"""

class LLMInterpreter:
    def __init__(self, model: str = "claude-haiku-4.5-20251001"):
        self.model = model

    def interpret(self, output: str) -> InterpretationResult:
        """Interpret task output using Claude Code CLI with Haiku."""
        prompt = INTERPRETATION_PROMPT.format(output=output[:8000])

        result = subprocess.run(
            [
                "claude",
                "--model", self.model,
                "--print",  # Output only, no interactive
                "--no-session-persistence",  # Don't save session
                "--tools", "",  # No tools, just LLM response
                "-p", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Fallback: assume task completed if we can't interpret
            return InterpretationResult(
                needs_human=False,
                question=None,
                options=None,
                recommendation=None,
                task_completed=True,
                task_failed=False,
                error_message=f"Interpreter error: {result.stderr[:200]}",
            )

        # Parse JSON response
        try:
            data = json.loads(result.stdout.strip())
            return InterpretationResult(**data)
        except json.JSONDecodeError:
            # Try to extract JSON from response (may have extra text)
            import re
            json_match = re.search(r'\{[^{}]*\}', result.stdout, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return InterpretationResult(**data)
            raise
```

**Acceptance Criteria:**

- [ ] Uses Claude Code CLI with `claude-haiku-4.5-20251001`
- [ ] Uses `--no-session-persistence` and `--tools ""` for minimal footprint
- [ ] Returns structured InterpretationResult
- [ ] Handles output truncation for large outputs
- [ ] Handles JSON parsing errors gracefully
- [ ] Graceful fallback if CLI fails
- [ ] Unit tests with mocked subprocess

---

### Task 4.10: Integrate LLM Interpreter into Escalation

**File:** `orchestrator/escalation.py`
**Type:** CODING

**Description:**
Replace regex-based `detect_needs_human()` and `extract_escalation_info()` with LLM interpreter. Keep regex as optional fast-path for explicit markers, controlled by `--llm-only` CLI flag.

**Implementation Notes:**

```python
from orchestrator.llm_interpreter import LLMInterpreter, InterpretationResult

# Module-level state (set by configure_interpreter)
_interpreter: LLMInterpreter | None = None
_llm_only: bool = False

def configure_interpreter(llm_only: bool = False) -> None:
    """Configure interpreter behavior. Called from CLI."""
    global _llm_only
    _llm_only = llm_only

def get_interpreter() -> LLMInterpreter:
    global _interpreter
    if _interpreter is None:
        _interpreter = LLMInterpreter()
    return _interpreter

def _check_explicit_markers(output: str) -> bool | None:
    """Check for explicit markers. Returns None if no match (use LLM)."""
    if _llm_only:
        return None  # Skip fast-path, always use LLM

    if "STATUS: needs_human" in output:
        return True
    if "NEEDS_HUMAN:" in output:
        return True

    return None  # No explicit marker, need LLM

def detect_needs_human(output: str) -> bool:
    """Detect if Claude needs human input.

    Uses optional fast-path for explicit markers, then LLM interpretation.
    Use --llm-only flag to skip fast-path.
    """
    # Optional fast path: explicit markers
    explicit = _check_explicit_markers(output)
    if explicit is not None:
        return explicit

    # Semantic understanding via LLM
    result = get_interpreter().interpret(output)
    return result.needs_human

# ... rest unchanged ...
```

**CLI Integration (cli.py):**

```python
@click.option("--llm-only", is_flag=True, help="Use LLM interpreter only, skip regex fast-path")
def run(plan_path: str, llm_only: bool, ...):
    """Run a milestone plan."""
    from orchestrator.escalation import configure_interpreter
    configure_interpreter(llm_only=llm_only)
    # ... rest of run command ...
```

**Acceptance Criteria:**

- [ ] `--llm-only` flag skips all regex, uses pure LLM
- [ ] Default behavior: explicit markers use fast-path, rest uses LLM
- [ ] Easy to remove regex code later (isolated in `_check_explicit_markers`)
- [ ] Existing tests still pass
- [ ] New tests for LLM integration (mocked)
- [ ] Graceful degradation if CLI fails

---

### Task 4.11: Update Escalation Tests for LLM Interpreter

**File:** `orchestrator/tests/test_escalation.py`, `orchestrator/tests/test_llm_interpreter.py`
**Type:** CODING

**Description:**
Update tests to mock subprocess calls and add integration tests. Test the `ORCHESTRATOR_LLM_ONLY` config flag.

**Implementation Notes:**

```python
# test_llm_interpreter.py
import json
from unittest.mock import patch, MagicMock
from orchestrator.llm_interpreter import LLMInterpreter, InterpretationResult

class TestLLMInterpreter:
    """Test LLM interpreter with mocked subprocess."""

    def test_interpret_success(self):
        """Should parse valid JSON response."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "needs_human": True,
            "question": "Which approach?",
            "options": ["A", "B"],
            "recommendation": "A",
            "task_completed": False,
            "task_failed": False,
            "error_message": None,
        })

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            assert result.needs_human is True
            assert result.question == "Which approach?"
            mock_run.assert_called_once()

    def test_interpret_cli_failure_fallback(self):
        """Should fallback gracefully on CLI error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error"

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            # Fallback: assume completed
            assert result.needs_human is False
            assert result.task_completed is True

    def test_uses_correct_model(self):
        """Should use claude-haiku-4.5-20251001."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"needs_human": false, "task_completed": true}'

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("test")

            call_args = mock_run.call_args[0][0]
            assert "--model" in call_args
            model_idx = call_args.index("--model") + 1
            assert call_args[model_idx] == "claude-haiku-4.5-20251001"


# test_escalation.py additions
class TestDetectNeedsHumanWithLLM:
    """Test LLM-based detection."""

    def test_explicit_marker_skips_llm(self):
        """Explicit markers should not call LLM (default behavior)."""
        with patch("orchestrator.escalation.get_interpreter") as mock:
            output = "STATUS: needs_human\nI need clarification."
            result = detect_needs_human(output)

            assert result is True
            mock.assert_not_called()  # Fast path, no LLM

    def test_llm_only_mode_ignores_markers(self):
        """--llm-only should always use LLM, skip markers."""
        from orchestrator.escalation import configure_interpreter, detect_needs_human

        mock_result = InterpretationResult(
            needs_human=True,
            question="Q",
            options=None,
            recommendation=None,
            task_completed=False,
            task_failed=False,
            error_message=None,
        )

        # Enable LLM-only mode
        configure_interpreter(llm_only=True)

        try:
            with patch("orchestrator.escalation.get_interpreter") as mock:
                mock.return_value.interpret.return_value = mock_result

                output = "STATUS: needs_human"  # Has marker
                result = detect_needs_human(output)

                # Should call LLM despite marker
                mock.return_value.interpret.assert_called_once()
        finally:
            # Reset to default
            configure_interpreter(llm_only=False)


class TestLLMInterpreterIntegration:
    """Integration tests (require Claude CLI, skip in CI)."""

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Skip in CI"
    )
    def test_real_haiku_interpretation(self):
        """Test with real Claude Code CLI call."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter.interpret(
            "The task says to add caching but doesn't specify the type. "
            "Options: A) Redis B) In-memory. I recommend B for simplicity. "
            "What would you prefer?"
        )

        assert result.needs_human is True
        assert result.options is not None
```

**Acceptance Criteria:**

- [ ] LLMInterpreter tests mock subprocess.run
- [ ] Tests verify correct CLI args (model, --no-session-persistence, --tools)
- [ ] Tests cover CLI failure fallback
- [ ] Tests for `--llm-only` CLI flag via `configure_interpreter()`
- [ ] Integration test with real CLI (skipped in CI)
- [ ] All tests pass: `make test-unit`

---

## Milestone Verification

**Test with ambiguous_task.md:**

```bash
./scripts/sandbox-reset.sh
uv run orchestrator run orchestrator/test_plans/ambiguous_task.md

# Should trigger NEEDS HUMAN INPUT
# Enter: "Use in-memory caching with LRU eviction, max 1000 items"
# Should complete successfully
```

**Test with doomed_to_fail.md:**

```bash
./scripts/sandbox-reset.sh
uv run orchestrator run orchestrator/test_plans/doomed_to_fail.md

# Should attempt 3 times then LOOP DETECTED
```

**Test with real feature (from GATE):**

```bash
# Run first milestone of "Orchestrator Enhancements"
uv run orchestrator run docs/milestones/orchestrator_enhancements_m1.md

# Should handle any escalations that arise
# Should complete or escalate appropriately
```

**Checklist:**

- [ ] All tasks complete
- [ ] Unit tests pass
- [ ] Escalation flow works end-to-end
- [ ] Loop detection triggers appropriately
- [ ] Traces include escalation spans
- [ ] Metrics update correctly
- [ ] Quality gates pass
