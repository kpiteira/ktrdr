"""
Tests for the indicator naming migration script.

Tests the migration from legacy format (type field) to explicit naming (indicator + name).
"""

# We'll import the migration functions after they're created
# from scripts.migrate_indicator_naming import migrate_strategy_file, migrate_indicator_config


class TestIndicatorConfigMigration:
    """Test migration of individual indicator configurations."""

    def test_migrate_simple_rsi(self):
        """Test migrating a simple RSI indicator."""
        from scripts.migrate_indicator_naming import migrate_indicator_config

        legacy_config = {"type": "rsi", "params": {"period": 14}}

        migrated = migrate_indicator_config(legacy_config)

        assert migrated["indicator"] == "rsi"
        assert migrated["name"] == "rsi_14"
        assert migrated["period"] == 14
        assert "type" not in migrated
        assert "params" not in migrated

    def test_migrate_macd_with_multiple_params(self):
        """Test migrating MACD with multiple parameters."""
        from scripts.migrate_indicator_naming import migrate_indicator_config

        legacy_config = {
            "type": "macd",
            "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        }

        migrated = migrate_indicator_config(legacy_config)

        assert migrated["indicator"] == "macd"
        assert migrated["name"] == "macd_12_26_9"
        assert migrated["fast_period"] == 12
        assert migrated["slow_period"] == 26
        assert migrated["signal_period"] == 9

    def test_migrate_indicator_with_source(self):
        """Test that source parameter is included but not in name."""
        from scripts.migrate_indicator_naming import migrate_indicator_config

        legacy_config = {"type": "ema", "params": {"period": 20, "source": "close"}}

        migrated = migrate_indicator_config(legacy_config)

        assert migrated["indicator"] == "ema"
        assert migrated["name"] == "ema_20"  # source not in name
        assert migrated["period"] == 20
        assert migrated["source"] == "close"

    def test_migrate_already_migrated_indicator(self):
        """Test that already-migrated indicators are left unchanged."""
        from scripts.migrate_indicator_naming import migrate_indicator_config

        new_config = {"indicator": "rsi", "name": "rsi_custom", "period": 14}

        migrated = migrate_indicator_config(new_config)

        # Should be identical (already in new format)
        assert migrated == new_config

    def test_migrate_bollinger_bands(self):
        """Test migrating Bollinger Bands with float parameters."""
        from scripts.migrate_indicator_naming import migrate_indicator_config

        legacy_config = {
            "type": "bbands",
            "params": {"period": 20, "std_dev": 2.0},
        }

        migrated = migrate_indicator_config(legacy_config)

        assert migrated["indicator"] == "bbands"
        # Should handle float formatting
        assert migrated["name"] in ["bbands_20_2", "bbands_20_2.0"]
        assert migrated["period"] == 20
        assert migrated["std_dev"] == 2.0


class TestStrategyFileMigration:
    """Test migration of complete strategy YAML files."""

    def test_migrate_simple_strategy_file(self, tmp_path):
        """Test migrating a simple strategy file."""
        import yaml

        from scripts.migrate_indicator_naming import migrate_strategy_file

        # Create legacy strategy file
        legacy_content = """
name: Test Strategy
version: 1.0.0
scope: universal

training_data:
  symbols:
    mode: single
    symbol: AAPL
  timeframes:
    mode: single
    timeframe: 1d

deployment:
  target_symbols:
    mode: universal
  target_timeframes:
    mode: single
    timeframe: 1d

indicators:
  - type: rsi
    params:
      period: 14
  - type: macd
    params:
      fast_period: 12
      slow_period: 26
      signal_period: 9

fuzzy_sets:
  rsi_14:
    oversold: [0, 20, 40]
  macd_12_26_9:
    bullish: [0, 10, 50]

model:
  type: mlp

decisions:
  rules: []

training:
  epochs: 10
"""

        strategy_file = tmp_path / "legacy_strategy.yaml"
        strategy_file.write_text(legacy_content)

        # Migrate
        output_file = tmp_path / "migrated_strategy.yaml"
        result = migrate_strategy_file(strategy_file, output_file)

        assert result is True
        assert output_file.exists()

        # Load migrated file
        with open(output_file) as f:
            migrated = yaml.safe_load(f)

        # Check indicators migrated
        assert len(migrated["indicators"]) == 2
        assert migrated["indicators"][0]["indicator"] == "rsi"
        assert migrated["indicators"][0]["name"] == "rsi_14"
        assert migrated["indicators"][1]["indicator"] == "macd"
        assert migrated["indicators"][1]["name"] == "macd_12_26_9"

    def test_migrate_with_dry_run(self, tmp_path):
        """Test dry-run mode doesn't write files."""

        from scripts.migrate_indicator_naming import migrate_strategy_file

        legacy_content = """
indicators:
  - type: rsi
    params:
      period: 14
"""

        strategy_file = tmp_path / "strategy.yaml"
        strategy_file.write_text(legacy_content)

        output_file = tmp_path / "output.yaml"

        # Dry run
        result = migrate_strategy_file(strategy_file, output_file, dry_run=True)

        assert result is True
        assert not output_file.exists()  # File should NOT be created

    def test_migrate_already_migrated_file(self, tmp_path):
        """Test that already-migrated files are detected."""

        from scripts.migrate_indicator_naming import migrate_strategy_file

        new_content = """
indicators:
  - indicator: rsi
    name: rsi_14
    period: 14
"""

        strategy_file = tmp_path / "new_strategy.yaml"
        strategy_file.write_text(new_content)

        output_file = tmp_path / "output.yaml"

        # Should detect it's already migrated
        result = migrate_strategy_file(strategy_file, output_file)

        # Result should be False (no migration needed)
        assert result is False

    def test_migrate_file_without_indicators(self, tmp_path):
        """Test handling files without indicators section."""

        from scripts.migrate_indicator_naming import migrate_strategy_file

        content = """
name: Test Strategy
model:
  type: mlp
"""

        strategy_file = tmp_path / "no_indicators.yaml"
        strategy_file.write_text(content)

        output_file = tmp_path / "output.yaml"

        # Should handle gracefully
        result = migrate_strategy_file(strategy_file, output_file)

        # No migration needed (no indicators)
        assert result is False

    def test_migrate_preserves_other_fields(self, tmp_path):
        """Test that migration preserves all other strategy fields."""
        import yaml

        from scripts.migrate_indicator_naming import migrate_strategy_file

        legacy_content = """
name: Test Strategy
description: A test strategy
version: 1.0.0

indicators:
  - type: rsi
    params:
      period: 14

fuzzy_sets:
  test: {}

model:
  type: mlp
  layers: [64, 32]

decisions:
  rules:
    - condition: test
      action: buy

training:
  epochs: 100
  batch_size: 32

custom_field: custom_value
"""

        strategy_file = tmp_path / "full_strategy.yaml"
        strategy_file.write_text(legacy_content)

        output_file = tmp_path / "migrated.yaml"
        migrate_strategy_file(strategy_file, output_file)

        with open(output_file) as f:
            migrated = yaml.safe_load(f)

        # Check preserved fields
        assert migrated["name"] == "Test Strategy"
        assert migrated["description"] == "A test strategy"
        assert migrated["version"] == "1.0.0"
        assert migrated["model"]["layers"] == [64, 32]
        assert migrated["training"]["batch_size"] == 32
        assert migrated["custom_field"] == "custom_value"


class TestNameGeneration:
    """Test auto-generated name logic."""

    def test_generate_name_for_rsi(self):
        """Test name generation for RSI."""
        from scripts.migrate_indicator_naming import generate_indicator_name

        name = generate_indicator_name("rsi", {"period": 14})
        assert name == "rsi_14"

    def test_generate_name_for_macd(self):
        """Test name generation for MACD."""
        from scripts.migrate_indicator_naming import generate_indicator_name

        name = generate_indicator_name(
            "macd", {"fast_period": 12, "slow_period": 26, "signal_period": 9}
        )
        assert name == "macd_12_26_9"

    def test_generate_name_excludes_source(self):
        """Test that source parameter is excluded from name."""
        from scripts.migrate_indicator_naming import generate_indicator_name

        name = generate_indicator_name("ema", {"period": 20, "source": "close"})
        assert name == "ema_20"
        assert "close" not in name

    def test_generate_name_with_float(self):
        """Test name generation with float parameter."""
        from scripts.migrate_indicator_naming import generate_indicator_name

        name = generate_indicator_name("bbands", {"period": 20, "std_dev": 2.0})
        # Should handle float (either 2 or 2.0 is acceptable)
        assert "bbands_20" in name
        assert "2" in name

    def test_generate_name_lowercase(self):
        """Test that generated names are lowercase."""
        from scripts.migrate_indicator_naming import generate_indicator_name

        name = generate_indicator_name("RSI", {"period": 14})
        assert name == "rsi_14"
        assert name.islower()
