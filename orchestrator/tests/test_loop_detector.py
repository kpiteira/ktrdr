"""Tests for loop detection functionality.

These tests verify the LoopDetector can:
1. Count task attempts and detect repeated failures
2. Compute error similarity between attempts
3. Detect E2E oscillation patterns (A-B-A)
4. Use configurable thresholds
"""

from datetime import datetime


class TestLoopDetectorConfig:
    """Test the LoopDetectorConfig dataclass."""

    def test_config_has_defaults(self):
        """Should have sensible defaults."""
        from orchestrator.loop_detector import LoopDetectorConfig

        config = LoopDetectorConfig()
        assert config.max_task_attempts == 3
        assert config.max_e2e_fix_attempts == 5
        assert config.error_similarity_threshold == 0.8

    def test_config_can_be_customized(self):
        """Should allow custom thresholds."""
        from orchestrator.loop_detector import LoopDetectorConfig

        config = LoopDetectorConfig(
            max_task_attempts=5,
            max_e2e_fix_attempts=10,
            error_similarity_threshold=0.9,
        )
        assert config.max_task_attempts == 5
        assert config.max_e2e_fix_attempts == 10
        assert config.error_similarity_threshold == 0.9


class TestLoopDetectorTaskFailures:
    """Test task failure tracking."""

    def test_record_task_failure_increments_count(self):
        """Should increment attempt count on failure."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        detector.record_task_failure("4.1", "Module not found")
        assert state.task_attempt_counts["4.1"] == 1

        detector.record_task_failure("4.1", "Module not found")
        assert state.task_attempt_counts["4.1"] == 2

    def test_record_task_failure_stores_error(self):
        """Should store error messages for later analysis."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        detector.record_task_failure("4.1", "Error A")
        detector.record_task_failure("4.1", "Error B")

        assert state.task_errors["4.1"] == ["Error A", "Error B"]

    def test_should_stop_task_false_before_max_attempts(self):
        """Should not stop before max attempts reached."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(max_task_attempts=3)
        detector = LoopDetector(config, state)

        detector.record_task_failure("4.1", "Error")
        detector.record_task_failure("4.1", "Error")

        should_stop, reason = detector.should_stop_task("4.1")
        assert should_stop is False
        assert reason == ""

    def test_should_stop_task_true_at_max_attempts(self):
        """Should stop at max attempts."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(max_task_attempts=3)
        detector = LoopDetector(config, state)

        detector.record_task_failure("4.1", "Error")
        detector.record_task_failure("4.1", "Error")
        detector.record_task_failure("4.1", "Error")

        should_stop, reason = detector.should_stop_task("4.1")
        assert should_stop is True
        assert "4.1" in reason
        assert "3 times" in reason

    def test_should_stop_task_includes_similarity(self):
        """Stop reason should include error similarity."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(max_task_attempts=3)
        detector = LoopDetector(config, state)

        # Same error 3 times - high similarity
        detector.record_task_failure("4.1", "Module 'foo' not found")
        detector.record_task_failure("4.1", "Module 'foo' not found")
        detector.record_task_failure("4.1", "Module 'foo' not found")

        should_stop, reason = detector.should_stop_task("4.1")
        assert should_stop is True
        assert "similarity" in reason.lower()


class TestLoopDetectorErrorSimilarity:
    """Test error similarity computation."""

    def test_identical_errors_high_similarity(self):
        """Identical errors should have 100% similarity."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        errors = ["Same error message", "Same error message", "Same error message"]
        similarity = detector._compute_error_similarity(errors)
        assert similarity == 1.0

    def test_different_errors_lower_similarity(self):
        """Different errors should have lower similarity."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        errors = [
            "Module 'foo' not found",
            "Connection timeout on port 8080",
            "Invalid JSON in response",
        ]
        similarity = detector._compute_error_similarity(errors)
        assert similarity < 0.5

    def test_single_error_zero_similarity(self):
        """Single error should return 0 similarity."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        errors = ["Only one error"]
        similarity = detector._compute_error_similarity(errors)
        assert similarity == 0.0

    def test_empty_errors_zero_similarity(self):
        """Empty errors list should return 0 similarity."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        similarity = detector._compute_error_similarity([])
        assert similarity == 0.0


class TestLoopDetectorE2E:
    """Test E2E failure tracking and oscillation detection."""

    def test_record_e2e_failure_increments_count(self):
        """Should increment E2E attempt count."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        detector.record_e2e_failure("Test A failed")
        assert state.e2e_attempt_count == 1

        detector.record_e2e_failure("Test B failed")
        assert state.e2e_attempt_count == 2

    def test_record_e2e_failure_stores_error(self):
        """Should store E2E error messages."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        detector.record_e2e_failure("Error A")
        detector.record_e2e_failure("Error B")

        assert state.e2e_errors == ["Error A", "Error B"]

    def test_should_stop_e2e_false_before_max(self):
        """Should not stop E2E before max attempts."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(max_e2e_fix_attempts=5)
        detector = LoopDetector(config, state)

        for _ in range(4):
            detector.record_e2e_failure("Error")

        should_stop, reason = detector.should_stop_e2e()
        assert should_stop is False

    def test_should_stop_e2e_true_at_max(self):
        """Should stop E2E at max attempts."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(max_e2e_fix_attempts=5)
        detector = LoopDetector(config, state)

        for _ in range(5):
            detector.record_e2e_failure("Error")

        should_stop, reason = detector.should_stop_e2e()
        assert should_stop is True
        assert "5 times" in reason

    def test_detect_oscillation_aba_pattern(self):
        """Should detect A-B-A oscillation pattern."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(error_similarity_threshold=0.8)
        detector = LoopDetector(config, state)

        # A-B-A pattern: first error, different error, back to first
        detector.record_e2e_failure("Test A: auth module failed with missing token")
        detector.record_e2e_failure("Test B: database connection timeout")
        detector.record_e2e_failure("Test A: auth module failed with missing token")

        should_stop, reason = detector.should_stop_e2e()
        assert should_stop is True
        assert "oscillation" in reason.lower()

    def test_no_oscillation_when_errors_different(self):
        """Should not detect oscillation when errors are all different."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(error_similarity_threshold=0.8)
        detector = LoopDetector(config, state)

        detector.record_e2e_failure("Error type A")
        detector.record_e2e_failure("Error type B")
        detector.record_e2e_failure("Error type C")

        should_stop, reason = detector.should_stop_e2e()
        assert should_stop is False

    def test_reset_e2e_clears_counters(self):
        """reset_e2e should clear E2E counters."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        detector.record_e2e_failure("Error")
        detector.record_e2e_failure("Error")

        detector.reset_e2e()

        assert state.e2e_attempt_count == 0
        assert state.e2e_errors == []


