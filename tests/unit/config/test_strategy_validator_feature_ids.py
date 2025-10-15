"""
Unit tests for StrategyValidator feature_id validation (Task 1.3).

Tests cover:
- Indicator definitions validation (feature_id presence, format, uniqueness)
- Indicator-to-fuzzy matching validation (strict)
- Error messages and suggestions
"""

from ktrdr.config.strategy_validator import StrategyValidator


class TestIndicatorDefinitionsValidation:
    """Test _validate_indicator_definitions() method."""

    def test_valid_indicator_definitions(self, tmp_path):
        """Valid indicator definitions should pass validation."""
        strategy_yaml = """
name: test_strategy
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
    params:
      period: 14
  - name: macd
    feature_id: macd_standard
    params:
      fast_period: 12
      slow_period: 26
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
    neutral: {type: triangle, parameters: [20, 50, 80]}
    overbought: {type: trapezoid, parameters: [70, 80, 100, 100]}
  macd_standard:
    bearish: {type: trapezoid, parameters: [-10, -10, -2, 0]}
    neutral: {type: triangle, parameters: [-2, 0, 2]}
    bullish: {type: trapezoid, parameters: [0, 2, 10, 10]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "valid_strategy.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert result.is_valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0

    def test_missing_feature_id_rejected(self, tmp_path):
        """Indicators missing feature_id should fail Pydantic validation."""
        strategy_yaml = """
name: test_strategy
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
    params:
      period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "missing_feature_id.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any("feature_id" in err.lower() for err in result.errors)

    def test_invalid_feature_id_format_rejected(self, tmp_path):
        """Invalid feature_id format should fail Pydantic validation."""
        strategy_yaml = """
name: test_strategy
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
    feature_id: "123_invalid"
    params:
      period: 14
fuzzy_sets:
  "123_invalid":
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "invalid_format.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "letter" in err.lower() or "format" in err.lower() for err in result.errors
        )

    def test_reserved_word_feature_id_rejected(self, tmp_path):
        """Reserved word feature_ids should fail Pydantic validation."""
        strategy_yaml = """
name: test_strategy
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
    feature_id: "close"
    params:
      period: 14
fuzzy_sets:
  close:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "reserved_word.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any("reserved" in err.lower() for err in result.errors)

    def test_duplicate_feature_ids_rejected(self, tmp_path):
        """Duplicate feature_ids should fail validation."""
        strategy_yaml = """
name: test_strategy
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
    params:
      period: 14
  - name: rsi
    feature_id: rsi_14
    params:
      period: 21
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "duplicate_feature_ids.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        assert any(
            "duplicate" in err.lower() or "rsi_14" in err for err in result.errors
        )


class TestIndicatorFuzzyMatchingValidation:
    """Test _validate_indicator_fuzzy_matching() method."""

    def test_perfect_match_passes(self, tmp_path):
        """All indicators have matching fuzzy_sets - should pass."""
        strategy_yaml = """
name: test_strategy
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
    params: {period: 14}
  - name: macd
    feature_id: macd_standard
    params: {}
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
  macd_standard:
    bearish: {type: trapezoid, parameters: [-10, -10, -2, 0]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "perfect_match.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert result.is_valid, f"Errors: {result.errors}"

    def test_missing_fuzzy_sets_error(self, tmp_path):
        """Indicators without fuzzy_sets should produce STRICT error."""
        strategy_yaml = """
name: test_strategy
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
    params: {period: 14}
  - name: macd
    feature_id: macd_standard
    params: {}
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
  # macd_standard is missing!
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "missing_fuzzy.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        # Should mention missing fuzzy_sets for macd_standard
        assert any("macd_standard" in err for err in result.errors)
        assert any("fuzzy" in err.lower() for err in result.errors)

    def test_orphaned_fuzzy_sets_warning(self, tmp_path):
        """Fuzzy sets without indicators should produce WARNING (not error)."""
        strategy_yaml = """
name: test_strategy
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
    params: {period: 14}
fuzzy_sets:
  rsi_14:
    oversold: {type: trapezoid, parameters: [0, 0, 20, 30]}
  derived_feature:  # Orphaned - might be intentional
    high: {type: trapezoid, parameters: [0, 0, 0.5, 1]}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "orphaned_fuzzy.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        # Should be valid (warnings only)
        assert result.is_valid, f"Errors: {result.errors}"
        # Should have warning about orphaned fuzzy_set
        assert any("derived_feature" in warn for warn in result.warnings)

    def test_error_message_includes_suggestions(self, tmp_path):
        """Error for missing fuzzy_sets should include helpful suggestions."""
        strategy_yaml = """
name: test_strategy
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
    feature_id: rsi_fast
    params: {period: 7}
fuzzy_sets: {}  # Empty - missing rsi_fast
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "missing_with_suggestion.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        # Should suggest adding fuzzy_sets
        assert len(result.suggestions) > 0
        # Suggestion should mention the missing feature_id
        assert any("rsi_fast" in sugg for sugg in result.suggestions)


class TestValidationErrorMessages:
    """Test quality of validation error messages."""

    def test_error_includes_feature_id(self, tmp_path):
        """Error messages should include the specific feature_id."""
        strategy_yaml = """
name: test_strategy
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
    feature_id: my_rsi
    params: {period: 14}
fuzzy_sets: {}
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "error_detail.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        # Error should mention specific feature_id
        assert any("my_rsi" in err for err in result.errors)

    def test_multiple_missing_fuzzy_sets_all_reported(self, tmp_path):
        """All missing fuzzy_sets should be reported, not just the first."""
        strategy_yaml = """
name: test_strategy
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
    params: {period: 14}
  - name: macd
    feature_id: macd_std
    params: {}
  - name: ema
    feature_id: ema_20
    params: {period: 20}
fuzzy_sets: {}  # All missing
model:
  type: mlp
  architecture: {hidden_layers: [20, 10], activation: relu}
  training: {learning_rate: 0.001, batch_size: 32, epochs: 100}
  features: {include_price_context: true}
decisions:
  output_format: classification
  confidence_threshold: 0.6
  position_awareness: true
training:
  method: supervised
  labels: {type: zigzag, parameters: {threshold_pct: 3.0}}
  data_split: {train: 0.7, validation: 0.15, test: 0.15}
"""
        config_path = tmp_path / "multiple_missing.yaml"
        config_path.write_text(strategy_yaml)

        validator = StrategyValidator()
        result = validator.validate_strategy(str(config_path))

        assert not result.is_valid
        # Should report all missing feature_ids
        errors_str = " ".join(result.errors + result.suggestions)
        assert "rsi_14" in errors_str
        assert "macd_std" in errors_str
        assert "ema_20" in errors_str
