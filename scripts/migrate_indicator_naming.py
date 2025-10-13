#!/usr/bin/env python3
"""
Migration script for explicit indicator naming.

Migrates strategy files from legacy format (type field) to new format (indicator + name).

Legacy format:
    indicators:
      - type: rsi
        params:
          period: 14

New format:
    indicators:
      - indicator: rsi
        name: rsi_14
        period: 14
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

import yaml


def generate_indicator_name(indicator_type: str, params: dict[str, Any]) -> str:
    """
    Generate an auto-generated indicator name from type and parameters.

    This mimics the legacy auto-generation logic for backward compatibility.

    Args:
        indicator_type: The indicator type (e.g., 'rsi', 'macd')
        params: Dictionary of indicator parameters

    Returns:
        Generated name (e.g., 'rsi_14', 'macd_12_26_9')
    """
    indicator_type = indicator_type.lower()
    base_name = indicator_type

    # Define parameter order for common indicators to match legacy auto-generation
    # This ensures consistent naming: macd_12_26_9 (not macd_12_9_26)
    PARAM_ORDER = {
        "macd": ["fast_period", "slow_period", "signal_period"],
        "stochastic": ["k_period", "d_period", "smooth_k"],
        "bbands": ["period", "std_dev"],
        "bollinger_bands": ["period", "std_dev"],
    }

    # Get parameter order for this indicator type
    param_order = PARAM_ORDER.get(indicator_type.lower(), [])

    # Build parameter string, excluding 'source' (implicit)
    param_parts = []

    # First, add parameters in defined order
    for key in param_order:
        if key in params:
            value = params[key]
            if isinstance(value, float) and value.is_integer():
                param_parts.append(str(int(value)))
            elif isinstance(value, (int, float, str)):
                param_parts.append(str(value))

    # Then add remaining parameters (sorted alphabetically)
    for key, value in sorted(params.items()):
        if key == "source" or key in param_order:
            continue  # Skip source and already-added params

        # Handle float formatting (remove trailing .0)
        if isinstance(value, float) and value.is_integer():
            param_parts.append(str(int(value)))
        elif isinstance(value, (int, float, str)):
            param_parts.append(str(value))

    # Join parts
    if param_parts:
        return f"{base_name}_{'_'.join(param_parts)}"
    else:
        return base_name


def migrate_indicator_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Migrate a single indicator configuration from legacy to new format.

    Args:
        config: Legacy indicator config with 'type' and 'params'

    Returns:
        Migrated config with 'indicator', 'name', and flattened params
    """
    # Check if already in new format
    if "indicator" in config and "name" in config:
        return config.copy()

    # Legacy format: has 'type' and possibly 'params'
    if "type" not in config:
        raise ValueError(f"Invalid indicator config: missing 'type' field: {config}")

    indicator_type = config["type"]
    params = config.get("params", {})

    # Generate name from type and params
    name = generate_indicator_name(indicator_type, params)

    # Build new config
    new_config = {
        "indicator": indicator_type,
        "name": name,
    }

    # Flatten params to top level
    new_config.update(params)

    return new_config


def migrate_strategy_file(
    input_file: Path, output_file: Optional[Path] = None, dry_run: bool = False
) -> bool:
    """
    Migrate a strategy YAML file from legacy to new format.

    Args:
        input_file: Path to input strategy file
        output_file: Path to output file (if None, overwrites input)
        dry_run: If True, don't write output file

    Returns:
        True if migration performed, False if no migration needed
    """
    # Load input file
    with open(input_file) as f:
        strategy = yaml.safe_load(f)

    # Check if migration needed
    if "indicators" not in strategy or not strategy["indicators"]:
        print(f"⏭️  {input_file}: No indicators to migrate")
        return False

    # Check if already migrated
    first_indicator = strategy["indicators"][0]
    if "indicator" in first_indicator and "name" in first_indicator:
        print(f"✅ {input_file}: Already migrated (skipping)")
        return False

    # Migrate indicators
    migrated_indicators = []
    for idx, indicator in enumerate(strategy["indicators"]):
        try:
            migrated = migrate_indicator_config(indicator)
            migrated_indicators.append(migrated)
            print(
                f"  [{idx+1}] {indicator.get('type', '?')} → "
                f"{migrated['indicator']} (name: {migrated['name']})"
            )
        except Exception as e:
            print(f"❌ Error migrating indicator {idx+1}: {e}", file=sys.stderr)
            return False

    strategy["indicators"] = migrated_indicators

    # Dry run: don't write file
    if dry_run:
        print(f"🔍 {input_file}: Dry run - would migrate {len(migrated_indicators)} indicators")
        return True

    # Write output file
    output_path = output_file or input_file
    with open(output_path, "w") as f:
        yaml.dump(strategy, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"✅ {output_path}: Migrated {len(migrated_indicators)} indicators")
    return True


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate strategy files to explicit indicator naming format"
    )
    parser.add_argument(
        "files", nargs="+", type=Path, help="Strategy YAML files to migrate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (if not specified, overwrites input files)",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="Suffix to add to output filenames (e.g., '_migrated')",
    )

    args = parser.parse_args()

    # Validate output directory
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    print("🔄 Starting migration...\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for input_file in args.files:
        if not input_file.exists():
            print(f"❌ {input_file}: File not found", file=sys.stderr)
            error_count += 1
            continue

        # Determine output file
        if args.output_dir:
            stem = input_file.stem + args.suffix
            output_file = args.output_dir / f"{stem}{input_file.suffix}"
        elif args.suffix:
            stem = input_file.stem + args.suffix
            output_file = input_file.parent / f"{stem}{input_file.suffix}"
        else:
            output_file = None  # Overwrite input

        try:
            result = migrate_strategy_file(input_file, output_file, args.dry_run)
            if result:
                success_count += 1
            else:
                skip_count += 1
        except Exception as e:
            print(f"❌ {input_file}: Migration failed: {e}", file=sys.stderr)
            error_count += 1

        print()  # Blank line between files

    # Summary
    print("=" * 60)
    print(f"✅ Migrated: {success_count}")
    print(f"⏭️  Skipped: {skip_count}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")

    if args.dry_run:
        print("\n💡 This was a dry run. Run without --dry-run to apply changes.")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
