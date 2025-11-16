"""
Unit tests for persistence configuration loading.

Tests verify that config/persistence.yaml:
- Exists and is valid YAML
- Has required structure (database, checkpointing sections)
- Has correct default values for checkpoint policies
- Loads without errors

These tests should FAIL until config/persistence.yaml is created.
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def config_path():
    """Return path to persistence.yaml config file."""
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "config" / "persistence.yaml"


def test_persistence_config_file_exists(config_path):
    """
    Test that config/persistence.yaml file exists.

    Acceptance Criteria:
    - ✅ persistence.yaml file exists in config directory
    """
    assert config_path.exists(), (
        f"persistence.yaml not found at {config_path}. " "Ensure file has been created."
    )

    assert config_path.is_file(), f"{config_path} is not a file"


def test_persistence_config_valid_yaml(config_path):
    """
    Test that persistence.yaml is valid YAML and loads without errors.

    Acceptance Criteria:
    - ✅ File is valid YAML syntax
    - ✅ Loads without parse errors
    """
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        pytest.fail(f"persistence.yaml is not valid YAML: {e}")
    except Exception as e:
        pytest.fail(f"Failed to load persistence.yaml: {e}")

    assert config is not None, "persistence.yaml is empty"
    assert isinstance(config, dict), "persistence.yaml should be a dictionary"


def test_persistence_config_has_database_section(config_path):
    """
    Test that persistence.yaml has database configuration section.

    Acceptance Criteria:
    - ✅ database section exists
    - ✅ database section has required fields (host, port, database, user, password)
    - ✅ database section has pool configuration
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert "database" in config, "persistence.yaml should have 'database' section"

    database = config["database"]
    assert isinstance(database, dict), "'database' section should be a dictionary"

    # Required connection fields (from architecture document)
    required_fields = ["host", "port", "database", "user", "password"]
    for field in required_fields:
        assert (
            field in database
        ), f"'database' section missing required field: '{field}'"

    # Connection pool configuration
    assert (
        "pool_size" in database or "pool" in database
    ), "'database' section should have connection pool configuration"

    # Timeout configuration
    assert (
        "pool_timeout" in database or "timeout" in database or "pool" in database
    ), "'database' section should have timeout configuration"


def test_persistence_config_has_checkpointing_section(config_path):
    """
    Test that persistence.yaml has checkpointing configuration section.

    Acceptance Criteria:
    - ✅ checkpointing section exists
    - ✅ Has training policy configuration
    - ✅ Has backtesting policy configuration
    - ✅ Has artifacts_dir configuration
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert (
        "checkpointing" in config
    ), "persistence.yaml should have 'checkpointing' section"

    checkpointing = config["checkpointing"]
    assert isinstance(
        checkpointing, dict
    ), "'checkpointing' section should be a dictionary"

    # Global checkpointing settings
    assert (
        "enabled" in checkpointing
    ), "'checkpointing' section should have 'enabled' flag"
    assert isinstance(checkpointing["enabled"], bool), "'enabled' should be a boolean"

    assert (
        "artifacts_dir" in checkpointing
    ), "'checkpointing' section should have 'artifacts_dir' path"

    # Training policy
    assert (
        "training" in checkpointing
    ), "'checkpointing' section should have 'training' policy"

    # Backtesting policy
    assert (
        "backtesting" in checkpointing
    ), "'checkpointing' section should have 'backtesting' policy"


def test_training_checkpoint_policy_structure(config_path):
    """
    Test that training checkpoint policy has correct structure.

    Acceptance Criteria:
    - ✅ Has checkpoint_interval_seconds (time-based checkpointing)
    - ✅ Has force_checkpoint_every_n (safety net)
    - ✅ Has delete_on_completion flag
    - ✅ Has checkpoint_on_failure flag
    - ✅ Default values are reasonable
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    training = config["checkpointing"]["training"]
    assert isinstance(training, dict), "'training' policy should be a dictionary"

    # Required fields (from architecture document - CheckpointPolicy dataclass)
    required_fields = [
        "checkpoint_interval_seconds",  # Time-based checkpointing
        "force_checkpoint_every_n",  # Safety net
        "delete_on_completion",  # Cleanup policy
        "checkpoint_on_failure",  # Failure handling
    ]

    for field in required_fields:
        assert field in training, f"'training' policy missing required field: '{field}'"

    # Validate types and reasonable defaults
    assert isinstance(
        training["checkpoint_interval_seconds"], (int, float)
    ), "'checkpoint_interval_seconds' should be numeric"
    assert (
        training["checkpoint_interval_seconds"] > 0
    ), "'checkpoint_interval_seconds' should be positive"
    # Architecture doc specifies 300 seconds (5 minutes) as default
    assert (
        training["checkpoint_interval_seconds"] >= 60
    ), "'checkpoint_interval_seconds' should be at least 60 seconds (1 minute)"

    assert isinstance(
        training["force_checkpoint_every_n"], int
    ), "'force_checkpoint_every_n' should be an integer"
    assert (
        training["force_checkpoint_every_n"] > 0
    ), "'force_checkpoint_every_n' should be positive"

    assert isinstance(
        training["delete_on_completion"], bool
    ), "'delete_on_completion' should be a boolean"

    assert isinstance(
        training["checkpoint_on_failure"], bool
    ), "'checkpoint_on_failure' should be a boolean"


