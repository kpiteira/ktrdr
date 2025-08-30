"""Strategy configuration loading with support for both v1 (legacy) and v2 (multi-scope) formats."""

from pathlib import Path
from typing import Any, Optional, Union

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from ktrdr import get_logger
from ktrdr.config.models import (
    DeploymentConfiguration,
    LegacyStrategyConfiguration,
    StrategyConfigurationV2,
    StrategyScope,
    SymbolConfiguration,
    SymbolMode,
    TargetSymbolConfiguration,
    TargetSymbolMode,
    TargetTimeframeConfiguration,
    TimeframeConfiguration,
    TimeframeMode,
    TrainingDataConfiguration,
)

logger = get_logger(__name__)


class StrategyConfigurationLoader:
    """Loads and validates strategy configurations, supporting both v1 and v2 formats."""

    def load_strategy_config(
        self, config_path: Union[str, Path]
    ) -> tuple[Union[StrategyConfigurationV2, LegacyStrategyConfiguration], bool]:
        """
        Load strategy configuration from YAML file.

        Args:
            config_path: Path to strategy configuration file

        Returns:
            Tuple of (config_object, is_v2_format)

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config format is invalid
            ValidationError: If config validation fails
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Strategy configuration not found: {config_path}")

        # Load YAML content
        try:
            with open(config_path) as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

        if not isinstance(raw_config, dict):
            raise ValueError(
                f"Strategy configuration must be a dictionary: {config_path}"
            )

        # Detect format and validate
        is_v2_format = self._detect_v2_format(raw_config)

        if is_v2_format:
            logger.info(
                f"Loading v2 multi-scope strategy configuration: {config_path.name}"
            )
            try:
                config = StrategyConfigurationV2(**raw_config)
                return config, True
            except ValidationError as e:
                raise ValueError(
                    f"V2 strategy validation failed for {config_path}: {e}"
                ) from e
        else:
            logger.info(f"Loading v1 legacy strategy configuration: {config_path.name}")
            try:
                # Add sensible defaults for missing required fields
                raw_config = self._add_legacy_defaults(raw_config)
                config = LegacyStrategyConfiguration(**raw_config)
                return config, False
            except ValidationError as e:
                raise ValueError(
                    f"Legacy strategy validation failed for {config_path}: {e}"
                ) from e

    def _detect_v2_format(self, config: dict[str, Any]) -> bool:
        """
        Detect if configuration uses v2 format.

        V2 format indicators:
        - Has 'scope' field
        - Has 'training_data' section
        - Has 'deployment' section
        - 'training_data' has 'symbols' and 'timeframes' with 'mode' fields
        """
        # Check for v2-specific top-level fields
        v2_indicators = ["scope", "training_data", "deployment"]
        has_v2_fields = any(field in config for field in v2_indicators)

        # Check for v2-specific nested structure
        training_data = config.get("training_data", {})
        has_v2_structure = (
            isinstance(training_data, dict)
            and "symbols" in training_data
            and "timeframes" in training_data
            and isinstance(training_data.get("symbols", {}), dict)
            and "mode" in training_data.get("symbols", {})
        )

        return has_v2_fields or has_v2_structure

    def migrate_v1_to_v2(
        self,
        legacy_config: LegacyStrategyConfiguration,
        output_path: Optional[Union[str, Path]] = None,
    ) -> StrategyConfigurationV2:
        """
        Migrate v1 legacy configuration to v2 format.

        Args:
            legacy_config: Legacy configuration object
            output_path: Optional path to save migrated config

        Returns:
            Migrated v2 configuration
        """
        logger.info(f"Migrating legacy strategy '{legacy_config.name}' to v2 format")

        # Determine scope and modes from legacy config
        data_section = legacy_config.data or {}
        legacy_symbols = data_section.get("symbols", [])
        legacy_timeframes = data_section.get("timeframes", [])

        # Determine strategy scope
        if len(legacy_symbols) > 1 or len(legacy_timeframes) > 1:
            scope = (
                StrategyScope.SYMBOL_GROUP
            )  # Multi-symbol/timeframe suggests group scope
        else:
            scope = (
                StrategyScope.SYMBOL_SPECIFIC
            )  # Single symbol/timeframe is legacy specific

        # Create symbol configuration
        if len(legacy_symbols) <= 1:
            symbol_config = SymbolConfiguration(
                mode=SymbolMode.SINGLE,
                symbol=legacy_symbols[0] if legacy_symbols else "PLACEHOLDER",
            )
        else:
            symbol_config = SymbolConfiguration(
                mode=SymbolMode.MULTI_SYMBOL, list=legacy_symbols
            )

        # Create timeframe configuration
        if len(legacy_timeframes) <= 1:
            timeframe_config = TimeframeConfiguration(
                mode=TimeframeMode.SINGLE,
                timeframe=legacy_timeframes[0] if legacy_timeframes else "1h",
            )
        else:
            timeframe_config = TimeframeConfiguration(
                mode=TimeframeMode.MULTI_TIMEFRAME,
                list=legacy_timeframes,
                base_timeframe=legacy_timeframes[0],  # Use first as base
            )

        # Create training data configuration
        training_data_config = TrainingDataConfiguration(
            symbols=symbol_config,
            timeframes=timeframe_config,
            history_required=data_section.get("history_required", 200),
        )

        # Create deployment configuration
        if scope == StrategyScope.SYMBOL_SPECIFIC:
            target_symbol_mode = TargetSymbolMode.TRAINING_ONLY
        elif scope == StrategyScope.SYMBOL_GROUP:
            target_symbol_mode = TargetSymbolMode.GROUP_RESTRICTED
        else:
            target_symbol_mode = TargetSymbolMode.UNIVERSAL

        target_symbols = TargetSymbolConfiguration(mode=target_symbol_mode)

        target_timeframes = TargetTimeframeConfiguration(
            mode=timeframe_config.mode,
            supported=(
                timeframe_config.timeframes
                if timeframe_config.mode == TimeframeMode.MULTI_TIMEFRAME
                else None
            ),
            timeframe=(
                timeframe_config.timeframe
                if timeframe_config.mode == TimeframeMode.SINGLE
                else None
            ),
        )

        deployment_config = DeploymentConfiguration(
            target_symbols=target_symbols, target_timeframes=target_timeframes
        )

        # Create v2 configuration
        v2_config = StrategyConfigurationV2(
            name=(
                f"{legacy_config.name}_multi"
                if scope != StrategyScope.SYMBOL_SPECIFIC
                else legacy_config.name
            ),
            description=legacy_config.description
            or f"Migrated from v1: {legacy_config.name}",
            version=f"{legacy_config.version or '1.0'}_v2",
            scope=scope,
            training_data=training_data_config,
            deployment=deployment_config,
            indicators=legacy_config.indicators,
            fuzzy_sets=legacy_config.fuzzy_sets,
            model=legacy_config.model,
            decisions=legacy_config.decisions,
            training=legacy_config.training,
            orchestrator=legacy_config.orchestrator,
            risk_management=legacy_config.risk_management,
            backtesting=legacy_config.backtesting,
        )

        # Save migrated config if output path provided
        if output_path:
            output_path = Path(output_path)
            with open(output_path, "w") as f:
                # Convert to dict for YAML serialization with enum value extraction
                config_dict = v2_config.model_dump(exclude_unset=True, mode="json")
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            logger.info(f"Migrated configuration saved to: {output_path}")

        return v2_config

    def _add_legacy_defaults(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Add sensible defaults for missing required fields in legacy strategies.

        Args:
            config: Raw configuration dictionary

        Returns:
            Configuration with missing required fields filled with defaults
        """
        # Create a copy to avoid modifying the original
        config = config.copy()

        # Add default decisions section if missing
        if "decisions" not in config:
            config["decisions"] = {
                "output_format": "classification",
                "confidence_threshold": 0.6,
                "position_awareness": True,
                "filters": {"min_signal_separation": 4, "volume_filter": False},
            }
            logger.info("Added default decisions section to legacy strategy")

        # Add default data section if missing
        if "data" not in config:
            config["data"] = {
                "symbols": ["AAPL"],  # Default single symbol
                "timeframes": ["1h"],  # Default single timeframe
                "history_required": 200,
            }
            logger.info("Added default data section to legacy strategy")

        # Ensure required training fields exist
        if "training" not in config:
            config["training"] = {}

        training = config["training"]
        if "method" not in training:
            training["method"] = "supervised"
        if "labels" not in training:
            training["labels"] = {
                "source": "zigzag",
                "zigzag_threshold": 0.03,
                "label_lookahead": 20,
            }
        if "data_split" not in training:
            training["data_split"] = {"train": 0.7, "validation": 0.15, "test": 0.15}

        # Ensure model section has required fields
        if "model" in config:
            model = config["model"]
            if "type" not in model:
                model["type"] = "mlp"
            if "architecture" not in model:
                model["architecture"] = {
                    "hidden_layers": [50, 25],
                    "activation": "relu",
                    "output_activation": "softmax",
                    "dropout": 0.2,
                }
            if "training" not in model:
                model["training"] = {
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "epochs": 100,
                    "optimizer": "adam",
                }
            if "features" not in model:
                model["features"] = {
                    "include_price_context": False,
                    "include_volume_context": False,
                    "include_raw_indicators": False,
                    "lookback_periods": 2,
                    "scale_features": False,
                }

        return config

    def extract_training_symbols_and_timeframes(
        self, config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration]
    ) -> tuple[list[str], list[str]]:
        """
        Extract training symbols and timeframes from any config format.

        Args:
            config: Strategy configuration (v1 or v2)

        Returns:
            Tuple of (symbols_list, timeframes_list)
        """
        if isinstance(config, StrategyConfigurationV2):
            # V2 format
            symbols_config = config.training_data.symbols
            timeframes_config = config.training_data.timeframes

            if symbols_config.mode == SymbolMode.SINGLE:
                symbols = [symbols_config.symbol] if symbols_config.symbol else []
            else:
                symbols = symbols_config.symbols or []

            if timeframes_config.mode == TimeframeMode.SINGLE:
                timeframes = (
                    [timeframes_config.timeframe] if timeframes_config.timeframe else []
                )
            else:
                timeframes = timeframes_config.timeframes or []

        else:
            # Legacy format
            data_section = config.data or {}
            symbols = data_section.get("symbols", [])
            timeframes = data_section.get("timeframes", [])

            # Ensure they're lists
            if isinstance(symbols, str):
                symbols = [symbols]
            if isinstance(timeframes, str):
                timeframes = [timeframes]

        return symbols, timeframes

    def is_multi_scope_strategy(
        self, config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration]
    ) -> bool:
        """
        Check if strategy is multi-scope (supports multiple symbols/timeframes).

        Args:
            config: Strategy configuration

        Returns:
            True if strategy supports multiple symbols or timeframes
        """
        symbols, timeframes = self.extract_training_symbols_and_timeframes(config)
        return len(symbols) > 1 or len(timeframes) > 1

    def get_model_storage_path_components(
        self, config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration]
    ) -> tuple[str, str]:
        """
        Get model storage path components based on configuration.

        Args:
            config: Strategy configuration

        Returns:
            Tuple of (strategy_directory, model_identifier)
        """
        if isinstance(config, StrategyConfigurationV2):
            # V2 format: scope-based naming
            strategy_dir = config.name

            if config.scope == StrategyScope.UNIVERSAL:
                model_id = "universal"
            elif config.scope == StrategyScope.SYMBOL_GROUP:
                # Create identifier from symbol list or criteria
                symbols, _ = self.extract_training_symbols_and_timeframes(config)
                if symbols:
                    if len(symbols) <= 3:
                        model_id = "_".join(symbols).lower()
                    else:
                        # Use asset class or create summary
                        criteria = config.training_data.symbols.selection_criteria
                        if criteria and criteria.asset_class:
                            model_id = f"{criteria.asset_class}_group"
                        else:
                            model_id = f"group_{len(symbols)}_symbols"
                else:
                    model_id = "symbol_group"
            else:
                # Symbol specific - use legacy format
                symbols, timeframes = self.extract_training_symbols_and_timeframes(
                    config
                )
                symbol = symbols[0] if symbols else "unknown"
                timeframe = timeframes[0] if timeframes else "1h"
                model_id = f"{symbol.lower()}_{timeframe}"
        else:
            # Legacy format: symbol_timeframe naming
            strategy_dir = config.name
            symbols, timeframes = self.extract_training_symbols_and_timeframes(config)
            symbol = symbols[0] if symbols else "unknown"
            timeframe = timeframes[0] if timeframes else "1h"
            model_id = f"{symbol.lower()}_{timeframe}"

        return strategy_dir, model_id


# Global instance for easy access
strategy_loader = StrategyConfigurationLoader()
