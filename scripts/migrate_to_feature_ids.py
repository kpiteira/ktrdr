#!/usr/bin/env python3
"""
Migration tool for adding feature_id to indicator configurations.

This script migrates old strategy configuration files (without feature_id)
to the new format (with required feature_id field).

Usage:
    python scripts/migrate_to_feature_ids.py strategy.yaml [--dry-run] [--backup]
    python scripts/migrate_to_feature_ids.py strategies/*.yaml
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ktrdr.config.models import IndicatorConfig
from ktrdr.errors import ConfigurationError
from ktrdr.indicators.indicator_factory import IndicatorFactory


class MigrationError(Exception):
    """Exception raised when migration fails."""

    pass


def generate_feature_id_from_indicator(indicator_config: dict[str, Any]) -> str:
    """
    Generate a feature_id from an indicator configuration.

    This function instantiates the indicator to get its column name,
    which becomes the feature_id (preserving existing fuzzy set keys).

    Args:
        indicator_config: Dictionary containing indicator type and params

    Returns:
        Generated feature_id string

    Raises:
        MigrationError: If indicator cannot be instantiated or column name generated
    """
    try:
        # Get indicator name
        indicator_name = indicator_config.get("name")

        # Params are at the same level as 'name' (flat format)
        params = {
            k: v
            for k, v in indicator_config.items()
            if k not in ["name", "feature_id"]
        }

        if not indicator_name:
            raise MigrationError("Indicator config missing 'name' field")

        # Create a temporary config for instantiation
        # Note: feature_id is required in new schema, but we're generating it
        # So we use a temporary placeholder
        temp_config = IndicatorConfig(
            name=indicator_name, feature_id="temp_placeholder", params=params
        )

        # Use IndicatorFactory to instantiate the indicator
        factory = IndicatorFactory([temp_config])
        indicators = factory.build()

        if not indicators:
            raise MigrationError(
                f"Failed to instantiate indicator of type '{indicator_type}'"
            )

        # Get the column name from the indicator
        indicator = indicators[0]
        column_name = indicator.get_column_name()

        return column_name

    except ConfigurationError as e:
        raise MigrationError(
            f"Failed to generate feature_id for indicator name '{indicator_name}': {e}"
        ) from e
    except Exception as e:
        raise MigrationError(
            f"Unexpected error generating feature_id for indicator name '{indicator_name}': {e}"
        ) from e


def migrate_strategy_file(
    file_path: str, dry_run: bool = False, backup: bool = False
) -> dict[str, Any]:
    """
    Migrate a single strategy file to add feature_ids to indicators.

    Args:
        file_path: Path to the strategy YAML file
        dry_run: If True, preview changes without modifying the file
        backup: If True, create a .bak backup before modifying

    Returns:
        Dictionary with migration results:
        - success: bool
        - changes: int (number of indicators modified)
        - dry_run: bool
        - errors: list of error messages (if any)

    Raises:
        MigrationError: If migration fails (e.g., duplicate feature_ids)
    """
    file_path_obj = Path(file_path)

    # Use ruamel.yaml to preserve comments and formatting
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False

    # Read strategy file
    try:
        with open(file_path_obj) as f:
            strategy = yaml.load(f)
    except Exception as e:
        raise MigrationError(f"Failed to read strategy file '{file_path}': {e}") from e

    if not isinstance(strategy, dict):
        raise MigrationError(
            f"Invalid strategy file format: expected dict, got {type(strategy)}"
        )

    indicators = strategy.get("indicators", [])
    if not indicators:
        return {"success": True, "changes": 0, "dry_run": dry_run, "errors": []}

    # Track changes and feature_ids
    changes_made = 0
    feature_ids_seen = set()
    errors = []

    # Process each indicator
    for idx, indicator in enumerate(indicators):
        # Skip if already has feature_id
        if "feature_id" in indicator:
            # Still need to track for duplicate detection
            existing_feature_id = indicator["feature_id"]
            if existing_feature_id in feature_ids_seen:
                raise MigrationError(
                    f"Duplicate feature_id '{existing_feature_id}' found at indicator {idx}. "
                    f"Each feature_id must be unique within the strategy."
                )
            feature_ids_seen.add(existing_feature_id)
            continue

        # Generate feature_id
        try:
            feature_id = generate_feature_id_from_indicator(indicator)

            # Check for duplicates
            if feature_id in feature_ids_seen:
                indicator_name = indicator.get("name")
                raise MigrationError(
                    f"Duplicate feature_id '{feature_id}' would be created for indicator {idx} "
                    f"(name: {indicator_name}). Multiple indicators with identical parameters "
                    f"require manually distinct feature_ids. Please add unique feature_ids manually."
                )

            feature_ids_seen.add(feature_id)

            # MINIMAL CHANGE: Only add 'feature_id' field
            # Keep flat structure and preserve all comments
            # Old format: {name: "rsi", period: 14, source: "close"}
            # New format: {name: "rsi", feature_id: "rsi_14", period: 14, source: "close"}

            # Add feature_id after name field
            if "name" in indicator:
                # Insert feature_id right after name field
                indicator.insert(1, "feature_id", feature_id)
            else:
                # Fallback: just add it at the end
                indicator["feature_id"] = feature_id

            changes_made += 1

        except MigrationError as e:
            indicator_name = indicator.get("name", "unknown")
            errors.append(f"Indicator {idx} ({indicator_name}): {str(e)}")

    # If any errors occurred, raise
    if errors:
        raise MigrationError(
            f"Migration failed for '{file_path}':\n"
            + "\n".join(f"  - {err}" for err in errors)
        )

    # If no changes needed, return early
    if changes_made == 0:
        return {"success": True, "changes": 0, "dry_run": dry_run, "errors": []}

    # If dry-run, don't write file
    if dry_run:
        return {"success": True, "changes": changes_made, "dry_run": True, "errors": []}

    # Create backup if requested
    if backup:
        backup_path = file_path_obj.with_suffix(file_path_obj.suffix + ".bak")
        try:
            shutil.copy2(file_path_obj, backup_path)
        except Exception as e:
            raise MigrationError(f"Failed to create backup file: {e}") from e

    # Write migrated strategy (ruamel.yaml preserves comments and formatting)
    try:
        with open(file_path_obj, "w") as f:
            yaml.dump(strategy, f)
    except Exception as e:
        raise MigrationError(
            f"Failed to write migrated strategy to '{file_path}': {e}"
        ) from e

    return {"success": True, "changes": changes_made, "dry_run": False, "errors": []}


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: List of arguments (for testing), or None to use sys.argv

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Migrate strategy files to add feature_id to indicators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration (dry-run)
  python scripts/migrate_to_feature_ids.py strategy.yaml --dry-run

  # Migrate single file
  python scripts/migrate_to_feature_ids.py strategy.yaml

  # Migrate with backup
  python scripts/migrate_to_feature_ids.py strategy.yaml --backup

  # Migrate all strategies
  python scripts/migrate_to_feature_ids.py strategies/*.yaml
        """,
    )

    parser.add_argument("files", nargs="+", help="Strategy YAML file(s) to migrate")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--backup", action="store_true", help="Create .bak backup before migrating"
    )

    return parser.parse_args(args)


