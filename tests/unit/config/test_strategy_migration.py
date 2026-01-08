"""Tests for v2 to v3 strategy migration."""

from ktrdr.config.strategy_migration import migrate_v2_to_v3, validate_migration


class TestMigrateV2ToV3:
    """Tests for migrate_v2_to_v3 function."""

    def test_converts_indicator_list_to_dict(self):
        """Indicators list should be converted to dict with feature_id as key."""
        v2_config = {
            "name": "test",
            "version": "2.0",
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14},
                {
                    "name": "bbands",
                    "feature_id": "bbands_20",
                    "period": 20,
                    "multiplier": 2.0,
                },
            ],
            "fuzzy_sets": {},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert isinstance(v3_config["indicators"], dict)
        assert "rsi_14" in v3_config["indicators"]
        assert "bbands_20" in v3_config["indicators"]
        assert v3_config["indicators"]["rsi_14"]["type"] == "rsi"
        assert v3_config["indicators"]["rsi_14"]["period"] == 14
        assert v3_config["indicators"]["bbands_20"]["type"] == "bbands"
        assert v3_config["indicators"]["bbands_20"]["period"] == 20
        assert v3_config["indicators"]["bbands_20"]["multiplier"] == 2.0

    def test_preserves_all_indicator_parameters(self):
        """All indicator parameters should be preserved during migration."""
        v2_config = {
            "name": "test",
            "indicators": [
                {
                    "name": "macd",
                    "feature_id": "macd_custom",
                    "fast_period": 8,
                    "slow_period": 21,
                    "signal_period": 5,
                    "custom_param": "value",
                }
            ],
            "fuzzy_sets": {},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        indicator = v3_config["indicators"]["macd_custom"]
        assert indicator["type"] == "macd"
        assert indicator["fast_period"] == 8
        assert indicator["slow_period"] == 21
        assert indicator["signal_period"] == 5
        assert indicator["custom_param"] == "value"
        # feature_id should NOT be in the dict value (it's the key)
        assert "feature_id" not in indicator
        # name should NOT be in the dict value (it's 'type')
        assert "name" not in indicator

    def test_adds_indicator_field_to_fuzzy_sets(self):
        """Each fuzzy set should get an 'indicator' field if missing."""
        v2_config = {
            "name": "test",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                    "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
                }
            },
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert v3_config["fuzzy_sets"]["rsi_14"]["indicator"] == "rsi_14"

    def test_preserves_existing_indicator_field(self):
        """If fuzzy set already has indicator field, preserve it."""
        v2_config = {
            "name": "test",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {
                "momentum": {
                    "indicator": "rsi_14",  # Already specified
                    "low": {"type": "triangular", "parameters": [0, 30, 50]},
                }
            },
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert v3_config["fuzzy_sets"]["momentum"]["indicator"] == "rsi_14"

    def test_generates_nn_inputs_when_missing(self):
        """nn_inputs should be generated from fuzzy_sets when missing."""
        v2_config = {
            "name": "test",
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14},
                {"name": "bbands", "feature_id": "bbands_20", "period": 20},
            ],
            "fuzzy_sets": {
                "rsi_14": {"oversold": [0, 20, 35], "overbought": [65, 80, 100]},
                "bbands_20": {"low": [0, 0.2, 0.4], "high": [0.6, 0.8, 1.0]},
            },
            "training_data": {"timeframes": {"list": ["5m", "1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert "nn_inputs" in v3_config
        assert len(v3_config["nn_inputs"]) == 2  # One per fuzzy_set

        # Verify structure
        fuzzy_set_ids = {inp["fuzzy_set"] for inp in v3_config["nn_inputs"]}
        assert fuzzy_set_ids == {"rsi_14", "bbands_20"}

        # All should have timeframes: 'all'
        for inp in v3_config["nn_inputs"]:
            assert inp["timeframes"] == "all"

    def test_preserves_existing_nn_inputs(self):
        """If nn_inputs already exists, don't overwrite it."""
        existing_nn_inputs = [
            {"fuzzy_set": "rsi_14", "timeframes": ["1h"]},
        ]
        v2_config = {
            "name": "test",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {"rsi_14": {"oversold": [0, 20, 35]}},
            "nn_inputs": existing_nn_inputs,
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert v3_config["nn_inputs"] == existing_nn_inputs

    def test_updates_version_to_3_0(self):
        """Version should be updated to 3.0."""
        v2_config = {
            "name": "test",
            "version": "2.0",
            "indicators": [],
            "fuzzy_sets": {},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert v3_config["version"] == "3.0"

    def test_handles_empty_fuzzy_sets(self):
        """Migration should handle empty fuzzy_sets gracefully."""
        v2_config = {
            "name": "test",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert v3_config["fuzzy_sets"] == {}
        assert v3_config["nn_inputs"] == []

    def test_handles_indicator_without_feature_id(self):
        """If feature_id is missing, fall back to name as the key."""
        v2_config = {
            "name": "test",
            "indicators": [
                {"name": "rsi", "period": 14},  # No feature_id
            ],
            "fuzzy_sets": {},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        assert "rsi" in v3_config["indicators"]
        assert v3_config["indicators"]["rsi"]["type"] == "rsi"

    def test_preserves_all_other_sections(self):
        """All non-indicator sections should be preserved."""
        v2_config = {
            "name": "test_strategy",
            "description": "A test strategy",
            "version": "2.0",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {"rsi_14": {"oversold": [0, 20, 35]}},
            "training_data": {
                "symbols": {"mode": "single_symbol", "list": ["EURUSD"]},
                "timeframes": {"mode": "multi_timeframe", "list": ["5m", "1h"]},
                "history_required": 100,
            },
            "model": {"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
            "decisions": {"output_format": "classification"},
            "training": {"method": "supervised", "labels": {"source": "zigzag"}},
            "risk_management": {"max_position_size": 0.1},
            "backtesting": {"initial_capital": 10000},
        }

        v3_config = migrate_v2_to_v3(v2_config)

        # These should be unchanged
        assert v3_config["name"] == "test_strategy"
        assert v3_config["description"] == "A test strategy"
        assert v3_config["training_data"] == v2_config["training_data"]
        assert v3_config["model"] == v2_config["model"]
        assert v3_config["decisions"] == v2_config["decisions"]
        assert v3_config["training"] == v2_config["training"]
        assert v3_config["risk_management"] == v2_config["risk_management"]
        assert v3_config["backtesting"] == v2_config["backtesting"]

    def test_does_not_modify_original_config(self):
        """Migration should not modify the original config."""
        v2_config = {
            "name": "test",
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {"rsi_14": {"oversold": [0, 20, 35]}},
            "training_data": {"timeframes": {"list": ["1h"]}},
            "model": {},
            "decisions": {},
            "training": {},
        }
        original_indicators = v2_config["indicators"].copy()

        migrate_v2_to_v3(v2_config)

        # Original should be unchanged
        assert v2_config["indicators"] == original_indicators
        assert isinstance(v2_config["indicators"], list)


class TestValidateMigration:
    """Tests for validate_migration function."""

    def test_returns_empty_list_on_valid_migration(self):
        """No issues should be reported for valid migration."""
        original = {
            "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
            "fuzzy_sets": {"rsi_14": {"oversold": [0, 20, 35]}},
        }
        migrated = {
            "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
            "fuzzy_sets": {"rsi_14": {"indicator": "rsi_14", "oversold": [0, 20, 35]}},
        }

        issues = validate_migration(original, migrated)

        assert issues == []

    def test_reports_indicator_count_mismatch(self):
        """Report if indicator count changed during migration."""
        original = {
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14"},
                {"name": "macd", "feature_id": "macd_default"},
            ],
            "fuzzy_sets": {},
        }
        migrated = {
            "indicators": {"rsi_14": {"type": "rsi"}},  # Missing one
            "fuzzy_sets": {},
        }

        issues = validate_migration(original, migrated)

        # Enhanced validation reports count mismatch AND specific missing indicator
        assert len(issues) == 2
        assert any("Indicator count changed: 2 -> 1" in issue for issue in issues)
        assert any("macd_default" in issue and "missing" in issue for issue in issues)

    def test_reports_fuzzy_set_count_mismatch(self):
        """Report if fuzzy set count changed during migration."""
        original = {
            "indicators": [],
            "fuzzy_sets": {"rsi_14": {}, "macd_default": {}},
        }
        migrated = {
            "indicators": {},
            "fuzzy_sets": {"rsi_14": {}},  # Missing one
        }

        issues = validate_migration(original, migrated)

        # Enhanced validation reports count mismatch AND specific missing fuzzy set
        assert len(issues) == 2
        assert any("Fuzzy set count changed: 2 -> 1" in issue for issue in issues)
        assert any("macd_default" in issue for issue in issues)

    def test_handles_missing_sections(self):
        """Handle configs with missing indicators/fuzzy_sets sections."""
        original = {"name": "test"}  # No indicators or fuzzy_sets
        migrated = {"name": "test", "indicators": {}, "fuzzy_sets": {}}

        issues = validate_migration(original, migrated)

        # Should handle gracefully without errors
        assert isinstance(issues, list)
