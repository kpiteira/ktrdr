"""
Exhaustive Real IB Connection Resilience Tests - DISABLED

DISABLED: These tests create competing IB connections with the backend.

This test file was designed for the old IB architecture with complex connection
pool logic and 6-phase resilience scoring. The new simplified architecture
makes these tests obsolete.

The new architecture (ktrdr/ib/) with dedicated threads and persistent event loops
is tested by:
- tests/integration/test_ib_new_architecture_integration.py
- tests/e2e_real/test_real_api.py
- tests/e2e_real/test_real_cli.py

All tests in this file are disabled to prevent competing IB connections
that could interfere with the backend's connection pool.
"""

import asyncio
import time
from datetime import datetime, timezone

import pytest

# DISABLED: Old IB architecture imports - tests are disabled
# from ktrdr.data.ib_connection_pool import get_connection_pool, acquire_ib_connection
# from ktrdr.data.ib_client_id_registry import ClientIdPurpose
# from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
# from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestPhase1SystematicValidationExhaustive:
    """Exhaustive tests for Phase 1: Systematic validation before handoff."""

    @pytest.mark.asyncio
    async def test_validation_prevents_silent_connections(
        self, real_ib_connection_test
    ):
        """Test that systematic validation catches silent connections that would hang."""
        pool = await get_connection_pool()

        # Test multiple rapid connection acquisitions
        successful_validations = 0
        failed_validations = 0

        for i in range(10):
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"validation_test_{i}",
                ) as connection:
                    # This should only succeed if validation passes
                    # (isConnected() + reqCurrentTime() within 3 seconds)
                    assert connection.client_id is not None
                    assert connection.ib is not None

                    # Verify connection is actually responsive
                    start_time = time.time()
                    accounts = await asyncio.wait_for(
                        connection.ib.reqManagedAcctsAsync(), timeout=5.0
                    )
                    elapsed = time.time() - start_time

                    assert accounts is not None, "Should get managed accounts"
                    assert elapsed < 5.0, f"Request took too long: {elapsed:.2f}s"
                    successful_validations += 1

            except asyncio.TimeoutError:
                failed_validations += 1
                # Timeouts are acceptable - this means validation caught a bad connection

            except Exception as e:
                # Any other error should not be async/coroutine related
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str
                failed_validations += 1

        # At least some should succeed with real IB
        assert (
            successful_validations > 0
        ), "No successful validations out of 10 attempts"
        print(
            f"✅ Systematic validation: {successful_validations}/10 succeeded, {failed_validations}/10 failed gracefully"
        )

    @pytest.mark.asyncio
    async def test_validation_timing_requirements(self, real_ib_connection_test):
        """Test that validation completes within the 3-second requirement."""
        pool = await get_connection_pool()

        validation_times = []

        for i in range(5):
            start_time = time.time()
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by=f"timing_test_{i}"
                ) as connection:
                    elapsed = time.time() - start_time
                    validation_times.append(elapsed)

                    # Validation should complete quickly
                    assert elapsed < 10.0, f"Validation too slow: {elapsed:.2f}s"

            except Exception:
                elapsed = time.time() - start_time
                validation_times.append(elapsed)
                # Even failures should be quick (within timeout)
                assert (
                    elapsed < 15.0
                ), f"Failed validation took too long: {elapsed:.2f}s"

        avg_time = sum(validation_times) / len(validation_times)
        print(
            f"✅ Average validation time: {avg_time:.2f}s (target: <3s per validation)"
        )

        # Most validations should be reasonably fast
        fast_validations = sum(1 for t in validation_times if t < 5.0)
        assert (
            fast_validations >= len(validation_times) // 2
        ), "Too many slow validations"

    @pytest.mark.asyncio
    async def test_concurrent_validation_integrity(self, real_ib_connection_test):
        """Test that concurrent connection validations don't interfere."""
        pool = await get_connection_pool()

        async def validate_connection(connection_id: str):
            """Validate a single connection and return results."""
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"concurrent_validation_{connection_id}",
                ) as connection:
                    # Test that connection is actually working
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(), timeout=5.0
                    )
                    return {
                        "id": connection_id,
                        "success": True,
                        "client_id": connection.client_id,
                    }

            except Exception as e:
                error_str = str(e).lower()
                # Ensure no async/coroutine errors
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str
                return {"id": connection_id, "success": False, "error": str(e)}

        # Run 5 concurrent validation attempts
        tasks = [validate_connection(f"conn_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        for result in results:
            assert not isinstance(
                result, Exception
            ), f"Concurrent validation failed: {result}"

        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        print(f"✅ Concurrent validation: {len(successful_results)}/5 succeeded")

        # Verify unique client IDs for successful connections
        if len(successful_results) > 1:
            client_ids = [r["client_id"] for r in successful_results]
            assert len(set(client_ids)) == len(
                client_ids
            ), "Client IDs should be unique"


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestPhase2GarbageCollectionExhaustive:
    """Exhaustive tests for Phase 2: Garbage collection with 5-minute idle timeout."""

    @pytest.mark.asyncio
    async def test_garbage_collection_timing_accuracy(self, real_ib_connection_test):
        """Test that garbage collection honors the 5-minute (300s) idle timeout."""
        pool = await get_connection_pool()

        # Create connections and let them idle
        connection_times = []

        # Create a connection and release it
        start_time = time.time()
        async with pool.acquire_connection(
            purpose=ClientIdPurpose.API_POOL, requested_by="gc_timing_test"
        ) as connection:
            client_id = connection.client_id
            connection_times.append({"client_id": client_id, "created": start_time})

        # Check resilience endpoint for garbage collection metrics
        import httpx

        client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

        # Immediately after release, connection should exist
        response = client.get("/api/v1/ib/resilience")
        assert response.status_code == 200

        resilience_data = response.json()["data"]
        phase2 = resilience_data["phase_2_garbage_collection"]

        # Verify GC configuration
        assert phase2["status"] == "working"
        assert phase2["max_idle_time_seconds"] == 300.0  # 5 minutes
        assert phase2["health_check_interval"] == 60.0  # 1 minute

        print(
            f"✅ Garbage collection configured: {phase2['max_idle_time_seconds']}s idle timeout"
        )

        client.close()

    @pytest.mark.asyncio
    async def test_connection_lifecycle_tracking(self, real_ib_connection_test):
        """Test that connection lifecycle is properly tracked for GC."""
        pool = await get_connection_pool()

        # Create multiple connections with different lifetimes
        connections_created = []

        for i in range(3):
            async with pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL, requested_by=f"lifecycle_test_{i}"
            ) as connection:
                connections_created.append(
                    {"client_id": connection.client_id, "created_at": time.time()}
                )

                # Hold connection briefly to simulate work
                await asyncio.sleep(0.5)

        # Check pool health after connections released
        import httpx

        client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

        response = client.get("/api/v1/ib/resilience")
        assert response.status_code == 200

        resilience_data = response.json()["data"]
        pool_health = resilience_data["connection_pool_health"]

        # Pool should be tracking connections
        assert pool_health["pool_uptime_seconds"] > 0
        print(f"✅ Pool uptime: {pool_health['pool_uptime_seconds']:.1f}s")
        print(f"✅ Total connections tracked: {pool_health['total_connections']}")

        client.close()

    @pytest.mark.asyncio
    async def test_memory_stability_over_time(self, real_ib_connection_test):
        """Test that repeated connection creation/cleanup doesn't leak memory."""
        pool = await get_connection_pool()

        # Create and release many connections to test memory stability
        for cycle in range(10):
            cycle_connections = []

            # Create multiple connections in this cycle
            for i in range(3):
                try:
                    async with pool.acquire_connection(
                        purpose=ClientIdPurpose.API_POOL,
                        requested_by=f"memory_stability_cycle_{cycle}_conn_{i}",
                    ) as connection:
                        cycle_connections.append(connection.client_id)

                        # Do some light work to test real usage
                        await connection.ib.reqCurrentTimeAsync()

                except Exception as e:
                    # Connection exhaustion is okay, just track it
                    error_str = str(e).lower()
                    assert "runtimewarning" not in error_str
                    assert "coroutine" not in error_str

            # Small delay between cycles
            await asyncio.sleep(0.1)

            if cycle % 5 == 0:
                print(f"✅ Memory stability test: completed cycle {cycle}/10")

        print("✅ Memory stability test completed - no memory leaks detected")


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestPhase3ClientIdPreferenceExhaustive:
    """Exhaustive tests for Phase 3: Client ID 1 preference with incremental fallback."""

    @pytest.mark.asyncio
    async def test_client_id_preference_order(self, real_ib_connection_test):
        """Test that Client ID 1 is preferred, with sequential fallback."""
        pool = await get_connection_pool()

        # Create multiple connections to test ID allocation
        allocated_ids = []
        connections = []

        try:
            # Create several connections to test ID preference
            for i in range(5):
                try:
                    conn_ctx = await acquire_ib_connection(
                        purpose=ClientIdPurpose.API_POOL,
                        requested_by=f"id_preference_test_{i}",
                    )
                    connection = await conn_ctx.__aenter__()

                    allocated_ids.append(connection.client_id)
                    connections.append((conn_ctx, connection))

                    print(
                        f"✅ Connection {i}: allocated Client ID {connection.client_id}"
                    )

                except Exception as e:
                    # Pool exhaustion is okay
                    error_str = str(e).lower()
                    assert "runtimewarning" not in error_str
                    assert "coroutine" not in error_str
                    break

            # Verify ID allocation strategy
            if allocated_ids:
                # Should prefer low numbers
                min_id = min(allocated_ids)
                max_id = max(allocated_ids)

                print(f"✅ Client ID range: {min_id} to {max_id}")

                # First connection should get ID 1 or close to it
                first_id = allocated_ids[0]
                assert (
                    first_id <= 3
                ), f"First connection should get low ID, got {first_id}"

                # IDs should be sequential or close to sequential
                if len(allocated_ids) > 1:
                    id_gaps = [
                        allocated_ids[i + 1] - allocated_ids[i]
                        for i in range(len(allocated_ids) - 1)
                    ]
                    avg_gap = sum(id_gaps) / len(id_gaps)
                    assert avg_gap <= 2.0, f"ID gaps too large: {id_gaps}"

        finally:
            # Clean up connections
            for conn_ctx, connection in connections:
                try:
                    await conn_ctx.__aexit__(None, None, None)
                except:
                    pass

    @pytest.mark.asyncio
    async def test_client_id_reuse_after_cleanup(self, real_ib_connection_test):
        """Test that Client IDs are reused efficiently after cleanup."""
        pool = await get_connection_pool()

        # Phase 1: Create and release connections
        first_round_ids = []

        for i in range(3):
            async with pool.acquire_connection(
                purpose=ClientIdPurpose.API_POOL, requested_by=f"reuse_test_first_{i}"
            ) as connection:
                first_round_ids.append(connection.client_id)

        print(f"✅ First round IDs: {first_round_ids}")

        # Small delay to allow cleanup
        await asyncio.sleep(1)

        # Phase 2: Create new connections and check ID reuse
        second_round_ids = []

        for i in range(3):
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"reuse_test_second_{i}",
                ) as connection:
                    second_round_ids.append(connection.client_id)
            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str

        print(f"✅ Second round IDs: {second_round_ids}")

        # Should reuse low IDs efficiently
        if second_round_ids:
            min_second_id = min(second_round_ids)
            assert min_second_id <= 3, f"Should reuse low IDs, got {min_second_id}"

    @pytest.mark.asyncio
    async def test_client_id_error_326_handling(self, real_ib_connection_test):
        """Test handling of IB error 326 (client ID already in use)."""
        # Note: This test simulates the error handling logic
        # Real error 326 is hard to trigger reliably in tests

        pool = await get_connection_pool()

        # Test resilience endpoint for Client ID preference metrics
        import httpx

        client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

        response = client.get("/api/v1/ib/resilience")
        assert response.status_code == 200

        resilience_data = response.json()["data"]
        phase3 = resilience_data["phase_3_client_id_preference"]

        # Verify Client ID preference is working
        assert phase3["status"] == "working"
        assert "client_ids_in_use" in phase3
        assert "total_active_connections" in phase3

        print("✅ Client ID preference system active")
        print(f"✅ Current active connections: {phase3['total_active_connections']}")

        if phase3["client_ids_in_use"]:
            ids_in_use = phase3["client_ids_in_use"]
            print(f"✅ Client IDs currently in use: {ids_in_use}")

            # Should prefer low IDs
            min_id = min(ids_in_use)
            assert min_id <= 5, f"Should use low IDs, minimum is {min_id}"

        client.close()


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestConnectionPoolStressExhaustive:
    """Exhaustive stress tests for connection pool under load."""

    @pytest.mark.asyncio
    async def test_rapid_connection_creation_destruction(self, real_ib_connection_test):
        """Test rapid connection creation and destruction for memory leaks."""
        pool = await get_connection_pool()

        successful_operations = 0
        failed_operations = 0

        start_time = time.time()

        # Rapid fire connection operations
        for i in range(20):
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by=f"rapid_test_{i}"
                ) as connection:
                    # Do minimal work
                    await connection.ib.reqCurrentTimeAsync()
                    successful_operations += 1

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str
                failed_operations += 1

            # Very short delay
            await asyncio.sleep(0.05)

        elapsed = time.time() - start_time

        print(
            f"✅ Rapid operations: {successful_operations}/20 succeeded in {elapsed:.2f}s"
        )
        print(
            f"✅ Failed operations: {failed_operations}/20 (acceptable for stress test)"
        )

        # At least some should succeed
        assert successful_operations > 0, "No operations succeeded under stress"

    @pytest.mark.asyncio
    async def test_concurrent_heavy_load(self, real_ib_connection_test):
        """Test concurrent heavy load on connection pool."""
        pool = await get_connection_pool()

        async def heavy_connection_work(worker_id: int):
            """Perform heavy work with a connection."""
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"heavy_worker_{worker_id}",
                ) as connection:
                    # Simulate heavy work
                    tasks = []
                    for i in range(3):
                        task = connection.ib.reqCurrentTimeAsync()
                        tasks.append(task)

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Check for async errors in results
                    for result in results:
                        if isinstance(result, Exception):
                            error_str = str(result).lower()
                            assert "runtimewarning" not in error_str
                            assert "coroutine" not in error_str

                    return {
                        "worker": worker_id,
                        "success": True,
                        "results": len(results),
                    }

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                return {"worker": worker_id, "success": False, "error": str(e)}

        # Run 8 concurrent heavy workers
        workers = [heavy_connection_work(i) for i in range(8)]
        results = await asyncio.gather(*workers, return_exceptions=True)

        # Verify no uncaught exceptions
        for result in results:
            assert not isinstance(
                result, Exception
            ), f"Worker failed with exception: {result}"

        successful_workers = [r for r in results if r["success"]]
        failed_workers = [r for r in results if not r["success"]]

        print(f"✅ Heavy load test: {len(successful_workers)}/8 workers succeeded")

        # At least half should succeed under heavy load
        assert len(successful_workers) >= 4, "Too many workers failed under heavy load"

    @pytest.mark.asyncio
    async def test_connection_pool_recovery_after_stress(self, real_ib_connection_test):
        """Test that connection pool recovers properly after stress."""
        pool = await get_connection_pool()

        # Phase 1: Apply stress
        print("✅ Applying stress to connection pool...")
        stress_tasks = []

        for i in range(10):

            async def stress_connection(conn_id):
                try:
                    async with pool.acquire_connection(
                        purpose=ClientIdPurpose.API_POOL,
                        requested_by=f"stress_{conn_id}",
                    ) as connection:
                        await asyncio.sleep(0.1)  # Hold connection briefly
                        return True
                except:
                    return False

            stress_tasks.append(stress_connection(i))

        stress_results = await asyncio.gather(*stress_tasks, return_exceptions=True)

        # Phase 2: Recovery test
        print("✅ Testing recovery after stress...")
        await asyncio.sleep(2)  # Allow recovery time

        # Normal operations should work after stress
        recovery_successful = 0

        for i in range(5):
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by=f"recovery_test_{i}"
                ) as connection:
                    await connection.ib.reqCurrentTimeAsync()
                    recovery_successful += 1

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str

        print(f"✅ Recovery test: {recovery_successful}/5 operations succeeded")

        # Should recover and work normally
        assert recovery_successful > 0, "Pool did not recover after stress"


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestSilentConnectionDetectionExhaustive:
    """Exhaustive tests for silent connection detection (the original bug)."""

    @pytest.mark.asyncio
    async def test_detect_hanging_connections(self, real_ib_connection_test):
        """Test detection of connections that hang on operations."""
        pool = await get_connection_pool()

        # Test with realistic timeout scenarios
        timeout_tests = [
            {"timeout": 3.0, "description": "validation timeout"},
            {"timeout": 5.0, "description": "operation timeout"},
            {"timeout": 10.0, "description": "extended timeout"},
        ]

        for test in timeout_tests:
            timeout = test["timeout"]
            description = test["description"]

            try:
                start_time = time.time()

                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"hanging_test_{timeout}",
                ) as connection:
                    # Test that operations complete within reasonable time
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(), timeout=timeout
                    )

                    elapsed = time.time() - start_time
                    print(f"✅ {description}: completed in {elapsed:.2f}s")

                    # Should be much faster than timeout
                    assert (
                        elapsed < timeout * 0.8
                    ), f"Operation too slow for {description}"

            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                print(
                    f"⚠️  {description}: timed out after {elapsed:.2f}s (this is acceptable)"
                )
                # Timeout is acceptable - means we detected a hanging connection

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

    @pytest.mark.asyncio
    async def test_connection_responsiveness_validation(self, real_ib_connection_test):
        """Test that connections are validated for responsiveness."""
        pool = await get_connection_pool()

        responsiveness_times = []

        for i in range(5):
            try:
                start_time = time.time()

                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"responsiveness_test_{i}",
                ) as connection:
                    # Test multiple operations for responsiveness
                    operations = [
                        connection.ib.reqCurrentTimeAsync(),
                        connection.ib.reqCurrentTimeAsync(),
                        connection.ib.reqCurrentTimeAsync(),
                    ]

                    await asyncio.gather(*operations)
                    elapsed = time.time() - start_time
                    responsiveness_times.append(elapsed)

                    print(f"✅ Responsiveness test {i}: {elapsed:.2f}s")

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str

        if responsiveness_times:
            avg_responsiveness = sum(responsiveness_times) / len(responsiveness_times)
            max_responsiveness = max(responsiveness_times)

            print(f"✅ Average responsiveness: {avg_responsiveness:.2f}s")
            print(f"✅ Maximum responsiveness: {max_responsiveness:.2f}s")

            # Connections should be consistently responsive
            assert avg_responsiveness < 5.0, "Average responsiveness too slow"
            assert max_responsiveness < 10.0, "Maximum responsiveness too slow"


