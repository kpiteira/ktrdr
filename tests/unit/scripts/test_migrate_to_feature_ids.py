"""
Unit tests for feature_id migration tool.

This module tests the migration tool that converts old strategy configs
(without feature_id) to new format (with required feature_id).
"""

import pytest
import yaml

from scripts.migrate_to_feature_ids import (
    MigrationError,
    generate_feature_id_from_indicator,
    migrate_strategy_file,
    parse_args,
)


class TestFeatureIdGeneration:
    """Test feature_id generation from indicator configs."""

    def test_simple_rsi_generates_correct_feature_id(self):
        """Test RSI with period generates feature_id with period."""
        indicator_config = {"name": "rsi", "params": {"period": 14}}

        feature_id = generate_feature_id_from_indicator(indicator_config)

        assert feature_id == "rsi_14"

    def test_rsi_with_different_period(self):
        """Test RSI with different period generates correct feature_id."""
        indicator_config = {"name": "rsi", "params": {"period": 21}}

        feature_id = generate_feature_id_from_indicator(indicator_config)

        assert feature_id == "rsi_21"

    def test_ema_generates_correct_feature_id(self):
        """Test EMA generates feature_id (should exclude adjust param)."""
        indicator_config = {
            "name": "ema",
            "params": {"period": 20, "adjust": False, "source": "close"},
        }

        feature_id = generate_feature_id_from_indicator(indicator_config)

        # Should only include period, not adjust or source
        assert feature_id == "ema_20"

    def test_macd_generates_correct_feature_id(self):
        """Test MACD with multiple params generates correct feature_id."""
        indicator_config = {
            "name": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        }

        feature_id = generate_feature_id_from_indicator(indicator_config)

        # Should include all periods
        assert feature_id == "macd_12_26_9"

    def test_sma_generates_correct_feature_id(self):
        """Test SMA generates feature_id with period."""
        indicator_config = {"name": "sma", "params": {"period": 50}}

        feature_id = generate_feature_id_from_indicator(indicator_config)

        assert feature_id == "sma_50"

    def test_indicator_with_no_params_uses_type_only(self):
        """Test indicator with no params uses type name only."""
        indicator_config = {"name": "obv", "params": {}}

        feature_id = generate_feature_id_from_indicator(indicator_config)

        assert feature_id == "obv"

    def test_zigzag_custom_format(self):
        """Test ZigZag indicator with custom column name format."""
        indicator_config = {"name": "zigzag", "params": {"threshold": 0.05}}

        feature_id = generate_feature_id_from_indicator(indicator_config)

        # ZigZag uses custom format: ZigZag_{threshold * 100 as int}
        # threshold=0.05 (5%) -> ZigZag_5
        assert feature_id == "ZigZag_5"