class TestLoopDetectorOscillationDetection:
    """Test the _detect_oscillation helper."""

    def test_detect_oscillation_needs_three_errors(self):
        """Oscillation requires at least 3 errors."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        detector = LoopDetector(LoopDetectorConfig(), state)

        # Only 2 errors - can't detect oscillation
        errors = ["Error A", "Error B"]
        assert detector._detect_oscillation(errors) is False

    def test_detect_oscillation_true_for_matching_first_and_third(self):
        """Should detect oscillation when first and third errors match."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(error_similarity_threshold=0.8)
        detector = LoopDetector(config, state)

        errors = ["Same error message", "Different error", "Same error message"]
        assert detector._detect_oscillation(errors) is True

    def test_detect_oscillation_false_for_all_different(self):
        """Should not detect oscillation when all errors differ."""
        from orchestrator.loop_detector import LoopDetector, LoopDetectorConfig
        from orchestrator.state import OrchestratorState

        state = OrchestratorState(
            milestone_id="M4",
            plan_path="test.md",
            started_at=datetime.now(),
        )
        config = LoopDetectorConfig(error_similarity_threshold=0.8)
        detector = LoopDetector(config, state)

        errors = ["Error A", "Error B", "Error C"]
        assert detector._detect_oscillation(errors) is False
