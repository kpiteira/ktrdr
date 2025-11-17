"""
Unit tests for CheckpointPolicy and CheckpointDecisionEngine.

Tests verify:
- CheckpointPolicy dataclass validation
- Time-based checkpoint decision logic
- Force checkpoint at natural boundaries (epochs, bars)
- Config file loading

These tests should FAIL until ktrdr/checkpoint/policy.py is implemented.
"""

import time

import pytest
import yaml

# These imports will fail until implementation exists
from ktrdr.checkpoint.policy import (
    CheckpointDecisionEngine,
    CheckpointPolicy,
    load_checkpoint_policies,
)


class TestCheckpointPolicy:
    """Test CheckpointPolicy dataclass."""

    def test_policy_creation_with_defaults(self):
        """
        Test creating policy with default values.

        Acceptance Criteria:
        - ✅ Policy created with all required fields
        - ✅ Default values are reasonable
        """
        policy = CheckpointPolicy(
            checkpoint_interval_seconds=300.0,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )

        assert policy.checkpoint_interval_seconds == 300.0
        assert policy.force_checkpoint_every_n == 50
        assert policy.delete_on_completion is True
        assert policy.checkpoint_on_failure is True

    def test_policy_validation_negative_interval(self):
        """
        Test that negative interval is rejected.

        Acceptance Criteria:
        - ✅ ValueError raised for negative checkpoint_interval_seconds
        """
        with pytest.raises(
            ValueError, match="checkpoint_interval_seconds must be positive"
        ):
            CheckpointPolicy(
                checkpoint_interval_seconds=-1.0,
                force_checkpoint_every_n=50,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )

    def test_policy_validation_zero_interval(self):
        """
        Test that zero interval is rejected.

        Acceptance Criteria:
        - ✅ ValueError raised for zero checkpoint_interval_seconds
        """
        with pytest.raises(
            ValueError, match="checkpoint_interval_seconds must be positive"
        ):
            CheckpointPolicy(
                checkpoint_interval_seconds=0.0,
                force_checkpoint_every_n=50,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )

    def test_policy_validation_negative_force_boundary(self):
        """
        Test that negative force boundary is rejected.

        Acceptance Criteria:
        - ✅ ValueError raised for negative force_checkpoint_every_n
        """
        with pytest.raises(
            ValueError, match="force_checkpoint_every_n must be positive"
        ):
            CheckpointPolicy(
                checkpoint_interval_seconds=300.0,
                force_checkpoint_every_n=-1,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )

    def test_policy_validation_zero_force_boundary(self):
        """
        Test that zero force boundary is rejected.

        Acceptance Criteria:
        - ✅ ValueError raised for zero force_checkpoint_every_n
        """
        with pytest.raises(
            ValueError, match="force_checkpoint_every_n must be positive"
        ):
            CheckpointPolicy(
                checkpoint_interval_seconds=300.0,
                force_checkpoint_every_n=0,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )


