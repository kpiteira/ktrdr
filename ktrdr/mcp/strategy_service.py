"""Strategy service for MCP tools.

Provides business logic for strategy operations used by MCP tools.
This module is testable without FastMCP dependencies.
"""

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ktrdr import get_logger
from ktrdr.config.feature_resolver import FeatureResolver
from ktrdr.config.strategy_loader import StrategyConfigurationLoader

logger = get_logger(__name__)

# Default strategies directory (overridable for testing)
DEFAULT_STRATEGIES_DIR = "strategies"


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


def _sanitize_filename(name: str) -> str:
    """Sanitize strategy name for use as filename."""
    # Allow alphanumeric, underscore, hyphen
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


async def save_strategy_config(
    strategy_name: str,
    strategy_yaml: str,
    strategies_dir: str | None = None,
) -> dict[str, Any]:
    """Save a validated v3 strategy configuration atomically.

    Validates the YAML content as v3 format first, then saves only if valid.
    This ensures no invalid strategies are persisted.

    Args:
        strategy_name: Name for the strategy file
        strategy_yaml: Strategy configuration as YAML string
        strategies_dir: Directory to save strategies (default: strategies/)

    Returns:
        Dict with success status, strategy_name, strategy_path on success,
        or success=False with errors on failure.
    """
    target_dir = Path(strategies_dir or DEFAULT_STRATEGIES_DIR)

    # Step 1: Parse YAML
    try:
        raw_config = yaml.safe_load(strategy_yaml)
    except yaml.YAMLError as e:
        return {
            "success": False,
            "errors": [f"Invalid YAML: {e}"],
        }

    if not isinstance(raw_config, dict):
        return {
            "success": False,
            "errors": ["Strategy configuration must be a YAML mapping"],
        }

    # Step 2: Write to temp file and validate via existing loader
    # (The loader requires a file path, so we write temporarily)
    safe_name = _sanitize_filename(strategy_name)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            tmp.write(strategy_yaml)
            tmp_path = Path(tmp.name)

        # Validate using existing infrastructure
        validation = await validate_strategy(str(tmp_path))

        if not validation.get("valid"):
            return {
                "success": False,
                "errors": validation.get("errors", ["Validation failed"]),
            }

    except Exception as e:
        logger.error(f"Error during strategy validation: {e}")
        return {
            "success": False,
            "errors": [str(e)],
        }
    finally:
        # Clean up temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Step 3: Save atomically (write to temp, then rename)
    target_path = target_dir / f"{safe_name}.yaml"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", dir=target_dir, delete=False
        ) as out:
            out.write(strategy_yaml.strip() + "\n")
            tmp_out = Path(out.name)

        # Atomic rename
        tmp_out.rename(target_path)

        logger.info("Strategy saved: %s -> %s", strategy_name, target_path)

        return {
            "success": True,
            "strategy_name": strategy_name,
            "strategy_path": str(target_path),
        }

    except Exception as e:
        # Clean up partial write
        try:
            tmp_out.unlink(missing_ok=True)
        except Exception:
            pass
        logger.error(f"Error saving strategy: {e}")
        return {
            "success": False,
            "errors": [f"Failed to save: {e}"],
        }


async def get_recent_strategies(
    limit: int = 10,
    strategies_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent strategies sorted by modification date.

    Scans the strategies directory for YAML files, extracts key metadata,
    and returns them sorted by modification date (newest first).

    Args:
        limit: Maximum number of strategies to return (default 10)
        strategies_dir: Directory to scan (default: strategies/)

    Returns:
        List of strategy summaries with name, indicators, date, and assessment.
    """
    target_dir = Path(strategies_dir or DEFAULT_STRATEGIES_DIR)

    if not target_dir.is_dir():
        return []

    # Collect YAML strategy files with their modification times
    strategy_files: list[tuple[float, Path]] = []
    for path in target_dir.iterdir():
        if path.suffix in (".yaml", ".yml") and not path.name.startswith("."):
            strategy_files.append((path.stat().st_mtime, path))

    # Sort by modification time, newest first
    strategy_files.sort(key=lambda x: x[0], reverse=True)

    # Apply limit
    strategy_files = strategy_files[:limit]

    # Build result
    results: list[dict[str, Any]] = []
    for mtime, path in strategy_files:
        try:
            with open(path) as f:
                config = yaml.safe_load(f)
        except Exception:
            logger.warning("Skipping invalid YAML: %s", path)
            continue

        if not isinstance(config, dict):
            continue

        name = config.get("name", path.stem)

        # Extract indicator names
        indicators_section = config.get("indicators", {})
        if isinstance(indicators_section, dict):
            indicator_names = list(indicators_section.keys())
        else:
            indicator_names = []

        # Check for assessment file
        assessment_verdict = None
        assessment_path = path.parent / f"{path.stem}_assessment.json"
        if assessment_path.exists():
            try:
                with open(assessment_path) as f:
                    assessment = json.load(f)
                assessment_verdict = assessment.get("verdict")
            except Exception:
                pass

        created_date = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        results.append(
            {
                "name": name,
                "description": config.get("description", ""),
                "indicators": indicator_names,
                "created_date": created_date,
                "assessment_verdict": assessment_verdict,
                "path": str(path),
            }
        )

    return results
