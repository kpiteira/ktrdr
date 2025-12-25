"""Escalation detection and handling for the Orchestrator.

DEPRECATED: This module is a backwards-compatibility shim.
All functionality has been moved to orchestrator.runner (Task 4.3).
This file will be deleted in Task 4.4.

Import from orchestrator.runner instead:
    from orchestrator.runner import (
        EscalationInfo,
        escalate_and_wait,
        configure_interpreter,
        detect_needs_human,
        extract_escalation_info,
        get_brain,
    )
"""

# Re-export everything from runner.py for backwards compatibility
from orchestrator.runner import (
    EscalationInfo,
    _check_explicit_markers,
    _extract_question_heuristic,
    _parse_options,
    configure_interpreter,
    detect_needs_human,
    escalate_and_wait,
    extract_escalation_info,
    get_brain,
)

__all__ = [
    "EscalationInfo",
    "configure_interpreter",
    "detect_needs_human",
    "escalate_and_wait",
    "extract_escalation_info",
    "get_brain",
    "_check_explicit_markers",
    "_extract_question_heuristic",
    "_parse_options",
]