class TestCheckpointDecisionEngine:
    """Test CheckpointDecisionEngine checkpoint decision logic."""

    @pytest.fixture
    def policy(self):
        """Create standard test policy: 5-minute intervals, force every 50 boundaries."""
        return CheckpointPolicy(
            checkpoint_interval_seconds=300.0,  # 5 minutes
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )

    @pytest.fixture
    def engine(self):
        """Create decision engine instance."""
        return CheckpointDecisionEngine()

    def test_first_boundary_no_checkpoint(self, engine, policy):
        """
        Test that first boundary (epoch 1, bar 1) does NOT trigger checkpoint.

        Acceptance Criteria:
        - ✅ should_checkpoint() returns False for first natural boundary
        - ✅ Reason indicates "first boundary"
        """
        current_time = time.time()
        last_checkpoint_time = current_time  # Just started

        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=1,  # First epoch/bar
            total_boundaries=1,
        )

        assert should_checkpoint is False
        assert "first" in reason.lower() or "boundary" in reason.lower()

    def test_force_checkpoint_at_boundary(self, engine, policy):
        """
        Test that force checkpoint triggers at configured boundary.

        Acceptance Criteria:
        - ✅ Checkpoint triggers every force_checkpoint_every_n boundaries
        - ✅ Reason indicates "force checkpoint"
        """
        current_time = time.time()
        last_checkpoint_time = current_time - 10.0  # Recent checkpoint (10s ago)

        # Epoch/bar 50 should trigger (force_checkpoint_every_n=50)
        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=50,
            total_boundaries=50,
        )

        assert should_checkpoint is True
        assert "force" in reason.lower() or "boundary" in reason.lower()

    def test_force_checkpoint_at_multiple_boundaries(self, engine, policy):
        """
        Test force checkpoint at 50, 100, 150 boundaries.

        Acceptance Criteria:
        - ✅ Checkpoint triggers at exact multiples of force_checkpoint_every_n
        """
        current_time = time.time()
        last_checkpoint_time = current_time - 10.0

        for boundary in [50, 100, 150, 200]:
            should_checkpoint, reason = engine.should_checkpoint(
                policy=policy,
                last_checkpoint_time=last_checkpoint_time,
                current_time=current_time,
                natural_boundary=boundary,
                total_boundaries=boundary,
            )

            assert (
                should_checkpoint is True
            ), f"Should checkpoint at boundary {boundary}"
            assert "force" in reason.lower() or "boundary" in reason.lower()

    def test_time_based_checkpoint_triggers(self, engine, policy):
        """
        Test that checkpoint triggers after checkpoint_interval_seconds.

        Acceptance Criteria:
        - ✅ Checkpoint triggers when time_since_last >= checkpoint_interval_seconds
        - ✅ Reason indicates "time elapsed"
        """
        current_time = time.time()
        last_checkpoint_time = current_time - 301.0  # 301 seconds ago (> 300s interval)

        # Epoch 10 (not a force boundary, but enough time passed)
        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=10,
            total_boundaries=10,
        )

        assert should_checkpoint is True
        assert "time" in reason.lower() or "elapsed" in reason.lower()

    def test_time_based_checkpoint_does_not_trigger_too_early(self, engine, policy):
        """
        Test that checkpoint does NOT trigger before checkpoint_interval_seconds.

        Acceptance Criteria:
        - ✅ No checkpoint when time_since_last < checkpoint_interval_seconds
        - ✅ Reason indicates "not enough time"
        """
        current_time = time.time()
        last_checkpoint_time = (
            current_time - 100.0
        )  # Only 100 seconds ago (< 300s interval)

        # Epoch 10 (not a force boundary, not enough time)
        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=10,
            total_boundaries=10,
        )

        assert should_checkpoint is False
        assert "time" in reason.lower() or "not enough" in reason.lower()

    def test_force_checkpoint_overrides_time(self, engine, policy):
        """
        Test that force checkpoint triggers even if time threshold not met.

        Acceptance Criteria:
        - ✅ Force boundary triggers checkpoint regardless of time since last
        """
        current_time = time.time()
        last_checkpoint_time = current_time - 10.0  # Very recent (10s ago)

        # Boundary 50 should still trigger (force boundary)
        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=50,
            total_boundaries=50,
        )

        assert should_checkpoint is True
        assert "force" in reason.lower() or "boundary" in reason.lower()

    def test_exact_time_threshold_triggers(self, engine, policy):
        """
        Test checkpoint at exact time threshold (boundary condition).

        Acceptance Criteria:
        - ✅ Checkpoint triggers when time_since_last == checkpoint_interval_seconds
        """
        current_time = time.time()
        last_checkpoint_time = current_time - 300.0  # Exactly 300 seconds (threshold)

        should_checkpoint, reason = engine.should_checkpoint(
            policy=policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=10,
            total_boundaries=10,
        )

        assert should_checkpoint is True  # >= threshold
        assert "time" in reason.lower() or "elapsed" in reason.lower()

    def test_different_policy_intervals(self, engine):
        """
        Test decision engine with different checkpoint intervals.

        Acceptance Criteria:
        - ✅ Engine adapts to different policy intervals correctly
        """
        # Fast checkpointing policy (1 minute)
        fast_policy = CheckpointPolicy(
            checkpoint_interval_seconds=60.0,
            force_checkpoint_every_n=10,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )

        current_time = time.time()
        last_checkpoint_time = current_time - 61.0  # 61 seconds ago

        should_checkpoint, _ = engine.should_checkpoint(
            policy=fast_policy,
            last_checkpoint_time=last_checkpoint_time,
            current_time=current_time,
            natural_boundary=5,
            total_boundaries=5,
        )

        assert should_checkpoint is True  # Time threshold met for 1-minute policy


class TestLoadCheckpointPolicies:
    """Test loading checkpoint policies from config/persistence.yaml."""

    def test_load_policies_from_config(self):
        """
        Test loading policies from persistence.yaml config file.

        Acceptance Criteria:
        - ✅ Policies loaded from config/persistence.yaml
        - ✅ Training policy has correct values
        - ✅ Backtesting policy has correct values
        """
        policies = load_checkpoint_policies()

        assert "training" in policies
        assert "backtesting" in policies

        # Verify training policy (from config/persistence.yaml)
        training_policy = policies["training"]
        assert isinstance(training_policy, CheckpointPolicy)
        assert training_policy.checkpoint_interval_seconds == 300.0
        assert training_policy.force_checkpoint_every_n == 50
        assert training_policy.delete_on_completion is True
        assert training_policy.checkpoint_on_failure is True

        # Verify backtesting policy
        backtesting_policy = policies["backtesting"]
        assert isinstance(backtesting_policy, CheckpointPolicy)
        assert backtesting_policy.checkpoint_interval_seconds == 300.0
        assert backtesting_policy.force_checkpoint_every_n == 5000
        assert backtesting_policy.delete_on_completion is True
        assert backtesting_policy.checkpoint_on_failure is True

    def test_load_policies_handles_missing_file(self):
        """
        Test that loading policies fails gracefully if config file missing.

        Acceptance Criteria:
        - ✅ FileNotFoundError raised with clear message
        """
        # This test will validate error handling (implementation will check file exists)
        # For now, we know file exists, but we test the error path
        from unittest.mock import patch

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="persistence.yaml"):
                load_checkpoint_policies()

    def test_load_policies_handles_invalid_yaml(self):
        """
        Test that loading policies fails gracefully if YAML is invalid.

        Acceptance Criteria:
        - ✅ ValueError raised for invalid YAML syntax
        """
        from unittest.mock import mock_open, patch

        invalid_yaml = "invalid: yaml: content: ][]["

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with pytest.raises((ValueError, yaml.YAMLError)):
                load_checkpoint_policies()

    def test_load_policies_validates_structure(self):
        """
        Test that config validation catches missing required fields.

        Acceptance Criteria:
        - ✅ ValueError raised if checkpointing section missing
        - ✅ ValueError raised if training/backtesting policies missing
        """
        from unittest.mock import mock_open, patch

        # Config missing checkpointing section
        incomplete_config = yaml.dump({"database": {}})

        with patch("builtins.open", mock_open(read_data=incomplete_config)):
            with pytest.raises(ValueError, match="checkpointing"):
                load_checkpoint_policies()
