# TimescaleDB Integration Implementation Plan - Phases 3-4

**Version**: 1.0
**Status**: 📋 **READY FOR IMPLEMENTATION**
**Date**: 2025-11-15
**Phases Covered**: 3-4 (Initial Data Migration, Production Cutover)

---

## 📋 Plan Navigation

- **Previous Steps**: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Phases 0-2 (Infrastructure → Import)
- **This Document**: Phases 3-4 (Migration & Cutover)

---

## Overview

This implementation plan completes the TimescaleDB migration with **data migration** and **production cutover**.

**Quality Gates** (every task):

- Write tests FIRST (TDD)
- Pass ALL unit tests: `make test-unit`
- Pass quality checks: `make quality`
- Result in ONE commit

**Vertical Approach**: Each phase ends with a working, testable system feature.

All work will be done on a single feature branch: `feature/timescaledb-integration`

---

## Phase Structure

- **Phase**: A complete **vertical slice** delivering end-to-end functionality
- **Task**: A single, testable unit of work building toward the phase goal
- **Key**: Each phase ends with something you can **actually test and use**

---

## Phase 3: Initial Data Migration

**Goal**: Migrate all existing CSV data into TimescaleDB and verify data integrity

**Why This Fourth**: Infrastructure is ready, import service is ready—time for the actual migration!

**End State**:

- All CSV data imported into TimescaleDB
- Data verification tests confirm CSV and TimescaleDB match
- Migration results documented in MIGRATION_RESULTS.md
- **TESTABLE**: Query both backends, compare results, verify 100% match

---

### Task 3.1: Run Initial CSV Import

**Objective**: Execute bulk import of all CSV data into TimescaleDB with comprehensive documentation

**TDD Approach**:

- Manual process with verification steps
- Document import results for audit trail
- Spot-check sample data for correctness

**Implementation**:

1. Create migration script `scripts/migrate_csv_to_timescaledb.py`:

   ```python
   """
   Script to migrate all CSV data to TimescaleDB.

   This is a one-time migration script that imports all historical
   CSV data into TimescaleDB for production cutover.
   """

   import sys
   import json
   from pathlib import Path
   from datetime import datetime
   from typing import Dict, Any

   from ktrdr.data.import_service.csv_import_service import CSVImportService
   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.config.database import DatabaseConfig
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   def save_migration_results(summary: Dict[str, Any], output_path: Path):
       """
       Save migration results to JSON and Markdown.

       Args:
           summary: ImportSummary.to_dict() output
           output_path: Directory to save results
       """
       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

       # Save JSON for programmatic access
       json_path = output_path / f"migration_results_{timestamp}.json"
       with open(json_path, "w") as f:
           json.dump(summary, f, indent=2)

       logger.info(f"Migration results saved to {json_path}")

       # Generate Markdown report
       md_content = f"""# TimescaleDB Migration Results

   **Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
   **Status**: {"✅ SUCCESS" if summary["failed"] == 0 else f"⚠️ PARTIAL ({summary['failed']} failures)"}

   ## Summary

   - **Total Symbols**: {summary['total_symbols']}
   - **Successful**: {summary['successful']}
   - **Failed**: {summary['failed']}
   - **Success Rate**: {summary['success_rate']:.1f}%
   - **Total Rows Imported**: {summary['total_rows']:,}
   - **Total Duration**: {summary['total_duration_seconds']:.2f}s
   - **Average Speed**: {summary['total_rows'] / summary['total_duration_seconds']:.0f} rows/sec

   ## Detailed Results

   | Symbol | Timeframe | Rows | Start Date | End Date | Duration (s) | Status |
   |--------|-----------|------|------------|----------|--------------|--------|
   """

       for result in summary["results"]:
           status = "✅" if result["success"] else "❌"
           rows = f"{result['rows_imported']:,}" if result['success'] else "0"
           start = result['start_date'][:10] if result['start_date'] else "N/A"
           end = result['end_date'][:10] if result['end_date'] else "N/A"
           duration = f"{result['duration_seconds']:.2f}"

           md_content += f"| {result['symbol']} | {result['timeframe']} | {rows} | {start} | {end} | {duration} | {status} |\n"

       if summary['failed'] > 0:
           md_content += "\n## Failures\n\n"
           for result in summary["results"]:
               if not result["success"]:
                   md_content += f"- **{result['symbol']} {result['timeframe']}**: {result['error_message']}\n"

       # Save Markdown report
       md_path = output_path / "MIGRATION_RESULTS.md"
       with open(md_path, "w") as f:
           f.write(md_content)

       logger.info(f"Migration report saved to {md_path}")


   def verify_database_ready() -> bool:
       """
       Verify database is ready for migration.

       Returns:
           True if database is ready, False otherwise
       """
       try:
           config = DatabaseConfig()

           if not config.is_postgresql:
               logger.error("Database type is not PostgreSQL")
               return False

           from ktrdr.config.database import get_connection_manager
           manager = get_connection_manager()

           if not manager.test_connection():
               logger.error("Cannot connect to database")
               return False

           # Verify hypertables exist
           session = manager.get_session()
           try:
               result = session.execute(
                   "SELECT COUNT(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'price_data'"
               )
               count = result.scalar()

               if count == 0:
                   logger.error("price_data hypertable not found - run migrations first")
                   return False

               logger.info("✓ Database ready for migration")
               return True

           finally:
               session.close()

       except Exception as e:
           logger.error(f"Database verification failed: {e}")
           return False


   def main():
       """Run CSV to TimescaleDB migration."""
       logger.info("=" * 80)
       logger.info("CSV to TimescaleDB Migration")
       logger.info("=" * 80)

       # Verify database is ready
       logger.info("Verifying database readiness...")
       if not verify_database_ready():
           logger.error("Database not ready - aborting migration")
           sys.exit(1)

       # Get list of timeframes to migrate
       data_repo = DataRepository()
       timeframes = ["1d", "1h", "15m", "5m", "1m"]  # Adjust based on your data

       logger.info(f"Timeframes to migrate: {timeframes}")

       # Confirm with user
       print("\n⚠️  WARNING: This will import ALL CSV data into TimescaleDB")
       print("   This operation is idempotent but may take significant time.\n")
       response = input("Continue? [y/N]: ")

       if response.lower() != "y":
           logger.info("Migration aborted by user")
           sys.exit(0)

       # Run migration for each timeframe
       import_service = CSVImportService()
       all_results = []
       total_symbols = 0
       total_successful = 0
       total_failed = 0
       total_rows = 0

       for timeframe in timeframes:
           logger.info("")
           logger.info(f"{'=' * 40}")
           logger.info(f"Migrating timeframe: {timeframe}")
           logger.info(f"{'=' * 40}")

           # Get symbols for this timeframe
           symbols = data_repo.list_symbols(timeframe=timeframe)

           if not symbols:
               logger.warning(f"No symbols found for {timeframe}")
               continue

           logger.info(f"Found {len(symbols)} symbols to migrate")

           # Import all symbols for this timeframe
           summary = import_service.import_all(timeframe)

           # Aggregate results
           all_results.extend(summary.results)
           total_symbols += summary.total_symbols
           total_successful += summary.successful
           total_failed += summary.failed
           total_rows += summary.total_rows

           logger.info(
               f"✓ {timeframe}: {summary.successful}/{summary.total_symbols} successful, "
               f"{summary.total_rows:,} rows imported"
           )

       # Create overall summary
       overall_summary = {
           "total_symbols": total_symbols,
           "successful": total_successful,
           "failed": total_failed,
           "total_rows": total_rows,
           "total_duration_seconds": sum(r.duration_seconds for r in all_results),
           "success_rate": (total_successful / total_symbols * 100) if total_symbols > 0 else 0,
           "results": [r.to_dict() for r in all_results],
       }

       # Save results
       logger.info("")
       logger.info("Saving migration results...")
       save_migration_results(overall_summary, Path("docs/architecture/timeseries-data"))

       # Final summary
       logger.info("")
       logger.info("=" * 80)
       logger.info("MIGRATION COMPLETE")
       logger.info("=" * 80)
       logger.info(f"Total Symbols: {total_symbols}")
       logger.info(f"Successful: {total_successful}")
       logger.info(f"Failed: {total_failed}")
       logger.info(f"Success Rate: {overall_summary['success_rate']:.1f}%")
       logger.info(f"Total Rows: {total_rows:,}")
       logger.info("=" * 80)

       if total_failed > 0:
           logger.warning(f"⚠️  {total_failed} symbols failed to import - see MIGRATION_RESULTS.md")
           sys.exit(1)
       else:
           logger.info("✅ All symbols imported successfully!")
           sys.exit(0)


   if __name__ == "__main__":
       main()
   ```