def test_backtesting_checkpoint_policy_structure(config_path):
    """
    Test that backtesting checkpoint policy has correct structure.

    Acceptance Criteria:
    - ✅ Has checkpoint_interval_seconds (time-based checkpointing)
    - ✅ Has force_checkpoint_every_n (safety net)
    - ✅ Has delete_on_completion flag
    - ✅ Has checkpoint_on_failure flag
    - ✅ Default values are reasonable
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    backtesting = config["checkpointing"]["backtesting"]
    assert isinstance(backtesting, dict), "'backtesting' policy should be a dictionary"

    # Required fields (same as training, from CheckpointPolicy dataclass)
    required_fields = [
        "checkpoint_interval_seconds",
        "force_checkpoint_every_n",
        "delete_on_completion",
        "checkpoint_on_failure",
    ]

    for field in required_fields:
        assert (
            field in backtesting
        ), f"'backtesting' policy missing required field: '{field}'"

    # Validate types and reasonable defaults
    assert isinstance(
        backtesting["checkpoint_interval_seconds"], (int, float)
    ), "'checkpoint_interval_seconds' should be numeric"
    assert (
        backtesting["checkpoint_interval_seconds"] > 0
    ), "'checkpoint_interval_seconds' should be positive"

    assert isinstance(
        backtesting["force_checkpoint_every_n"], int
    ), "'force_checkpoint_every_n' should be an integer"
    assert (
        backtesting["force_checkpoint_every_n"] > 0
    ), "'force_checkpoint_every_n' should be positive"

    assert isinstance(
        backtesting["delete_on_completion"], bool
    ), "'delete_on_completion' should be a boolean"

    assert isinstance(
        backtesting["checkpoint_on_failure"], bool
    ), "'checkpoint_on_failure' should be a boolean"


def test_cleanup_policy_structure(config_path):
    """
    Test that cleanup policy has correct structure.

    Acceptance Criteria:
    - ✅ Has cleanup section
    - ✅ Has run_interval_hours (how often to run cleanup)
    - ✅ Has delete_old_checkpoints_days (30-day retention)
    - ✅ Has disk usage warning threshold
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    checkpointing = config["checkpointing"]

    assert (
        "cleanup" in checkpointing
    ), "'checkpointing' section should have 'cleanup' policy"

    cleanup = checkpointing["cleanup"]
    assert isinstance(cleanup, dict), "'cleanup' policy should be a dictionary"

    # Required fields (from architecture appendix)
    required_fields = [
        "run_interval_hours",  # How often to run cleanup job
        "delete_old_checkpoints_days",  # Age-based retention (30 days)
        "warn_disk_usage_percent",  # Disk usage warning threshold
    ]

    for field in required_fields:
        assert field in cleanup, f"'cleanup' policy missing required field: '{field}'"

    # Validate types and reasonable defaults
    assert isinstance(
        cleanup["run_interval_hours"], (int, float)
    ), "'run_interval_hours' should be numeric"
    assert cleanup["run_interval_hours"] > 0, "'run_interval_hours' should be positive"

    assert isinstance(
        cleanup["delete_old_checkpoints_days"], int
    ), "'delete_old_checkpoints_days' should be an integer"
    assert (
        cleanup["delete_old_checkpoints_days"] > 0
    ), "'delete_old_checkpoints_days' should be positive"
    # Architecture doc specifies 30 days
    assert (
        cleanup["delete_old_checkpoints_days"] >= 7
    ), "'delete_old_checkpoints_days' should be at least 7 days"

    assert isinstance(
        cleanup["warn_disk_usage_percent"], (int, float)
    ), "'warn_disk_usage_percent' should be numeric"
    assert (
        0 < cleanup["warn_disk_usage_percent"] <= 100
    ), "'warn_disk_usage_percent' should be between 0 and 100"


