"""Tests for v1.5 strategy template structure."""

from pathlib import Path

import pytest
import yaml

TEMPLATE_PATH = Path("strategies/v15_template.yaml")

# Fixed parameters that must be identical across all v1.5 strategies
FIXED_PARAMS = {
    "training_data.symbols.list": ["EURUSD"],
    "training_data.timeframes.list": ["1h"],
    "training_data.timeframes.base_timeframe": "1h",
    "training_data.history_required": 200,
    "model.architecture.hidden_layers": [64, 32],
    "model.architecture.activation": "relu",
    "model.architecture.output_activation": "softmax",
    "model.architecture.dropout": 0.2,
    "model.features.include_price_context": False,
    "model.features.lookback_periods": 2,
    "model.features.scale_features": True,
    "model.training.learning_rate": 0.001,
    "model.training.batch_size": 32,
    "model.training.epochs": 100,
    "model.training.optimizer": "adam",
    "model.training.early_stopping.enabled": True,
    "model.training.early_stopping.patience": 15,
    "model.training.early_stopping.min_delta": 0.001,
    "model.training.analytics.enabled": True,
    "training.method": "supervised",
    "training.labels.source": "zigzag",
    "training.labels.zigzag_threshold": 0.025,
    "training.labels.label_lookahead": 20,
    "training.data_split.train": 0.7,
    "training.data_split.validation": 0.15,
    "training.data_split.test": 0.15,
    "training.date_range.start": "2015-01-01",
    "training.date_range.end": "2023-12-31",
}


def get_nested_value(config: dict, path: str):
    """Get a nested value from config using dot notation."""
    keys = path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


class TestV15Template:
    """Tests for the v1.5 strategy template."""

    @pytest.fixture
    def template(self) -> dict:
        """Load the template file."""
        assert TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}"
        with open(TEMPLATE_PATH) as f:
            return yaml.safe_load(f)

    def test_template_exists(self):
        """Template file must exist."""
        assert TEMPLATE_PATH.exists(), f"Template file not found: {TEMPLATE_PATH}"

    def test_template_is_valid_yaml(self, template):
        """Template must be valid YAML."""
        assert isinstance(template, dict), "Template must parse to a dictionary"

    def test_has_required_sections(self, template):
        """Template must have all required top-level sections."""
        required = [
            "name",
            "description",
            "version",
            "training_data",
            "indicators",
            "fuzzy_sets",
            "model",
            "training",
        ]
        for section in required:
            assert section in template, f"Missing required section: {section}"

    def test_fixed_parameters_are_correct(self, template):
        """All fixed parameters must have the specified values."""
        for path, expected in FIXED_PARAMS.items():
            actual = get_nested_value(template, path)
            assert actual == expected, (
                f"Fixed parameter '{path}' has wrong value. "
                f"Expected: {expected}, Got: {actual}"
            )

    def test_has_placeholder_indicators(self, template):
        """Template should have placeholder indicator section."""
        assert "indicators" in template
        # The template should have some indicator defined (even if placeholder)
        # to show the correct structure
        assert isinstance(template["indicators"], list)

    def test_has_placeholder_fuzzy_sets(self, template):
        """Template should have placeholder fuzzy sets section."""
        assert "fuzzy_sets" in template
        assert isinstance(template["fuzzy_sets"], dict)

    def test_name_has_v15_prefix(self, template):
        """Template name should follow v15 naming convention."""
        name = template.get("name", "")
        assert name.startswith("v15_"), f"Name should start with 'v15_': {name}"

    def test_analytics_fully_enabled(self, template):
        """Analytics must be fully enabled for experiment tracking."""
        analytics = get_nested_value(template, "model.training.analytics")
        assert analytics is not None, "Analytics config missing"
        assert analytics.get("enabled") is True
        assert analytics.get("export_csv") is True
        assert analytics.get("export_json") is True
        assert analytics.get("export_alerts") is True

    def test_pure_fuzzy_features(self, template):
        """Template must use pure fuzzy features (no price context)."""
        include_price = get_nested_value(
            template, "model.features.include_price_context"
        )
        assert (
            include_price is False
        ), "include_price_context must be False for pure fuzzy"


