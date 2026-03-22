"""Tests for TB (triple barrier) ensemble configuration files.

Validates that ensemble YAML configs for TB-trained classification signal models
parse correctly via EnsembleConfiguration and have the right structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ktrdr.config.ensemble_config import EnsembleConfiguration

CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"


class TestTBRegimeOnlyEnsembleConfig:
    """Tests for ensemble_tb_regime_only.yaml."""

    @pytest.fixture()
    def config_path(self) -> Path:
        return CONFIGS_DIR / "ensemble_tb_regime_only.yaml"

    @pytest.fixture()
    def config(self, config_path: Path) -> EnsembleConfiguration:
        return EnsembleConfiguration.from_yaml(config_path)

    def test_config_file_exists(self, config_path: Path) -> None:
        assert config_path.exists(), f"Missing config: {config_path}"

    def test_parses_without_error(self, config: EnsembleConfiguration) -> None:
        assert config.name == "tb_regime_only"

    def test_signal_models_are_classification(
        self, config: EnsembleConfiguration
    ) -> None:
        for name, model in config.models.items():
            if name == "regime":
                assert model.output_type == "regime_classification"
            else:
                assert model.output_type == "classification", (
                    f"Signal model '{name}' should be classification, "
                    f"got {model.output_type}"
                )

    def test_no_context_gate(self, config: EnsembleConfiguration) -> None:
        assert config.composition.context_gate is None
        assert config.composition.context_modifiers is None

    def test_regime_routing_rules(self, config: EnsembleConfiguration) -> None:
        rules = config.composition.rules
        assert "trending_up" in rules
        assert "trending_down" in rules
        assert "ranging" in rules
        assert "volatile" in rules
        assert rules["volatile"].action == "FLAT"

    def test_allow_short_from_flat(self, config: EnsembleConfiguration) -> None:
        assert config.composition.allow_short_from_flat is True


class TestTBContextGatedEnsembleConfig:
    """Tests for ensemble_tb_context_gated.yaml."""

    @pytest.fixture()
    def config_path(self) -> Path:
        return CONFIGS_DIR / "ensemble_tb_context_gated.yaml"

    @pytest.fixture()
    def config(self, config_path: Path) -> EnsembleConfiguration:
        return EnsembleConfiguration.from_yaml(config_path)

    def test_config_file_exists(self, config_path: Path) -> None:
        assert config_path.exists(), f"Missing config: {config_path}"

    def test_parses_without_error(self, config: EnsembleConfiguration) -> None:
        assert config.name == "tb_context_gated"

    def test_signal_models_are_classification(
        self, config: EnsembleConfiguration
    ) -> None:
        for name, model in config.models.items():
            if name == "regime":
                assert model.output_type == "regime_classification"
            elif name == "context":
                assert model.output_type == "context_classification"
            else:
                assert model.output_type == "classification", (
                    f"Signal model '{name}' should be classification, "
                    f"got {model.output_type}"
                )

    def test_context_gate_present(self, config: EnsembleConfiguration) -> None:
        assert config.composition.context_gate == "context"
        assert config.composition.context_modifiers is not None

    def test_context_modifiers_values(self, config: EnsembleConfiguration) -> None:
        mods = config.composition.context_modifiers
        assert mods is not None
        assert mods.aligned_discount == 0.2
        assert mods.counter_premium == 0.3
        assert mods.neutral_effect == 0.05

    def test_regime_routing_rules(self, config: EnsembleConfiguration) -> None:
        rules = config.composition.rules
        assert "trending_up" in rules
        assert "trending_down" in rules
        assert "ranging" in rules
        assert "volatile" in rules
        assert rules["volatile"].action == "FLAT"

    def test_allow_short_from_flat(self, config: EnsembleConfiguration) -> None:
        assert config.composition.allow_short_from_flat is True


class TestTBContainerConfigs:
    """Tests for container-path variants of TB ensemble configs."""

    @pytest.fixture(
        params=[
            "ensemble_tb_regime_only_container.yaml",
            "ensemble_tb_context_gated_container.yaml",
        ]
    )
    def config_path(self, request: pytest.FixtureRequest) -> Path:
        return CONFIGS_DIR / request.param

    @pytest.fixture()
    def config(self, config_path: Path) -> EnsembleConfiguration:
        return EnsembleConfiguration.from_yaml(config_path)

    def test_config_file_exists(self, config_path: Path) -> None:
        assert config_path.exists(), f"Missing config: {config_path}"

    def test_parses_without_error(self, config: EnsembleConfiguration) -> None:
        assert config is not None

    def test_model_paths_use_container_prefix(
        self, config: EnsembleConfiguration
    ) -> None:
        for name, model in config.models.items():
            assert model.model_path.startswith("/app/models/"), (
                f"Model '{name}' path should use /app/models/ prefix, "
                f"got {model.model_path}"
            )

    def test_signal_models_are_classification(
        self, config: EnsembleConfiguration
    ) -> None:
        for name, model in config.models.items():
            if name not in ("regime", "context"):
                assert model.output_type == "classification"
