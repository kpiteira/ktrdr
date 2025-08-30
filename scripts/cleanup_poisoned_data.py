#!/usr/bin/env python3
"""
Data Cleanup Script for Timezone-Poisoned Files

This script backs up and removes data files that may contain incorrect timestamps
due to the timezone issues that were present before the TimestampManager fixes.

After running this script, users should re-download data from IB to get clean,
properly timezone-aware data using the new TimestampManager system.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    script_dir = Path(__file__).parent
    return script_dir.parent


def create_backup_directory() -> Path:
    """Create a timestamped backup directory."""
    project_root = get_project_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "data" / f"backup_poisoned_data_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_data_files(data_dir: Path) -> list[Path]:
    """Get all CSV data files in the data directory."""
    if not data_dir.exists():
        return []
    return list(data_dir.glob("*.csv"))


def backup_data_files(data_dir: Path, backup_dir: Path) -> list[str]:
    """Backup all CSV files to the backup directory."""
    data_files = get_data_files(data_dir)
    backed_up_files = []

    for file_path in data_files:
        backup_path = backup_dir / file_path.name
        shutil.copy2(file_path, backup_path)
        backed_up_files.append(file_path.name)
        print(f"✅ Backed up: {file_path.name}")

    return backed_up_files


def backup_symbol_cache(data_dir: Path, backup_dir: Path) -> bool:
    """Backup the symbol discovery cache."""
    cache_file = data_dir / "symbol_discovery_cache.json"
    if cache_file.exists():
        backup_path = backup_dir / cache_file.name
        shutil.copy2(cache_file, backup_path)
        print(f"✅ Backed up: {cache_file.name}")
        return True
    return False


def reset_symbol_cache(data_dir: Path) -> None:
    """Reset the symbol cache to remove failed symbols that should be retested."""
    cache_file = data_dir / "symbol_discovery_cache.json"

    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cache_data = json.load(f)

            # Keep validated symbols but clear failed symbols
            # This allows previously working symbols to be re-validated with new timezone logic
            original_failed_count = len(cache_data.get("failed_symbols", []))
            cache_data["failed_symbols"] = []
            cache_data["last_updated"] = datetime.now().timestamp()

            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            print(
                f"✅ Reset symbol cache: cleared {original_failed_count} failed symbols"
            )

        except Exception as e:
            print(f"⚠️  Failed to reset symbol cache: {e}")
    else:
        print("ℹ️  No symbol cache found to reset")


def remove_data_files(data_dir: Path, backed_up_files: list[str]) -> None:
    """Remove the backed-up data files from the data directory."""
    removed_count = 0
    for filename in backed_up_files:
        file_path = data_dir / filename
        if file_path.exists():
            file_path.unlink()
            removed_count += 1
            print(f"🗑️  Removed: {filename}")

    print(f"✅ Removed {removed_count} poisoned data files")


def create_cleanup_summary(
    backup_dir: Path, backed_up_files: list[str], cache_backed_up: bool
) -> None:
    """Create a summary file of what was cleaned up."""
    summary = {
        "cleanup_timestamp": datetime.now().isoformat(),
        "backup_location": str(backup_dir),
        "backed_up_files": backed_up_files,
        "symbol_cache_backed_up": cache_backed_up,
        "total_files_backed_up": len(backed_up_files),
        "cleanup_reason": "Timezone-poisoned data cleanup after TimestampManager implementation",
        "instructions": [
            "Data files contained incorrect timestamps due to timezone handling issues",
            "Backup created before removal to allow recovery if needed",
            "Symbol cache reset to allow re-validation of previously failed symbols",
            "Re-download data from IB to get clean, timezone-aware data",
            "Use the data API or CLI to fetch fresh data with proper UTC timestamps",
        ],
    }

    summary_file = backup_dir / "cleanup_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"📄 Created cleanup summary: {summary_file}")


def main():
    """Main cleanup procedure."""
    print("🧹 Starting Data Cleanup for Timezone-Poisoned Files")
    print("=" * 60)

    project_root = get_project_root()
    data_dir = project_root / "data"

    if not data_dir.exists():
        print("ℹ️  No data directory found. Nothing to clean up.")
        return

    # Step 1: Create backup directory
    print("\n📁 Creating backup directory...")
    backup_dir = create_backup_directory()
    print(f"✅ Backup directory created: {backup_dir}")

    # Step 2: Backup data files
    print("\n💾 Backing up data files...")
    backed_up_files = backup_data_files(data_dir, backup_dir)

    if not backed_up_files:
        print("ℹ️  No CSV data files found to backup.")
    else:
        print(f"✅ Backed up {len(backed_up_files)} data files")

    # Step 3: Backup symbol cache
    print("\n💾 Backing up symbol cache...")
    cache_backed_up = backup_symbol_cache(data_dir, backup_dir)

    # Step 4: Reset symbol cache (clear failed symbols)
    print("\n🔄 Resetting symbol cache...")
    reset_symbol_cache(data_dir)

    # Step 5: Remove poisoned data files
    if backed_up_files:
        print("\n🗑️  Removing poisoned data files...")
        remove_data_files(data_dir, backed_up_files)

    # Step 6: Create cleanup summary
    print("\n📄 Creating cleanup summary...")
    create_cleanup_summary(backup_dir, backed_up_files, cache_backed_up)

    # Final instructions
    print("\n" + "=" * 60)
    print("✅ CLEANUP COMPLETE!")
    print("\n📋 NEXT STEPS:")
    print("1. Use the data API or CLI to re-download fresh data from IB")
    print("2. The new data will use proper UTC timestamps via TimestampManager")
    print("3. Symbol validation will retry previously failed symbols")
    print("4. Charts should now show correct market opening times")
    print(f"\n💾 Backup Location: {backup_dir}")
    print("   (Can be restored if needed)")
    print("\n🎯 Example commands to re-download data:")
    print("   # Via CLI:")
    print("   uv run python -m ktrdr.cli.commands fetch MSFT 1h --days 90")
    print("   # Via API:")
    print("   curl -X POST 'http://localhost:8000/api/v1/data/load' \\")
    print("        -H 'Content-Type: application/json' \\")
    print('        -d \'{"symbol": "MSFT", "timeframe": "1h", "days": 90}\'')


if __name__ == "__main__":
    main()