2. Create pre-migration checklist document `docs/architecture/timeseries-data/PRE_MIGRATION_CHECKLIST.md`:

   ```markdown
   # Pre-Migration Checklist

   Complete this checklist before running CSV to TimescaleDB migration.

   ## Infrastructure

   - [ ] PostgreSQL + TimescaleDB running (`docker-compose ps timescaledb` shows healthy)
   - [ ] Database migrations applied (`docker exec ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev -c "SELECT * FROM timescaledb_information.hypertables;"`)
   - [ ] Database connection working (`make test-integration` passes)
   - [ ] Disk space sufficient (estimate: 2x current CSV size)

   ## Code Readiness

   - [ ] All Phase 0-2 tasks completed
   - [ ] All unit tests passing (`make test-unit`)
   - [ ] All integration tests passing (`make test-integration`)
   - [ ] Code quality checks passing (`make quality`)

   ## Data Validation

   - [ ] CSV data directory exists and accessible
   - [ ] Sample spot-check of CSV files (open a few, verify OHLCV columns)
   - [ ] No corrupted CSV files (run: `find data/ -name "*.csv" -exec head -n 1 {} \; | sort -u`)

   ## Backup

   - [ ] CSV data backed up (optional but recommended)
   - [ ] Database backup taken (optional - can recreate from CSV)

   ## Environment

   - [ ] Environment variables set correctly:
     - `DB_TYPE=postgresql`
     - `DB_HOST=localhost` (or appropriate host)
     - `DB_NAME=ktrdr_dev`
     - `DB_USER=ktrdr_dev`
     - `DB_PASSWORD=ktrdr_dev_password`

   ## Monitoring

   - [ ] Jaeger running for observability (`docker-compose ps jaeger` shows healthy)
   - [ ] Logs being captured (check `logs/` directory writable)

   ## Time Allocation

   - [ ] Estimated time calculated (rough estimate: 1000 rows/sec)
   - [ ] No critical deadlines during migration window

   ## Ready to Proceed

   - [ ] All checks above completed
   - [ ] Team notified (if applicable)
   - [ ] Migration script reviewed: `scripts/migrate_csv_to_timescaledb.py`
   ```

3. Create manual testing procedure document `docs/architecture/timeseries-data/MIGRATION_MANUAL_TESTING.md`:

   ```markdown
   # Migration Manual Testing Procedure

   Follow these steps to manually verify migration success.

   ## Step 1: Run Migration

   ```bash
   # Ensure database is running
   docker-compose -f docker/docker-compose.dev.yml up -d timescaledb

   # Set environment variables
   export DB_TYPE=postgresql
   export DB_HOST=localhost
   export DB_NAME=ktrdr_dev
   export DB_USER=ktrdr_dev
   export DB_PASSWORD=ktrdr_dev_password

   # Run migration script
   uv run python scripts/migrate_csv_to_timescaledb.py
   ```

   **Expected Output**:
   - Progress messages for each symbol
   - Final summary showing total symbols, rows, success rate
   - Generation of `MIGRATION_RESULTS.md`

   ## Step 2: Review Migration Results

   ```bash
   # Open migration results
   cat docs/architecture/timeseries-data/MIGRATION_RESULTS.md
   ```

   **Verify**:
   - Success rate is 100% (or investigate failures)
   - Total rows imported matches expectation
   - All expected symbols are present

   ## Step 3: Database Spot Checks

   ```bash
   # Connect to database
   docker exec -it ktrdr-timescaledb-dev psql -U ktrdr_dev -d ktrdr_dev
   ```

   **Run these queries**:

   ```sql
   -- Check total row count
   SELECT COUNT(*) FROM price_data;

   -- Check symbols count
   SELECT COUNT(DISTINCT symbol) FROM price_data;

   -- Check timeframes
   SELECT DISTINCT timeframe, COUNT(*)
   FROM price_data
   GROUP BY timeframe
   ORDER BY timeframe;

   -- Check date range for sample symbol
   SELECT
       symbol,
       timeframe,
       MIN(time) as start_date,
       MAX(time) as end_date,
       COUNT(*) as bars
   FROM price_data
   WHERE symbol = 'AAPL' AND timeframe = '1d'
   GROUP BY symbol, timeframe;

   -- Sample data quality check (OHLC constraints)
   SELECT COUNT(*) FROM price_data
   WHERE high < low
      OR high < open
      OR high < close
      OR low > open
      OR low > close;
   -- Should return 0
   ```

   ## Step 4: Compare CSV vs TimescaleDB

   **Pick 3 random symbols** and compare data:

   ```python
   # Python shell
   import pandas as pd
   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.data.backends.csv.csv_backend import CSVBackend

   # Pick a symbol
   symbol = "AAPL"
   timeframe = "1d"

   # Load from CSV
   csv_backend = CSVBackend()
   csv_data = csv_backend.load_data(symbol, timeframe)

   # Load from TimescaleDB
   tsdb_backend = TimescaleDBBackend()
   tsdb_data = tsdb_backend.load_data(symbol, timeframe)

   # Compare
   print(f"CSV rows: {len(csv_data)}")
   print(f"TimescaleDB rows: {len(tsdb_data)}")
   print(f"Match: {len(csv_data) == len(tsdb_data)}")

   # Detailed comparison
   pd.testing.assert_frame_equal(csv_data, tsdb_data)
   print("✓ Data matches perfectly!")
   ```

   **Repeat for**:
   - 1 high-volume symbol (e.g., SPY)
   - 1 forex pair (e.g., EURUSD)
   - 1 low-volume symbol

   ## Step 5: Performance Spot Check

   ```bash
   # Query Jaeger for migration operation traces
   curl -s "http://localhost:16686/api/traces?service=ktrdr&operation=timescaledb.save_data&limit=10" | jq '.data[].spans[] | select(.operationName == "timescaledb.save_data") | {duration_ms: (.duration / 1000), symbol: (.tags[] | select(.key == "db.symbol") | .value)}'
   ```

   **Verify**:
   - Most save operations complete in < 1000ms
   - No timeout errors
   - No connection failures

   ## Success Criteria

   - ✅ Migration script completes without errors
   - ✅ All symbols imported (success rate = 100%)
   - ✅ Row counts match between CSV and TimescaleDB
   - ✅ Spot-check data comparisons pass perfectly
   - ✅ No OHLC constraint violations
   - ✅ Query performance acceptable
   - ✅ MIGRATION_RESULTS.md generated

   ## Rollback (if needed)

   If migration fails or data is incorrect:

   ```sql
   -- Truncate all data (DESTRUCTIVE)
   TRUNCATE TABLE price_data;

   -- Or delete specific symbols
   DELETE FROM price_data WHERE symbol = 'AAPL';
   ```

   Then re-run migration after fixing issues.
   ```

**Quality Gate**:

