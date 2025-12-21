"""Loop detection for preventing runaway orchestrator execution.

Tracks task and E2E failures, computes error similarity, and detects
oscillation patterns to prevent wasting resources on tasks that
repeatedly fail with similar errors.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from orchestrator.state import OrchestratorState


@dataclass
class LoopDetectorConfig:
    """Configuration for loop detection thresholds.

    Attributes:
        max_task_attempts: Max retries for a single task before stopping
        max_e2e_fix_attempts: Max E2E fix cycles before stopping
        error_similarity_threshold: Similarity ratio (0-1) to consider errors "the same"
    """

    max_task_attempts: int = 3
    max_e2e_fix_attempts: int = 5
    error_similarity_threshold: float = 0.8


class LoopDetector:
    """Detects loops and repeated failures in orchestrator execution.

    Tracks failures per task and for E2E tests, computing error similarity
    to detect when the same problem keeps recurring. Prevents runaway
    execution by signaling when to stop.

    The detector uses OrchestratorState for persistence, so loop detection
    state survives orchestrator restarts.
    """

    def __init__(self, config: LoopDetectorConfig, state: OrchestratorState):
        """Initialize detector with config and state.

        Args:
            config: Thresholds for loop detection
            state: Orchestrator state for persistent tracking
        """
        self.config = config
        self.state = state

    def record_task_failure(self, task_id: str, error: str) -> None:
        """Record a task failure for loop detection.

        Increments attempt count and stores error message for similarity analysis.

        Args:
            task_id: ID of the failed task
            error: Error message from the failure
        """
        if task_id not in self.state.task_attempt_counts:
            self.state.task_attempt_counts[task_id] = 0
            self.state.task_errors[task_id] = []

        self.state.task_attempt_counts[task_id] += 1
        self.state.task_errors[task_id].append(error)

    def record_e2e_failure(self, error: str) -> None:
        """Record an E2E test failure.

        Increments E2E attempt count and stores error for oscillation detection.

        Args:
            error: Error message from the E2E failure
        """
        self.state.e2e_attempt_count += 1
        self.state.e2e_errors.append(error)

    def should_stop_task(self, task_id: str) -> tuple[bool, str]:
        """Check if we should stop retrying this task.

        Returns True if the task has exceeded max attempts, along with
        a reason message including error similarity analysis.

        Args:
            task_id: ID of the task to check

        Returns:
            Tuple of (should_stop, reason_message)
        """
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
        """Check if we should stop E2E fix attempts.

        Returns True if E2E has exceeded max attempts or if oscillation
        is detected (A-B-A pattern where fixes keep breaking each other).

        Returns:
            Tuple of (should_stop, reason_message)
        """
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
        """Reset E2E counters for a new milestone run.

        Clears E2E attempt count and error list while preserving
        task-level failure tracking.
        """
        self.state.e2e_attempt_count = 0
        self.state.e2e_errors = []

    def _compute_error_similarity(self, errors: list[str]) -> float:
        """Compute average similarity between consecutive errors.

        Uses SequenceMatcher to compare consecutive error pairs and
        returns the average similarity ratio.

        Args:
            errors: List of error messages to compare

        Returns:
            Average similarity ratio (0.0-1.0), or 0.0 if < 2 errors
        """
        if len(errors) < 2:
            return 0.0

        similarities = []
        for i in range(1, len(errors)):
            ratio = SequenceMatcher(None, errors[i - 1], errors[i]).ratio()
            similarities.append(ratio)

        return sum(similarities) / len(similarities)

    def _detect_oscillation(self, errors: list[str]) -> bool:
        """Detect A-B-A pattern in errors indicating fix oscillation.

        True A-B-A oscillation means: first and third errors are similar,
        but the middle error is DIFFERENT. This indicates fixing A broke B,
        then fixing B broke A again.

        If all three errors are similar (A-A-A), that's just repeated failure
        with the same error, not oscillation.

        Args:
            errors: List of error messages

        Returns:
            True if oscillation pattern detected
        """
        if len(errors) < 3:
            return False

        # A-B-A pattern: first and third similar, but middle is different
        first_third_similarity = SequenceMatcher(None, errors[-3], errors[-1]).ratio()
        first_second_similarity = SequenceMatcher(None, errors[-3], errors[-2]).ratio()

        # Oscillation = first and third are similar, but second is different
        is_first_third_similar = first_third_similarity > self.config.error_similarity_threshold
        is_second_different = first_second_similarity < self.config.error_similarity_threshold

        return is_first_third_similar and is_second_different
