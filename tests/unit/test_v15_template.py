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