# =============================================================================
# Tests for all 27 v1.5 strategies
# =============================================================================

# Expected strategy files (27 total)
EXPECTED_STRATEGIES = [
    # Single indicator (9)
    "v15_rsi_only",
    "v15_stochastic_only",
    "v15_williams_only",
    "v15_mfi_only",
    "v15_adx_only",
    "v15_aroon_only",
    "v15_cmf_only",
    "v15_rvi_only",
    "v15_di_only",
    # Two indicator (11)
    "v15_rsi_adx",
    "v15_rsi_stochastic",
    "v15_rsi_williams",
    "v15_rsi_mfi",
    "v15_adx_aroon",
    "v15_adx_di",
    "v15_stochastic_williams",
    "v15_mfi_cmf",
    "v15_rsi_cmf",
    "v15_adx_rsi",
    "v15_aroon_rvi",
    # Three indicator (3)
    "v15_rsi_adx_stochastic",
    "v15_mfi_adx_aroon",
    "v15_williams_stochastic_cmf",
    # Zigzag variations (4)
    "v15_rsi_zigzag_1.5",
    "v15_rsi_zigzag_2.0",
    "v15_rsi_zigzag_3.0",
    "v15_rsi_zigzag_3.5",
]

# Tier 2/3 indicators that must NOT appear
FORBIDDEN_INDICATORS = [
    "atr",
    "macd",
    "cci",
    "obv",
    "vwap",
    "momentum",
    "bollinger",
    "keltner",
    "ichimoku",
    "supertrend",
    "parabolic",
]

# Zigzag threshold expectations
ZIGZAG_THRESHOLDS = {
    "v15_rsi_zigzag_1.5": 0.015,
    "v15_rsi_zigzag_2.0": 0.020,
    "v15_rsi_zigzag_3.0": 0.030,
    "v15_rsi_zigzag_3.5": 0.035,
}

# Fixed params for strategies (excludes zigzag_threshold which varies for Z01-Z04)
FIXED_PARAMS_STRATEGIES = {
    k: v for k, v in FIXED_PARAMS.items() if k != "training.labels.zigzag_threshold"
}


