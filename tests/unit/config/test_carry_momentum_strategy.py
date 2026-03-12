"""Unit tests for eurusd_carry_momentum_v1 strategy validation (M9 Task 9.4).

Tests that the multi-source context strategy:
1. Loads and parses as valid v3 YAML
2. Contains all 3 context data entries (FRED, IB, CFTC)
3. Indicator data_source references resolve to context source IDs
4. Fuzzy sets reference valid indicators
5. nn_inputs reference valid fuzzy sets
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

STRATEGY_PATH = Path("strategies/eurusd_carry_momentum_v1.yaml")


class TestCarryMomentumStrategyParsing:
    """Test that the strategy YAML loads and has correct structure."""

    @pytest.fixture
    def strategy(self) -> dict:
        """Load the strategy YAML."""
        assert STRATEGY_PATH.exists(), f"Strategy file not found: {STRATEGY_PATH}"
        with open(STRATEGY_PATH) as f:
            return yaml.safe_load(f)

    def test_strategy_loads(self, strategy: dict) -> None:
        assert strategy["name"] == "eurusd_carry_momentum_v1"
        assert strategy["version"] == "3.0"

    def test_has_context_data(self, strategy: dict) -> None:
        """Strategy must have context_data with 3 providers."""
        assert "context_data" in strategy
        providers = [e["provider"] for e in strategy["context_data"]]
        assert "ib" in providers
        assert "fred" in providers
        assert "cftc_cot" in providers
        assert len(strategy["context_data"]) == 3

    def test_ib_context_entry(self, strategy: dict) -> None:
        ib_entry = [e for e in strategy["context_data"] if e["provider"] == "ib"][0]
        assert ib_entry["symbol"] == "GBPUSD"
        assert ib_entry["timeframe"] == "1h"

    def test_fred_context_entry(self, strategy: dict) -> None:
        fred_entry = [e for e in strategy["context_data"] if e["provider"] == "fred"][0]
        assert fred_entry["series"] == ["DGS2", "IRLTLT01DEM156N"]

    def test_cftc_context_entry(self, strategy: dict) -> None:
        cftc_entry = [
            e for e in strategy["context_data"] if e["provider"] == "cftc_cot"
        ][0]
        assert cftc_entry["report"] == "EUR"

    def test_indicators_have_data_source(self, strategy: dict) -> None:
        """Context-aware indicators must have data_source field."""
        indicators = strategy["indicators"]
        # Primary — no data_source
        assert "data_source" not in indicators["rsi_14"]
        # Context — must have data_source
        assert indicators["gbp_rsi_14"]["data_source"] == "GBPUSD"
        assert (
            indicators["yield_spread_rsi"]["data_source"]
            == "yield_spread_DGS2_IRLTLT01DEM156N"
        )
        assert indicators["cot_percentile_ema"]["data_source"] == "cot_EUR_net_pct"

    def test_fuzzy_sets_reference_valid_indicators(self, strategy: dict) -> None:
        """Each fuzzy set must reference an indicator that exists."""
        indicators = set(strategy["indicators"].keys())
        for fs_name, fs_def in strategy["fuzzy_sets"].items():
            indicator_ref = fs_def["indicator"]
            assert (
                indicator_ref in indicators
            ), f"Fuzzy set '{fs_name}' references unknown indicator '{indicator_ref}'"

    def test_nn_inputs_reference_valid_fuzzy_sets(self, strategy: dict) -> None:
        """Each nn_input must reference a fuzzy set that exists."""
        fuzzy_sets = set(strategy["fuzzy_sets"].keys())
        for inp in strategy["nn_inputs"]:
            assert (
                inp["fuzzy_set"] in fuzzy_sets
            ), f"nn_input references unknown fuzzy set '{inp['fuzzy_set']}'"

    def test_all_four_fuzzy_sets_in_inputs(self, strategy: dict) -> None:
        """All 4 fuzzy sets should be used in nn_inputs."""
        input_sets = {inp["fuzzy_set"] for inp in strategy["nn_inputs"]}
        expected = {"rsi_momentum", "gbp_momentum", "carry_direction", "positioning"}
        assert input_sets == expected


class TestCarryMomentumStrategyV3Parsing:
    """Test that the strategy loads as a valid StrategyConfigurationV3."""

    def test_loads_as_v3_config(self) -> None:
        """Strategy should parse into StrategyConfigurationV3 without errors."""
        from ktrdr.config.strategy_loader import StrategyConfigurationLoader

        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(str(STRATEGY_PATH))

        assert config.name == "eurusd_carry_momentum_v1"
        assert config.context_data is not None
        assert len(config.context_data) == 3
        assert len(config.indicators) == 4
        assert len(config.fuzzy_sets) == 4
        assert len(config.nn_inputs) == 4

    def test_context_data_entries_are_typed(self) -> None:
        """Context data entries should be ContextDataEntry instances."""
        from ktrdr.config.models import ContextDataEntry
        from ktrdr.config.strategy_loader import StrategyConfigurationLoader

        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(str(STRATEGY_PATH))

        for entry in config.context_data:
            assert isinstance(entry, ContextDataEntry)

    def test_data_source_indicators_marked(self) -> None:
        """Indicators with data_source should have it in model_extra."""
        from ktrdr.config.strategy_loader import StrategyConfigurationLoader

        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(str(STRATEGY_PATH))

        # gbp_rsi_14 should have data_source
        gbp_rsi = config.indicators["gbp_rsi_14"]
        assert gbp_rsi.model_extra.get("data_source") == "GBPUSD"

        # rsi_14 should NOT have data_source
        rsi = config.indicators["rsi_14"]
        assert rsi.model_extra is None or rsi.model_extra.get("data_source") is None
