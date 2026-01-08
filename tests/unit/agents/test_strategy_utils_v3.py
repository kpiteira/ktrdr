"""Tests for v3 strategy utilities.

Validates that agent utility functions:
1. Parse YAML from markdown code blocks
2. Validate v3 structure
3. Reject v2 structure with clear error
4. Extract features correctly
"""

from pydantic import ValidationError

# Sample v3 config for testing
V3_CONFIG = {
    "name": "test_v3",
    "version": "3.0",
    "training_data": {
        "symbols": {"mode": "single", "list": ["EURUSD"]},
        "timeframes": {"mode": "single", "list": ["1h"], "base_timeframe": "1h"},
        "history_required": 100,
    },
    "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
    "fuzzy_sets": {
        "rsi_momentum": {
            "indicator": "rsi_14",
            "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
            "overbought": {"type": "triangular", "parameters": [65, 80, 100]},
        }
    },
    "nn_inputs": [{"fuzzy_set": "rsi_momentum", "timeframes": "all"}],
    "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
    "decisions": {"output_format": "classification"},
    "training": {"method": "supervised", "labels": {"source": "zigzag"}},
}

# Sample v2 config (list indicators, no nn_inputs)
V2_CONFIG = {
    "name": "test_v2",
    "indicators": [{"name": "rsi", "feature_id": "rsi_14", "period": 14}],
    "fuzzy_sets": {
        "rsi_14": {
            "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
        }
    },
}


class TestParseStrategyResponse:
    """Test parse_strategy_response function."""

    def test_parses_yaml_from_code_block(self):
        """Should extract YAML from ```yaml code block."""
        from ktrdr.agents.strategy_utils import parse_strategy_response

        response = """Here's a strategy:

```yaml
name: test_strategy
version: "3.0"
indicators:
  rsi_14:
    type: rsi
    period: 14
```

This strategy uses RSI."""

        result = parse_strategy_response(response)

        assert result["name"] == "test_strategy"
        assert result["version"] == "3.0"
        assert "rsi_14" in result["indicators"]

    def test_parses_yaml_from_generic_code_block(self):
        """Should extract YAML from generic ``` code block."""
        from ktrdr.agents.strategy_utils import parse_strategy_response

        response = """```
name: test_strategy
version: "3.0"
```"""

        result = parse_strategy_response(response)
        assert result["name"] == "test_strategy"

    def test_parses_raw_yaml(self):
        """Should parse raw YAML without code blocks."""
        from ktrdr.agents.strategy_utils import parse_strategy_response

        response = """name: test_strategy
version: "3.0"
indicators:
  rsi_14:
    type: rsi"""

        result = parse_strategy_response(response)
        assert result["name"] == "test_strategy"

    def test_handles_empty_response(self):
        """Should return empty dict for empty response."""
        from ktrdr.agents.strategy_utils import parse_strategy_response

        result = parse_strategy_response("")
        assert result == {}


class TestValidateAgentStrategy:
    """Test validate_agent_strategy function."""

    def test_validates_v3_config(self):
        """Should validate correct v3 config."""
        from ktrdr.agents.strategy_utils import validate_agent_strategy

        is_valid, messages = validate_agent_strategy(V3_CONFIG)

        assert is_valid is True
        # May have warnings but no errors blocking validation

    def test_rejects_v2_config_with_list_indicators(self):
        """Should reject v2 config where indicators is a list."""
        from ktrdr.agents.strategy_utils import validate_agent_strategy

        is_valid, messages = validate_agent_strategy(V2_CONFIG)

        assert is_valid is False
        # Should mention that indicators must be a dict
        assert any("dict" in m.lower() for m in messages)

    def test_rejects_config_without_nn_inputs(self):
        """Should reject config missing nn_inputs."""
        from ktrdr.agents.strategy_utils import validate_agent_strategy

        config_no_nn_inputs = {
            "name": "test",
            "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
            "fuzzy_sets": {},
        }

        is_valid, messages = validate_agent_strategy(config_no_nn_inputs)

        assert is_valid is False
        assert any("nn_inputs" in m.lower() for m in messages)

    def test_returns_error_messages_for_invalid_config(self):
        """Should return helpful error messages."""
        from ktrdr.agents.strategy_utils import validate_agent_strategy

        is_valid, messages = validate_agent_strategy(V2_CONFIG)

        assert is_valid is False
        assert len(messages) > 0
        # Messages should be strings
        assert all(isinstance(m, str) for m in messages)


class TestExtractFeatures:
    """Test extract_features function."""

    def test_extracts_features_from_v3_config(self):
        """Should extract resolved feature IDs from v3 config."""
        from ktrdr.agents.strategy_utils import extract_features

        features = extract_features(V3_CONFIG)

        # Should have 2 features: oversold and overbought for the single timeframe
        assert len(features) == 2
        assert "1h_rsi_momentum_oversold" in features
        assert "1h_rsi_momentum_overbought" in features

    def test_extracts_features_with_multiple_fuzzy_sets(self):
        """Should extract features from multiple fuzzy sets."""
        from ktrdr.agents.strategy_utils import extract_features

        config = {
            "name": "test",
            "version": "3.0",
            "training_data": {
                "symbols": {"mode": "single", "list": ["EURUSD"]},
                "timeframes": {
                    "mode": "single",
                    "list": ["1h"],
                    "base_timeframe": "1h",
                },
                "history_required": 100,
            },
            "indicators": {
                "rsi_14": {"type": "rsi", "period": 14},
                "macd_12_26_9": {
                    "type": "macd",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
            },
            "fuzzy_sets": {
                "rsi_momentum": {
                    "indicator": "rsi_14",
                    "low": {"type": "triangular", "parameters": [0, 30, 50]},
                    "high": {"type": "triangular", "parameters": [50, 70, 100]},
                },
                "macd_trend": {
                    "indicator": "macd_12_26_9.histogram",
                    "negative": {"type": "triangular", "parameters": [-50, -10, 0]},
                    "positive": {"type": "triangular", "parameters": [0, 10, 50]},
                },
            },
            "nn_inputs": [
                {"fuzzy_set": "rsi_momentum", "timeframes": "all"},
                {"fuzzy_set": "macd_trend", "timeframes": "all"},
            ],
            "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
            "decisions": {"output_format": "classification"},
            "training": {"method": "supervised", "labels": {"source": "zigzag"}},
        }

        features = extract_features(config)

        # 2 fuzzy sets × 2 membership functions each = 4 features
        assert len(features) == 4
        assert "1h_rsi_momentum_low" in features
        assert "1h_rsi_momentum_high" in features
        assert "1h_macd_trend_negative" in features
        assert "1h_macd_trend_positive" in features

    def test_raises_for_invalid_config(self):
        """Should raise ValidationError for invalid config."""
        import pytest

        from ktrdr.agents.strategy_utils import extract_features

        with pytest.raises(ValidationError):
            extract_features(V2_CONFIG)
