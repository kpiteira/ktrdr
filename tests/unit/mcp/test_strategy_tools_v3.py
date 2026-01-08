"""Tests for MCP strategy tools v3 integration.

These tests verify that the MCP strategy tools:
1. Can validate v3 strategies and return format info
2. Extract feature lists from v3 strategies
3. Provide clear guidance for v2 strategies (migration suggestion)

Note: These tests import the validate_strategy function directly from the
strategy_service module (which contains the business logic) rather than
through the MCP tool wrappers (which require FastMCP at import time).
"""

import tempfile
from pathlib import Path

import pytest

# Import the business logic function, not the MCP wrapper
from ktrdr.mcp.strategy_service import validate_strategy


class TestValidateStrategyV3:
    """Tests for validate_strategy MCP tool."""

    @pytest.fixture
    def v3_strategy_yaml(self) -> str:
        """A minimal valid v3 strategy YAML."""
        return """
name: test_v3_strategy
description: Test v3 strategy
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
"""

    @pytest.fixture
    def v2_strategy_yaml(self) -> str:
        """A v2 strategy YAML (indicators as list, no nn_inputs)."""
        return """
name: test_v2_strategy
description: Test v2 strategy
version: "2.0"
scope: universal

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: 1h
  history_required: 100

indicators:
  - type: rsi
    feature_id: rsi_14
    period: 14

fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
"""

    @pytest.mark.asyncio
    async def test_validate_v3_strategy_returns_valid_true(self, v3_strategy_yaml):
        """Validating a v3 strategy should return valid=True and format='v3'."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(v3_strategy_yaml.encode())
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert result["valid"] is True
            assert result["format"] == "v3"
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_validate_v3_strategy_returns_features(self, v3_strategy_yaml):
        """Validating a v3 strategy should return resolved features."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(v3_strategy_yaml.encode())
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert "features" in result
            assert isinstance(result["features"], list)
            assert len(result["features"]) >= 1
            # Should have feature IDs like "1h_rsi_momentum_oversold"
            assert any("rsi_momentum" in f for f in result["features"])
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_validate_v3_strategy_returns_feature_count(self, v3_strategy_yaml):
        """Validating a v3 strategy should return feature_count."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(v3_strategy_yaml.encode())
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert "feature_count" in result
            assert isinstance(result["feature_count"], int)
            assert result["feature_count"] >= 1
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_validate_v2_strategy_returns_v2_format(self, v2_strategy_yaml):
        """Validating a v2 strategy should return format='v2' and migration suggestion."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(v2_strategy_yaml.encode())
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert result["format"] == "v2"
            assert result["valid"] is False
            assert "errors" in result
            assert len(result["errors"]) > 0
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_validate_v2_strategy_suggests_migration(self, v2_strategy_yaml):
        """Validating a v2 strategy should suggest running migration command."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(v2_strategy_yaml.encode())
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert "suggestion" in result
            assert "migrate" in result["suggestion"].lower()
        finally:
            Path(path).unlink()

    @pytest.mark.asyncio
    async def test_validate_nonexistent_file_returns_error(self):
        """Validating a non-existent file should return an error."""
        result = await validate_strategy("/nonexistent/path/to/strategy.yaml")

        assert result["valid"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_invalid_yaml_returns_error(self):
        """Validating an invalid YAML file should return an error."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"invalid: yaml: content: [")
            f.flush()
            path = f.name

        try:
            result = await validate_strategy(path)

            assert result["valid"] is False
            assert "errors" in result
        finally:
            Path(path).unlink()