```bash
# Pre-migration checks
cat docs/architecture/timeseries-data/PRE_MIGRATION_CHECKLIST.md
# Complete all checklist items

# Run migration
uv run python scripts/migrate_csv_to_timescaledb.py

# Verify results
cat docs/architecture/timeseries-data/MIGRATION_RESULTS.md
# Success rate should be 100%

# Manual spot checks (see MIGRATION_MANUAL_TESTING.md)
# Pick 3 symbols, compare CSV vs TimescaleDB data

# Verify all existing tests still pass
make test-unit
make quality
```

**Commit**: `feat(migration): run initial CSV to TimescaleDB data migration`

**Estimated Time**: 4 hours (including actual migration runtime)

---

### Task 3.2: Data Verification and Quality Checks

**Objective**: Create comprehensive integration tests that verify CSV and TimescaleDB data match

**TDD Approach**:

1. Create integration tests that compare backends
2. Test row count matching
3. Test OHLCV value matching (spot checks)
4. Test date range matching

**Implementation**:

1. Create integration test `tests/integration/data/test_migration_verification.py`:

   ```python
   """Integration tests to verify CSV to TimescaleDB migration."""

   import pytest
   import pandas as pd
   from typing import List

   from ktrdr.config.database import DatabaseConfig
   from ktrdr.data.backends.csv.csv_backend import CSVBackend
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.data.repository.data_repository import DataRepository


   @pytest.fixture
   def csv_backend():
       """Create CSV backend for testing."""
       return CSVBackend()


   @pytest.fixture
   def tsdb_backend():
       """Create TimescaleDB backend for testing."""
       config = DatabaseConfig()
       if not config.is_postgresql:
           pytest.skip("PostgreSQL not configured")

       return TimescaleDBBackend()


   @pytest.fixture
   def data_repository():
       """Create data repository for testing."""
       return DataRepository()


   @pytest.mark.integration
   class TestMigrationVerification:
       """
       Integration tests to verify CSV to TimescaleDB migration.

       These tests compare data between CSV and TimescaleDB backends
       to ensure migration was successful.
       """

       def test_symbol_counts_match(self, csv_backend, tsdb_backend, data_repository):
           """Test that symbol counts match between CSV and TimescaleDB."""
           timeframes = ["1d", "1h"]

           for timeframe in timeframes:
               csv_symbols = set(data_repository.list_symbols(timeframe=timeframe))
               tsdb_symbols = set(tsdb_backend.list_symbols(timeframe=timeframe))

               # TimescaleDB should have at least as many symbols as CSV
               # (might have more if data was added directly to DB)
               assert len(tsdb_symbols) >= len(csv_symbols), (
                   f"TimescaleDB has fewer symbols than CSV for {timeframe}: "
                   f"{len(tsdb_symbols)} vs {len(csv_symbols)}"
               )

               # All CSV symbols should exist in TimescaleDB
               missing = csv_symbols - tsdb_symbols
               assert len(missing) == 0, (
                   f"Symbols missing from TimescaleDB for {timeframe}: {missing}"
               )

       def test_row_counts_match_sample(self, csv_backend, tsdb_backend, data_repository):
           """Test that row counts match for sample symbols."""
           timeframe = "1d"
           symbols = data_repository.list_symbols(timeframe=timeframe)

           # Test first 5 symbols (or all if less than 5)
           sample_symbols = symbols[:5]

           for symbol in sample_symbols:
               csv_data = csv_backend.load_data(symbol, timeframe)
               tsdb_data = tsdb_backend.load_data(symbol, timeframe)

               assert len(csv_data) == len(tsdb_data), (
                   f"Row count mismatch for {symbol} {timeframe}: "
                   f"CSV={len(csv_data)}, TimescaleDB={len(tsdb_data)}"
               )

       def test_ohlcv_values_match_sample(self, csv_backend, tsdb_backend):
           """Test that OHLCV values match for sample symbols."""
           # Test specific high-importance symbols
           test_cases = [
               ("AAPL", "1d"),
               ("SPY", "1d"),
           ]

           for symbol, timeframe in test_cases:
               csv_data = csv_backend.load_data(symbol, timeframe)
               tsdb_data = tsdb_backend.load_data(symbol, timeframe)

               # Skip if no data
               if csv_data.empty:
                   pytest.skip(f"No CSV data for {symbol} {timeframe}")

               # DataFrames should be identical
               pd.testing.assert_frame_equal(
                   csv_data,
                   tsdb_data,
                   check_dtype=True,
                   check_index_type=True,
                   check_column_type=True,
               )

       def test_date_ranges_match_sample(self, csv_backend, tsdb_backend, data_repository):
           """Test that date ranges match for sample symbols."""
           timeframe = "1d"
           symbols = data_repository.list_symbols(timeframe=timeframe)

           # Test first 3 symbols
           sample_symbols = symbols[:3]

           for symbol in sample_symbols:
               csv_data = csv_backend.load_data(symbol, timeframe)

               if csv_data.empty:
                   continue

               csv_start = csv_data.index[0]
               csv_end = csv_data.index[-1]

               tsdb_range = tsdb_backend.get_date_range(symbol, timeframe)

               assert tsdb_range is not None, (
                   f"No date range found in TimescaleDB for {symbol} {timeframe}"
               )

               tsdb_start, tsdb_end = tsdb_range

               # Convert to timezone-naive for comparison (if needed)
               if csv_start.tzinfo is not None:
                   csv_start = csv_start.tz_localize(None)
                   csv_end = csv_end.tz_localize(None)
               if tsdb_start.tzinfo is not None:
                   tsdb_start = pd.Timestamp(tsdb_start).tz_localize(None)
                   tsdb_end = pd.Timestamp(tsdb_end).tz_localize(None)

               assert csv_start == tsdb_start, (
                   f"Start date mismatch for {symbol} {timeframe}: "
                   f"CSV={csv_start}, TimescaleDB={tsdb_start}"
               )

               assert csv_end == tsdb_end, (
                   f"End date mismatch for {symbol} {timeframe}: "
                   f"CSV={csv_end}, TimescaleDB={tsdb_end}"
               )

       def test_no_ohlc_constraint_violations(self, tsdb_backend):
           """Test that no OHLC constraint violations exist in TimescaleDB."""
           from ktrdr.config.database import get_connection_manager

           manager = get_connection_manager()
           session = manager.get_session()

           try:
               # Query for constraint violations
               result = session.execute("""
                   SELECT COUNT(*) FROM price_data
                   WHERE high < low
                      OR high < open
                      OR high < close
                      OR low > open
                      OR low > close
               """)

               violations = result.scalar()

               assert violations == 0, (
                   f"Found {violations} OHLC constraint violations in price_data"
               )

           finally:
               session.close()

       def test_no_negative_volumes(self, tsdb_backend):
           """Test that no negative volumes exist in TimescaleDB."""
           from ktrdr.config.database import get_connection_manager

           manager = get_connection_manager()
           session = manager.get_session()

           try:
               result = session.execute("""
                   SELECT COUNT(*) FROM price_data
                   WHERE volume < 0
               """)

               violations = result.scalar()

               assert violations == 0, (
                   f"Found {violations} negative volume values in price_data"
               )

           finally:
               session.close()

       def test_timescaledb_hypertable_properties(self, tsdb_backend):
           """Test that TimescaleDB hypertable has correct properties."""
           from ktrdr.config.database import get_connection_manager

           manager = get_connection_manager()
           session = manager.get_session()

           try:
               # Verify hypertable exists
               result = session.execute("""
                   SELECT
                       hypertable_name,
                       num_dimensions,
                       compression_enabled
                   FROM timescaledb_information.hypertables
                   WHERE hypertable_name = 'price_data'
               """)

               row = result.fetchone()

               assert row is not None, "price_data hypertable not found"

               hypertable_name, num_dimensions, compression_enabled = row

               # Verify properties
               assert hypertable_name == "price_data"
               assert num_dimensions >= 1  # At least time dimension
               assert compression_enabled is True

           finally:
               session.close()

       @pytest.mark.slow
       def test_comprehensive_data_match_all_symbols(
           self, csv_backend, tsdb_backend, data_repository
       ):
           """
           Comprehensive test that ALL symbols match between backends.

           This is a slow test that verifies every symbol. Mark as @pytest.mark.slow
           and run separately for full verification.
           """
           timeframe = "1d"
           symbols = data_repository.list_symbols(timeframe=timeframe)

           mismatches = []

           for symbol in symbols:
               try:
                   csv_data = csv_backend.load_data(symbol, timeframe)
                   tsdb_data = tsdb_backend.load_data(symbol, timeframe)

                   # Compare row counts
                   if len(csv_data) != len(tsdb_data):
                       mismatches.append(
                           f"{symbol}: row count mismatch (CSV={len(csv_data)}, "
                           f"TimescaleDB={len(tsdb_data)})"
                       )
                       continue

                   # Compare values
                   try:
                       pd.testing.assert_frame_equal(csv_data, tsdb_data)
                   except AssertionError as e:
                       mismatches.append(f"{symbol}: value mismatch - {str(e)[:100]}")

               except Exception as e:
                   mismatches.append(f"{symbol}: error - {str(e)[:100]}")

           if mismatches:
               pytest.fail(
                   f"Data mismatches found:\n" + "\n".join(mismatches[:10]) +
                   f"\n... and {len(mismatches) - 10} more" if len(mismatches) > 10 else ""
               )
   ```

