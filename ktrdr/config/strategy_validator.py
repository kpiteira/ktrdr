"""Strategy configuration validation and upgrade utilities."""

import yaml
import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class ValidationResult:
    """Result of strategy validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class StrategyValidator:
    """Validates and upgrades strategy configuration files."""

    REQUIRED_SECTIONS = {
        "name": str,
        "indicators": list,
        "fuzzy_sets": dict,
        "model": dict,
        "decisions": dict,
        "training": dict,
    }

    OPTIONAL_SECTIONS = {
        "description": str,
        "version": str,
        "data": dict,
        "orchestrator": dict,
        "risk_management": dict,
        "backtesting": dict,
    }

    NEURAL_MODEL_REQUIRED = {
        "type": str,
        "architecture": dict,
        "training": dict,
        "features": dict,
    }

    TRAINING_REQUIRED = {"method": str, "labels": dict, "data_split": dict}

    DECISIONS_REQUIRED = {
        "output_format": str,
        "confidence_threshold": (int, float),
        "position_awareness": bool,
    }

    DEFAULT_UPGRADES = {
        "model": {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [20, 10],
                "activation": "relu",
                "output_activation": "softmax",
                "dropout": 0.2,
            },
            "training": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "optimizer": "adam",
                "weight_decay": 0.0001,
                "early_stopping": {
                    "patience": 15,
                    "monitor": "val_loss",
                    "min_delta": 0.0001,
                },
            },
            "features": {
                "include_price_context": True,
                "include_volume_context": False,
                "include_raw_indicators": False,
                "lookback_periods": 3,
                "scale_features": True,
                "scaling_method": "standard",
            },
        },
        "decisions": {
            "output_format": "classification",
            "confidence_threshold": 0.6,
            "position_awareness": True,
            "filters": {"min_signal_separation": 4, "volume_filter": False},
        },
        "training": {
            "method": "supervised",
            "labels": {
                "source": "zigzag",
                "zigzag_threshold": 0.05,
                "label_lookahead": 20,
            },
            "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
            "fitness_metrics": {
                "primary": "accuracy",
                "secondary": ["precision", "recall", "f1_score"],
            },
        },
        "orchestrator": {
            "max_position_size": 0.95,
            "signal_cooldown": 4,
            "modes": {
                "backtest": {"confidence_threshold": 0.6},
                "paper": {"confidence_threshold": 0.65},
                "live": {"confidence_threshold": 0.7, "require_confirmation": True},
            },
        },
        "risk_management": {
            "position_sizing": "fixed_fraction",
            "risk_per_trade": 0.02,
            "max_portfolio_risk": 0.10,
        },
        "backtesting": {
            "start_date": "2020-01-01",
            "end_date": "2024-01-01",
            "initial_capital": 100000,
            "transaction_costs": 0.001,
            "slippage": 0.0005,
        },
    }

    def validate_strategy(self, config_path: str) -> ValidationResult:
        """Validate a strategy configuration file.

        Args:
            config_path: Path to strategy YAML file

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to load YAML file: {e}")
            return result

        if not isinstance(config, dict):
            result.is_valid = False
            result.errors.append("Configuration must be a dictionary")
            return result

        # Check required sections
        for section, expected_type in self.REQUIRED_SECTIONS.items():
            if section not in config:
                result.is_valid = False
                result.missing_sections.append(section)
                result.errors.append(f"Missing required section: {section}")
            elif not isinstance(config[section], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Section '{section}' must be of type {expected_type.__name__}"
                )

        # Validate neural model configuration
        if "model" in config:
            model_result = self._validate_model_section(config["model"])
            result.errors.extend(model_result.errors)
            result.warnings.extend(model_result.warnings)
            result.missing_sections.extend(model_result.missing_sections)
            if not model_result.is_valid:
                result.is_valid = False

        # Validate training configuration
        if "training" in config:
            training_result = self._validate_training_section(config["training"])
            result.errors.extend(training_result.errors)
            result.warnings.extend(training_result.warnings)
            result.missing_sections.extend(training_result.missing_sections)
            if not training_result.is_valid:
                result.is_valid = False

        # Validate decisions configuration
        if "decisions" in config:
            decisions_result = self._validate_decisions_section(config["decisions"])
            result.errors.extend(decisions_result.errors)
            result.warnings.extend(decisions_result.warnings)
            if not decisions_result.is_valid:
                result.is_valid = False

        # Check for old format indicators
        self._check_legacy_format(config, result)

        # Generate suggestions
        self._generate_suggestions(config, result)

        return result

    def _validate_model_section(self, model_config: Dict[str, Any]) -> ValidationResult:
        """Validate model section."""
        result = ValidationResult(is_valid=True)

        for field, expected_type in self.NEURAL_MODEL_REQUIRED.items():
            if field not in model_config:
                result.is_valid = False
                result.missing_sections.append(f"model.{field}")
                result.errors.append(f"Missing required model field: {field}")
            elif not isinstance(model_config[field], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Model field '{field}' must be of type {expected_type.__name__}"
                )

        # Check for old format
        if "input_size" in model_config or "output_size" in model_config:
            result.warnings.append(
                "Detected old model format with input_size/output_size - consider upgrading"
            )

        return result

    def _validate_training_section(
        self, training_config: Dict[str, Any]
    ) -> ValidationResult:
        """Validate training section."""
        result = ValidationResult(is_valid=True)

        for field, expected_type in self.TRAINING_REQUIRED.items():
            if field not in training_config:
                result.is_valid = False
                result.missing_sections.append(f"training.{field}")
                result.errors.append(f"Missing required training field: {field}")
            elif not isinstance(training_config[field], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Training field '{field}' must be of type {expected_type.__name__}"
                )

        return result

    def _validate_decisions_section(
        self, decisions_config: Dict[str, Any]
    ) -> ValidationResult:
        """Validate decisions section."""
        result = ValidationResult(is_valid=True)

        for field, expected_type in self.DECISIONS_REQUIRED.items():
            if field not in decisions_config:
                result.is_valid = False
                result.missing_sections.append(f"decisions.{field}")
                result.errors.append(f"Missing required decisions field: {field}")
            elif not isinstance(decisions_config[field], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Decisions field '{field}' must be of type {expected_type.__name__}"
                )

        return result

    def _check_legacy_format(self, config: Dict[str, Any], result: ValidationResult):
        """Check for legacy format indicators."""
        # Check for old fuzzy set format
        if "fuzzy_sets" in config:
            for indicator, sets in config["fuzzy_sets"].items():
                if isinstance(sets, dict):
                    for set_name, set_config in sets.items():
                        if (
                            isinstance(set_config, dict)
                            and "type" in set_config
                            and "parameters" in set_config
                        ):
                            result.warnings.append(
                                f"Legacy fuzzy set format detected for {indicator}.{set_name}"
                            )

        # Check for minimal model configuration
        if "model" in config:
            model = config["model"]
            if len(model) < 4:  # Less than required fields
                result.warnings.append(
                    "Minimal model configuration detected - consider upgrading"
                )

    def _generate_suggestions(self, config: Dict[str, Any], result: ValidationResult):
        """Generate upgrade suggestions."""
        missing_optional = []
        for section in self.OPTIONAL_SECTIONS:
            if section not in config:
                missing_optional.append(section)

        if missing_optional:
            result.suggestions.append(
                f"Consider adding optional sections: {', '.join(missing_optional)}"
            )

        if "orchestrator" not in config:
            result.suggestions.append(
                "Add orchestrator section for advanced decision logic"
            )

        if "risk_management" not in config:
            result.suggestions.append("Add risk_management section for position sizing")

    def upgrade_strategy(
        self, config_path: str, output_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Upgrade a strategy configuration to neuro-fuzzy format.

        Args:
            config_path: Path to input strategy file
            output_path: Optional output path (defaults to input_path + '.upgraded')

        Returns:
            Tuple of (success, message)
        """
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            return False, f"Failed to load configuration: {e}"

        if not isinstance(config, dict):
            return False, "Configuration must be a dictionary"

        # Create upgraded config
        upgraded_config = deepcopy(config)

        # Add missing sections with defaults
        for section, defaults in self.DEFAULT_UPGRADES.items():
            if section not in upgraded_config:
                upgraded_config[section] = deepcopy(defaults)
            else:
                # Merge missing fields
                self._merge_defaults(upgraded_config[section], defaults)

        # Update version if present
        if "version" in upgraded_config:
            upgraded_config["version"] = f"{upgraded_config['version']}.neuro"
        else:
            upgraded_config["version"] = "1.0.neuro"

        # Add neuro prefix to name if not present
        if "name" in upgraded_config and not upgraded_config["name"].startswith(
            "neuro_"
        ):
            upgraded_config["name"] = f"neuro_{upgraded_config['name']}"

        # Convert old fuzzy set format if needed
        self._convert_fuzzy_sets(upgraded_config)

        # Save upgraded configuration
        if output_path is None:
            path = Path(config_path)
            output_path = str(path.parent / f"{path.stem}.upgraded{path.suffix}")

        try:
            with open(output_path, "w") as f:
                yaml.dump(upgraded_config, f, default_flow_style=False, indent=2)
            return True, f"Upgraded configuration saved to: {output_path}"
        except Exception as e:
            return False, f"Failed to save upgraded configuration: {e}"

    def _merge_defaults(self, config_section: Dict[str, Any], defaults: Dict[str, Any]):
        """Recursively merge defaults into configuration section."""
        for key, value in defaults.items():
            if key not in config_section:
                config_section[key] = deepcopy(value)
            elif isinstance(value, dict) and isinstance(config_section[key], dict):
                self._merge_defaults(config_section[key], value)

    def _convert_fuzzy_sets(self, config: Dict[str, Any]):
        """Convert old fuzzy set format to simplified format."""
        if "fuzzy_sets" not in config:
            return

        for indicator, sets in config["fuzzy_sets"].items():
            if isinstance(sets, dict):
                for set_name, set_config in sets.items():
                    if isinstance(set_config, dict) and "parameters" in set_config:
                        # Convert from {type: triangular, parameters: [a,b,c]} to [a,b,c]
                        if (
                            set_config.get("type") == "triangular"
                            and len(set_config["parameters"]) == 3
                        ):
                            sets[set_name] = set_config["parameters"]
