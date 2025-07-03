"""Strategy migration utility for converting legacy strategies to v2 format."""

import yaml
from pathlib import Path
from typing import Union, Optional, List, Tuple
import argparse

from ktrdr import get_logger
from ktrdr.config.strategy_loader import strategy_loader, StrategyConfigurationLoader
from ktrdr.config.models import LegacyStrategyConfiguration, StrategyConfigurationV2

logger = get_logger(__name__)


class StrategyMigrator:
    """Utility for migrating legacy strategy configurations to v2 format."""

    def __init__(self):
        self.loader = StrategyConfigurationLoader()

    def migrate_strategy_file(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        force: bool = False
    ) -> Tuple[bool, str, Optional[Path]]:
        """
        Migrate a single strategy file from v1 to v2 format.

        Args:
            input_path: Path to legacy strategy file
            output_path: Optional output path (auto-generated if None)
            force: Whether to overwrite existing output file

        Returns:
            Tuple of (success, message, output_path)
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            return False, f"Input file not found: {input_path}", None

        try:
            # Load the strategy configuration
            config, is_v2 = self.loader.load_strategy_config(input_path)
            
            if is_v2:
                return False, f"Strategy {input_path.name} is already v2 format", None

            # Generate output path if not provided
            if output_path is None:
                output_path = input_path.parent / f"{input_path.stem}_v2{input_path.suffix}"
            else:
                output_path = Path(output_path)

            # Check if output exists and force flag
            if output_path.exists() and not force:
                return False, f"Output file exists (use --force to overwrite): {output_path}", None

            # Migrate to v2 format
            logger.info(f"Migrating {input_path.name} to v2 format...")
            v2_config = strategy_loader.migrate_v1_to_v2(config, output_path)

            return True, f"Successfully migrated {input_path.name} to {output_path.name}", output_path

        except Exception as e:
            logger.error(f"Migration failed for {input_path}: {e}")
            return False, f"Migration failed: {e}", None

    def migrate_directory(
        self,
        directory: Union[str, Path],
        pattern: str = "*.yaml",
        output_suffix: str = "_v2",
        force: bool = False
    ) -> Tuple[int, int, List[str]]:
        """
        Migrate all strategy files in a directory.

        Args:
            directory: Directory containing strategy files
            pattern: File pattern to match (default: "*.yaml")
            output_suffix: Suffix to add to output files
            force: Whether to overwrite existing files

        Returns:
            Tuple of (successful_count, failed_count, error_messages)
        """
        directory = Path(directory)
        
        if not directory.exists() or not directory.is_dir():
            return 0, 0, [f"Directory not found: {directory}"]

        strategy_files = list(directory.glob(pattern))
        
        if not strategy_files:
            return 0, 0, [f"No strategy files found matching {pattern} in {directory}"]

        successful = 0
        failed = 0
        errors = []

        for file_path in strategy_files:
            # Skip already migrated files
            if output_suffix in file_path.stem:
                logger.debug(f"Skipping already migrated file: {file_path.name}")
                continue

            # Generate output path
            output_path = file_path.parent / f"{file_path.stem}{output_suffix}{file_path.suffix}"

            success, message, _ = self.migrate_strategy_file(file_path, output_path, force)
            
            if success:
                successful += 1
                logger.info(message)
            else:
                failed += 1
                errors.append(f"{file_path.name}: {message}")
                logger.warning(message)

        return successful, failed, errors

    def analyze_strategy_compatibility(
        self, config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration]
    ) -> dict:
        """
        Analyze strategy configuration for multi-scope compatibility.

        Args:
            config: Strategy configuration

        Returns:
            Dictionary with compatibility analysis
        """
        symbols, timeframes = self.loader.extract_training_symbols_and_timeframes(config)
        is_multi_scope = self.loader.is_multi_scope_strategy(config)

        analysis = {
            "format_version": "v2" if isinstance(config, StrategyConfigurationV2) else "v1",
            "is_multi_scope": is_multi_scope,
            "training_symbols": symbols,
            "training_timeframes": timeframes,
            "symbol_count": len(symbols),
            "timeframe_count": len(timeframes),
            "recommendations": []
        }

        # Generate recommendations
        if not is_multi_scope:
            analysis["recommendations"].append(
                "Strategy uses single symbol/timeframe - consider migrating to multi-scope for better generalization"
            )
        
        if len(symbols) == 1 and len(timeframes) == 1:
            analysis["scope_recommendation"] = "symbol_specific"
            analysis["recommendations"].append(
                "Single symbol/timeframe strategy - suitable for symbol-specific trading"
            )
        elif len(symbols) > 1 and len(timeframes) > 1:
            analysis["scope_recommendation"] = "universal"
            analysis["recommendations"].append(
                "Multi-symbol, multi-timeframe strategy - excellent candidate for universal model"
            )
        elif len(symbols) > 1:
            analysis["scope_recommendation"] = "symbol_group"
            analysis["recommendations"].append(
                "Multi-symbol strategy - suitable for symbol group trading"
            )
        elif len(timeframes) > 1:
            analysis["scope_recommendation"] = "universal"
            analysis["recommendations"].append(
                "Multi-timeframe strategy - good candidate for universal model with timeframe adaptation"
            )

        if isinstance(config, StrategyConfigurationV2):
            model_dir, model_id = self.loader.get_model_storage_path_components(config)
            analysis["model_storage"] = {
                "directory": model_dir,
                "identifier": model_id,
                "full_path": f"models/{model_dir}/{model_id}_v1/"
            }

        return analysis

    def validate_migration(
        self, original_path: Union[str, Path], migrated_path: Union[str, Path]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that migration preserved essential configuration.

        Args:
            original_path: Path to original strategy file
            migrated_path: Path to migrated strategy file

        Returns:
            Tuple of (is_valid, validation_messages)
        """
        messages = []
        is_valid = True

        try:
            # Load both configurations
            original_config, _ = self.loader.load_strategy_config(original_path)
            migrated_config, is_v2 = self.loader.load_strategy_config(migrated_path)

            if not is_v2:
                is_valid = False
                messages.append("Migrated file is not in v2 format")
                return is_valid, messages

            # Extract training data
            orig_symbols, orig_timeframes = self.loader.extract_training_symbols_and_timeframes(original_config)
            migr_symbols, migr_timeframes = self.loader.extract_training_symbols_and_timeframes(migrated_config)

            # Check symbol preservation
            if set(orig_symbols) != set(migr_symbols):
                is_valid = False
                messages.append(f"Symbols mismatch: {orig_symbols} -> {migr_symbols}")
            else:
                messages.append(f"✓ Symbols preserved: {orig_symbols}")

            # Check timeframe preservation
            if set(orig_timeframes) != set(migr_timeframes):
                is_valid = False
                messages.append(f"Timeframes mismatch: {orig_timeframes} -> {migr_timeframes}")
            else:
                messages.append(f"✓ Timeframes preserved: {orig_timeframes}")

            # Check essential sections
            essential_sections = ["indicators", "fuzzy_sets", "model", "decisions", "training"]
            for section in essential_sections:
                orig_section = getattr(original_config, section, None)
                migr_section = getattr(migrated_config, section, None)
                
                if orig_section != migr_section:
                    messages.append(f"⚠ Section '{section}' may have been modified during migration")
                else:
                    messages.append(f"✓ Section '{section}' preserved")

            if is_valid:
                messages.append("✅ Migration validation passed")

        except Exception as e:
            is_valid = False
            messages.append(f"Validation failed: {e}")

        return is_valid, messages