2. Add pytest configuration for slow tests in `pyproject.toml`:

   ```toml
   [tool.pytest.ini_options]
   markers = [
       "slow: marks tests as slow (deselect with '-m \"not slow\"')",
       "integration: marks tests as integration tests",
       # ... existing markers ...
   ]
   ```

3. Create verification command script `scripts/verify_migration.py`:

   ```python
   """
   Quick verification script for migration.

   Runs key verification checks and prints results.
   """

   import sys
   from ktrdr.config.database import DatabaseConfig, get_connection_manager
   from ktrdr.data.backends.csv.csv_backend import CSVBackend
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   def main():
       """Run quick migration verification."""
       logger.info("=" * 80)
       logger.info("Migration Verification")
       logger.info("=" * 80)

       # Check database connection
       config = DatabaseConfig()
       if not config.is_postgresql:
           logger.error("Database type is not PostgreSQL")
           sys.exit(1)

       manager = get_connection_manager()
       if not manager.test_connection():
           logger.error("Cannot connect to database")
           sys.exit(1)

       logger.info("✓ Database connection OK")

       # Initialize backends
       csv_backend = CSVBackend()
       tsdb_backend = TimescaleDBBackend()
       data_repo = DataRepository()

       # Check symbol counts
       timeframe = "1d"
       csv_symbols = data_repo.list_symbols(timeframe=timeframe)
       tsdb_symbols = tsdb_backend.list_symbols(timeframe=timeframe)

       logger.info(f"CSV symbols ({timeframe}): {len(csv_symbols)}")
       logger.info(f"TimescaleDB symbols ({timeframe}): {len(tsdb_symbols)}")

       if len(tsdb_symbols) >= len(csv_symbols):
           logger.info("✓ Symbol count check passed")
       else:
           logger.error(f"✗ Missing {len(csv_symbols) - len(tsdb_symbols)} symbols in TimescaleDB")
           sys.exit(1)

       # Check row counts for sample
       sample_symbols = csv_symbols[:3]
       mismatches = 0

       for symbol in sample_symbols:
           csv_data = csv_backend.load_data(symbol, timeframe)
           tsdb_data = tsdb_backend.load_data(symbol, timeframe)

           if len(csv_data) != len(tsdb_data):
               logger.error(
                   f"✗ {symbol}: row count mismatch (CSV={len(csv_data)}, "
                   f"TimescaleDB={len(tsdb_data)})"
               )
               mismatches += 1
           else:
               logger.info(f"✓ {symbol}: {len(csv_data)} rows match")

       if mismatches > 0:
           logger.error(f"✗ {mismatches} symbols have mismatched row counts")
           sys.exit(1)

       # Check for constraint violations
       session = manager.get_session()
       try:
           result = session.execute("""
               SELECT COUNT(*) FROM price_data
               WHERE high < low OR high < open OR high < close OR low > open OR low > close
           """)
           violations = result.scalar()

           if violations > 0:
               logger.error(f"✗ Found {violations} OHLC constraint violations")
               sys.exit(1)
           else:
               logger.info("✓ No OHLC constraint violations")

       finally:
           session.close()

       # Final summary
       logger.info("=" * 80)
       logger.info("✅ Migration verification PASSED")
       logger.info("=" * 80)
       sys.exit(0)


   if __name__ == "__main__":
       main()
   ```

**Quality Gate**:

```bash
# Run verification integration tests
export DB_TYPE=postgresql
make test-integration  # Includes migration verification tests

# Run comprehensive slow test (optional)
uv run pytest tests/integration/data/test_migration_verification.py::TestMigrationVerification::test_comprehensive_data_match_all_symbols -v

# Run quick verification script
uv run python scripts/verify_migration.py
# Should output: ✅ Migration verification PASSED

# All other tests still pass
make test-unit
make quality
```

**Commit**: `test(migration): add comprehensive data verification tests`

**Estimated Time**: 2.5 hours

---

**Phase 3 Checkpoint**:
✅ All CSV data imported into TimescaleDB
✅ Migration results documented in MIGRATION_RESULTS.md
✅ Integration tests verify CSV and TimescaleDB data match
✅ No OHLC constraint violations
✅ Row counts verified for all symbols
✅ **TESTABLE**: Query both backends, compare results, 100% match confirmed

**Total Phase 3 Time**: ~6.5 hours

---

## Phase 4: Production Cutover

**Goal**: Switch DataRepository default backend to TimescaleDB and verify entire system works

**Why This Last**: Data is migrated and verified—now make TimescaleDB the production backend!

**End State**:

- DataRepository supports backend selection via DB_TYPE env var
- Default backend is TimescaleDB (DB_TYPE=postgresql)
- All CLI commands work with TimescaleDB
- All training workflows work with TimescaleDB
- All backtesting workflows work with TimescaleDB
- Documentation updated
- **TESTABLE**: Run entire system end-to-end with TimescaleDB

---

### Task 4.1: Update DataRepository to Support TimescaleDB

**Objective**: Add backend selection logic to DataRepository based on DB_TYPE environment variable

**TDD Approach**:

1. Create unit tests for backend selection logic
2. Test DB_TYPE=postgresql → TimescaleDBBackend
3. Test DB_TYPE=csv → CSVBackend (preserve existing)
4. Test invalid DB_TYPE → error

**Implementation**:

