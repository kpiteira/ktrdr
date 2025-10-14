"""Strategy configuration validation and upgrade utilities."""

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError as PydanticValidationError

from ktrdr import get_logger
from ktrdr.config.models import LegacyStrategyConfiguration, StrategyConfigurationV2
from ktrdr.config.strategy_loader import strategy_loader

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of strategy validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


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

    def _format_pydantic_error(
        self, error: PydanticValidationError
    ) -> tuple[list[str], list[str]]:
        """
        Format Pydantic validation errors into user-friendly messages.

        Args:
            error: Pydantic ValidationError

        Returns:
            Tuple of (error_messages, missing_sections)
        """
        error_messages = []
        missing_sections = []

        for err in error.errors():
            # Extract field location (e.g., ['indicators'] or ['model', 'architecture'])
            field_path: tuple[Any, ...] = err.get("loc", ())
            field_name = (
                ".".join(str(f) for f in field_path) if field_path else "unknown"
            )

            # Extract error type and message
            error_type = err.get("type", "unknown")
            error_msg = err.get("msg", "Validation failed")

            # Format error message based on type
            if error_type == "missing":
                # Track missing sections
                if field_path and len(field_path) == 1:
                    missing_sections.append(str(field_path[0]))
                error_messages.append(f"Missing required field: {field_name}")
            elif error_type.startswith("type_error"):
                expected_type = err.get("ctx", {}).get("expected", "correct type")
                error_messages.append(
                    f"Field '{field_name}' has incorrect type (expected {expected_type})"
                )
            else:
                # Generic error message
                error_messages.append(
                    f"Validation error in '{field_name}': {error_msg}"
                )

        return error_messages, missing_sections

    def validate_strategy(self, config_path: str) -> ValidationResult:
        """Validate a strategy configuration file (supports both v1 and v2 formats).

        Args:
            config_path: Path to strategy YAML file

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)

        try:
            # Use strategy_loader to handle both v1 and v2 formats
            config, is_v2 = strategy_loader.load_strategy_config(config_path)
        except Exception as e:
            # Check if this is a wrapped Pydantic ValidationError
            pydantic_error = None
            if hasattr(e, "__cause__") and isinstance(
                e.__cause__, PydanticValidationError
            ):
                pydantic_error = e.__cause__
            elif isinstance(e, PydanticValidationError):
                pydantic_error = e

            if pydantic_error:
                # Format Pydantic validation errors
                logger.error(f"Pydantic validation failed for {config_path}")
                result.is_valid = False

                error_messages, missing_sections = self._format_pydantic_error(
                    pydantic_error
                )
                result.errors.extend(error_messages)
                result.missing_sections.extend(missing_sections)

                # Log each error
                for error_msg in error_messages:
                    logger.error(f"Validation error: {error_msg}")

                return result
            else:
                # Non-Pydantic error (file not found, YAML parse error, etc.)
                logger.error(
                    f"Failed to load strategy configuration {config_path}: {e}"
                )
                result.is_valid = False
                result.errors.append(f"Failed to load strategy configuration: {e}")
                return result

        if is_v2:
            # Type checked - config is StrategyConfigurationV2 when is_v2 is True
            return self._validate_v2_strategy(config, result)  # type: ignore
        else:
            # Type checked - config is LegacyStrategyConfiguration when is_v2 is False
            return self._validate_v1_strategy(config, result)  # type: ignore

    def _validate_v2_strategy(
        self, config: StrategyConfigurationV2, result: ValidationResult
    ) -> ValidationResult:
        """Validate v2 strategy configuration."""
        # V2 strategies are already validated by Pydantic during loading
        # Just add some additional checks and suggestions

        # Check for comprehensive sections
        if not config.training_data:
            result.errors.append("V2 strategy missing training_data section")
            result.is_valid = False

        if not config.deployment:
            result.errors.append("V2 strategy missing deployment section")
            result.is_valid = False

        # Validate model configuration (shared with v1)
        if config.model:
            model_dict = (
                config.model
                if isinstance(config.model, dict)
                else config.model.model_dump()
            )
            model_result = self._validate_model_section(model_dict)
            result.errors.extend(model_result.errors)
            result.warnings.extend(model_result.warnings)
            if not model_result.is_valid:
                result.is_valid = False

        # Validate training configuration (shared with v1)
        if config.training:
            training_dict = (
                config.training
                if isinstance(config.training, dict)
                else config.training.model_dump()
            )
            training_result = self._validate_training_section(training_dict)
            result.errors.extend(training_result.errors)
            result.warnings.extend(training_result.warnings)
            if not training_result.is_valid:
                result.is_valid = False

        # Validate decisions configuration (shared with v1)
        if config.decisions:
            decisions_dict = (
                config.decisions
                if isinstance(config.decisions, dict)
                else config.decisions.model_dump()
            )
            decisions_result = self._validate_decisions_section(decisions_dict)
            result.errors.extend(decisions_result.errors)
            result.warnings.extend(decisions_result.warnings)
            if not decisions_result.is_valid:
                result.is_valid = False

        # Check for legacy format indicators in fuzzy sets
        if config.fuzzy_sets:
            fuzzy_dict = config.fuzzy_sets
            self._check_legacy_format({"fuzzy_sets": fuzzy_dict}, result)

        # Validate indicator-fuzzy matching (STRICT validation)
        if config.indicators and config.fuzzy_sets:
            self._validate_indicator_fuzzy_matching(
                config.indicators, config.fuzzy_sets, result
            )

        # V2-specific suggestions
        result.suggestions.append(
            "Strategy is in v2 format - ready for multi-scope training"
        )

        # Check scope recommendations
        if config.scope == "symbol_specific":
            result.suggestions.append(
                "Consider migrating to multi-symbol scope for better generalization"
            )
        elif config.scope == "universal":
            result.suggestions.append(
                "Universal scope strategy - excellent for cross-market trading"
            )

        return result

    def _validate_v1_strategy(
        self, config: LegacyStrategyConfiguration, result: ValidationResult
    ) -> ValidationResult:
        """Validate v1 (legacy) strategy configuration."""
        # Convert to dict for existing validation methods
        config_dict = config.model_dump()

        # Check required sections for v1
        for section, expected_type in self.REQUIRED_SECTIONS.items():
            if section not in config_dict or config_dict[section] is None:
                result.is_valid = False
                result.missing_sections.append(section)
                error_msg = f"Missing required section: {section}"
                result.errors.append(error_msg)
                logger.error(error_msg)
            elif not isinstance(config_dict[section], expected_type):
                result.is_valid = False
                error_msg = (
                    f"Section '{section}' must be of type {expected_type.__name__}"
                )
                result.errors.append(error_msg)
                logger.error(error_msg)

        # Validate neural model configuration
        if config_dict.get("model"):
            model_result = self._validate_model_section(config_dict["model"])
            result.errors.extend(model_result.errors)
            result.warnings.extend(model_result.warnings)
            result.missing_sections.extend(model_result.missing_sections)
            if not model_result.is_valid:
                result.is_valid = False

        # Validate training configuration
        if config_dict.get("training"):
            training_result = self._validate_training_section(config_dict["training"])
            result.errors.extend(training_result.errors)
            result.warnings.extend(training_result.warnings)
            result.missing_sections.extend(training_result.missing_sections)
            if not training_result.is_valid:
                result.is_valid = False

        # Validate decisions configuration
        if config_dict.get("decisions"):
            decisions_result = self._validate_decisions_section(
                config_dict["decisions"]
            )
            result.errors.extend(decisions_result.errors)
            result.warnings.extend(decisions_result.warnings)
            if not decisions_result.is_valid:
                result.is_valid = False

        # Check for old format indicators
        self._check_legacy_format(config_dict, result)

        # Generate suggestions for v1
        self._generate_suggestions(config_dict, result)

        # V1-specific suggestion
        result.suggestions.append(
            "Consider migrating to v2 format with 'ktrdr strategies migrate' for multi-scope support"
        )

        return result

    def _validate_model_section(self, model_config: dict[str, Any]) -> ValidationResult:
        """Validate model section."""
        result = ValidationResult(is_valid=True)

        for field_name, expected_type in self.NEURAL_MODEL_REQUIRED.items():
            if field_name not in model_config:
                result.is_valid = False
                result.missing_sections.append(f"model.{field_name}")
                result.errors.append(f"Missing required model field: {field_name}")
            elif not isinstance(model_config[field_name], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Model field '{field_name}' must be of type {expected_type.__name__}"
                )

        # Check for old format
        if "input_size" in model_config or "output_size" in model_config:
            result.warnings.append(
                "Detected old model format with input_size/output_size - consider upgrading"
            )

        return result

    def _validate_training_section(
        self, training_config: dict[str, Any]
    ) -> ValidationResult:
        """Validate training section."""
        result = ValidationResult(is_valid=True)

        for field_name, expected_type in self.TRAINING_REQUIRED.items():
            if field_name not in training_config:
                result.is_valid = False
                result.missing_sections.append(f"training.{field_name}")
                result.errors.append(f"Missing required training field: {field_name}")
            elif not isinstance(training_config[field_name], expected_type):
                result.is_valid = False
                result.errors.append(
                    f"Training field '{field_name}' must be of type {expected_type.__name__}"
                )

        return result

    def _validate_decisions_section(
        self, decisions_config: dict[str, Any]
    ) -> ValidationResult:
        """Validate decisions section."""
        result = ValidationResult(is_valid=True)

        for field_name, expected_type in self.DECISIONS_REQUIRED.items():
            if field_name not in decisions_config:
                result.is_valid = False
                result.missing_sections.append(f"decisions.{field_name}")
                result.errors.append(f"Missing required decisions field: {field_name}")
            elif not isinstance(decisions_config[field_name], expected_type):  # type: ignore[arg-type]
                result.is_valid = False
                type_name = getattr(expected_type, "__name__", str(expected_type))
                result.errors.append(
                    f"Decisions field '{field_name}' must be of type {type_name}"
                )

        return result

    def _check_legacy_format(self, config: dict[str, Any], result: ValidationResult):
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

    def _generate_suggestions(self, config: dict[str, Any], result: ValidationResult):
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
    ) -> tuple[bool, str]:
        """Upgrade a strategy configuration to neuro-fuzzy format.

        Args:
            config_path: Path to input strategy file
            output_path: Optional output path (defaults to input_path + '.upgraded')

        Returns:
            Tuple of (success, message)
        """
        try:
            with open(config_path) as f:
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
                if isinstance(defaults, dict):
                    self._merge_defaults(upgraded_config[section], defaults)
                else:
                    self._merge_defaults(upgraded_config[section], dict(defaults))  # type: ignore

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

    def _merge_defaults(self, config_section: dict[str, Any], defaults: dict[str, Any]):
        """Recursively merge defaults into configuration section."""
        for key, value in defaults.items():
            if key not in config_section:
                config_section[key] = deepcopy(value)
            elif isinstance(value, dict) and isinstance(config_section[key], dict):
                self._merge_defaults(config_section[key], value)

    def _convert_fuzzy_sets(self, config: dict[str, Any]):
        """Convert old fuzzy set format to simplified format."""
        if "fuzzy_sets" not in config:
            return

        for _indicator, sets in config["fuzzy_sets"].items():
            if isinstance(sets, dict):
                for set_name, set_config in sets.items():
                    if isinstance(set_config, dict) and "parameters" in set_config:
                        # Convert from {type: triangular, parameters: [a,b,c]} to [a,b,c]
                        if (
                            set_config.get("type") == "triangular"
                            and len(set_config["parameters"]) == 3
                        ):
                            sets[set_name] = set_config["parameters"]

    def _validate_indicator_fuzzy_matching(
        self, indicators: list[dict[str, Any]], fuzzy_sets: dict[str, Any], result: ValidationResult
    ) -> None:
        """
        Validate that all indicators have corresponding fuzzy_sets (STRICT).

        This implements the simplified validation logic from Phase 1:
        - Use feature_ids directly (no column name guessing)
        - Simple set comparison: feature_ids vs fuzzy_keys
        - STRICT validation: all feature_ids MUST have fuzzy_sets
        - Warn about orphaned fuzzy sets (might be derived features)

        Args:
            indicators: List of indicator configuration dictionaries
            fuzzy_sets: Fuzzy sets configuration dictionary
            result: ValidationResult to update with errors/warnings
        """
        # Extract feature_ids from indicators
        feature_ids = set()
        for indicator in indicators:
            feature_id = indicator.get("feature_id")
            if feature_id:  # Should always have feature_id due to Pydantic validation
                feature_ids.add(feature_id)

        # Get fuzzy_set keys
        fuzzy_keys = set(fuzzy_sets.keys())

        # Check for missing fuzzy_sets (STRICT - this is an ERROR)
        missing = feature_ids - fuzzy_keys
        if missing:
            result.is_valid = False
            missing_list = sorted(missing)

            error_msg = (
                f"Missing fuzzy_sets for indicators: {', '.join(missing_list)}. "
                "All indicators must have corresponding fuzzy_sets defined."
            )
            result.errors.append(error_msg)
            logger.error(f"Indicator-fuzzy validation failed: {error_msg}")

            # Add helpful suggestion with example structure
            example_feature_id = missing_list[0]
            suggestion = f"""
Add fuzzy_sets for missing indicators. Example for '{example_feature_id}':

fuzzy_sets:
  {example_feature_id}:
    low: {{type: trapezoid, parameters: [min, min, low_mid, mid]}}
    medium: {{type: triangle, parameters: [low_mid, mid, high_mid]}}
    high: {{type: trapezoid, parameters: [mid, high_mid, max, max]}}

Missing feature_ids: {', '.join(missing_list)}
"""
            result.suggestions.append(suggestion.strip())

        # Check for orphaned fuzzy_sets (WARNING only - might be derived features)
        orphans = fuzzy_keys - feature_ids
        if orphans:
            orphans_list = sorted(orphans)
            warning_msg = (
                f"Fuzzy sets defined without corresponding indicators: {', '.join(orphans_list)}. "
                "These might be derived features or intentional. "
                "If unintentional, remove from fuzzy_sets or add corresponding indicators."
            )
            result.warnings.append(warning_msg)
            logger.warning(f"Orphaned fuzzy_sets detected: {warning_msg}")
