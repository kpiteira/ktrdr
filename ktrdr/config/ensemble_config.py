"""Ensemble configuration models for regime-routed backtesting.

Defines the configuration schema for multi-model ensemble backtests where
a regime classifier gates routing to per-regime signal models.
"""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class ModelReference(BaseModel):
    """Reference to a trained model bundle."""

    name: str = Field(..., description="Logical name in ensemble")
    model_path: str = Field(..., description="Path to model bundle directory")
    output_type: str = Field(
        ...,
        description="Output type: classification, regression, regime_classification",
    )


class RouteRule(BaseModel):
    """What to do when a specific regime is detected.

    Exactly one of `model` or `action` must be specified.
    """

    model: Optional[str] = Field(None, description="Signal model to dispatch to")
    action: Optional[str] = Field(None, description="Fixed action (e.g., FLAT)")

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "RouteRule":
        if self.model is not None and self.action is not None:
            raise ValueError(
                "RouteRule fields 'model' and 'action' are mutually exclusive"
            )
        if self.model is None and self.action is None:
            raise ValueError("RouteRule must specify either 'model' or 'action'")
        return self


VALID_TRANSITION_POLICIES = {"close_and_switch", "let_run"}


class CompositionConfig(BaseModel):
    """How models compose their outputs."""

    type: str = Field(..., description="Composition type (regime_route)")
    gate_model: str = Field(
        ..., description="Model that produces regime classification"
    )
    regime_threshold: float = Field(0.4, description="Min probability to assign regime")
    stability_bars: int = Field(
        3, description="Consecutive bars required before regime transition"
    )
    rules: dict[str, RouteRule] = Field(
        ..., description="regime_name → route rule mapping"
    )
    on_regime_transition: str = Field(
        ..., description="Transition policy: close_and_switch or let_run"
    )

    @model_validator(mode="after")
    def validate_transition_policy(self) -> "CompositionConfig":
        if self.on_regime_transition not in VALID_TRANSITION_POLICIES:
            raise ValueError(
                f"Invalid on_regime_transition: '{self.on_regime_transition}'. "
                f"Must be one of: {sorted(VALID_TRANSITION_POLICIES)}"
            )
        return self


class EnsembleConfiguration(BaseModel):
    """Top-level ensemble configuration for regime-routed backtesting."""

    name: str = Field(..., description="Ensemble name")
    description: Optional[str] = Field(None, description="Human-readable description")
    models: dict[str, ModelReference] = Field(..., description="Named model references")
    composition: CompositionConfig = Field(
        ..., description="Composition/routing configuration"
    )

    @model_validator(mode="after")
    def validate_ensemble(self) -> "EnsembleConfiguration":
        """Validate model references, gate model, and route rules."""
        model_names = set(self.models.keys())

        # Gate model must exist
        if self.composition.gate_model not in model_names:
            raise ValueError(
                f"gate_model '{self.composition.gate_model}' not found in models. "
                f"Available: {sorted(model_names)}"
            )

        # Gate model must have regime_classification output_type
        gate = self.models[self.composition.gate_model]
        if gate.output_type != "regime_classification":
            raise ValueError(
                f"gate_model '{self.composition.gate_model}' has output_type "
                f"'{gate.output_type}', expected 'regime_classification'"
            )

        # All model references in rules must exist
        for regime_name, rule in self.composition.rules.items():
            if rule.model is not None and rule.model not in model_names:
                raise ValueError(
                    f"Route rule for '{regime_name}' references model "
                    f"'{rule.model}' which is not defined in models. "
                    f"Available: {sorted(model_names)}"
                )

        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnsembleConfiguration":
        """Create ensemble configuration from a dictionary.

        Handles the YAML structure where models are keyed by name
        and the name field is injected from the key.
        """
        # Inject model names from dict keys if not present
        if "models" in data:
            for name, model_data in data["models"].items():
                if isinstance(model_data, dict) and "name" not in model_data:
                    model_data["name"] = name

        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "EnsembleConfiguration":
        """Load ensemble configuration from a YAML file."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