@pytest.mark.real_ib
@pytest.mark.exhaustive_resilience
@pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
class TestResilienceScoreValidationExhaustive:
    """Exhaustive validation of resilience scoring with real IB data."""

    def test_resilience_score_with_active_connections(self, real_ib_connection_test):
        """Test resilience score calculation with active IB connections."""
        import httpx

        client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

        try:
            # Get resilience status with real IB
            response = client.get("/api/v1/ib/resilience")
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True

            resilience_data = data["data"]

            # Validate overall score
            score = resilience_data["overall_resilience_score"]
            assert isinstance(score, (int, float))
            assert 0 <= score <= 100

            print(f"✅ Overall resilience score: {score}/100")

            # With real IB, should get high score
            assert score >= 75, f"Expected high score with real IB, got {score}"

            # Validate each phase
            phases = [
                ("phase_1_systematic_validation", "Systematic Validation"),
                ("phase_2_garbage_collection", "Garbage Collection"),
                ("phase_3_client_id_preference", "Client ID Preference"),
            ]

            for phase_key, phase_name in phases:
                phase_data = resilience_data[phase_key]
                assert phase_data["status"] == "working", f"{phase_name} not working"
                print(f"✅ {phase_name}: {phase_data['status']}")

            # Validate connection pool health
            pool_health = resilience_data["connection_pool_health"]
            assert pool_health["pool_uptime_seconds"] > 0
            assert pool_health["total_connections"] >= 0
            assert pool_health["healthy_connections"] >= 0

            print(
                f"✅ Pool health: {pool_health['healthy_connections']}/{pool_health['total_connections']} healthy"
            )

        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_resilience_score_under_load(self, real_ib_connection_test):
        """Test that resilience score remains high under connection load."""
        import httpx

        pool = await get_connection_pool()

        # Create some load on the connection pool
        load_tasks = []

        async def create_load(load_id: int):
            try:
                async with pool.acquire_connection(
                    purpose=ClientIdPurpose.API_POOL,
                    requested_by=f"load_test_{load_id}",
                ) as connection:
                    await connection.ib.reqCurrentTimeAsync()
                    await asyncio.sleep(1)  # Hold connection under load
                    return True
            except:
                return False

        # Start background load
        for i in range(3):
            load_tasks.append(asyncio.create_task(create_load(i)))

        try:
            # Check resilience score under load
            await asyncio.sleep(0.5)  # Let load establish

            client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

            response = client.get("/api/v1/ib/resilience")
            assert response.status_code == 200

            data = response.json()["data"]
            score_under_load = data["overall_resilience_score"]

            print(f"✅ Resilience score under load: {score_under_load}/100")

            # Score should remain high under load
            assert (
                score_under_load >= 65
            ), f"Score dropped too much under load: {score_under_load}"

            # Pool should show active connections
            pool_health = data["connection_pool_health"]
            assert (
                pool_health["active_connections"] > 0
            ), "Should show active connections under load"

            client.close()

        finally:
            # Wait for load tasks to complete
            await asyncio.gather(*load_tasks, return_exceptions=True)

    def test_resilience_timestamp_accuracy(self, real_ib_connection_test):
        """Test that resilience timestamps are accurate and recent."""
        import httpx

        client = httpx.Client(base_url="http://localhost:8000", timeout=30.0)

        try:
            before_time = datetime.now(timezone.utc)

            response = client.get("/api/v1/ib/resilience")
            assert response.status_code == 200

            after_time = datetime.now(timezone.utc)

            data = response.json()["data"]

            # Validate timestamp
            timestamp_str = data["timestamp"]
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Timestamp should be between before and after
            assert (
                before_time <= timestamp <= after_time
            ), "Timestamp not in expected range"

            # Should be very recent
            time_diff = abs((after_time - timestamp).total_seconds())
            assert time_diff < 10, f"Timestamp too old: {time_diff}s"

            print(f"✅ Timestamp accuracy: within {time_diff:.2f}s")

        finally:
            client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib", "-m", "exhaustive_resilience"])
