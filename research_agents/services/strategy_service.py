"""
Strategy service for agent operations.

Provides functions for saving and managing agent-generated strategies:
- save_strategy_config: Validate and save strategy to disk
- get_recent_strategies: Query recent strategies for agent context

These functions are used by MCP tools and can be tested independently.
"""

from pathlib import Path
from typing import Any

import structlog
import yaml

from ktrdr.config.strategy_validator import StrategyValidator
from research_agents.database.queries import get_agent_db

logger = structlog.get_logger(__name__)

# Default strategies directory
DEFAULT_STRATEGIES_DIR = "strategies"


async def validate_strategy_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a strategy configuration without saving.

    This allows the agent to check a config before saving, catching
    errors early and reducing save failures.

    Args:
        config: Strategy configuration dictionary

    Returns:
        Dict with structure:
        {
            "valid": bool,          # True if config is valid
            "errors": list,         # List of error messages
            "warnings": list,       # List of warnings
            "suggestions": list     # Suggestions for fixing errors
        }
    """
    try:
        # Create validator
        validator = StrategyValidator()

        # Validate the configuration
        validation_result = validator.validate_strategy_config(config)

        return {
            "valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
            "suggestions": validation_result.suggestions,
        }

    except Exception as e:
        logger.error(
            "Failed to validate strategy",
            error=str(e),
            exc_info=True,
        )
        return {
            "valid": False,
            "errors": [f"Validation error: {e}"],
            "warnings": [],
            "suggestions": [],
        }


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


async def get_recent_strategies(
    n: int = 5,
    strategies_dir: str = DEFAULT_STRATEGIES_DIR,
) -> list[dict[str, Any]]:
    """
    Get the N most recent strategies designed by the agent.

    Queries the agent_sessions table for completed sessions and enriches
    with strategy details from saved YAML files.

    Args:
        n: Number of strategies to return (default 5).
        strategies_dir: Directory containing strategy YAML files.

    Returns:
        List of dicts with structure:
        [
            {
                "name": str,              # Strategy name
                "type": str | None,       # Model type (e.g., "mlp", "lstm")
                "indicators": list | None, # List of indicator names
                "outcome": str,           # Session outcome
                "created_at": str         # ISO format timestamp
            }
        ]
    """
    try:
        db = await get_agent_db()
        sessions = await db.get_recent_completed_sessions(n=n)

        strategies = []
        strategies_path = Path(strategies_dir)

        for session in sessions:
            strategy_name = session.get("strategy_name")

            # Skip sessions without a strategy name (e.g., failed_design)
            if not strategy_name:
                continue

            # Build base info from database
            strategy_info = {
                "name": strategy_name,
                "type": None,
                "indicators": None,
                "outcome": session.get("outcome"),
                "created_at": _format_datetime(session.get("created_at")),
            }

            # Try to enrich with YAML file details
            yaml_path = strategies_path / f"{strategy_name}.yaml"
            if yaml_path.exists():
                try:
                    with open(yaml_path) as f:
                        config = yaml.safe_load(f)

                    if config:
                        # Extract model type
                        model = config.get("model", {})
                        strategy_info["type"] = model.get("type")

                        # Extract indicator names
                        indicators = config.get("indicators", [])
                        if indicators:
                            strategy_info["indicators"] = [
                                ind.get("name") for ind in indicators if ind.get("name")
                            ]

                except Exception as e:
                    logger.warning(
                        "Failed to read strategy YAML",
                        strategy_name=strategy_name,
                        error=str(e),
                    )
                    # Continue with partial info

            strategies.append(strategy_info)

        return strategies

    except Exception as e:
        logger.error(
            "Failed to get recent strategies",
            error=str(e),
            exc_info=True,
        )
        return []


def _format_datetime(dt: Any) -> str | None:
    """Format a datetime to ISO 8601 string."""
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)
