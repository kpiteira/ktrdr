"""Unit tests for CheckpointPolicy.

Tests the policy logic that determines when checkpoints should be created,
based on unit intervals (epochs) and time intervals (seconds).
"""

from unittest.mock import patch

from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy


class TestCheckpointPolicyUnitTrigger:
    """Tests for unit-based (epoch) checkpoint triggers."""

    def test_should_checkpoint_at_unit_interval(self):
        """should_checkpoint returns True when unit interval is reached."""
        policy = CheckpointPolicy(unit_interval=10, time_interval_seconds=3600)

        # At epoch 0, no checkpoint yet
        assert policy.should_checkpoint(current_unit=0) is False

        # Record first checkpoint at epoch 0
        policy.record_checkpoint(current_unit=0)

        # Epochs 1-9 should not trigger
        for epoch in range(1, 10):
            assert policy.should_checkpoint(current_unit=epoch) is False

        # Epoch 10 should trigger (10 units since last checkpoint)
        assert policy.should_checkpoint(current_unit=10) is True

    def test_unit_trigger_after_multiple_intervals(self):
        """should_checkpoint triggers correctly after multiple intervals."""
        policy = CheckpointPolicy(unit_interval=5, time_interval_seconds=3600)

        # Record checkpoint at epoch 0
        policy.record_checkpoint(current_unit=0)

        # Epoch 5 should trigger
        assert policy.should_checkpoint(current_unit=5) is True
        policy.record_checkpoint(current_unit=5)

        # Epoch 10 should trigger (5 more epochs)
        assert policy.should_checkpoint(current_unit=10) is True
        policy.record_checkpoint(current_unit=10)

        # Epoch 14 should not trigger yet
        assert policy.should_checkpoint(current_unit=14) is False

        # Epoch 15 should trigger
        assert policy.should_checkpoint(current_unit=15) is True

    def test_unit_trigger_with_gaps(self):
        """should_checkpoint handles skipped epochs correctly."""
        policy = CheckpointPolicy(unit_interval=10, time_interval_seconds=3600)

        policy.record_checkpoint(current_unit=0)

        # Jump to epoch 25 (>= 10 units since last checkpoint)
        assert policy.should_checkpoint(current_unit=25) is True

    def test_first_checkpoint_without_prior_record(self):
        """First checkpoint triggers at unit_interval from 0."""
        policy = CheckpointPolicy(unit_interval=5, time_interval_seconds=3600)

        # No prior checkpoint recorded, starts from 0
        assert policy.should_checkpoint(current_unit=4) is False
        assert policy.should_checkpoint(current_unit=5) is True


