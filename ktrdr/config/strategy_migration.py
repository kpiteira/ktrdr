"""Strategy migration from v2 to v3 format.

This module provides migration logic to convert v2 strategy configurations
to v3 format, enabling transition from the legacy indicator-centric format
to the new feature-centric format.

Migration rules (from ARCHITECTURE.md):
1. Convert `indicators` list to dict (key = existing feature_id)
2. Add `indicator` field to each fuzzy_set (value = matching indicator key)
3. Generate `nn_inputs` from training_data.timeframes × fuzzy_sets
4. Remove deprecated fields: `feature_id` from indicators
"""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def migrate_v2_to_v3(v2_config: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate v2 strategy config to v3 format.

    Args:
        v2_config: Raw dict from v2 YAML

    Returns:
        v3-compatible dict with:
        - indicators as dict (key = feature_id, value includes 'type')
        - fuzzy_sets with 'indicator' field on each
        - nn_inputs generated from fuzzy_sets
        - version set to "3.0"
    """
    # Deep copy to avoid modifying original
    v3_config = copy.deepcopy(v2_config)

    # 1. Convert indicators list to dict
    if isinstance(v2_config.get("indicators"), list):
        indicators_dict: dict[str, dict[str, Any]] = {}
        for ind in v2_config["indicators"]:
            # feature_id becomes the key, falls back to 'name' if missing
            ind_id = ind.get("feature_id", ind.get("name"))
            if ind_id is None:
                logger.warning(
                    "Skipping indicator during migration: missing both 'feature_id' and 'name'. "
                    f"Indicator data: {ind}"
                )
                continue

            # Build the indicator definition, handling missing 'name' safely
            name = ind.get("name") or ind_id
            indicator_def: dict[str, Any] = {"type": name}

            # Copy all parameters except name and feature_id
            for key, value in ind.items():
                if key not in ("name", "feature_id"):
                    indicator_def[key] = value

            indicators_dict[ind_id] = indicator_def

        v3_config["indicators"] = indicators_dict

    # 2. Add indicator field to fuzzy_sets
    if "fuzzy_sets" in v3_config:
        for fs_id, fs_def in v3_config["fuzzy_sets"].items():
            if isinstance(fs_def, dict) and "indicator" not in fs_def:
                # In v2, fuzzy_set key typically matches indicator feature_id
                fs_def["indicator"] = fs_id

    # 3. Generate nn_inputs if missing
    if "nn_inputs" not in v3_config:
        nn_inputs: list[dict[str, Any]] = []
        for fs_id in v3_config.get("fuzzy_sets", {}).keys():
            nn_inputs.append({"fuzzy_set": fs_id, "timeframes": "all"})
        v3_config["nn_inputs"] = nn_inputs

    # 4. Update version
    v3_config["version"] = "3.0"

    return v3_config


def validate_migration(original: dict[str, Any], migrated: dict[str, Any]) -> list[str]:
    """
    Validate migration preserved expected behavior.

    Compares original v2 config with migrated v3 config to identify
    potential issues or data loss during migration.

    Args:
        original: Original v2 config dict
        migrated: Migrated v3 config dict

    Returns:
        List of warning/issue messages. Empty list means migration looks correct.
    """
    issues: list[str] = []

    # Check indicator count preserved
    orig_indicators = original.get("indicators", [])
    if isinstance(orig_indicators, list):
        orig_count = len(orig_indicators)
    else:
        orig_count = len(orig_indicators) if orig_indicators else 0

    migrated_indicators = migrated.get("indicators", {})
    if isinstance(migrated_indicators, dict):
        migrated_count = len(migrated_indicators)
    else:
        migrated_count = len(migrated_indicators) if migrated_indicators else 0

    if orig_count != migrated_count:
        issues.append(f"Indicator count changed: {orig_count} -> {migrated_count}")

    # Check fuzzy set count preserved
    orig_fs = len(original.get("fuzzy_sets", {}))
    migrated_fs = len(migrated.get("fuzzy_sets", {}))
    if orig_fs != migrated_fs:
        issues.append(f"Fuzzy set count changed: {orig_fs} -> {migrated_fs}")

    return issues
