"""
Configuration migration utilities for fuzzy logic.

This module provides utilities to migrate single-timeframe fuzzy configurations
to the new multi-timeframe format introduced in Phase 5.
"""

from pathlib import Path
from typing import Any, Optional

import yaml

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy.config import FuzzyConfigLoader

# Set up module-level logger
logger = get_logger(__name__)


class FuzzyConfigMigrator:
    """
    Utility for migrating single-timeframe fuzzy configurations to multi-timeframe format.

    Note: Migration is optional since MultiTimeframeFuzzyEngine provides full backward
    compatibility. This utility is provided for users who want to explicitly convert
    their configurations to the new format.
    """

    def __init__(self):
        """Initialize the migrator."""
        logger.debug("Initialized FuzzyConfigMigrator")

    def migrate_single_to_multi_timeframe(
        self,
        single_config: dict[str, Any],
        target_timeframe: str = "1h",
        timeframe_weight: float = 1.0,
    ) -> dict[str, Any]:
        """
        Migrate a single-timeframe fuzzy configuration to multi-timeframe format.

        Args:
            single_config: Single-timeframe fuzzy configuration dictionary
            target_timeframe: Target timeframe for the migrated config (default: "1h")
            timeframe_weight: Weight for the timeframe (default: 1.0)

        Returns:
            Multi-timeframe fuzzy configuration dictionary

        Raises:
            ConfigurationError: If migration fails
        """
        logger.info(
            f"Migrating single-timeframe config to timeframe: {target_timeframe}"
        )

        try:
            # Validate the input configuration
            loader = FuzzyConfigLoader()
            fuzzy_config = loader.load_from_dict(single_config)

            # Extract indicators from the single config
            indicators = list(single_config.keys())

            # Create the multi-timeframe structure
            multi_config = {
                "timeframes": {
                    target_timeframe: {
                        "indicators": indicators,
                        "fuzzy_sets": single_config,
                        "weight": timeframe_weight,
                        "enabled": True,
                    }
                },
                "indicators": indicators,
            }

            logger.info(
                f"Successfully migrated config with {len(indicators)} indicators"
            )
            return multi_config

        except Exception as e:
            logger.error(f"Failed to migrate fuzzy configuration: {e}")
            raise ConfigurationError(
                message="Failed to migrate fuzzy configuration",
                error_code="MIGRATION-SingleToMultiFailed",
                details={"original_error": str(e)},
            ) from e

    def migrate_to_multiple_timeframes(
        self,
        single_config: dict[str, Any],
        timeframes: list[str],
        timeframe_weights: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        """
        Migrate a single-timeframe configuration to multiple timeframes.

        Args:
            single_config: Single-timeframe fuzzy configuration dictionary
            timeframes: List of target timeframes (e.g., ["1h", "4h", "1d"])
            timeframe_weights: Optional weights for each timeframe

        Returns:
            Multi-timeframe fuzzy configuration dictionary

        Raises:
            ConfigurationError: If migration fails
        """
        logger.info(
            f"Migrating single-timeframe config to {len(timeframes)} timeframes"
        )

        if not timeframes:
            raise ConfigurationError(
                message="At least one timeframe must be specified",
                error_code="MIGRATION-NoTimeframes",
                details={},
            )

        # Default weights
        if timeframe_weights is None:
            weight_per_tf = 1.0 / len(timeframes)
            timeframe_weights = dict.fromkeys(timeframes, weight_per_tf)

        try:
            # Validate the input configuration
            loader = FuzzyConfigLoader()
            fuzzy_config = loader.load_from_dict(single_config)

            # Extract indicators from the single config
            indicators = list(single_config.keys())

            # Create timeframe configurations
            timeframe_configs = {}
            for timeframe in timeframes:
                timeframe_configs[timeframe] = {
                    "indicators": indicators,
                    "fuzzy_sets": single_config,
                    "weight": timeframe_weights.get(timeframe, 1.0),
                    "enabled": True,
                }

            # Create the multi-timeframe structure
            multi_config = {"timeframes": timeframe_configs, "indicators": indicators}

            logger.info(f"Successfully migrated config to {len(timeframes)} timeframes")
            return multi_config

        except Exception as e:
            logger.error(f"Failed to migrate fuzzy configuration: {e}")
            raise ConfigurationError(
                message="Failed to migrate fuzzy configuration to multiple timeframes",
                error_code="MIGRATION-MultiTimeframeFailed",
                details={"original_error": str(e)},
            ) from e

    def migrate_yaml_file(
        self,
        input_file: Path,
        output_file: Path,
        target_timeframe: str = "1h",
        timeframe_weight: float = 1.0,
    ) -> None:
        """
        Migrate a YAML fuzzy configuration file to multi-timeframe format.

        Args:
            input_file: Path to input single-timeframe YAML file
            output_file: Path to output multi-timeframe YAML file
            target_timeframe: Target timeframe for the migrated config
            timeframe_weight: Weight for the timeframe

        Raises:
            ConfigurationError: If migration fails
        """
        logger.info(f"Migrating YAML file: {input_file} -> {output_file}")

        try:
            # Load the input file
            with open(input_file) as f:
                single_config = yaml.safe_load(f)

            # Migrate the configuration
            multi_config = self.migrate_single_to_multi_timeframe(
                single_config, target_timeframe, timeframe_weight
            )

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write the migrated configuration
            with open(output_file, "w") as f:
                yaml.dump(multi_config, f, default_flow_style=False, indent=2)

            logger.info(f"Successfully migrated YAML file to: {output_file}")

        except Exception as e:
            logger.error(f"Failed to migrate YAML file: {e}")
            raise ConfigurationError(
                message="Failed to migrate YAML fuzzy configuration file",
                error_code="MIGRATION-YamlFailed",
                details={
                    "input_file": str(input_file),
                    "output_file": str(output_file),
                    "original_error": str(e),
                },
            ) from e

    def check_migration_needed(self, config: dict[str, Any]) -> bool:
        """
        Check if a fuzzy configuration needs migration to multi-timeframe format.

        Args:
            config: Fuzzy configuration dictionary

        Returns:
            True if migration is needed (single-timeframe), False if already multi-timeframe
        """
        # Multi-timeframe configs have 'timeframes' key
        if "timeframes" in config:
            logger.debug("Configuration is already multi-timeframe format")
            return False

        # Single-timeframe configs are flat dictionaries with indicator names as keys
        if isinstance(config, dict) and config:
            # Check if all top-level keys look like indicator names
            for key, value in config.items():
                if isinstance(value, dict) and any(
                    mf_key in value
                    for mf_key in ["low", "high", "neutral", "negative", "positive"]
                ):
                    logger.debug("Configuration appears to be single-timeframe format")
                    return True

        logger.debug("Configuration format could not be determined")
        return False

    def get_migration_recommendations(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Get recommendations for migrating a single-timeframe configuration.

        Args:
            config: Single-timeframe fuzzy configuration

        Returns:
            Dictionary with migration recommendations
        """
        recommendations = {
            "migration_needed": self.check_migration_needed(config),
            "indicators_found": list(config.keys()) if isinstance(config, dict) else [],
            "recommended_timeframes": ["1h", "4h", "1d"],
            "suggested_weights": {
                "1h": 0.5,  # Short-term timing
                "4h": 0.3,  # Medium-term trend
                "1d": 0.2,  # Long-term context
            },
            "notes": [
                "Migration is optional - existing configs work with backward compatibility",
                "Consider using different membership functions for different timeframes",
                "Adjust timeframe weights based on your trading strategy",
            ],
        }

        return recommendations


def migrate_fuzzy_config(
    config: dict[str, Any], target_timeframe: str = "1h"
) -> dict[str, Any]:
    """
    Convenience function to migrate a single-timeframe config to multi-timeframe.

    Args:
        config: Single-timeframe fuzzy configuration
        target_timeframe: Target timeframe for migration

    Returns:
        Multi-timeframe fuzzy configuration
    """
    migrator = FuzzyConfigMigrator()
    return migrator.migrate_single_to_multi_timeframe(config, target_timeframe)


def check_config_compatibility(config: dict[str, Any]) -> dict[str, Any]:
    """
    Check configuration compatibility and provide migration recommendations.

    Args:
        config: Fuzzy configuration to check

    Returns:
        Compatibility report with recommendations
    """
    migrator = FuzzyConfigMigrator()
    return migrator.get_migration_recommendations(config)