def test_config_default_values_match_architecture(config_path):
    """
    Test that default values match architecture document specifications.

    Acceptance Criteria:
    - ✅ Training checkpoint_interval_seconds = 300 (5 minutes)
    - ✅ Backtesting checkpoint_interval_seconds = 300 (5 minutes)
    - ✅ Training force_checkpoint_every_n = 50 epochs
    - ✅ Backtesting force_checkpoint_every_n = 5000 bars
    - ✅ Cleanup delete_old_checkpoints_days = 30
    - ✅ Cleanup run_interval_hours = 24 (daily)
    - ✅ Cleanup warn_disk_usage_percent = 80%
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Values from Appendix A: Configuration Reference in architecture doc
    training = config["checkpointing"]["training"]
    backtesting = config["checkpointing"]["backtesting"]
    cleanup = config["checkpointing"]["cleanup"]

    # Checkpoint intervals (5 minutes for both)
    assert (
        training["checkpoint_interval_seconds"] == 300
    ), "Training checkpoint interval should be 300 seconds (5 minutes) per architecture doc"
    assert (
        backtesting["checkpoint_interval_seconds"] == 300
    ), "Backtesting checkpoint interval should be 300 seconds (5 minutes) per architecture doc"

    # Force checkpoint boundaries
    assert (
        training["force_checkpoint_every_n"] == 50
    ), "Training force checkpoint should be every 50 epochs per architecture doc"
    assert (
        backtesting["force_checkpoint_every_n"] == 5000
    ), "Backtesting force checkpoint should be every 5000 bars per architecture doc"

    # Delete on completion (both should be true)
    assert (
        training["delete_on_completion"] is True
    ), "Training should delete checkpoints on completion"
    assert (
        backtesting["delete_on_completion"] is True
    ), "Backtesting should delete checkpoints on completion"

    # Checkpoint on failure (both should be true)
    assert (
        training["checkpoint_on_failure"] is True
    ), "Training should checkpoint on failure"
    assert (
        backtesting["checkpoint_on_failure"] is True
    ), "Backtesting should checkpoint on failure"

    # Cleanup policy
    assert (
        cleanup["run_interval_hours"] == 24
    ), "Cleanup should run every 24 hours (daily) per architecture doc"
    assert (
        cleanup["delete_old_checkpoints_days"] == 30
    ), "Should delete checkpoints older than 30 days per architecture doc"
    assert (
        cleanup["warn_disk_usage_percent"] == 80
    ), "Should warn at 80% disk usage per architecture doc"