class TestStrategyMigration:
    """Test full strategy file migration."""

    def test_migrate_simple_strategy_with_single_indicator(self, tmp_path):
        """Test migration of simple strategy with one indicator."""
        # Create old format strategy
        old_strategy = {
            "name": "Test Strategy",
            "version": "1.0",
            "indicators": [{"name": "rsi", "params": {"period": 14}}],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                    "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
                }
            },
            "model": {},
            "decisions": {},
            "training": {},
        }

        # Write to temp file
        strategy_file = tmp_path / "test_strategy.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        # Migrate
        result = migrate_strategy_file(str(strategy_file), dry_run=False)

        # Read migrated file
        with open(strategy_file) as f:
            migrated = yaml.safe_load(f)

        # Verify feature_id added
        assert "feature_id" in migrated["indicators"][0]
        assert migrated["indicators"][0]["feature_id"] == "rsi_14"

        # Verify fuzzy_sets unchanged (key already matches)
        assert "rsi_14" in migrated["fuzzy_sets"]

        # Verify result summary
        assert result["success"] is True
        assert result["changes"] == 1

    def test_migrate_strategy_with_multiple_indicators(self, tmp_path):
        """Test migration with multiple indicators."""
        old_strategy = {
            "name": "Multi Indicator Strategy",
            "version": "1.0",
            "indicators": [
                {"name": "rsi", "params": {"period": 14}},
                {"name": "rsi", "params": {"period": 21}},
                {"name": "ema", "params": {"period": 20}},
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": {}},
                "rsi_21": {"oversold": {}},
                "ema_20": {"below": {}},
            },
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "multi_indicator.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        result = migrate_strategy_file(str(strategy_file), dry_run=False)

        with open(strategy_file) as f:
            migrated = yaml.safe_load(f)

        # All indicators should have feature_ids
        assert migrated["indicators"][0]["feature_id"] == "rsi_14"
        assert migrated["indicators"][1]["feature_id"] == "rsi_21"
        assert migrated["indicators"][2]["feature_id"] == "ema_20"

        assert result["changes"] == 3

    def test_migrate_strategy_already_has_feature_ids(self, tmp_path):
        """Test that migration skips indicators that already have feature_ids."""
        new_strategy = {
            "name": "Already Migrated",
            "version": "1.0",
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "params": {"period": 14}}
            ],
            "fuzzy_sets": {"rsi_14": {}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "already_migrated.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(new_strategy, f)

        result = migrate_strategy_file(str(strategy_file), dry_run=False)

        # No changes should be made
        assert result["changes"] == 0
        assert result["success"] is True

    def test_migration_detects_duplicate_feature_ids(self, tmp_path):
        """Test that migration fails when duplicate feature_ids would be created."""
        # Two indicators with same params would create duplicate feature_ids
        old_strategy = {
            "name": "Duplicate Strategy",
            "version": "1.0",
            "indicators": [
                {"name": "rsi", "params": {"period": 14}},
                {"name": "rsi", "params": {"period": 14}},  # Duplicate!
            ],
            "fuzzy_sets": {"rsi_14": {}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "duplicate.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        # Should raise MigrationError
        with pytest.raises(MigrationError) as exc_info:
            migrate_strategy_file(str(strategy_file), dry_run=False)

        assert "duplicate feature_id" in str(exc_info.value).lower()
        assert "rsi_14" in str(exc_info.value)

    def test_dry_run_mode_does_not_modify_file(self, tmp_path):
        """Test that dry-run mode previews changes without modifying file."""
        old_strategy = {
            "name": "Dry Run Test",
            "version": "1.0",
            "indicators": [{"name": "rsi", "params": {"period": 14}}],
            "fuzzy_sets": {"rsi_14": {}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "dry_run.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        # Get original content
        with open(strategy_file) as f:
            original_content = f.read()

        # Run in dry-run mode
        result = migrate_strategy_file(str(strategy_file), dry_run=True)

        # Read file again
        with open(strategy_file) as f:
            after_content = f.read()

        # File should be unchanged
        assert original_content == after_content

        # But result should show what would change
        assert result["changes"] == 1
        assert result["dry_run"] is True

    def test_backup_mode_creates_backup_file(self, tmp_path):
        """Test that backup mode creates .bak file before migration."""
        old_strategy = {
            "name": "Backup Test",
            "version": "1.0",
            "indicators": [{"name": "rsi", "params": {"period": 14}}],
            "fuzzy_sets": {"rsi_14": {}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "backup_test.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        # Migrate with backup
        migrate_strategy_file(str(strategy_file), dry_run=False, backup=True)

        # Check backup file exists
        backup_file = tmp_path / "backup_test.yaml.bak"
        assert backup_file.exists()

        # Backup should have original content (no feature_id)
        with open(backup_file) as f:
            backup_content = yaml.safe_load(f)
        assert "feature_id" not in backup_content["indicators"][0]

        # Original file should have feature_id
        with open(strategy_file) as f:
            migrated_content = yaml.safe_load(f)
        assert migrated_content["indicators"][0]["feature_id"] == "rsi_14"

    def test_migration_handles_macd_multi_output(self, tmp_path):
        """Test migration correctly handles MACD multi-output indicator."""
        old_strategy = {
            "name": "MACD Strategy",
            "version": "1.0",
            "indicators": [
                {
                    "name": "macd",
                    "params": {
                        "fast_period": 12,
                        "slow_period": 26,
                        "signal_period": 9,
                    },
                }
            ],
            "fuzzy_sets": {
                # Current fuzzy sets reference main line (matches column name pattern)
                "macd_12_26_9": {
                    "bullish": {"type": "triangular", "parameters": [0, 5, 20]}
                }
            },
            "model": {},
            "decisions": {},
            "training": {},
        }

        strategy_file = tmp_path / "macd_strategy.yaml"
        with open(strategy_file, "w") as f:
            yaml.dump(old_strategy, f)

        result = migrate_strategy_file(str(strategy_file), dry_run=False)

        with open(strategy_file) as f:
            migrated = yaml.safe_load(f)

        # Should generate feature_id matching main line
        assert migrated["indicators"][0]["feature_id"] == "macd_12_26_9"
        assert result["success"] is True


class TestCLIInterface:
    """Test command-line interface argument parsing."""

    def test_parse_args_single_file(self):
        """Test parsing single file argument."""
        args = parse_args(["strategy.yaml"])

        assert args.files == ["strategy.yaml"]
        assert args.dry_run is False
        assert args.backup is False

    def test_parse_args_dry_run_flag(self):
        """Test --dry-run flag parsing."""
        args = parse_args(["strategy.yaml", "--dry-run"])

        assert args.dry_run is True

    def test_parse_args_backup_flag(self):
        """Test --backup flag parsing."""
        args = parse_args(["strategy.yaml", "--backup"])

        assert args.backup is True

    def test_parse_args_multiple_files(self):
        """Test multiple file arguments."""
        args = parse_args(["strategy1.yaml", "strategy2.yaml", "strategy3.yaml"])

        assert len(args.files) == 3
        assert "strategy1.yaml" in args.files

    def test_parse_args_glob_pattern(self):
        """Test parsing glob pattern (handled by shell, not argparse)."""
        # In real usage, shell expands "strategies/*.yaml"
        # argparse just sees the expanded list
        args = parse_args(["strategies/strat1.yaml", "strategies/strat2.yaml"])

        assert len(args.files) == 2