class TestCheckpointPolicyTimeTrigger:
    """Tests for time-based checkpoint triggers."""

    def test_should_checkpoint_after_time_interval(self):
        """should_checkpoint returns True when time interval has elapsed."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=60)

        with patch("time.time") as mock_time:
            # Record checkpoint at t=0
            mock_time.return_value = 1000.0
            policy.record_checkpoint(current_unit=0)

            # At t=30s, not yet
            mock_time.return_value = 1030.0
            assert policy.should_checkpoint(current_unit=1) is False

            # At t=60s, should trigger
            mock_time.return_value = 1060.0
            assert policy.should_checkpoint(current_unit=1) is True

    def test_time_trigger_without_prior_checkpoint(self):
        """Time trigger doesn't fire if no checkpoint has been recorded yet."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=10)

        with patch("time.time") as mock_time:
            # No prior checkpoint, so time-based trigger won't fire
            mock_time.return_value = 1000.0
            assert policy.should_checkpoint(current_unit=5) is False

    def test_time_and_unit_triggers_are_independent(self):
        """Either time or unit trigger is sufficient to trigger checkpoint."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=60)

        with patch("time.time") as mock_time:
            # Record checkpoint at t=0, unit=0
            mock_time.return_value = 1000.0
            policy.record_checkpoint(current_unit=0)

            # Unit 50 but 120 seconds elapsed - time trigger should fire
            mock_time.return_value = 1120.0
            assert policy.should_checkpoint(current_unit=50) is True


class TestCheckpointPolicyForce:
    """Tests for forced checkpoint trigger."""

    def test_force_triggers_checkpoint_immediately(self):
        """force=True always triggers checkpoint regardless of intervals."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=3600)

        # Record checkpoint
        policy.record_checkpoint(current_unit=0)

        # Without force, should not trigger
        assert policy.should_checkpoint(current_unit=1) is False

        # With force, should trigger immediately
        assert policy.should_checkpoint(current_unit=1, force=True) is True

    def test_force_works_without_prior_checkpoint(self):
        """force=True works even without prior checkpoint."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=3600)

        assert policy.should_checkpoint(current_unit=0, force=True) is True


class TestCheckpointPolicyRecordCheckpoint:
    """Tests for record_checkpoint method."""

    def test_record_checkpoint_updates_last_unit(self):
        """record_checkpoint updates internal unit tracking."""
        policy = CheckpointPolicy(unit_interval=10, time_interval_seconds=3600)

        policy.record_checkpoint(current_unit=5)

        # Should not trigger at 14 (only 9 units since 5)
        assert policy.should_checkpoint(current_unit=14) is False

        # Should trigger at 15 (10 units since 5)
        assert policy.should_checkpoint(current_unit=15) is True

    def test_record_checkpoint_updates_last_time(self):
        """record_checkpoint updates internal time tracking."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=60)

        with patch("time.time") as mock_time:
            # Record at t=1000
            mock_time.return_value = 1000.0
            policy.record_checkpoint(current_unit=0)

            # At t=1030 (30s later), should not trigger
            mock_time.return_value = 1030.0
            assert policy.should_checkpoint(current_unit=1) is False

            # Record new checkpoint at t=1030
            policy.record_checkpoint(current_unit=1)

            # At t=1080 (50s since first, but only 50s since second)
            mock_time.return_value = 1080.0
            assert policy.should_checkpoint(current_unit=2) is False

            # At t=1090 (60s since second checkpoint)
            mock_time.return_value = 1090.0
            assert policy.should_checkpoint(current_unit=2) is True


class TestCheckpointPolicyDefaults:
    """Tests for default configuration values."""

    def test_default_values(self):
        """CheckpointPolicy has sensible defaults."""
        policy = CheckpointPolicy()

        # Should have default unit interval (from implementation)
        assert policy.unit_interval > 0
        assert policy.time_interval_seconds > 0

    def test_custom_intervals_are_respected(self):
        """Custom intervals override defaults."""
        policy = CheckpointPolicy(unit_interval=5, time_interval_seconds=120)

        assert policy.unit_interval == 5
        assert policy.time_interval_seconds == 120


class TestCheckpointPolicyEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_unit_interval_triggers_every_unit(self):
        """unit_interval=1 triggers after every single unit."""
        policy = CheckpointPolicy(unit_interval=1, time_interval_seconds=3600)

        policy.record_checkpoint(current_unit=0)

        # Every unit should trigger
        assert policy.should_checkpoint(current_unit=1) is True
        policy.record_checkpoint(current_unit=1)
        assert policy.should_checkpoint(current_unit=2) is True

    def test_very_large_time_interval(self):
        """Large time intervals work correctly."""
        policy = CheckpointPolicy(unit_interval=100, time_interval_seconds=86400)

        with patch("time.time") as mock_time:
            mock_time.return_value = 0.0
            policy.record_checkpoint(current_unit=0)

            # 23 hours later, should not trigger (unit-based also not met)
            mock_time.return_value = 82800.0  # 23 hours
            assert policy.should_checkpoint(current_unit=50) is False

            # 24 hours later, should trigger (time-based)
            mock_time.return_value = 86400.0  # 24 hours
            assert policy.should_checkpoint(current_unit=50) is True
