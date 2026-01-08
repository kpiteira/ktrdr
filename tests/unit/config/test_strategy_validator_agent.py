"""
Unit tests for StrategyValidator enhancements for agent use (Task 1.2).

Tests cover agent-specific validation requirements:
- Indicator type exists in KTRDR (BUILT_IN_INDICATORS)
- Fuzzy membership parameter validation (correct param counts)
- Duplicate strategy name detection
- Validation for agent-generated strategies (dict input, not file)

These tests follow TDD - written BEFORE implementation.
"""

from pathlib import Path

from ktrdr.config.strategy_validator import StrategyValidator


class TestIndicatorTypeValidation:
    """Test validation that indicator types exist in KTRDR."""

    def test_valid_indicator_types_pass(self, tmp_path):
        """Strategy with valid indicator types should pass validation."""
        strategy_yaml = """
name: test_valid_indicators
version: "1.0"
scope: universal
training_data:
  symbols:
    mode: single
    symbol: AAPL
  timeframes:
    mode: single
    timeframe: 1h
deployment:
  target_symbols:
    mode: universal
  target_timeframes:
    mode: single
    timeframe: 1h
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
    source: close
  - name: macd
    feature_id: macd_standard
    fast_period: 12
    slow_period: 26
    signal_period: 9
fuzzy_sets:
  rsi_14:
    oversold: {type: triangular, parameters: [0, 20, 35]}
    neutral: {type: triangular, parameters: [30, 50, 70]}
    overbought: {type: triangular, parameters: [65, 80, 100]}
  macd_standard:
    bearish: {type: triangular, parameters: [-5, -2, 0]}
    neutral: {type: triangular, parameters: [-1, 0, 1]}
    bullish: {type: triangular, parameters: [0, 2, 5]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "valid_indicators.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert result.is_valid, f"Errors: {result.errors}"

    def test_unknown_indicator_type_rejected(self, tmp_path):
        """Strategy with unknown indicator type should fail validation."""
        strategy_yaml = """
name: test_unknown_indicator
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: totally_fake_indicator
    feature_id: fake_indicator_1
    period: 14
fuzzy_sets:
  fake_indicator_1:
    low: {type: triangular, parameters: [0, 20, 40]}
    high: {type: triangular, parameters: [60, 80, 100]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "unknown_indicator.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "totally_fake_indicator" in err.lower()
            or "unknown indicator" in err.lower()
            for err in result.errors
        )

    def test_case_insensitive_indicator_type_match(self, tmp_path):
        """Indicator types should match case-insensitively (rsi, RSI, Rsi all valid)."""
        strategy_yaml = """
name: test_case_insensitive
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: RSI
    feature_id: rsi_upper
    period: 14
  - name: Macd
    feature_id: macd_mixed
    fast_period: 12
    slow_period: 26
fuzzy_sets:
  rsi_upper:
    low: {type: triangular, parameters: [0, 20, 40]}
    high: {type: triangular, parameters: [60, 80, 100]}
  macd_mixed:
    bearish: {type: triangular, parameters: [-5, -2, 0]}
    bullish: {type: triangular, parameters: [0, 2, 5]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "case_insensitive.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        # Should pass - RSI and Macd should match built-in indicators
        assert result.is_valid, f"Errors: {result.errors}"

    def test_indicator_type_error_message_suggests_alternatives(self, tmp_path):
        """Error for unknown indicator should suggest similar valid indicators."""
        strategy_yaml = """
name: test_typo_suggestion
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsii
    feature_id: rsii_14
    period: 14
fuzzy_sets:
  rsii_14:
    low: {type: triangular, parameters: [0, 20, 40]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "typo_indicator.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        # Should suggest 'rsi' as alternative to 'rsii'
        combined = " ".join(result.errors + result.suggestions)
        assert "rsi" in combined.lower()


class TestFuzzyMembershipParameterValidation:
    """Test validation of fuzzy membership function parameters."""

    def test_triangular_three_params_valid(self, tmp_path):
        """Triangular membership with 3 parameters should be valid."""
        strategy_yaml = """
name: test_triangular_valid
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: triangular, parameters: [0, 20, 35]}
    neutral: {type: triangular, parameters: [30, 50, 70]}
    overbought: {type: triangular, parameters: [65, 80, 100]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "triangular_valid.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert result.is_valid, f"Errors: {result.errors}"

    def test_triangular_wrong_param_count_rejected(self, tmp_path):
        """Triangular membership with wrong number of parameters should fail."""
        strategy_yaml = """
name: test_triangular_wrong_params
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: triangular, parameters: [0, 20]}
    neutral: {type: triangular, parameters: [30, 50, 70]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "triangular_wrong.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "triangular" in err.lower()
            or "3 parameters" in err.lower()
            or "oversold" in err
            for err in result.errors
        )

    def test_trapezoid_four_params_valid(self, tmp_path):
        """Trapezoid membership with 4 parameters should be valid."""
        strategy_yaml = """
name: test_trapezoid_valid
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 35]}
    overbought: {type: trapezoid, parameters: [65, 80, 100, 100]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "trapezoid_valid.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert result.is_valid, f"Errors: {result.errors}"

    def test_trapezoid_wrong_param_count_rejected(self, tmp_path):
        """Trapezoid membership with wrong number of parameters should fail."""
        strategy_yaml = """