def main():
    """Command-line interface for strategy migration."""
    parser = argparse.ArgumentParser(description="Migrate KTRDR strategy configurations to v2 format")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Migrate single file
    migrate_parser = subparsers.add_parser("migrate", help="Migrate a single strategy file")
    migrate_parser.add_argument("input", help="Input strategy file path")
    migrate_parser.add_argument("-o", "--output", help="Output file path (auto-generated if not specified)")
    migrate_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing output file")
    
    # Migrate directory
    batch_parser = subparsers.add_parser("batch", help="Migrate all strategy files in a directory")
    batch_parser.add_argument("directory", help="Directory containing strategy files")
    batch_parser.add_argument("-p", "--pattern", default="*.yaml", help="File pattern to match")
    batch_parser.add_argument("-s", "--suffix", default="_v2", help="Suffix for output files")
    batch_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")
    
    # Analyze strategy
    analyze_parser = subparsers.add_parser("analyze", help="Analyze strategy for multi-scope compatibility")
    analyze_parser.add_argument("input", help="Strategy file path")
    
    # Validate migration
    validate_parser = subparsers.add_parser("validate", help="Validate migration result")
    validate_parser.add_argument("original", help="Original strategy file path")
    validate_parser.add_argument("migrated", help="Migrated strategy file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    migrator = StrategyMigrator()
    
    if args.command == "migrate":
        success, message, output_path = migrator.migrate_strategy_file(
            args.input, args.output, args.force
        )
        print(message)
        if success and output_path:
            print(f"Output: {output_path}")
    
    elif args.command == "batch":
        successful, failed, errors = migrator.migrate_directory(
            args.directory, args.pattern, args.suffix, args.force
        )
        print(f"Migration complete: {successful} successful, {failed} failed")
        if errors:
            print("\nErrors:")
            for error in errors:
                print(f"  - {error}")
    
    elif args.command == "analyze":
        try:
            config, is_v2 = strategy_loader.load_strategy_config(args.input)
            analysis = migrator.analyze_strategy_compatibility(config)
            
            print(f"Strategy Analysis: {Path(args.input).name}")
            print(f"Format: {analysis['format_version']}")
            print(f"Multi-scope: {analysis['is_multi_scope']}")
            print(f"Symbols ({analysis['symbol_count']}): {analysis['training_symbols']}")
            print(f"Timeframes ({analysis['timeframe_count']}): {analysis['training_timeframes']}")
            print(f"Recommended scope: {analysis.get('scope_recommendation', 'N/A')}")
            
            if analysis['recommendations']:
                print("\nRecommendations:")
                for rec in analysis['recommendations']:
                    print(f"  - {rec}")
                    
            if 'model_storage' in analysis:
                storage = analysis['model_storage']
                print(f"\nModel Storage Path: {storage['full_path']}")
                
        except Exception as e:
            print(f"Analysis failed: {e}")
    
    elif args.command == "validate":
        is_valid, messages = migrator.validate_migration(args.original, args.migrated)
        print(f"Validation: {'PASSED' if is_valid else 'FAILED'}")
        for message in messages:
            print(f"  {message}")


if __name__ == "__main__":
    main()