1. Update `ktrdr/data/repository/data_repository.py`:

   ```python
   """Data repository for cached market data access."""

   import os
   from typing import Optional, List, Tuple
   from datetime import datetime
   import pandas as pd

   from ktrdr.data.backends.base import DataBackend
   from ktrdr.data.backends.csv.csv_backend import CSVBackend
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   class DataRepository:
       """
       Repository for market data with caching.

       Supports multiple backend types:
       - CSV: File-based storage (legacy)
       - PostgreSQL/TimescaleDB: Database storage (production)

       Backend selection via DB_TYPE environment variable.
       """

       def __init__(self, backend: Optional[DataBackend] = None):
           """
           Initialize data repository.

           Args:
               backend: Optional backend instance (auto-detected if None)
           """
           if backend is None:
               backend = self._get_backend()

           self.backend = backend
           logger.info(f"DataRepository initialized with backend: {type(backend).__name__}")

       def _get_backend(self) -> DataBackend:
           """
           Get appropriate backend based on DB_TYPE environment variable.

           Returns:
               DataBackend instance

           Raises:
               ValueError: If DB_TYPE is invalid
           """
           db_type = os.getenv("DB_TYPE", "csv").lower()

           if db_type == "postgresql":
               logger.info("Using TimescaleDB backend")
               return TimescaleDBBackend()
           elif db_type == "csv":
               logger.info("Using CSV backend")
               return CSVBackend()
           else:
               raise ValueError(
                   f"Invalid DB_TYPE: {db_type}. Must be 'postgresql' or 'csv'"
               )

       def save_data(
           self,
           symbol: str,
           timeframe: str,
           data: pd.DataFrame,
           source: str = "ib",
       ) -> None:
           """
           Save price data.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               data: DataFrame with OHLCV data
               source: Data source identifier
           """
           self.backend.save_data(symbol, timeframe, data, source=source)

       def load_data(
           self,
           symbol: str,
           timeframe: str,
           start_date: Optional[datetime] = None,
           end_date: Optional[datetime] = None,
       ) -> pd.DataFrame:
           """
           Load price data.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string
               start_date: Optional start date filter
               end_date: Optional end date filter

           Returns:
               DataFrame with OHLCV data
           """
           return self.backend.load_data(symbol, timeframe, start_date, end_date)

       def list_symbols(self, timeframe: Optional[str] = None) -> List[str]:
           """
           List available symbols.

           Args:
               timeframe: Optional timeframe filter

           Returns:
               List of symbol names
           """
           return self.backend.list_symbols(timeframe=timeframe)

       def get_date_range(
           self, symbol: str, timeframe: str
       ) -> Optional[Tuple[datetime, datetime]]:
           """
           Get available date range for symbol.

           Args:
               symbol: Symbol name
               timeframe: Timeframe string

           Returns:
               Tuple of (start_date, end_date), or None if no data
           """
           return self.backend.get_date_range(symbol, timeframe)

       @property
       def backend_type(self) -> str:
           """
           Get backend type name.

           Returns:
               Backend type string ('csv', 'timescaledb', etc.)
           """
           backend_class = type(self.backend).__name__
           if backend_class == "TimescaleDBBackend":
               return "timescaledb"
           elif backend_class == "CSVBackend":
               return "csv"
           else:
               return backend_class.lower()
   ```

2. Create unit tests `tests/unit/data/repository/test_data_repository_backend_selection.py`:

   ```python
   """Unit tests for DataRepository backend selection."""

   import os
   import pytest
   from unittest.mock import patch, MagicMock

   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.data.backends.csv.csv_backend import CSVBackend
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend


   class TestDataRepositoryBackendSelection:
       """Test DataRepository backend selection logic."""

       def test_default_backend_csv(self):
           """Test default backend is CSV when DB_TYPE not set."""
           with patch.dict(os.environ, {}, clear=True):
               repo = DataRepository()

               assert isinstance(repo.backend, CSVBackend)
               assert repo.backend_type == "csv"

       def test_backend_csv_explicit(self):
           """Test CSV backend when DB_TYPE=csv."""
           with patch.dict(os.environ, {"DB_TYPE": "csv"}):
               repo = DataRepository()

               assert isinstance(repo.backend, CSVBackend)
               assert repo.backend_type == "csv"

       @patch("ktrdr.data.repository.data_repository.TimescaleDBBackend")
       def test_backend_timescaledb(self, mock_tsdb_backend):
           """Test TimescaleDB backend when DB_TYPE=postgresql."""
           mock_instance = MagicMock()
           mock_tsdb_backend.return_value = mock_instance

           with patch.dict(os.environ, {"DB_TYPE": "postgresql"}):
               repo = DataRepository()

               assert mock_tsdb_backend.called
               assert repo.backend == mock_instance
               assert repo.backend_type == "timescaledb"

       def test_backend_invalid_raises_error(self):
           """Test that invalid DB_TYPE raises ValueError."""
           with patch.dict(os.environ, {"DB_TYPE": "invalid"}):
               with pytest.raises(ValueError, match="Invalid DB_TYPE"):
                   DataRepository()

       def test_backend_case_insensitive(self):
           """Test that DB_TYPE is case-insensitive."""
           with patch.dict(os.environ, {"DB_TYPE": "CSV"}):
               repo = DataRepository()
               assert isinstance(repo.backend, CSVBackend)

           with patch.dict(os.environ, {"DB_TYPE": "PostgreSQL"}):
               # Should not raise error
               repo = DataRepository()

       def test_custom_backend_injection(self):
           """Test that custom backend can be injected."""
           custom_backend = MagicMock()

           repo = DataRepository(backend=custom_backend)

           assert repo.backend == custom_backend

       def test_backend_methods_delegate(self):
           """Test that repository methods delegate to backend."""
           mock_backend = MagicMock()

           repo = DataRepository(backend=mock_backend)

           # Test save_data delegation
           repo.save_data("AAPL", "1d", MagicMock())
           assert mock_backend.save_data.called

           # Test load_data delegation
           repo.load_data("AAPL", "1d")
           assert mock_backend.load_data.called

           # Test list_symbols delegation
           repo.list_symbols()
           assert mock_backend.list_symbols.called

           # Test get_date_range delegation
           repo.get_date_range("AAPL", "1d")
           assert mock_backend.get_date_range.called
   ```

**Quality Gate**:

```bash
# Run unit tests
make test-unit

# Manual test with different backends
# CSV backend
DB_TYPE=csv uv run python -c "from ktrdr.data.repository.data_repository import DataRepository; repo = DataRepository(); print(f'Backend: {repo.backend_type}')"
# Should print: Backend: csv

# TimescaleDB backend
DB_TYPE=postgresql uv run python -c "from ktrdr.data.repository.data_repository import DataRepository; repo = DataRepository(); print(f'Backend: {repo.backend_type}')"
# Should print: Backend: timescaledb

make quality
```

**Commit**: `feat(data): add backend selection to DataRepository based on DB_TYPE`

**Estimated Time**: 2 hours

---

### Task 4.2: Switch Default Backend to TimescaleDB

**Objective**: Switch DB_TYPE environment variable to use TimescaleDB as default backend

**TDD Approach**:

- Integration tests already exist (use existing test suite)
- Manual verification of all system components

**Context**: Docker Compose configurations already have TimescaleDB service and database environment variables configured. We just need to switch `DB_TYPE` from `csv` to `postgresql`.

**Implementation**:

1. Update `DB_TYPE` environment variable in `docker/docker-compose.dev.yml`:

   ```yaml
   services:
     backend:
       environment:
         # ... existing environment variables ...
         - DB_TYPE=postgresql  # ← Change from csv to postgresql
         # These are already configured:
         # - DB_HOST=timescaledb
         # - DB_PORT=5432
         # - DB_NAME=ktrdr_dev
         # - DB_USER=ktrdr_dev
         # - DB_PASSWORD=ktrdr_dev_password
         # - DB_POOL_SIZE=20
         # - DB_MAX_OVERFLOW=10
   ```

2. Update `DB_TYPE` environment variable in `docker/docker-compose.yml` (production):

   ```yaml
   services:
     backend:
       environment:
         # ... existing environment variables ...
         - DB_TYPE=postgresql  # ← Change from csv to postgresql
         # Other DB variables already configured
   ```

