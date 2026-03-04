"""Tests for get_recent_strategies MCP tool.

Tests the get_recent_strategies business logic:
1. Returns strategies sorted by date (most recent first)
2. Respects limit parameter
3. Includes indicator summary per strategy
4. Empty result when no strategies exist
5. Includes assessment outcome when available
"""

import json
import time
from pathlib import Path

import pytest

from ktrdr.mcp.strategy_service import get_recent_strategies

# Minimal valid v3 strategy YAML with RSI
V3_STRATEGY_A = """
name: strategy_a
description: Strategy A
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

# V3 strategy with MACD
V3_STRATEGY_B = """
name: strategy_b
description: Strategy B with MACD
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
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  macd_signal:
    indicator: macd_12_26_9.line
    bullish:
      type: triangular
      parameters: [-0.5, 0, 0.5]
    bearish:
      type: triangular
      parameters: [-0.5, 0, 0.5]

nn_inputs:
  - fuzzy_set: macd_signal
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


class TestGetRecentStrategies:
    """Tests for get_recent_strategies business logic."""

    @pytest.fixture
    def strategies_dir(self, tmp_path):
        """Create a temporary strategies directory with some strategies."""
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        return strat_dir

    def _write_strategy(
        self, strategies_dir: Path, name: str, yaml_content: str
    ) -> Path:
        """Write a strategy YAML file."""
        path = strategies_dir / f"{name}.yaml"
        path.write_text(yaml_content)
        return path

    @pytest.mark.asyncio
    async def test_empty_directory_returns_empty_list(self, strategies_dir):
        """No strategies → empty list."""
        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_strategies_with_names(self, strategies_dir):
        """Returns strategy names from YAML files."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        self._write_strategy(strategies_dir, "strategy_b", V3_STRATEGY_B)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        names = [s["name"] for s in result]
        assert "strategy_a" in names
        assert "strategy_b" in names

    @pytest.mark.asyncio
    async def test_sorted_by_modification_date_newest_first(self, strategies_dir):
        """Strategies should be sorted by modification date, newest first."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        time.sleep(0.05)  # Ensure different mtime
        self._write_strategy(strategies_dir, "strategy_b", V3_STRATEGY_B)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert len(result) == 2
        assert result[0]["name"] == "strategy_b"  # Newer
        assert result[1]["name"] == "strategy_a"  # Older

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, strategies_dir):
        """Limit parameter caps the number of results."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        time.sleep(0.05)
        self._write_strategy(strategies_dir, "strategy_b", V3_STRATEGY_B)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
            limit=1,
        )

        assert len(result) == 1
        assert result[0]["name"] == "strategy_b"  # Most recent

    @pytest.mark.asyncio
    async def test_includes_indicator_names(self, strategies_dir):
        """Each strategy should include indicator type names."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert len(result) == 1
        assert "indicators" in result[0]
        assert "rsi_14" in result[0]["indicators"]

    @pytest.mark.asyncio
    async def test_includes_created_date(self, strategies_dir):
        """Each strategy should include a creation/modification date."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert "created_date" in result[0]
        assert result[0]["created_date"] is not None

    @pytest.mark.asyncio
    async def test_includes_assessment_when_available(self, strategies_dir):
        """When an assessment file exists, include the verdict."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)

        # Create assessment file
        assessment = {
            "strategy_name": "strategy_a",
            "verdict": "promising",
            "strengths": ["good"],
            "weaknesses": ["ok"],
        }
        assessment_path = strategies_dir / "strategy_a_assessment.json"
        assessment_path.write_text(json.dumps(assessment))

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert result[0]["assessment_verdict"] == "promising"

    @pytest.mark.asyncio
    async def test_no_assessment_returns_none_verdict(self, strategies_dir):
        """When no assessment file exists, verdict should be None."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert result[0]["assessment_verdict"] is None

    @pytest.mark.asyncio
    async def test_skips_non_yaml_files(self, strategies_dir):
        """Non-YAML files should be ignored."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        (strategies_dir / "README.md").write_text("# Strategies")
        (strategies_dir / "notes.txt").write_text("some notes")

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert len(result) == 1
        assert result[0]["name"] == "strategy_a"

    @pytest.mark.asyncio
    async def test_skips_assessment_json_files(self, strategies_dir):
        """Assessment JSON files should not appear as strategies."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        (strategies_dir / "strategy_a_assessment.json").write_text("{}")

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_handles_invalid_yaml_gracefully(self, strategies_dir):
        """Invalid YAML files should be skipped, not crash."""
        self._write_strategy(strategies_dir, "strategy_a", V3_STRATEGY_A)
        (strategies_dir / "broken.yaml").write_text("invalid: yaml: [")

        result = await get_recent_strategies(
            strategies_dir=str(strategies_dir),
        )

        # Should still return the valid strategy
        names = [s["name"] for s in result]
        assert "strategy_a" in names