name: test_trapezoid_wrong_params
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 20, 35]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "trapezoid_wrong.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "trapezoid" in err.lower() or "4 parameters" in err.lower()
            for err in result.errors
        )

    def test_unknown_fuzzy_type_rejected(self, tmp_path):
        """Unknown fuzzy membership type should fail validation."""
        strategy_yaml = """
name: test_unknown_fuzzy_type
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: sigmoid_custom, parameters: [0, 20]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "unknown_fuzzy_type.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "sigmoid_custom" in err.lower()
            or "unknown" in err.lower()
            or "fuzzy type" in err.lower()
            for err in result.errors
        )


class TestDuplicateStrategyNameValidation:
    """Test validation for duplicate strategy names."""

    def test_unique_strategy_name_passes(self):
        """Unique strategy name should pass validation."""
        validator = StrategyValidator()

        # Use a name we know doesn't exist
        unique_name = "unique_test_strategy_that_definitely_does_not_exist_12345"
        strategies_dir = Path("strategies")

        result = validator.check_strategy_name_unique(unique_name, strategies_dir)

        assert result.is_valid, f"Errors: {result.errors}"

    def test_duplicate_strategy_name_rejected(self):
        """Duplicate strategy name should fail validation."""
        validator = StrategyValidator()

        # Use a v3 strategy name we know exists
        existing_name = "v3_minimal"
        strategies_dir = Path("strategies")

        result = validator.check_strategy_name_unique(existing_name, strategies_dir)

        assert not result.is_valid
        assert any(
            "v3_minimal" in err or "already exists" in err.lower()
            for err in result.errors
        )

    def test_duplicate_check_handles_yaml_extension(self):
        """Duplicate check should work with or without .yaml extension."""
        validator = StrategyValidator()

        # Check with .yaml extension - use existing v3 strategy
        name_with_ext = "v3_minimal.yaml"
        strategies_dir = Path("strategies")

        result = validator.check_strategy_name_unique(name_with_ext, strategies_dir)

        assert not result.is_valid

    def test_duplicate_check_handles_missing_directory(self):
        """Duplicate check should handle missing strategies directory gracefully."""
        validator = StrategyValidator()

        # Use non-existent directory
        result = validator.check_strategy_name_unique(
            "any_name", Path("/nonexistent/path/that/does/not/exist")
        )

        # Should pass (can't be duplicate if directory doesn't exist)
        assert result.is_valid


class TestValidateStrategyConfig:
    """Test validate_strategy_config for agent-generated configs (dict input)."""

    def test_validate_strategy_config_valid_dict(self):
        """Valid strategy config dict should pass validation."""
        validator = StrategyValidator()

        config = {
            "name": "agent_generated_strategy_1",
            "version": "1.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "EURUSD"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": [
                {"name": "rsi", "feature_id": "rsi_14", "period": 14},
            ],
            "fuzzy_sets": {
                "rsi_14": {
                    "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                    "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                    "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
                }
            },
            "model": {
                "type": "mlp",
                "architecture": {
                    "hidden_layers": [32, 16],
                    "activation": "relu",
                    "output_activation": "softmax",
                    "dropout": 0.2,
                },
                "training": {
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "epochs": 50,
                    "optimizer": "adam",
                },
                "features": {
                    "include_price_context": False,
                    "lookback_periods": 2,
                    "scale_features": True,
                },
            },
            "decisions": {
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
            },
            "training": {
                "method": "supervised",
                "labels": {
                    "source": "zigzag",
                    "zigzag_threshold": 0.03,
                    "label_lookahead": 20,
                },
                "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
            },
        }

        result = validator.validate_strategy_config(config)

        assert result.is_valid, f"Errors: {result.errors}"

    def test_validate_strategy_config_invalid_indicator(self):
        """Invalid indicator type in config dict should fail validation."""
        validator = StrategyValidator()

        config = {
            "name": "agent_bad_indicator",
            "version": "1.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "EURUSD"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": [
                {"name": "nonexistent_indicator", "feature_id": "bad_1", "period": 14},
            ],
            "fuzzy_sets": {
                "bad_1": {
                    "low": {"type": "triangular", "parameters": [0, 20, 40]},
                }
            },
            "model": {
                "type": "mlp",
                "architecture": {
                    "hidden_layers": [20, 10],
                    "activation": "relu",
                    "output_activation": "softmax",
                    "dropout": 0.2,
                },
                "training": {
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "epochs": 100,
                    "optimizer": "adam",
                },
                "features": {
                    "include_price_context": False,
                    "lookback_periods": 2,
                    "scale_features": True,
                },
            },
            "decisions": {
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
            },
            "training": {
                "method": "supervised",
                "labels": {
                    "source": "zigzag",
                    "zigzag_threshold": 0.03,
                    "label_lookahead": 20,
                },
                "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
            },
        }

        result = validator.validate_strategy_config(config)

        assert not result.is_valid
        assert any("nonexistent_indicator" in err.lower() for err in result.errors)


class TestAgentFriendlyErrorMessages:
    """Test that error messages are helpful for the agent to fix issues."""

    def test_error_messages_are_actionable(self, tmp_path):
        """Error messages should tell the agent HOW to fix the issue."""
        strategy_yaml = """
name: test_bad_config
version: "1.0"
scope: universal
training_data:
  symbols: {mode: single, symbol: AAPL}
  timeframes: {mode: single, timeframe: 1h}
deployment:
  target_symbols: {mode: universal}
  target_timeframes: {mode: single, timeframe: 1h}
indicators:
  - name: fake_indicator_xyz
    feature_id: fake_1
    period: 14
fuzzy_sets:
  fake_1:
    low: {type: wrong_type, parameters: [0, 20, 40, 60, 80]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu, output_activation: softmax, dropout: 0.2}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100, optimizer: adam}
  features: {include_price_context: false, lookback_periods: 2, scale_features: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {source: zigzag, zigzag_threshold: 0.03, label_lookahead: 20}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "bad_config.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid

        # Should include helpful info:
        # - The specific problematic value
        # - What valid values look like
        assert len(result.errors) > 0
        # Should have at least one suggestion for fixing
        # (This will pass once we implement helpful error messages)
