"""
Unit tests for CheckpointPolicy with checkpoint_on_cancellation field.

Tests verify:
- CheckpointPolicy can be created with checkpoint_on_cancellation field
- Field defaults and validation work correctly
- Policy can be loaded from config with new field
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from ktrdr.checkpoint.policy import CheckpointPolicy, load_checkpoint_policies


class TestCheckpointPolicyWithCancellation:
    """Test CheckpointPolicy with checkpoint_on_cancellation field."""

    def test_policy_creation_with_checkpoint_on_cancellation(self):
        """Test creating policy with checkpoint_on_cancellation field."""
        policy = CheckpointPolicy(
            checkpoint_interval_seconds=300,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )

        assert policy.checkpoint_interval_seconds == 300
        assert policy.force_checkpoint_every_n == 50
        assert policy.delete_on_completion is True
        assert policy.checkpoint_on_failure is True
        assert policy.checkpoint_on_cancellation is True

    def test_policy_checkpoint_on_cancellation_false(self):
        """Test policy with checkpoint_on_cancellation disabled."""
        policy = CheckpointPolicy(
            checkpoint_interval_seconds=300,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=False,
        )

        assert policy.checkpoint_on_cancellation is False

    def test_load_policies_with_checkpoint_on_cancellation(self):
        """Test loading policies from config with checkpoint_on_cancellation."""
        # Create temporary config file
        config_content = {
            "checkpointing": {
                "training": {
                    "checkpoint_interval_seconds": 300,
                    "force_checkpoint_every_n": 50,
                    "delete_on_completion": True,
                    "checkpoint_on_failure": True,
                    "checkpoint_on_cancellation": True,
                },
                "backtesting": {
                    "checkpoint_interval_seconds": 300,
                    "force_checkpoint_every_n": 5000,
                    "delete_on_completion": True,
                    "checkpoint_on_failure": True,
                    "checkpoint_on_cancellation": False,
                },
            }
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp_file:
            yaml.dump(config_content, tmp_file)
            tmp_path = Path(tmp_file.name)

        try:
            policies = load_checkpoint_policies(tmp_path)

            # Verify training policy
            assert policies["training"].checkpoint_on_cancellation is True

            # Verify backtesting policy
            assert policies["backtesting"].checkpoint_on_cancellation is False
        finally:
            tmp_path.unlink()

    def test_load_policies_defaults_to_false_if_missing(self):
        """Test that checkpoint_on_cancellation defaults to False if not in config."""
        # Create config without checkpoint_on_cancellation field
        config_content = {
            "checkpointing": {
                "training": {
                    "checkpoint_interval_seconds": 300,
                    "force_checkpoint_every_n": 50,
                    "delete_on_completion": True,
                    "checkpoint_on_failure": True,
                    # checkpoint_on_cancellation intentionally missing
                },
                "backtesting": {
                    "checkpoint_interval_seconds": 300,
                    "force_checkpoint_every_n": 5000,
                    "delete_on_completion": True,
                    "checkpoint_on_failure": True,
                    # checkpoint_on_cancellation intentionally missing
                },
            }
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp_file:
            yaml.dump(config_content, tmp_file)
            tmp_path = Path(tmp_file.name)

        try:
            policies = load_checkpoint_policies(tmp_path)

            # Should default to False for backward compatibility
            assert policies["training"].checkpoint_on_cancellation is False
            assert policies["backtesting"].checkpoint_on_cancellation is False
        finally:
            tmp_path.unlink()

    def test_policy_validation_unchanged(self):
        """Test that existing validation still works with new field."""
        # Valid policy should pass
        policy = CheckpointPolicy(
            checkpoint_interval_seconds=300,
            force_checkpoint_every_n=50,
            delete_on_completion=True,
            checkpoint_on_failure=True,
            checkpoint_on_cancellation=True,
        )
        # Should not raise

        # Invalid checkpoint_interval_seconds should fail
        with pytest.raises(ValueError, match="checkpoint_interval_seconds must be positive"):
            CheckpointPolicy(
                checkpoint_interval_seconds=-10,
                force_checkpoint_every_n=50,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )

        # Invalid force_checkpoint_every_n should fail
        with pytest.raises(ValueError, match="force_checkpoint_every_n must be positive"):
            CheckpointPolicy(
                checkpoint_interval_seconds=300,
                force_checkpoint_every_n=0,
                delete_on_completion=True,
                checkpoint_on_failure=True,
                checkpoint_on_cancellation=True,
            )
