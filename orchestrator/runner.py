"""Consolidated runner for orchestrator task execution.

This module is the single coordination point for task execution.
Handles task execution by constructing prompts, invoking Claude Code
in the sandbox, and parsing structured output using HaikuBrain.

Consolidation notes (M4):
- Task execution moved from task_runner.py (Task 4.1)
- E2E execution merged from e2e_runner.py (Task 4.2)
- Escalation merged from escalation.py (Task 4.3)
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Callable, Literal

from opentelemetry import trace
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ktrdr.llm.haiku_brain import HaikuBrain
from orchestrator import telemetry
from orchestrator.config import OrchestratorConfig
from orchestrator.discord_notifier import format_escalation_needed, send_discord_message
from orchestrator.models import Task, TaskResult
from orchestrator.notifications import send_notification
from orchestrator.sandbox import SandboxManager

# Console for output
console = Console()


def _send_discord_notification(webhook_url: str, embed) -> None:
    """Send a Discord notification in fire-and-forget mode.

    Uses asyncio.create_task to dispatch the notification without blocking.
    If the webhook call fails, it's logged but doesn't affect execution.

    Args:
        webhook_url: Discord webhook URL
        embed: DiscordEmbed to send
    """
    asyncio.create_task(send_discord_message(webhook_url, embed))


# =============================================================================
# ESCALATION LOGIC (Task 4.3 - Merged from escalation.py)
# =============================================================================

# Module-level state for interpreter configuration
_brain: HaikuBrain | None = None
_llm_only: bool = False


def configure_interpreter(llm_only: bool = False) -> None:
    """Configure interpreter behavior.

    Called from CLI to set the detection mode.
    The interpreter always uses Haiku for fast, cheap output interpretation.

    Args:
        llm_only: If True, skip fast-path markers and always use LLM.
    """
    global _llm_only, _brain
    _llm_only = llm_only
    # Reset brain so it gets recreated
    _brain = None


def get_brain() -> HaikuBrain:
    """Get the singleton HaikuBrain instance.

    Lazily creates the brain on first use.
    Always uses Haiku for fast, cheap output interpretation.

    Returns:
        The HaikuBrain instance.
    """
    global _brain
    if _brain is None:
        _brain = HaikuBrain()  # Always uses Haiku default
    return _brain


def _check_explicit_markers(output: str) -> bool | None:
    """Check for explicit escalation markers.

    This is a fast-path check that avoids LLM calls when explicit markers
    are present. Returns None when no marker is found (LLM should be used).

    Args:
        output: The text output to check.

    Returns:
        True if explicit marker found, None if no marker (use LLM).
    """
    if _llm_only:
        return None  # Skip fast-path in LLM-only mode

    if "STATUS: needs_human" in output:
        return True
    if "NEEDS_HUMAN:" in output:
        return True

    return None  # No explicit marker, need LLM


@dataclass
class EscalationInfo:
    """Information extracted from Claude's output when human input is needed.

    Contains the structured question, available options, recommendation,
    and the raw output for reference.
    """

    task_id: str
    question: str
    options: list[str] | None
    recommendation: str | None
    raw_output: str


def detect_needs_human(output: str) -> bool:
    """Detect if Claude's output indicates human input is needed.

    Uses a hybrid approach:
    1. Fast-path: Check for explicit markers (unless --llm-only mode)
    2. Semantic: Use HaikuBrain interpretation for everything else

    Args:
        output: The text output from Claude Code.

    Returns:
        True if the output indicates human input is needed.
    """
    # Fast-path: check explicit markers (skipped in LLM-only mode)
    explicit = _check_explicit_markers(output)
    if explicit is not None:
        return explicit

    # Semantic understanding via HaikuBrain
    result = get_brain().interpret_result(output)
    return result.status == "needs_help"


def extract_escalation_info(task_id: str, output: str) -> EscalationInfo:
    """Extract question, options, and recommendation from Claude's output.

    Tries structured format first (QUESTION:/OPTIONS:/RECOMMENDATION:),
    then falls back to heuristics for unstructured output.

    Args:
        task_id: The ID of the task being executed.
        output: The text output from Claude Code.

    Returns:
        EscalationInfo with extracted information.
    """
    # Try structured format first
    question_match = re.search(
        r"QUESTION:\s*(.+?)(?=OPTIONS:|RECOMMENDATION:|$)", output, re.DOTALL
    )
    options_match = re.search(
        r"OPTIONS:\s*(.+?)(?=RECOMMENDATION:|$)", output, re.DOTALL
    )
    rec_match = re.search(r"RECOMMENDATION:\s*(.+?)$", output, re.DOTALL)

    question = (
        question_match.group(1).strip()
        if question_match
        else _extract_question_heuristic(output)
    )
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
    """Extract question using heuristics when no structured format is present.

    Looks for sentences ending with ?, then for uncertainty statements.
    Falls back to a generic message if nothing found.

    Args:
        output: The text output to extract from.

    Returns:
        The extracted question or a fallback message.
    """
    # Find sentences ending with ?
    questions = re.findall(r"[^.!?]*\?", output)
    if questions:
        return questions[-1].strip()

    # Find "I'm not sure..." type statements
    uncertainty = re.search(
        r"(I'm not sure|I'm uncertain|I recommend).+?[.!]", output, re.IGNORECASE
    )
    if uncertainty:
        return uncertainty.group(0)

    return "Claude expressed uncertainty. Please review the output."


def _parse_options(options_text: str) -> list[str]:
    """Parse options from text in various formats.

    Supports:
    - Lettered: A) option, B) option
    - Numbered with dot: 1. option, 2. option
    - Numbered with paren: 1) option, 2) option
    - Bullets: - option or * option

    Args:
        options_text: The text containing options.

    Returns:
        List of parsed options, or the whole text as a single item if unparseable.
    """
    # Try lettered options: A) ..., B) ...
    lettered = re.findall(r"[A-Z]\)\s*(.+?)(?=[A-Z]\)|$)", options_text, re.DOTALL)
    if lettered:
        return [opt.strip() for opt in lettered]

    # Try numbered with dot: 1. ..., 2. ...
    numbered_dot = re.findall(r"\d+\.\s*(.+?)(?=\d+\.|$)", options_text, re.DOTALL)
    if numbered_dot:
        return [opt.strip() for opt in numbered_dot]

    # Try numbered with paren: 1) ..., 2) ...
    numbered_paren = re.findall(r"\d+\)\s*(.+?)(?=\d+\)|$)", options_text, re.DOTALL)
    if numbered_paren:
        return [opt.strip() for opt in numbered_paren]

    # Try bullet points with dash
    bullets_dash = re.findall(r"-\s*(.+?)(?=-|$)", options_text, re.DOTALL)
    if bullets_dash:
        return [opt.strip() for opt in bullets_dash]

    # Try bullet points with asterisk
    bullets_star = re.findall(r"\*\s*(.+?)(?=\*|$)", options_text, re.DOTALL)
    if bullets_star:
        return [opt.strip() for opt in bullets_star]

    # Fallback: return the whole text as a single option
    return [options_text.strip()]


async def escalate_and_wait(
    info: EscalationInfo,
    tracer: trace.Tracer,
    notify: bool = True,
) -> str:
    """Present escalation question to user and wait for response.

    Displays a formatted question with options and recommendation,
    sends a notification if requested, and waits for user input.
    Records timing and response in the trace span.

    Args:
        info: Extracted escalation information to present.
        tracer: OpenTelemetry tracer for creating spans.
        notify: Whether to send a macOS notification (default True).

    Returns:
        The user's response, or the recommendation if they enter 'skip'.
    """
    with tracer.start_as_current_span("orchestrator.escalation") as span:
        span.set_attribute("task.id", info.task_id)
        span.set_attribute("escalation.question", info.question[:200])

        start_time = time.time()

        # Send notification if requested
        if notify:
            send_notification(
                title="Orchestrator needs input",
                message=f"Task {info.task_id}: {info.question[:50]}...",
            )

        # Display Claude's full output first (what Claude actually said)
        console.print()
        console.print(
            Panel(
                info.raw_output[:2000]
                if len(info.raw_output) > 2000
                else info.raw_output,
                title=f"Task {info.task_id} - Claude's Output",
                border_style="dim",
            )
        )

        # Display parsed question
        console.print()
        console.print(
            Panel(
                f"[bold]Parsed question:[/bold]\n\n{info.question}",
                title="NEEDS HUMAN INPUT",
                border_style="yellow",
            )
        )

        if info.options and len(info.options) > 0 and info.options[0]:
            # Only show options if they look valid (not garbled)
            valid_options = [
                opt for opt in info.options if len(opt) > 2 and not opt.startswith('"')
            ]
            if valid_options:
                console.print("\n[bold]Options:[/bold]")
                for i, opt in enumerate(valid_options):
                    console.print(f"  {chr(65 + i)}) {opt}")

        if info.recommendation and len(info.recommendation) > 5:
            # Only show recommendation if it looks valid
            if not info.recommendation.startswith(
                '"'
            ) and not info.recommendation.startswith(")"):
                console.print(f"\n[bold]Recommendation:[/bold] {info.recommendation}")

        # Get input
        console.print()
        response = Prompt.ask(
            "Your response (or 'skip' for recommendation)",
            default="skip" if info.recommendation else None,
        )

        # Handle skip
        if response.lower() == "skip" and info.recommendation:
            response = info.recommendation

        wait_seconds = time.time() - start_time
        span.set_attribute("escalation.wait_seconds", wait_seconds)
        span.set_attribute("escalation.response", response[:200])

        # Record escalation metric
        try:
            telemetry.escalations_counter.add(1, {"task_id": info.task_id})
        except (AttributeError, NameError):
            pass  # Metrics not initialized

        return response


# =============================================================================
# TASK EXECUTION FUNCTIONS (Task 4.1 - Merged from task_runner.py)
# =============================================================================


async def run_task(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    plan_path: str,
    human_guidance: str | None = None,
    on_tool_use: Callable[[str, dict], None] | None = None,
    model: str | None = None,
    session_id: str | None = None,
) -> TaskResult:
    """Execute a task via Claude Code in the sandbox.

    Args:
        task: The task to execute
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        plan_path: Path to the milestone plan file (for /ktask invocation)
        human_guidance: Optional guidance from human (for retry after escalation)
        on_tool_use: Optional callback for streaming tool use events.
            If provided, uses streaming mode for real-time progress visibility.
        model: Claude model to use (e.g., 'sonnet', 'opus'). If None, uses default.
        session_id: Session ID to resume. If provided, continues previous session.

    Returns:
        TaskResult with execution outcome
    """
    # Construct prompt with /ktask command
    prompt = _build_prompt(task, plan_path, human_guidance)

    # Invoke Claude Code (streaming if callback provided)
    start_time = time.time()

    if on_tool_use is not None:
        # Use streaming mode for real-time progress
        claude_result = await sandbox.invoke_claude_streaming(
            prompt=prompt,
            on_tool_use=on_tool_use,
            max_turns=config.max_turns,
            timeout=config.task_timeout_seconds,
            model=model,
            session_id=session_id,
        )
    else:
        # Use standard mode (no streaming)
        claude_result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=config.max_turns,
            timeout=config.task_timeout_seconds,
            model=model,
            session_id=session_id,
        )

    duration = time.time() - start_time

    # Use HaikuBrain singleton for semantic interpretation of output
    brain = get_brain()
    interpretation = brain.interpret_result(claude_result.result)

    # Map status: HaikuBrain uses "needs_help", TaskResult uses "needs_human"
    status: Literal["completed", "failed", "needs_human"]
    if interpretation.status == "needs_help":
        status = "needs_human"
    elif interpretation.status == "completed":
        status = "completed"
    else:
        status = "failed"

    # Estimate tokens from cost (rough estimate: ~$0.01 per 1000 tokens)
    tokens_used = _estimate_tokens(claude_result.total_cost_usd)

    return TaskResult(
        task_id=task.id,
        status=status,
        duration_seconds=duration,
        tokens_used=tokens_used,
        cost_usd=claude_result.total_cost_usd,
        output=claude_result.result,
        session_id=claude_result.session_id,
        question=interpretation.question,
        options=interpretation.options,
        recommendation=interpretation.recommendation,
        error=interpretation.error,
    )


def _build_prompt(task: Task, plan_path: str, human_guidance: str | None = None) -> str:
    """Build the prompt for Claude Code execution using /ktask skill.

    Invokes the /ktask skill which handles:
    - TDD workflow (RED → GREEN → REFACTOR)
    - Git workflow (branch, commits)
    - Memory reflection
    - Handoff documents
    """
    prompt = f"/ktask impl: {plan_path} task: {task.id}"

    if human_guidance:
        prompt += f"\n\nAdditional guidance: {human_guidance}"

    return prompt


def _estimate_tokens(cost_usd: float) -> int:
    """Estimate token count from cost.

    Rough estimate based on Claude pricing (~$0.01 per 1000 tokens average).
    """
    if cost_usd <= 0:
        return 0
    return int(cost_usd * 100000)  # $0.01 = 1000 tokens


async def run_task_with_escalation(
    task: Task,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    plan_path: str,
    tracer: trace.Tracer,
    notify: bool = True,
    on_tool_use: Callable[[str, dict], None] | None = None,
    model: str | None = None,
) -> TaskResult:
    """Execute task with escalation and retry support.

    Wraps run_task with:
    - HaikuBrain-based retry/escalate decisions (contextual, not count-based)
    - Escalation to human when Claude needs input or Haiku says escalate
    - Retry with guidance_for_retry from Haiku
    - Session continuation via --resume after escalation

    Args:
        task: The task to execute
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        plan_path: Path to the milestone plan file
        tracer: OpenTelemetry tracer for creating spans
        notify: Whether to send notifications on escalation
        on_tool_use: Optional callback for streaming tool use events
        model: Claude model to use (e.g., 'sonnet', 'opus'). If None, uses default.

    Returns:
        TaskResult with execution outcome
    """
    guidance: str | None = None
    session_id: str | None = None  # Track session for continuation
    attempt_history: list[str] = []  # Track errors for retry decisions

    while True:
        # Execute the task
        result = await run_task(
            task, sandbox, config, plan_path, guidance, on_tool_use, model, session_id
        )

        # Track session for continuation after escalation
        if result.session_id:
            session_id = result.session_id

        if result.status == "completed":
            return result

        elif result.status == "needs_human":
            # Extract escalation info and present to user
            info = EscalationInfo(
                task_id=task.id,
                question=result.question or "Claude needs clarification.",
                options=result.options,
                recommendation=result.recommendation,
                raw_output=result.output,
            )

            # Send Discord notification: Escalation needed
            if config.discord_enabled:
                _send_discord_notification(
                    config.discord_webhook_url,
                    format_escalation_needed(
                        task.id,
                        task.title,
                        info.question,
                        info.options,
                    ),
                )

            response = await escalate_and_wait(info, tracer, notify)
            guidance = response

            session_info = f" session {session_id[:8]}..." if session_id else ""
            console.print(f"Task {task.id}: Resuming{session_info} with guidance")
            # Loop continues with guidance and session resumption

        elif result.status == "failed":
            # Record failure in attempt history
            error_summary = f"Failed: {result.error or 'Unknown error'}"
            attempt_history.append(error_summary)
            attempt_count = len(attempt_history)

            console.print(
                f"Task {task.id}: [bold red]FAILED[/] (attempt {attempt_count})"
            )

            # Ask HaikuBrain for retry/escalate decision
            brain = get_brain()
            decision = brain.should_retry_or_escalate(
                task_id=task.id,
                task_title=task.title,
                attempt_history=attempt_history,
                attempt_count=attempt_count,
            )

            if decision.decision == "retry":
                console.print(f"Retrying: {decision.reason}")
                if decision.guidance_for_retry:
                    console.print(f"Guidance: {decision.guidance_for_retry}")
                    guidance = decision.guidance_for_retry
                else:
                    guidance = None
                # Loop continues with guidance
            else:
                # Escalate
                console.print(f"Escalating: {decision.reason}")

                with tracer.start_as_current_span("orchestrator.escalate") as span:
                    span.set_attribute("task.id", task.id)
                    span.set_attribute("reason", decision.reason)

                # Record escalation metric
                try:
                    telemetry.loops_counter.add(1, {"type": "escalation"})
                except (AttributeError, NameError):
                    pass  # Metrics not initialized

                info = EscalationInfo(
                    task_id=task.id,
                    question=f"Task failed after {attempt_count} attempts: {decision.reason}",
                    options=None,
                    recommendation=None,
                    raw_output=result.output,
                )

                # Send Discord notification: Escalation needed (failure)
                if config.discord_enabled:
                    _send_discord_notification(
                        config.discord_webhook_url,
                        format_escalation_needed(
                            task.id,
                            task.title,
                            info.question,
                            info.options,
                        ),
                    )

                response = await escalate_and_wait(info, tracer, notify)
                guidance = response
                # Loop continues with human guidance after escalation


# =============================================================================
# E2E TEST EXECUTION (Task 4.2 - Merged from e2e_runner.py)
# =============================================================================


@dataclass
class E2EResult:
    """Result from an E2E test execution.

    Captures the outcome of running E2E tests via Claude Code, including
    status, metrics, and failure analysis.

    Status values:
        passed: All E2E tests passed
        failed: One or more E2E tests failed
        unclear: Could not determine test outcome
    """

    status: Literal["passed", "failed", "unclear"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    diagnosis: str | None = None
    fix_suggestion: str | None = None
    is_fixable: bool = False
    raw_output: str = ""


async def run_e2e_tests(
    milestone_id: str,
    e2e_scenario: str,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
) -> E2EResult:
    """Execute E2E tests via Claude Code.

    Invokes Claude Code with the E2E test scenario, then uses HaikuBrain
    to semantically interpret the output and determine pass/fail status.

    Args:
        milestone_id: Identifier for the milestone being tested
        e2e_scenario: The E2E test scenario text (from plan markdown)
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration
        tracer: OpenTelemetry tracer for creating spans

    Returns:
        E2EResult with test outcome and analysis
    """
    prompt = _build_e2e_prompt(milestone_id, e2e_scenario)

    with tracer.start_as_current_span("orchestrator.e2e_test") as span:
        span.set_attribute("milestone.id", milestone_id)

        start_time = time.time()
        claude_result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=30,  # E2E tests need fewer turns than full tasks
            timeout=config.task_timeout_seconds,
        )
        duration = time.time() - start_time

        # Use HaikuBrain for semantic interpretation (per M4 plan)
        output = claude_result.result
        brain = get_brain()
        interpretation = brain.interpret_result(output)

        # Map HaikuBrain status to E2E status
        if interpretation.status == "completed":
            status: Literal["passed", "failed", "unclear"] = "passed"
            diagnosis = None
            is_fixable = False
            fix_suggestion = None
        elif interpretation.status == "failed":
            status = "failed"
            diagnosis = interpretation.error or interpretation.summary
            # Check if output contains fix info
            is_fixable = "FIXABLE: yes" in output
            fix_suggestion = _extract_fix_plan(output) if is_fixable else None
        else:
            # needs_help -> unclear
            status = "unclear"
            diagnosis = interpretation.question or interpretation.summary
            is_fixable = False
            fix_suggestion = None

        # Set span attributes
        span.set_attribute("e2e.status", status)
        span.set_attribute("e2e.is_fixable", is_fixable)

        # Record metrics (safe if counter not yet defined - see Task 5.5)
        if hasattr(telemetry, "e2e_tests_counter"):
            telemetry.e2e_tests_counter.add(
                1, {"milestone": milestone_id, "status": status}
            )

        return E2EResult(
            status=status,
            duration_seconds=duration,
            tokens_used=_estimate_tokens(claude_result.total_cost_usd),
            cost_usd=claude_result.total_cost_usd,
            diagnosis=diagnosis,
            fix_suggestion=fix_suggestion,
            is_fixable=is_fixable,
            raw_output=output,
        )


def _build_e2e_prompt(milestone_id: str, e2e_scenario: str) -> str:
    """Build the prompt for E2E test execution.

    Instructs Claude to execute the E2E scenario and report results
    in a structured format that can be parsed.

    Args:
        milestone_id: Identifier for the milestone
        e2e_scenario: The test scenario text

    Returns:
        Formatted prompt string
    """
    return f"""Execute the following E2E test scenario for milestone {milestone_id}.
