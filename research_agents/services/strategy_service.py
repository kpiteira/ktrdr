"""
Strategy service for agent operations.

Provides functions for saving and managing agent-generated strategies:
- save_strategy_config: Validate and save strategy to disk

These functions are used by MCP tools and can be tested independently.
"""

from pathlib import Path
from typing import Any

import structlog
import yaml

from ktrdr.config.strategy_validator import StrategyValidator

logger = structlog.get_logger(__name__)

# Default strategies directory
DEFAULT_STRATEGIES_DIR = "strategies"


async def save_strategy_config(
    name: str,
    config: dict[str, Any],
    description: str,
    strategies_dir: str = DEFAULT_STRATEGIES_DIR,
) -> dict[str, Any]:
    """
    Validate and save a strategy configuration to disk.

    Args:
        name: Strategy name (file will be saved as {name}.yaml)
        config: Strategy configuration dictionary
        description: Description of the strategy
        strategies_dir: Directory to save strategy to

    Returns:
        Dict with structure:
        {
            "success": bool,
            "path": str,        # Absolute path to saved file (if success)
            "errors": list,     # List of error messages (if failed)
            "suggestions": list # Suggestions for fixing errors (if failed)
        }
    """
    try:
        # Normalize name - remove .yaml extension if present
        clean_name = name.replace(".yaml", "").replace(".yml", "")

        # Update config with name and description
        config_to_save = config.copy()
        config_to_save["name"] = clean_name
        config_to_save["description"] = description

        # Create validator
        validator = StrategyValidator()

        # Check for duplicate name first
        strategies_path = Path(strategies_dir)
        name_check = validator.check_strategy_name_unique(clean_name, strategies_path)

        if not name_check.is_valid:
            logger.warning(
                "Strategy name already exists",
                name=clean_name,
                errors=name_check.errors,
            )
            return {
                "success": False,
                "errors": name_check.errors,
                "suggestions": name_check.suggestions,
            }

        # Validate the configuration
        validation_result = validator.validate_strategy_config(config_to_save)

        if not validation_result.is_valid:
            logger.warning(
                "Strategy validation failed",
                name=clean_name,
                errors=validation_result.errors,
            )
            return {
                "success": False,
                "errors": validation_result.errors,
                "suggestions": validation_result.suggestions,
            }

        # Create directory if it doesn't exist
        strategies_path.mkdir(parents=True, exist_ok=True)

        # Save to file
        file_path = strategies_path / f"{clean_name}.yaml"

        with open(file_path, "w") as f:
            yaml.dump(config_to_save, f, default_flow_style=False, sort_keys=False)

        absolute_path = str(file_path.resolve())

        logger.info(
            "Strategy saved successfully",
            name=clean_name,
            path=absolute_path,
        )

        return {
            "success": True,
            "path": absolute_path,
            "message": f"Strategy '{clean_name}' saved to {absolute_path}",
        }

    except Exception as e:
        logger.error(
            "Failed to save strategy",
            name=name,
            error=str(e),
            exc_info=True,
        )
        return {
            "success": False,
            "errors": [f"Failed to save strategy: {e}"],
            "suggestions": [],
        }
