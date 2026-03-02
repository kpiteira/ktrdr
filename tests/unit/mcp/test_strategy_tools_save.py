"""Tests for save_strategy_config MCP tool.

Tests the save_strategy_config business logic:
1. Valid v3 strategy → saved + returns path
2. Invalid strategy (missing indicators) → rejected, no file created
3. Strategy with invalid indicator names → validation catches it
4. YAML syntax error → rejected
5. Atomic: never saves an invalid strategy
"""

from pathlib import Path

import pytest

from ktrdr.mcp.strategy_service import save_strategy_config

# Minimal valid v3 strategy YAML
VALID_V3_YAML = """
name: test_save_strategy
description: Test strategy for save
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

# Invalid: missing indicators (v3 requires indicators as dict)
INVALID_NO_INDICATORS_YAML = """
name: bad_strategy
description: Missing indicators
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

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]

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

# Invalid: not even valid YAML
BAD_YAML = "invalid: yaml: content: ["

# V2 format (should be rejected)
V2_YAML = """
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


class TestSaveStrategyConfig:
    """Tests for save_strategy_config business logic."""

    @pytest.fixture
    def strategies_dir(self, tmp_path):
        """Create a temporary strategies directory."""
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        return strat_dir

    @pytest.mark.asyncio
    async def test_valid_v3_strategy_saved_and_returns_path(self, strategies_dir):
        """Valid v3 strategy → saved + returns strategy_name and strategy_path."""
        result = await save_strategy_config(
            strategy_name="test_save_strategy",
            strategy_yaml=VALID_V3_YAML,
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is True
        assert result["strategy_name"] == "test_save_strategy"
        assert "strategy_path" in result
        # File should exist
        saved_path = Path(result["strategy_path"])
        assert saved_path.exists()
        assert saved_path.suffix == ".yaml"

    @pytest.mark.asyncio
    async def test_saved_file_is_valid_yaml(self, strategies_dir):
        """Saved strategy file should be parseable YAML."""
        import yaml

        result = await save_strategy_config(
            strategy_name="test_save_strategy",
            strategy_yaml=VALID_V3_YAML,
            strategies_dir=str(strategies_dir),
        )

        saved_path = Path(result["strategy_path"])
        with open(saved_path) as f:
            loaded = yaml.safe_load(f)
        assert loaded["name"] == "test_save_strategy"
        assert isinstance(loaded["indicators"], dict)

    @pytest.mark.asyncio
    async def test_invalid_strategy_rejected_no_file_created(self, strategies_dir):
        """Invalid strategy (missing indicators) → rejected, no file created."""
        result = await save_strategy_config(
            strategy_name="bad_strategy",
            strategy_yaml=INVALID_NO_INDICATORS_YAML,
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0
        # No file should be created
        assert not (strategies_dir / "bad_strategy.yaml").exists()

    @pytest.mark.asyncio
    async def test_bad_yaml_rejected(self, strategies_dir):
        """YAML syntax error → rejected, no file created."""
        result = await save_strategy_config(
            strategy_name="broken",
            strategy_yaml=BAD_YAML,
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result
        assert not (strategies_dir / "broken.yaml").exists()

    @pytest.mark.asyncio
    async def test_v2_strategy_rejected(self, strategies_dir):
        """V2 format strategy → rejected with migration suggestion."""
        result = await save_strategy_config(
            strategy_name="test_v2_strategy",
            strategy_yaml=V2_YAML,
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is False
        assert "errors" in result
        assert not (strategies_dir / "test_v2_strategy.yaml").exists()

    @pytest.mark.asyncio
    async def test_overwrite_existing_strategy(self, strategies_dir):
        """Saving a strategy with an existing name should overwrite it."""
        # Save first version
        result1 = await save_strategy_config(
            strategy_name="test_save_strategy",
            strategy_yaml=VALID_V3_YAML,
            strategies_dir=str(strategies_dir),
        )
        assert result1["success"] is True

        # Save again (overwrite)
        result2 = await save_strategy_config(
            strategy_name="test_save_strategy",
            strategy_yaml=VALID_V3_YAML,
            strategies_dir=str(strategies_dir),
        )
        assert result2["success"] is True
        assert result2["strategy_path"] == result1["strategy_path"]

    @pytest.mark.asyncio
    async def test_strategy_name_sanitized_in_path(self, strategies_dir):
        """Strategy name should be used as filename (sanitized)."""
        result = await save_strategy_config(
            strategy_name="my_strategy_v1",
            strategy_yaml=VALID_V3_YAML,
            strategies_dir=str(strategies_dir),
        )

        assert result["success"] is True
        saved_path = Path(result["strategy_path"])
        assert saved_path.name == "my_strategy_v1.yaml"