def main():
    """Main entry point for the migration tool."""
    args = parse_args()

    print("=" * 80)
    print("Feature ID Migration Tool")
    print("=" * 80)
    print()

    if args.dry_run:
        print("🔍 DRY-RUN MODE: No files will be modified")
        print()

    total_files = len(args.files)
    successful = 0
    failed = 0
    total_changes = 0

    for idx, file_path in enumerate(args.files, 1):
        print(f"[{idx}/{total_files}] Processing: {file_path}")

        try:
            result = migrate_strategy_file(
                file_path, dry_run=args.dry_run, backup=args.backup
            )

            if result["changes"] > 0:
                print(f"  ✅ {result['changes']} indicator(s) updated")
                total_changes += result["changes"]
            else:
                print("  ℹ️  No changes needed (already migrated)")

            successful += 1

        except MigrationError as e:
            print(f"  ❌ Failed: {e}")
            failed += 1

        print()

    # Summary
    print("=" * 80)
    print("Migration Summary")
    print("=" * 80)
    print(f"Files processed: {total_files}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total changes: {total_changes}")

    if args.dry_run:
        print()
        print(
            "⚠️  DRY-RUN: No files were modified. Run without --dry-run to apply changes."
        )

    if args.backup and total_changes > 0 and not args.dry_run:
        print()
        print("💾 Backup files created with .bak extension")

    # Exit with error code if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