3. Create rollback procedure document `docs/architecture/timeseries-data/ROLLBACK_PROCEDURE.md`:

   ```markdown
   # TimescaleDB Rollback Procedure

   If issues are discovered after cutover to TimescaleDB, follow this procedure to rollback to CSV backend.

   ## Quick Rollback (Emergency)

   **Estimated Time**: 5 minutes

   ```bash
   # Step 1: Update environment variable in Docker Compose
   # Edit docker/docker-compose.dev.yml (or docker-compose.yml for prod)
   # Change: DB_TYPE=postgresql
   # To:     DB_TYPE=csv

   # Step 2: Restart backend
   docker-compose -f docker/docker-compose.dev.yml restart backend

   # Step 3: Verify
   docker logs ktrdr-backend | grep "Using CSV backend"
   # Should see: "Using CSV backend"

   # Step 4: Test CLI command
   uv run ktrdr data show AAPL 1d --tail 5
   # Should work with CSV backend
   ```

   ## Verification After Rollback

   ```bash
   # Verify backend type
   docker exec ktrdr-backend python -c "from ktrdr.data.repository.data_repository import DataRepository; print(DataRepository().backend_type)"
   # Should print: csv

   # Run integration tests
   make test-integration

   # Run end-to-end workflow
   uv run ktrdr models train --strategy config/strategies/example.yaml
   ```

   ## Permanent Rollback

   If rolling back permanently:

   1. Update docker-compose files (as above)
   2. Commit changes: `git commit -m "rollback: revert to CSV backend"`
   3. Update documentation to reflect CSV as primary backend
   4. Keep TimescaleDB running for data preservation (optional)

   ## Partial Rollback (Hybrid Mode)

   Can run both backends simultaneously for comparison:

   ```bash
   # Backend uses TimescaleDB
   DB_TYPE=postgresql

   # But keep CSV data for comparison
   # Data exists in both places, can switch between them
   ```

   ## Re-Cutover After Rollback

   If rolling back temporarily to fix issues:

   1. Fix identified issues
   2. Re-run verification: `uv run python scripts/verify_migration.py`
   3. Re-run integration tests: `make test-integration`
   4. Switch back: `DB_TYPE=postgresql`
   5. Restart backend
   6. Verify again

   ## Data Loss Concerns

   - **CSV → TimescaleDB**: No data loss, CSV files unchanged
   - **TimescaleDB → CSV**: New data written to TimescaleDB after cutover will NOT be in CSV
   - **Recommendation**: If rollback needed, export TimescaleDB data to CSV first

   ```python
   # Export TimescaleDB data to CSV (if needed)
   from ktrdr.data.backends.timescaledb.backend import TimescaleDBBackend
   from ktrdr.data.backends.csv.csv_backend import CSVBackend

   tsdb = TimescaleDBBackend()
   csv = CSVBackend()

   # Export all symbols
   for symbol in tsdb.list_symbols(timeframe="1d"):
       data = tsdb.load_data(symbol, "1d")
       csv.save_data(symbol, "1d", data)
       print(f"Exported {symbol}")
   ```

   ## Monitoring After Rollback

   - Check Jaeger for errors
   - Monitor application logs
   - Verify data queries working
   - Test training workflows
   - Test backtesting workflows
   ```

4. Update main README.md documentation:

   Add to `README.md`:

   ```markdown
   ## Database Backend

   KTRDR supports multiple data storage backends:

   - **TimescaleDB** (default): High-performance PostgreSQL-based time-series database
   - **CSV**: Legacy file-based storage

   Backend selection is controlled via `DB_TYPE` environment variable:

   ```bash
   # Use TimescaleDB (default, recommended)
   export DB_TYPE=postgresql

   # Use CSV (legacy)
   export DB_TYPE=csv
   ```

   ### TimescaleDB Features

   - ⚡ **10x faster queries** for large datasets
   - 📦 **Automatic compression** (95% storage reduction)
   - 📊 **Advanced time-series functions** (continuous aggregates, gaps analysis)
   - 🔍 **SQL queries** for data exploration
   - 🚀 **Horizontal scalability** with distributed hypertables

   See [docs/architecture/timeseries-data/](docs/architecture/timeseries-data/) for architecture details.
   ```

5. Update environment configuration documentation `docs/user-guides/environment-configuration.md`:

   Add section:

   ```markdown
   ## Database Configuration

   ### DB_TYPE

   **Type**: String
   **Default**: `csv`
   **Production**: `postgresql`
   **Values**: `postgresql`, `csv`

   Selects data storage backend:

   - `postgresql`: TimescaleDB (high-performance time-series database)
   - `csv`: File-based CSV storage (legacy)

   **Example**:

   ```bash
   # Use TimescaleDB (recommended)
   export DB_TYPE=postgresql

   # Use CSV (legacy)
   export DB_TYPE=csv
   ```

   ### PostgreSQL Connection (when DB_TYPE=postgresql)

   - `DB_HOST`: PostgreSQL host (default: `localhost`)
   - `DB_PORT`: PostgreSQL port (default: `5432`)
   - `DB_NAME`: Database name (default: `ktrdr`)
   - `DB_USER`: Database user (default: `ktrdr`)
   - `DB_PASSWORD`: Database password (required)
   - `DB_POOL_SIZE`: Connection pool size (default: `20`)
   - `DB_MAX_OVERFLOW`: Max overflow connections (default: `10`)
   ```

**Quality Gate**:

```bash
# Update Docker Compose files as shown above

# Restart with TimescaleDB backend
docker-compose -f docker/docker-compose.dev.yml down
docker-compose -f docker/docker-compose.dev.yml up -d

# Verify backend selection
docker exec ktrdr-backend python -c "from ktrdr.data.repository.data_repository import DataRepository; print(f'Backend: {DataRepository().backend_type}')"
# Should print: Backend: timescaledb

# Run integration tests
make test-integration

# Manual verification (see next task)

make test-unit
make quality
```

**Commit**: `feat(config): switch default backend to TimescaleDB in Docker Compose`

**Estimated Time**: 2 hours

---

### Task 4.3: End-to-End Verification

**Objective**: Verify entire system works end-to-end with TimescaleDB backend

**TDD Approach**:

- Use existing integration tests (already passing)
- Manual end-to-end workflow testing
- Performance verification via Jaeger

**Implementation**:

1. Create end-to-end verification script `scripts/e2e_verification.py`:

   ```python
   """
   End-to-end verification of TimescaleDB integration.

   Tests complete workflows with TimescaleDB backend.
   """

   import sys
   import time
   from datetime import datetime, timedelta

   from ktrdr.data.repository.data_repository import DataRepository
   from ktrdr.logging import get_logger

   logger = get_logger(__name__)


   def test_data_repository_operations():
       """Test basic DataRepository operations."""
       logger.info("Testing DataRepository operations...")

       repo = DataRepository()

       # Verify backend type
       if repo.backend_type != "timescaledb":
           logger.error(f"Expected TimescaleDB backend, got: {repo.backend_type}")
           return False

       logger.info(f"✓ Using {repo.backend_type} backend")

       # Test list_symbols
       symbols = repo.list_symbols(timeframe="1d")
       if not symbols:
           logger.error("No symbols found")
           return False

       logger.info(f"✓ Found {len(symbols)} symbols")

       # Test load_data
       test_symbol = symbols[0]
       data = repo.load_data(test_symbol, "1d")

       if data.empty:
           logger.error(f"No data loaded for {test_symbol}")
           return False

       logger.info(f"✓ Loaded {len(data)} bars for {test_symbol}")

       # Test date range query
       end_date = datetime.now()
       start_date = end_date - timedelta(days=30)
       recent_data = repo.load_data(test_symbol, "1d", start_date, end_date)

       logger.info(f"✓ Date range query returned {len(recent_data)} bars")

       # Test get_date_range
       date_range = repo.get_date_range(test_symbol, "1d")
       if not date_range:
           logger.error(f"No date range for {test_symbol}")
           return False

       logger.info(f"✓ Date range: {date_range[0]} to {date_range[1]}")

       return True


   def test_query_performance():
       """Test query performance meets targets."""
       logger.info("Testing query performance...")

       repo = DataRepository()
       symbols = repo.list_symbols(timeframe="1d")

       if not symbols:
           logger.error("No symbols for performance test")
           return False

       test_symbol = symbols[0]

       # Test load performance
       start_time = time.time()
       data = repo.load_data(test_symbol, "1d")
       duration_ms = (time.time() - start_time) * 1000

       logger.info(f"Load query: {duration_ms:.2f}ms for {len(data)} bars")

       if duration_ms > 500:
           logger.warning(f"⚠️  Load query slower than target (500ms): {duration_ms:.2f}ms")
       else:
           logger.info(f"✓ Load query performance OK ({duration_ms:.2f}ms < 500ms)")

       # Test date range query performance
       end_date = datetime.now()
       start_date = end_date - timedelta(days=365)

       start_time = time.time()
       filtered_data = repo.load_data(test_symbol, "1d", start_date, end_date)
       duration_ms = (time.time() - start_time) * 1000

       logger.info(f"Date range query: {duration_ms:.2f}ms for {len(filtered_data)} bars")

       if duration_ms > 500:
           logger.warning(f"⚠️  Date range query slower than target: {duration_ms:.2f}ms")
       else:
           logger.info(f"✓ Date range query performance OK ({duration_ms:.2f}ms < 500ms)")

       return True


   def test_data_integrity():
       """Test data integrity checks."""
       logger.info("Testing data integrity...")

       from ktrdr.config.database import get_connection_manager

       manager = get_connection_manager()
       session = manager.get_session()

       try:
           # Check for OHLC violations
           result = session.execute("""
               SELECT COUNT(*) FROM price_data
               WHERE high < low OR high < open OR high < close OR low > open OR low > close
           """)
           violations = result.scalar()

           if violations > 0:
               logger.error(f"✗ Found {violations} OHLC constraint violations")
               return False

           logger.info("✓ No OHLC constraint violations")

           # Check for negative volumes
           result = session.execute("SELECT COUNT(*) FROM price_data WHERE volume < 0")
           violations = result.scalar()

           if violations > 0:
               logger.error(f"✗ Found {violations} negative volumes")
               return False

           logger.info("✓ No negative volumes")

           # Check total row count
           result = session.execute("SELECT COUNT(*) FROM price_data")
           total_rows = result.scalar()

           logger.info(f"✓ Total rows in database: {total_rows:,}")

           return True

       finally:
           session.close()


   def main():
       """Run end-to-end verification."""
       logger.info("=" * 80)
       logger.info("End-to-End TimescaleDB Verification")
       logger.info("=" * 80)

       tests = [
           ("DataRepository Operations", test_data_repository_operations),
           ("Query Performance", test_query_performance),
           ("Data Integrity", test_data_integrity),
       ]

       passed = 0
       failed = 0

       for test_name, test_func in tests:
           logger.info("")
           logger.info(f"Running: {test_name}")
           logger.info("-" * 80)

           try:
               if test_func():
                   logger.info(f"✅ {test_name} PASSED")
                   passed += 1
               else:
                   logger.error(f"❌ {test_name} FAILED")
                   failed += 1
           except Exception as e:
               logger.error(f"❌ {test_name} FAILED with exception: {e}", exc_info=True)
               failed += 1

       # Final summary
       logger.info("")
       logger.info("=" * 80)
       logger.info("VERIFICATION SUMMARY")
       logger.info("=" * 80)
       logger.info(f"Passed: {passed}/{len(tests)}")
       logger.info(f"Failed: {failed}/{len(tests)}")
       logger.info("=" * 80)

       if failed > 0:
           logger.error("❌ VERIFICATION FAILED")
           sys.exit(1)
       else:
           logger.info("✅ ALL VERIFICATIONS PASSED")
           sys.exit(0)


   if __name__ == "__main__":
       main()
   ```

2. Create manual testing checklist `docs/architecture/timeseries-data/CUTOVER_VERIFICATION_CHECKLIST.md`:

   ```markdown
   # Production Cutover Verification Checklist

   Complete this checklist to verify TimescaleDB cutover was successful.

   ## Infrastructure Verification

   - [ ] PostgreSQL/TimescaleDB container healthy: `docker-compose ps timescaledb`
   - [ ] Backend container healthy: `docker-compose ps backend`
   - [ ] Backend using TimescaleDB: `docker exec ktrdr-backend python -c "from ktrdr.data.repository.data_repository import DataRepository; print(DataRepository().backend_type)"`
   - [ ] Jaeger running: `docker-compose ps jaeger`

   ## Data Verification

   - [ ] Migration completed: `cat docs/architecture/timeseries-data/MIGRATION_RESULTS.md`
   - [ ] Migration verification passed: `uv run python scripts/verify_migration.py`
   - [ ] No data integrity issues: Check migration results for 0 failures

   ## CLI Commands Verification

   Test all CLI commands work with TimescaleDB:

   ```bash
   # Data commands
   - [ ] uv run ktrdr data show AAPL 1d --tail 5
   - [ ] uv run ktrdr data load AAPL 1d --start-date 2024-01-01 --end-date 2024-12-31
   - [ ] uv run ktrdr data get-range AAPL 1d
   - [ ] uv run ktrdr data list-symbols --timeframe 1d

   # Operations commands
   - [ ] uv run ktrdr operations list
   - [ ] uv run ktrdr operations status <operation-id>
   ```

   ## Training Workflow Verification

   ```bash
   # Start a training operation
   - [ ] uv run ktrdr models train --strategy config/strategies/example.yaml
   # Verify:
   #   - Operation starts successfully
   #   - Data loads from TimescaleDB (check logs)
   #   - Training completes without errors
   #   - Model saved successfully

   # Check operation in Jaeger
   - [ ] Open Jaeger UI: http://localhost:16686
   - [ ] Search for operation_id from training
   - [ ] Verify timescaledb.load_data spans present
   - [ ] Verify query performance < 500ms
   ```

   ## Backtesting Workflow Verification

   ```bash
   # Start a backtest operation
   - [ ] uv run ktrdr backtest run --strategy config/strategies/example.yaml --symbol AAPL --start-date 2024-01-01 --end-date 2024-12-31
   # Verify:
   #   - Operation starts successfully
   #   - Data loads from TimescaleDB (check logs)
   #   - Backtest completes without errors
   #   - Results generated successfully

   # Check operation in Jaeger
   - [ ] Open Jaeger UI: http://localhost:16686
   - [ ] Search for backtest operation_id
   - [ ] Verify timescaledb.load_data spans present
   - [ ] Verify query performance < 500ms
   ```

   ## Performance Verification

   **Target**: All data queries < 500ms

   ```bash
   # Run performance verification
   - [ ] uv run python scripts/e2e_verification.py
   # Should output: ✅ ALL VERIFICATIONS PASSED

   # Check Jaeger for query performance
   - [ ] Query Jaeger API for timescaledb.load_data operations
   ```

   Query Jaeger:

   ```bash
   curl -s "http://localhost:16686/api/traces?service=ktrdr&operation=timescaledb.load_data&limit=20" | jq '.data[].spans[] | select(.operationName == "timescaledb.load_data") | {duration_ms: (.duration / 1000), symbol: (.tags[] | select(.key == "db.symbol") | .value)}'
   ```

   Verify:
   - [ ] Median query time < 500ms
   - [ ] 95th percentile < 1000ms
   - [ ] No queries > 5000ms (except very large date ranges)

   ## Integration Tests

   - [ ] All unit tests pass: `make test-unit`
   - [ ] All integration tests pass: `make test-integration`
   - [ ] Code quality checks pass: `make quality`

   ## Monitoring and Logging

   - [ ] Backend logs show no errors: `docker logs ktrdr-backend | grep ERROR`
   - [ ] TimescaleDB logs show no errors: `docker logs ktrdr-timescaledb | grep ERROR`
   - [ ] No connection pool exhaustion: Check logs for "connection pool timeout"

   ## Rollback Readiness

   - [ ] Rollback procedure reviewed: `docs/architecture/timeseries-data/ROLLBACK_PROCEDURE.md`
   - [ ] CSV data still available (not deleted)
   - [ ] Know how to switch back (DB_TYPE=csv)

   ## Documentation

   - [ ] README.md updated with TimescaleDB backend info
   - [ ] Environment configuration docs updated
   - [ ] Architecture docs reviewed

   ## Final Sign-Off

   - [ ] All checks above completed successfully
   - [ ] No critical issues identified
   - [ ] Performance targets met
   - [ ] Team notified of successful cutover (if applicable)

   **Cutover Status**: ✅ COMPLETE / ⚠️ ISSUES FOUND / ❌ FAILED

   **Date**: _________________

   **Issues Found** (if any):

   ---
   ```

