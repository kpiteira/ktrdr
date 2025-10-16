#!/usr/bin/env python3
"""
One-time migration script to add input_transform configuration to existing strategies.

This script adds price_ratio input transforms to SMA and EMA indicators in fuzzy_sets
configurations, which is required for them to work correctly with the new architecture.

Background:
- SMA/EMA fuzzy sets use price ratio values (e.g., 0.93-1.07 centered at 1.0)
- These represent "price / SMA" ratios, not raw SMA values
- Previously, this transformation was done manually in training pipeline
- Now, it must be configured in fuzzy_sets with input_transform

Usage:
    python scripts/migrate_strategy_input_transforms.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def needs_price_ratio_transform(indicator_name: str, fuzzy_set_config: dict) -> bool:
    """
    Check if an indicator needs price_ratio transform based on fuzzy set parameters.

    Args:
        indicator_name: Name of the indicator (e.g., "sma_20", "ema_9")
        fuzzy_set_config: Fuzzy set configuration dictionary

    Returns:
        True if transform is needed
    """
    # Check if it's an SMA or EMA indicator
    if not (indicator_name.startswith("sma_") or indicator_name.startswith("ema_")):
        return False

    # Check if input_transform already exists
    if "input_transform" in fuzzy_set_config:
        return False

    # Check if fuzzy set parameters look like price ratios
    # Price ratios are typically centered around 1.0 (0.8-1.2 range)
    for fuzzy_set_name, config in fuzzy_set_config.items():
        if fuzzy_set_name == "input_transform":
            continue

        if isinstance(config, dict) and "parameters" in config:
            params = config["parameters"]
            # Check if parameters are in ratio range (0.5 to 2.0)
            # and have values close to 1.0
            if len(params) >= 2:
                min_val = min(params)
                max_val = max(params)
                if 0.5 <= min_val <= 1.5 and 0.5 <= max_val <= 2.0:
                    # Has at least one parameter near 1.0
                    if any(0.8 <= p <= 1.2 for p in params):
                        return True

    return False


def add_input_transform(fuzzy_set_config: dict, reference: str = "close") -> dict:
    """
    Add input_transform configuration to a fuzzy set.

    Args:
        fuzzy_set_config: Fuzzy set configuration dictionary
        reference: Reference price column (default: "close")

    Returns:
        Updated fuzzy set configuration with input_transform
    """
    # Create new config with input_transform as first key
    new_config = {"input_transform": {"type": "price_ratio", "reference": reference}}

    # Add all other keys
    for key, value in fuzzy_set_config.items():
        if key != "input_transform":
            new_config[key] = value

    return new_config


def migrate_strategy_file(
    file_path: Path, dry_run: bool = False
) -> tuple[bool, str, int]:
    """
    Migrate a single strategy file to add input transforms.

    Args:
        file_path: Path to strategy YAML file
        dry_run: If True, don't write changes

    Returns:
        Tuple of (success, message, num_transforms_added)
    """
    try:
        # Load strategy file
        with open(file_path) as f:
            strategy = yaml.safe_load(f)

        if not strategy or "fuzzy_sets" not in strategy:
            return False, "No fuzzy_sets found", 0

        fuzzy_sets = strategy["fuzzy_sets"]
        transforms_added = 0
        modified_indicators = []

        # Check each indicator in fuzzy_sets
        for indicator_name, fuzzy_set_config in fuzzy_sets.items():
            if needs_price_ratio_transform(indicator_name, fuzzy_set_config):
                # Add input_transform
                fuzzy_sets[indicator_name] = add_input_transform(fuzzy_set_config)
                transforms_added += 1
                modified_indicators.append(indicator_name)

        if transforms_added == 0:
            return True, "No transforms needed", 0

        # Write updated strategy (unless dry-run)
        if not dry_run:
            with open(file_path, "w") as f:
                yaml.dump(strategy, f, default_flow_style=False, sort_keys=False)

        message = f"Added {transforms_added} transform(s) to: {', '.join(modified_indicators)}"
        return True, message, transforms_added

    except Exception as e:
        return False, f"Error: {e}", 0


def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate strategy files to add input_transform configuration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing files",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        help="Migrate specific strategy file (default: all in strategies/)",
    )
    args = parser.parse_args()

    # Find strategy files
    if args.strategy:
        strategy_files = [Path(args.strategy)]
    else:
        strategies_dir = PROJECT_ROOT / "strategies"
        strategy_files = list(strategies_dir.glob("*.yaml"))

    if not strategy_files:
        print("No strategy files found!")
        return 1

    print(f"Found {len(strategy_files)} strategy file(s)")
    if args.dry_run:
        print("DRY RUN MODE - no files will be modified\n")

    total_transforms = 0
    successful = 0
    failed = 0

    for file_path in sorted(strategy_files):
        success, message, num_transforms = migrate_strategy_file(file_path, args.dry_run)

        status = "✓" if success else "✗"
        print(f"{status} {file_path.name}: {message}")

        if success:
            successful += 1
            total_transforms += num_transforms
        else:
            failed += 1

    print("\nSummary:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total transforms added: {total_transforms}")

    if args.dry_run:
        print("\nTo apply changes, run without --dry-run flag")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