Run each command, observe results, and determine if the test passes.

{e2e_scenario}

After executing, report:
- E2E_STATUS: passed | failed
- If failed: DIAGNOSIS: <root cause analysis>
- If failed: FIXABLE: yes | no
- If fixable: FIX_PLAN: <specific changes to make>
- If not fixable: OPTIONS: <options> RECOMMENDATION: <recommendation>
"""


def _extract_fix_plan(output: str) -> str | None:
    """Extract fix plan from Claude output.

    Looks for FIX_PLAN: marker and extracts the text that follows.

    Args:
        output: Raw output text from Claude Code

    Returns:
        Fix plan text if found, None otherwise
    """
    import re

    match = re.search(r"FIX_PLAN:\s*(.+?)(?:\n(?=[A-Z_]+:)|\Z)", output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


async def apply_e2e_fix(
    fix_plan: str,
    sandbox: SandboxManager,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
) -> bool:
    """Apply a fix suggested by Claude for a failed E2E test.

    Invokes Claude Code with the fix plan and determines if the fix
    was successfully applied by parsing the structured output.

    Args:
        fix_plan: The fix plan text from E2E failure analysis
        sandbox: Sandbox manager for Claude invocation
        config: Orchestrator configuration (unused but kept for consistency)
        tracer: OpenTelemetry tracer for creating spans

    Returns:
        True if fix was applied successfully, False otherwise
    """
    prompt = _build_fix_prompt(fix_plan)

    with tracer.start_as_current_span("orchestrator.e2e_fix") as span:
        span.set_attribute("fix.plan", fix_plan[:200])

        result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=20,
            timeout=300,
        )

        success = "FIX_APPLIED: yes" in result.result
        span.set_attribute("fix.success", success)

        # Record metrics (safe if counter not yet defined - see Task 5.5)
        if hasattr(telemetry, "e2e_fix_counter"):
            telemetry.e2e_fix_counter.add(1, {"success": str(success).lower()})

        return success


def _build_fix_prompt(fix_plan: str) -> str:
    """Build the prompt for applying an E2E fix.

    Instructs Claude to apply the specific fix and report success/failure.

    Args:
        fix_plan: The fix plan to apply

    Returns:
        Formatted prompt string
    """
    return f"""Apply the following fix:

{fix_plan}

Make the specific changes described. Do not make additional changes.
Report when complete:
- FIX_APPLIED: yes | no
- If no: REASON: <why it couldn't be applied>
"""
