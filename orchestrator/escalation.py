"""Escalation detection and handling for the Orchestrator.

Detects when Claude's output indicates uncertainty or the need for human input,
extracts questions/options/recommendations, and provides structured information
for presenting to the user.
"""

import re
import time
from dataclasses import dataclass

from opentelemetry import trace
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from orchestrator.notifications import send_notification

# Console for output
console = Console()


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

    Checks for explicit markers first, then looks for natural language
    patterns indicating uncertainty or a need for clarification.

    Args:
        output: The text output from Claude Code.

    Returns:
        True if the output indicates human input is needed.
    """
    # Explicit markers (highest priority)
    if "STATUS: needs_human" in output:
        return True
    if "NEEDS_HUMAN:" in output:
        return True
    if "OPTIONS:" in output:
        return True

    # Question patterns indicating uncertainty
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
    options_match = re.search(r"OPTIONS:\s*(.+?)(?=RECOMMENDATION:|$)", output, re.DOTALL)
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

        # Display formatted question
        console.print()
        console.print(
            Panel(
                f"[bold]Claude's question:[/bold]\n\n{info.question}",
                title=f"Task {info.task_id} - NEEDS HUMAN INPUT",
                border_style="yellow",
            )
        )

        if info.options:
            console.print("\n[bold]Options:[/bold]")
            for i, opt in enumerate(info.options):
                console.print(f"  {chr(65 + i)}) {opt}")

        if info.recommendation:
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

        return response
