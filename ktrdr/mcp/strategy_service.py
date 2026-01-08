"""Strategy service for MCP tools.

Provides business logic for strategy operations used by MCP tools.
This module is testable without FastMCP dependencies.
"""

from pathlib import Path
from typing import Any

from ktrdr import get_logger
from ktrdr.config.feature_resolver import FeatureResolver
from ktrdr.config.strategy_loader import StrategyConfigurationLoader

logger = get_logger(__name__)


async def validate_strategy(path: str) -> dict[str, Any]:
    """
    Validate a strategy file.

    Returns dict with:
    - valid: bool
    - format: "v3" | "v2" | "unknown"
    - features: list[str] (if v3)
    - feature_count: int (if v3)
    - errors: list[str] (if invalid)
    - suggestion: str (if v2 - migration suggestion)

    Args:
        path: Path to the strategy YAML file

    Returns:
        Validation result dictionary
    """
    loader = StrategyConfigurationLoader()
    strategy_path = Path(path)

    # Check file exists
    if not strategy_path.exists():
        return {
            "valid": False,
            "format": "unknown",
            "errors": [f"Strategy file not found: {path}"],
        }

    try:
        # Try loading as v3 first
        config = loader.load_v3_strategy(strategy_path)

        # Resolve features
        resolver = FeatureResolver()
        features = resolver.resolve(config)

        return {
            "valid": True,
            "format": "v3",
            "features": [f.feature_id for f in features],
            "feature_count": len(features),
        }

    except ValueError as e:
        error_str = str(e)

        # Detect v2 format based on the loader's error message.
        # StrategyConfigurationLoader.load_v3_strategy() raises ValueError
        # with message "Strategy '<name>' is not v3 format. Run 'ktrdr strategy
        # migrate' to upgrade." when the file is valid v2 but not v3.
        if "not v3 format" in error_str:
            return {
                "valid": False,
                "format": "v2",
                "errors": [error_str],
                "suggestion": "Run 'ktrdr strategy migrate' to upgrade to v3 format",
            }

        # Other validation error
        return {
            "valid": False,
            "format": "unknown",
            "errors": [error_str],
        }

    except Exception as e:
        logger.error(f"Error validating strategy {path}: {e}")
        return {
            "valid": False,
            "format": "unknown",
            "errors": [str(e)],
        }
