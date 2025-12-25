"""Task runner for executing tasks via Claude Code.

DEPRECATED: This module is a backwards-compatibility shim.
All functions have been moved to orchestrator.runner (M4 consolidation).
This file will be deleted in Task 4.4.

Import from orchestrator.runner instead:
    from orchestrator.runner import run_task, run_task_with_escalation
"""

# Re-export from consolidated runner for backwards compatibility
from orchestrator.runner import (
    _build_prompt,
    _estimate_tokens,
    run_task,
    run_task_with_escalation,
)

__all__ = [
    "run_task",
    "run_task_with_escalation",
    "_build_prompt",
    "_estimate_tokens",
]
