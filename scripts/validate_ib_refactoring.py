#!/usr/bin/env python3
"""
Quick validation script for IB refactoring.

This script performs basic validation of the unified IB components
to ensure the refactoring is working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ktrdr.data.ib_client_id_registry import ClientIdPurpose, get_client_id_registry
from ktrdr.data.ib_connection_pool import acquire_ib_connection, get_connection_pool
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.data.ib_health_monitor import get_health_monitor
from ktrdr.data.ib_metrics_collector import get_metrics_collector
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.logging import get_logger

logger = get_logger(__name__)


async def validate_component_imports():
    """Validate that all unified components can be imported."""
    logger.info("🔍 Validating component imports...")

    try:
        # Test imports
        components = [
            ("Connection Pool", get_connection_pool),
            ("Client ID Registry", get_client_id_registry),
            ("Metrics Collector", get_metrics_collector),
            ("Health Monitor", get_health_monitor),
        ]

        for name, component_func in components:
            try:
                if asyncio.iscoroutinefunction(component_func):
                    await component_func()
                else:
                    component_func()

                logger.info(f"  ✅ {name}: OK")
            except Exception as e:
                logger.error(f"  ❌ {name}: {e}")
                return False

        # Test component classes
        try:
            IbDataFetcherUnified(component_name="validation_test")
            logger.info("  ✅ Data Fetcher Unified: OK")
        except Exception as e:
            logger.error(f"  ❌ Data Fetcher Unified: {e}")
            return False

        try:
            IbSymbolValidatorUnified(
                component_name="validation_test"
            )
            logger.info("  ✅ Symbol Validator Unified: OK")
        except Exception as e:
            logger.error(f"  ❌ Symbol Validator Unified: {e}")
            return False

        logger.info("✅ All component imports successful")
        return True

    except Exception as e:
        logger.error(f"❌ Component import validation failed: {e}")
        return False


async def validate_client_id_registry():
    """Validate client ID registry functionality."""
    logger.info("🔍 Validating Client ID Registry...")

    try:
        registry = get_client_id_registry()

        # Test allocation
        client_id = registry.allocate_client_id(
            ClientIdPurpose.DATA_MANAGER, "validation_test"
        )

        if client_id is None:
            logger.error("  ❌ Failed to allocate client ID")
            return False

        logger.info(f"  ✅ Allocated client ID: {client_id}")

        # Test tracking
        allocations = registry.get_allocations()
        if client_id not in allocations:
            logger.error(f"  ❌ Client ID {client_id} not tracked in allocations")
            return False

        logger.info(f"  ✅ Client ID {client_id} properly tracked")

        # Test deallocation
        registry.deallocate_client_id(client_id, "validation_cleanup")

        allocations = registry.get_allocations()
        if client_id in allocations:
            logger.error(f"  ❌ Client ID {client_id} still tracked after deallocation")
            return False

        logger.info(f"  ✅ Client ID {client_id} properly deallocated")

        logger.info("✅ Client ID Registry validation successful")
        return True

    except Exception as e:
        logger.error(f"❌ Client ID Registry validation failed: {e}")
        return False


async def validate_metrics_collector():
    """Validate metrics collector functionality."""
    logger.info("🔍 Validating Metrics Collector...")

    try:
        collector = get_metrics_collector()

        # Test operation recording
        operation_id = collector.record_operation_start(
            "validation_test", "test_operation", {"test": "true"}
        )

        logger.info(f"  ✅ Started operation: {operation_id}")

        # Small delay to ensure measurable duration
        await asyncio.sleep(0.01)

        collector.record_operation_end(
            operation_id, "validation_test", "test_operation", success=True
        )

        logger.info(f"  ✅ Ended operation: {operation_id}")

        # Test metrics retrieval
        component_metrics = collector.get_component_metrics("validation_test")
        if component_metrics is None:
            logger.error("  ❌ Failed to retrieve component metrics")
            return False

        if component_metrics.total_operations != 1:
            logger.error(
                f"  ❌ Expected 1 operation, got {component_metrics.total_operations}"
            )
            return False

        logger.info(
            f"  ✅ Component metrics: {component_metrics.total_operations} operations"
        )

        # Test global metrics
        global_metrics = collector.get_global_metrics()
        if global_metrics["total_operations"] == 0:
            logger.error("  ❌ Global metrics not updated")
            return False

        logger.info(
            f"  ✅ Global metrics: {global_metrics['total_operations']} total operations"
        )

        # Test export
        json_export = collector.export_metrics("json")
        if not json_export or len(json_export) < 100:
            logger.error("  ❌ JSON export failed or too short")
            return False

        logger.info(f"  ✅ JSON export: {len(json_export)} characters")

        logger.info("✅ Metrics Collector validation successful")
        return True

    except Exception as e:
        logger.error(f"❌ Metrics Collector validation failed: {e}")
        return False


async def validate_connection_pool():
    """Validate connection pool functionality."""
    logger.info("🔍 Validating Connection Pool...")

    try:
        pool = await get_connection_pool()

        # Test pool status
        status = pool.get_pool_status()
        if status is None:
            logger.error("  ❌ Connection pool status is None")
            return False

        if not status.get("running"):
            logger.error("  ❌ Connection pool not running")
            return False

        logger.info(f"  ✅ Pool running: {status['total_connections']} connections")

        # Test connection acquisition (mock style - no actual IB connection)
        try:
            # This may fail if no IB Gateway is running, which is OK for validation
            async with await acquire_ib_connection(
                purpose=ClientIdPurpose.DATA_MANAGER, requested_by="validation_test"
            ) as connection:
                logger.info(
                    f"  ✅ Successfully acquired connection: {connection.client_id}"
                )

        except Exception as e:
            # This is expected if no IB Gateway is running
            logger.info(
                f"  ⚠️  Connection acquisition failed (expected without IB Gateway): {e}"
            )
            # Don't return False here - this is expected behavior

        logger.info("✅ Connection Pool validation successful")
        return True

    except Exception as e:
        logger.error(f"❌ Connection Pool validation failed: {e}")
        return False


async def validate_health_monitor():
    """Validate health monitor functionality."""
    logger.info("🔍 Validating Health Monitor...")

    try:
        monitor = get_health_monitor()

        # Test health status retrieval
        overall_health = monitor.get_overall_health()

        if "status" not in overall_health:
            logger.error("  ❌ Overall health missing status")
            return False

        logger.info(f"  ✅ Overall health status: {overall_health['status']}")

        # Test alerts
        alerts = monitor.get_all_alerts()
        logger.info(f"  ✅ Active alerts: {len(alerts)}")

        logger.info("✅ Health Monitor validation successful")
        return True

    except Exception as e:
        logger.error(f"❌ Health Monitor validation failed: {e}")
        return False


async def validate_unified_components():
    """Validate unified data fetcher and symbol validator."""
    logger.info("🔍 Validating Unified Components...")

    try:
        # Test data fetcher creation
        data_fetcher = IbDataFetcherUnified(component_name="validation_test_fetcher")
        metrics = data_fetcher.get_metrics()
        logger.info(f"  ✅ Data Fetcher created with metrics: {metrics}")

        # Test symbol validator creation
        symbol_validator = IbSymbolValidatorUnified(
            component_name="validation_test_validator"
        )
        cache_stats = symbol_validator.get_cache_stats()
        logger.info(f"  ✅ Symbol Validator created with cache stats: {cache_stats}")

        logger.info("✅ Unified Components validation successful")
        return True

    except Exception as e:
        logger.error(f"❌ Unified Components validation failed: {e}")
        return False


async def main():
    """Run all validations."""
    logger.info("🚀 Starting IB Refactoring Validation")
    logger.info("=" * 50)

    validations = [
        ("Component Imports", validate_component_imports),
        ("Client ID Registry", validate_client_id_registry),
        ("Metrics Collector", validate_metrics_collector),
        ("Connection Pool", validate_connection_pool),
        ("Health Monitor", validate_health_monitor),
        ("Unified Components", validate_unified_components),
    ]

    results = []

    for name, validation_func in validations:
        logger.info(f"\n📋 Running {name} validation...")
        try:
            success = await validation_func()
            results.append((name, success))

            if success:
                logger.info(f"✅ {name} validation PASSED")
            else:
                logger.error(f"❌ {name} validation FAILED")

        except Exception as e:
            logger.error(f"❌ {name} validation ERROR: {e}")
            results.append((name, False))

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 VALIDATION SUMMARY")
    logger.info("=" * 50)

    passed = sum(1 for name, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"  {name}: {status}")

    logger.info(f"\nTotal: {passed}/{total} validations passed")

    if passed == total:
        logger.info("🎉 ALL VALIDATIONS PASSED - IB refactoring is working correctly!")
        return True
    else:
        logger.error(
            f"💥 {total - passed} validations failed - please check the issues above"
        )
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
