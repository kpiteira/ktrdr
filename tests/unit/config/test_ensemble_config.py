"""Tests for ensemble configuration models."""

import textwrap
from pathlib import Path

import pytest
import yaml

from ktrdr.config.ensemble_config import (
    CompositionConfig,
    EnsembleConfiguration,
    ModelReference,
    RouteRule,
)

VALID_ENSEMBLE_YAML = textwrap.dedent(
    """\
    name: regime_routed_v1
    description: Regime-routed strategy with per-regime signal models

    models:
      regime:
        model_path: models/regime_classifier_v1
        output_type: regime_classification
      trend_long:
        model_path: models/trend_follower_long_v1
        output_type: classification
      trend_short:
        model_path: models/trend_follower_short_v1
        output_type: classification
      mean_reversion:
        model_path: models/range_trader_v1
        output_type: classification

    composition:
      type: regime_route
      gate_model: regime
      regime_threshold: 0.4
      stability_bars: 3
      rules:
        trending_up:
          model: trend_long
        trending_down:
          model: trend_short
        ranging:
          model: mean_reversion
        volatile:
          action: FLAT
      on_regime_transition: close_and_switch
"""
)


class TestModelReference:
    """Tests for ModelReference model."""

    def test_valid_model_reference(self) -> None:
        ref = ModelReference(
            name="regime",
            model_path="models/regime_v1",
            output_type="regime_classification",
        )
        assert ref.name == "regime"
        assert ref.model_path == "models/regime_v1"
        assert ref.output_type == "regime_classification"

    def test_output_type_values(self) -> None:
        for otype in ["classification", "regression", "regime_classification"]:
            ref = ModelReference(name="m", model_path="p", output_type=otype)
            assert ref.output_type == otype


class TestRouteRule:
    """Tests for RouteRule model."""

    def test_model_route(self) -> None:
        rule = RouteRule(model="trend_long")
        assert rule.model == "trend_long"
        assert rule.action is None

    def test_action_route(self) -> None:
        rule = RouteRule(action="FLAT")
        assert rule.action == "FLAT"
        assert rule.model is None

    def test_both_model_and_action_raises(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            RouteRule(model="trend_long", action="FLAT")

    def test_neither_model_nor_action_raises(self) -> None:
        with pytest.raises(ValueError, match="must specify"):
            RouteRule()


class TestCompositionConfig:
    """Tests for CompositionConfig model."""

    def test_valid_composition(self) -> None:
        config = CompositionConfig(
            type="regime_route",
            gate_model="regime",
            regime_threshold=0.4,
            stability_bars=3,
            rules={
                "trending_up": RouteRule(model="trend_long"),
                "volatile": RouteRule(action="FLAT"),
            },
            on_regime_transition="close_and_switch",
        )
        assert config.gate_model == "regime"
        assert config.regime_threshold == 0.4
        assert config.stability_bars == 3

    def test_defaults(self) -> None:
        config = CompositionConfig(
            type="regime_route",
            gate_model="regime",
            rules={"trending_up": RouteRule(model="m1")},
            on_regime_transition="close_and_switch",
        )
        assert config.regime_threshold == 0.4
        assert config.stability_bars == 3

    def test_invalid_transition_policy(self) -> None:
        with pytest.raises(ValueError):
            CompositionConfig(
                type="regime_route",
                gate_model="regime",
                rules={"trending_up": RouteRule(model="m1")},
                on_regime_transition="invalid_policy",
            )


class TestEnsembleConfiguration:
    """Tests for EnsembleConfiguration model."""

    def test_valid_ensemble_from_dict(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        config = EnsembleConfiguration.from_dict(data)
        assert config.name == "regime_routed_v1"
        assert len(config.models) == 4
        assert config.composition.gate_model == "regime"
        assert config.composition.on_regime_transition == "close_and_switch"

    def test_valid_ensemble_from_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "ensemble.yaml"
        yaml_file.write_text(VALID_ENSEMBLE_YAML)
        config = EnsembleConfiguration.from_yaml(yaml_file)
        assert config.name == "regime_routed_v1"
        assert len(config.models) == 4

    def test_missing_model_in_route_raises(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        # Reference a model that doesn't exist
        data["composition"]["rules"]["trending_up"]["model"] = "nonexistent_model"
        with pytest.raises(ValueError, match="nonexistent_model"):
            EnsembleConfiguration.from_dict(data)

    def test_missing_gate_model_raises(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        data["composition"]["gate_model"] = "nonexistent_gate"
        with pytest.raises(ValueError, match="nonexistent_gate"):
            EnsembleConfiguration.from_dict(data)

    def test_gate_model_wrong_output_type_raises(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        # Change regime model to non-regime output type
        data["models"]["regime"]["output_type"] = "classification"
        with pytest.raises(ValueError, match="regime_classification"):
            EnsembleConfiguration.from_dict(data)

    def test_serialization_roundtrip(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        config = EnsembleConfiguration.from_dict(data)
        roundtrip = config.model_dump()
        config2 = EnsembleConfiguration.from_dict(roundtrip)
        assert config2.name == config.name
        assert len(config2.models) == len(config.models)
        assert config2.composition.gate_model == config.composition.gate_model

    def test_description_optional(self) -> None:
        data = yaml.safe_load(VALID_ENSEMBLE_YAML)
        del data["description"]
        config = EnsembleConfiguration.from_dict(data)
        assert config.description is None