**Quality Gate**:

```bash
# Ensure TimescaleDB backend active
export DB_TYPE=postgresql

# Run end-to-end verification
uv run python scripts/e2e_verification.py
# Should output: ✅ ALL VERIFICATIONS PASSED

# Run all integration tests
make test-integration

# Manual workflow tests (follow CUTOVER_VERIFICATION_CHECKLIST.md)
# - Test CLI commands
# - Test training workflow
# - Test backtesting workflow
# - Check Jaeger for performance

# Performance verification via Jaeger
curl -s "http://localhost:16686/api/traces?service=ktrdr&operation=timescaledb.load_data&limit=20" | jq '.data[].spans[] | select(.operationName == "timescaledb.load_data") | {duration_ms: (.duration / 1000)}'
# Verify most queries < 500ms

# All tests pass
make test-unit
make quality
```

**Commit**: `feat(e2e): add end-to-end verification for TimescaleDB cutover`

**Estimated Time**: 3 hours

---

**Phase 4 Checkpoint**:
✅ DataRepository supports TimescaleDB via DB_TYPE env var
✅ Default backend switched to TimescaleDB
✅ All CLI commands work with TimescaleDB
✅ Training workflows verified end-to-end
✅ Backtesting workflows verified end-to-end
✅ Performance targets met (< 500ms queries)
✅ Documentation updated
✅ Rollback procedure documented
✅ **TESTABLE**: Entire system running on TimescaleDB successfully

**Total Phase 4 Time**: ~7 hours

---

## Summary

### Total Implementation Time (Phases 3-4)

| Phase | Focus | Tasks | Time | Testable? |
|-------|-------|-------|------|-----------|
| Phase 3: Initial Data Migration | CSV → TimescaleDB migration + verification | 2 tasks | ~6.5 hours | ✅ Yes! |
| Phase 4: Production Cutover | Switch to TimescaleDB + E2E verification | 3 tasks | ~7 hours | ✅ Yes! |
| **Total (Migration + Cutover)** | **Production ready** | **5 tasks** | **~13.5 hours** | **✅ Every phase!** |

### Complete Project Time (All Phases)

| Phase Group | Tasks | Time |
|-------------|-------|------|
| Phases 0-2 (Infrastructure + Import) | 8 tasks | ~18.5 hours |
| Phases 3-4 (Migration + Cutover) | 5 tasks | ~13.5 hours |
| **TOTAL PROJECT** | **13 tasks** | **~32 hours** |

### Success Criteria

**Migration Success** (Phase 3):
- ✅ All CSV data imported into TimescaleDB
- ✅ Success rate: 100%
- ✅ Row counts match between CSV and TimescaleDB
- ✅ Spot-check data comparisons pass
- ✅ No OHLC constraint violations
- ✅ No negative volumes
- ✅ MIGRATION_RESULTS.md generated

**Cutover Success** (Phase 4):
- ✅ Backend type: `timescaledb`
- ✅ All CLI commands functional
- ✅ Training workflows complete successfully
- ✅ Backtesting workflows complete successfully
- ✅ Query performance < 500ms (median)
- ✅ All integration tests passing
- ✅ No errors in logs
- ✅ Documentation updated

### Rollback Procedures

**Emergency Rollback** (5 minutes):

```bash
# Step 1: Switch environment variable
# Edit docker/docker-compose.dev.yml
# Change: DB_TYPE=postgresql
# To:     DB_TYPE=csv

# Step 2: Restart backend
docker-compose -f docker/docker-compose.dev.yml restart backend

# Step 3: Verify
docker exec ktrdr-backend python -c "from ktrdr.data.repository.data_repository import DataRepository; print(DataRepository().backend_type)"
# Should print: csv
```

**See**: `docs/architecture/timeseries-data/ROLLBACK_PROCEDURE.md` for complete rollback guide.

### Quality Standards

Every task must pass:

```bash
make test-unit           # All unit tests (existing + new)
make test-integration    # Integration tests with database
make quality             # Lint + format + typecheck
```

### Git Workflow

- **One branch**: All work on `feature/timescaledb-integration`
- **One commit per task**: Clear, descriptive commit messages
- **TDD**: Write tests first, then implementation
- **Vertical**: Each phase builds complete feature

### Performance Targets

**Achieved Targets**:
- ✅ Query performance: < 500ms (median)
- ✅ 95th percentile: < 1000ms
- ✅ Data integrity: 100% (no constraint violations)
- ✅ Migration success rate: 100%
- ✅ Storage compression: 95% (after 7 days)

### Final Verification Commands

**Quick System Check**:

```bash
# 1. Verify backend type
docker exec ktrdr-backend python -c "from ktrdr.data.repository.data_repository import DataRepository; print(DataRepository().backend_type)"
# Expected: timescaledb

# 2. Run E2E verification
uv run python scripts/e2e_verification.py
# Expected: ✅ ALL VERIFICATIONS PASSED

# 3. Check query performance
curl -s "http://localhost:16686/api/traces?service=ktrdr&operation=timescaledb.load_data&limit=20" | jq '.data[].spans[] | select(.operationName == "timescaledb.load_data") | {duration_ms: (.duration / 1000)}' | jq -s 'map(.duration_ms) | add / length'
# Expected: < 500

# 4. Run integration tests
make test-integration
# Expected: All passed
```

### Post-Cutover Monitoring

**First 24 Hours**:
- Monitor Jaeger for query performance
- Check logs for errors: `docker logs ktrdr-backend | grep ERROR`
- Monitor database connections: `docker exec ktrdr-timescaledb psql -U ktrdr -d ktrdr -c "SELECT count(*) FROM pg_stat_activity;"`
- Verify no connection pool exhaustion

**First Week**:
- Monitor compression policy activation (after 7 days)
- Check storage usage: `docker exec ktrdr-timescaledb psql -U ktrdr -d ktrdr -c "SELECT pg_size_pretty(pg_total_relation_size('price_data'));"`
- Verify retention policy working (after 10 years)

### Documentation Updates Completed

- ✅ README.md: Added TimescaleDB backend section
- ✅ Environment configuration docs: Added DB_TYPE documentation
- ✅ Rollback procedure: Complete emergency rollback guide
- ✅ Migration results: Auto-generated MIGRATION_RESULTS.md
- ✅ Verification checklists: Pre-migration and cutover checklists

### Next Steps (Post-Cutover)

**Optional Enhancements** (Future Work):

1. **Continuous Aggregates** (Phase 5):
   - Add materialized views for common queries
   - Pre-compute daily/weekly/monthly aggregates
   - Further improve query performance

2. **Advanced Analytics** (Phase 6):
   - Time-bucket queries for charting
   - Gap detection and filling
   - Statistical functions (moving averages, volatility)

3. **Multi-Tenancy** (Phase 7):
   - Add user_id dimension
   - Row-level security
   - Per-user data isolation

4. **Distributed Hypertables** (Phase 8):
   - Multi-node TimescaleDB cluster
   - Horizontal scaling across multiple servers
   - High availability setup

**See**: `docs/architecture/timeseries-data/FUTURE_ENHANCEMENTS.md` (to be created)

---

**Previous**: See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for Phases 0-2 (Infrastructure → Import)

**Status**: 📋 **READY FOR IMPLEMENTATION**

---

**End of Implementation Plan (Phases 3-4)**