class TestV15Strategies:
    """Tests for all 27 v1.5 experiment strategies."""

    @pytest.fixture
    def all_strategies(self) -> dict[str, dict]:
        """Load all v15 strategy files."""
        strategies = {}
        for name in EXPECTED_STRATEGIES:
            path = Path(f"strategies/{name}.yaml")
            if path.exists():
                with open(path) as f:
                    strategies[name] = yaml.safe_load(f)
        return strategies

    def test_all_27_strategies_exist(self):
        """All 27 strategy files must exist."""
        missing = []
        for name in EXPECTED_STRATEGIES:
            path = Path(f"strategies/{name}.yaml")
            if not path.exists():
                missing.append(name)
        assert not missing, f"Missing strategy files: {missing}"

    def test_all_strategies_valid_yaml(self, all_strategies):
        """All strategies must be valid YAML."""
        assert (
            len(all_strategies) == 27
        ), f"Expected 27 strategies, found {len(all_strategies)}"
        for name, config in all_strategies.items():
            assert isinstance(config, dict), f"{name} must parse to a dictionary"

    def test_all_strategies_have_v15_name(self, all_strategies):
        """All strategy names must start with v15_."""
        for name, config in all_strategies.items():
            actual_name = config.get("name", "")
            assert actual_name.startswith(
                "v15_"
            ), f"{name}: name should start with 'v15_', got '{actual_name}'"

    def test_all_strategies_have_required_sections(self, all_strategies):
        """All strategies must have required sections."""
        required = [
            "name",
            "description",
            "version",
            "training_data",
            "indicators",
            "fuzzy_sets",
            "model",
            "training",
        ]
        for name, config in all_strategies.items():
            for section in required:
                assert section in config, f"{name}: missing section '{section}'"

    def test_fixed_parameters_consistent(self, all_strategies):
        """Fixed parameters must be identical across all strategies."""
        for name, config in all_strategies.items():
            for path, expected in FIXED_PARAMS_STRATEGIES.items():
                actual = get_nested_value(config, path)
                assert actual == expected, (
                    f"{name}: fixed param '{path}' has wrong value. "
                    f"Expected: {expected}, Got: {actual}"
                )

    def test_no_forbidden_indicators(self, all_strategies):
        """No Tier 2/3 indicators should be used."""
        for name, config in all_strategies.items():
            indicators = config.get("indicators", [])
            for ind in indicators:
                ind_name = ind.get("name", "").lower()
                for forbidden in FORBIDDEN_INDICATORS:
                    assert (
                        forbidden not in ind_name
                    ), f"{name}: uses forbidden indicator '{ind_name}'"

    def test_zigzag_thresholds_correct(self, all_strategies):
        """Zigzag variations must have correct thresholds."""
        for name, expected_threshold in ZIGZAG_THRESHOLDS.items():
            if name in all_strategies:
                config = all_strategies[name]
                actual = get_nested_value(config, "training.labels.zigzag_threshold")
                assert actual == expected_threshold, (
                    f"{name}: zigzag_threshold should be {expected_threshold}, "
                    f"got {actual}"
                )

    def test_baseline_strategies_use_default_zigzag(self, all_strategies):
        """Non-zigzag-variation strategies must use 2.5% threshold."""
        for name, config in all_strategies.items():
            if name not in ZIGZAG_THRESHOLDS:
                actual = get_nested_value(config, "training.labels.zigzag_threshold")
                assert (
                    actual == 0.025
                ), f"{name}: should use default 2.5% threshold, got {actual}"

    def test_all_strategies_have_indicators(self, all_strategies):
        """All strategies must have at least one indicator."""
        for name, config in all_strategies.items():
            indicators = config.get("indicators", [])
            assert len(indicators) >= 1, f"{name}: must have at least one indicator"

    def test_all_strategies_have_fuzzy_sets(self, all_strategies):
        """All strategies must have fuzzy sets matching their indicators."""
        for name, config in all_strategies.items():
            indicators = config.get("indicators", [])
            fuzzy_sets = config.get("fuzzy_sets", {})
            for ind in indicators:
                feature_id = ind.get("feature_id")
                if feature_id:
                    # Handle indicators that produce multiple features
                    # ADX produces: ADX_14, DI_Plus_14, DI_Minus_14
                    # Aroon produces: aroon_up_25, aroon_down_25
                    if ind.get("name") == "adx":
                        # v15_di_only uses ADX indicator but only wants DI outputs
                        # ADX indicator produces DI_Plus_14 and DI_Minus_14 column names
                        if name == "v15_di_only":
                            assert (
                                "DI_Plus_14" in fuzzy_sets
                            ), f"{name}: missing fuzzy set for DI_Plus_14"
                            assert (
                                "DI_Minus_14" in fuzzy_sets
                            ), f"{name}: missing fuzzy set for DI_Minus_14"
                        else:
                            # Other ADX strategies need adx_14 (lowercase in most strategy files)
                            # Note: v15_adx_di uses ADX_14 but validator accepts both
                            assert (
                                "adx_14" in fuzzy_sets or "ADX_14" in fuzzy_sets
                            ), f"{name}: missing fuzzy set for adx_14 or ADX_14"
                    elif ind.get("name") == "aroon":
                        # Aroon indicator - check both up and down
                        assert (
                            "aroon_up_25" in fuzzy_sets
                        ), f"{name}: missing fuzzy set for aroon_up_25"
                        assert (
                            "aroon_down_25" in fuzzy_sets
                        ), f"{name}: missing fuzzy set for aroon_down_25"
                    else:
                        assert (
                            feature_id in fuzzy_sets
                        ), f"{name}: missing fuzzy set for {feature_id}"

    def test_analytics_enabled_all_strategies(self, all_strategies):
        """Analytics must be enabled for all strategies."""
        for name, config in all_strategies.items():
            analytics = get_nested_value(config, "model.training.analytics")
            assert analytics is not None, f"{name}: analytics config missing"
            assert (
                analytics.get("enabled") is True
            ), f"{name}: analytics.enabled must be True"
