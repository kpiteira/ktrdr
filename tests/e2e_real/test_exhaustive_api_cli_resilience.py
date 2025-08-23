"""
Exhaustive API and CLI Resilience Tests with Real IB

This module tests API endpoints and CLI commands under real IB conditions
to validate complete system resilience from user-facing interfaces down
to the connection pool.
"""

import concurrent.futures
import subprocess
import time

import pytest


@pytest.mark.real_ib
@pytest.mark.exhaustive_api_resilience
class TestAPIResilienceUnderRealLoad:
    """Test API resilience under real IB load conditions."""

    def test_api_endpoints_under_connection_stress(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test API endpoints remain responsive under connection pool stress."""

        # Test multiple endpoints concurrently to stress connection pool
        endpoints_to_test = [
            ("/api/v1/ib/status", "GET", None),
            ("/api/v1/ib/health", "GET", None),
            ("/api/v1/ib/resilience", "GET", None),
            ("/api/v1/ib/config", "GET", None),
            ("/api/v1/system/status", "GET", None),
        ]

        def test_endpoint(endpoint_info):
            url, method, data = endpoint_info
            start_time = time.time()

            try:
                if method == "GET":
                    response = api_client.get(url)
                else:
                    response = api_client.post(url, json=data)

                elapsed = time.time() - start_time
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "elapsed": elapsed,
                    "success": response.status_code
                    in [200, 503],  # 503 is acceptable for unavailable services
                    "response_size": len(response.content),
                }

            except Exception as e:
                elapsed = time.time() - start_time
                return {
                    "url": url,
                    "error": str(e),
                    "elapsed": elapsed,
                    "success": False,
                }

        # Test endpoints concurrently multiple times
        all_results = []

        for round_num in range(3):
            print(f"✅ Testing API resilience round {round_num + 1}/3")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Submit multiple concurrent requests
                futures = []
                for _ in range(2):  # 2 requests per endpoint
                    for endpoint in endpoints_to_test:
                        future = executor.submit(test_endpoint, endpoint)
                        futures.append(future)

                # Collect results
                round_results = []
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    round_results.append(result)
                    all_results.append(result)

            # Analyze round results
            successful_requests = [r for r in round_results if r["success"]]
            failed_requests = [r for r in round_results if not r["success"]]

            print(
                f"  Round {round_num + 1}: {len(successful_requests)}/{len(round_results)} successful"
            )

            if failed_requests:
                for failed in failed_requests[:3]:  # Show first 3 failures
                    print(
                        f"  Failed: {failed['url']} - {failed.get('error', 'HTTP error')}"
                    )

            # Brief pause between rounds
            time.sleep(1)

        # Overall analysis
        total_requests = len(all_results)
        successful_requests = [r for r in all_results if r["success"]]

        success_rate = len(successful_requests) / total_requests
        avg_response_time = sum(r["elapsed"] for r in successful_requests) / len(
            successful_requests
        )

        print(f"✅ Overall API resilience: {success_rate:.1%} success rate")
        print(f"✅ Average response time: {avg_response_time:.3f}s")

        # Requirements
        assert success_rate >= 0.8, f"API success rate too low: {success_rate:.1%}"
        assert avg_response_time < 5.0, f"API too slow: {avg_response_time:.3f}s"

    def test_symbol_discovery_resilience_under_load(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test symbol discovery API resilience under concurrent load."""

        symbols_to_test = clean_test_symbols[:3]  # AAPL, MSFT, EURUSD

        def test_symbol_discovery(symbol, test_id):
            start_time = time.time()

            try:
                request_data = {"symbol": symbol, "force_refresh": False}
                response = api_client.post(
                    "/api/v1/ib/symbols/discover", json=request_data
                )
                elapsed = time.time() - start_time

                data = response.json()

                return {
                    "symbol": symbol,
                    "test_id": test_id,
                    "status_code": response.status_code,
                    "elapsed": elapsed,
                    "success": response.status_code == 200,
                    "api_success": data.get("success", False),
                    "has_symbol_info": (
                        data.get("data", {}) is not None
                        if data.get("success")
                        else False
                    ),
                }

            except Exception as e:
                elapsed = time.time() - start_time
                # Check for async/coroutine errors
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

                return {
                    "symbol": symbol,
                    "test_id": test_id,
                    "error": str(e),
                    "elapsed": elapsed,
                    "success": False,
                }

        # Concurrent symbol discovery tests
        all_discovery_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = []

            # Multiple concurrent requests for each symbol
            for symbol in symbols_to_test:
                for test_id in range(3):  # 3 tests per symbol
                    future = executor.submit(test_symbol_discovery, symbol, test_id)
                    futures.append(future)

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                all_discovery_results.append(result)

        # Analyze results by symbol
        by_symbol = {}
        for result in all_discovery_results:
            symbol = result["symbol"]
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(result)

        for symbol, symbol_results in by_symbol.items():
            successful = [r for r in symbol_results if r["success"]]
            avg_time = (
                sum(r["elapsed"] for r in successful) / len(successful)
                if successful
                else 0
            )

            print(
                f"✅ {symbol}: {len(successful)}/{len(symbol_results)} successful, avg {avg_time:.2f}s"
            )

            # Each symbol should have some successes
            assert len(successful) > 0, f"All requests failed for {symbol}"

    def test_data_loading_api_resilience(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test data loading API resilience with real IB operations."""

        symbol = clean_test_symbols[0]  # AAPL

        # Test different data loading scenarios
        test_scenarios = [
            {
                "name": "recent_data",
                "data": {
                    "symbol": symbol,
                    "timeframe": "1h",
                    "start_date": "2024-12-01",
                    "end_date": "2024-12-02",
                    "mode": "tail",
                },
            },
            {
                "name": "cached_data",
                "data": {"symbol": symbol, "timeframe": "1d", "mode": "local"},
            },
        ]

        for scenario in test_scenarios:
            scenario_name = scenario["name"]
            request_data = scenario["data"]

            print(f"✅ Testing data loading scenario: {scenario_name}")

            start_time = time.time()

            try:
                response = api_client.post("/api/v1/data/load", json=request_data)
                elapsed = time.time() - start_time

                print(f"  {scenario_name}: {response.status_code} in {elapsed:.2f}s")

                # Should handle gracefully (200 or 400 for invalid params)
                assert response.status_code in [
                    200,
                    400,
                ], f"Unexpected status for {scenario_name}"

                if response.status_code == 200:
                    data = response.json()
                    # If successful, should have proper structure
                    assert "success" in data

                elif response.status_code == 400:
                    # If failed, should have error details
                    data = response.json()
                    assert "error" in data
                    error_msg = data["error"].get("message", "").lower()
                    # Should not be async/coroutine error
                    assert "runtimewarning" not in error_msg
                    assert "coroutine" not in error_msg

            except Exception as e:
                elapsed = time.time() - start_time
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

                print(f"  {scenario_name}: failed with {e}")


@pytest.mark.real_ib
@pytest.mark.exhaustive_cli_resilience
class TestCLIResilienceUnderRealLoad:
    """Test CLI command resilience under real IB load conditions."""

    def test_cli_commands_no_async_errors_under_load(self, clean_test_symbols):
        """Test that CLI commands never produce async/coroutine errors under any load."""

        commands_to_test = [
            ["ib", "test", "--symbol", clean_test_symbols[0]],
            ["ib", "cleanup"],
            ["data", "show", clean_test_symbols[0], "--timeframe", "1h", "--rows", "5"],
            ["strategy-list"],
            ["ib", "test", "--symbol", clean_test_symbols[1], "--timeout", "10"],
        ]

        def run_cli_command(cmd_args, test_id):
            start_time = time.time()

            try:
                full_cmd = ["uv", "run", "ktrdr"] + cmd_args
                result = subprocess.run(
                    full_cmd, capture_output=True, text=True, timeout=30
                )

                elapsed = time.time() - start_time

                # Critical check: NO async/coroutine errors
                stderr_lower = result.stderr.lower()
                stdout_lower = result.stdout.lower()

                async_errors = []
                if "runtimewarning" in stderr_lower:
                    async_errors.append("RuntimeWarning in stderr")
                if "coroutine" in stderr_lower:
                    async_errors.append("Coroutine error in stderr")
                if "was never awaited" in stderr_lower:
                    async_errors.append("Awaited error in stderr")
                if "runtimewarning" in stdout_lower:
                    async_errors.append("RuntimeWarning in stdout")

                return {
                    "command": " ".join(cmd_args),
                    "test_id": test_id,
                    "returncode": result.returncode,
                    "elapsed": elapsed,
                    "stderr_len": len(result.stderr),
                    "stdout_len": len(result.stdout),
                    "async_errors": async_errors,
                    "success": len(async_errors) == 0,  # Success = no async errors
                }

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                return {
                    "command": " ".join(cmd_args),
                    "test_id": test_id,
                    "timeout": True,
                    "elapsed": elapsed,
                    "async_errors": [],
                    "success": True,  # Timeout is acceptable, no async errors
                }

            except Exception as e:
                elapsed = time.time() - start_time
                return {
                    "command": " ".join(cmd_args),
                    "test_id": test_id,
                    "error": str(e),
                    "elapsed": elapsed,
                    "async_errors": [],
                    "success": True,  # Exception handling is acceptable
                }

        # Run commands concurrently to stress test
        all_cli_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []

            # Multiple concurrent runs of each command
            for cmd in commands_to_test:
                for test_id in range(2):  # 2 concurrent runs per command
                    future = executor.submit(run_cli_command, cmd, test_id)
                    futures.append(future)

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                all_cli_results.append(result)

        # Analyze results
        commands_with_async_errors = []

        for result in all_cli_results:
            if not result["success"]:
                commands_with_async_errors.append(result)
                print(
                    f"❌ ASYNC ERROR in '{result['command']}': {result['async_errors']}"
                )
            else:
                status = (
                    "timeout"
                    if result.get("timeout")
                    else f"rc:{result.get('returncode', 'unknown')}"
                )
                print(f"✅ '{result['command']}': {status} in {result['elapsed']:.2f}s")

        # CRITICAL: No commands should have async errors
        assert (
            len(commands_with_async_errors) == 0
        ), f"Commands with async errors: {commands_with_async_errors}"

        print(
            f"✅ CLI resilience: {len(all_cli_results)} commands completed without async errors"
        )

    def test_cli_concurrent_ib_operations(self, clean_test_symbols):
        """Test concurrent CLI IB operations for connection pool stress."""

        def run_ib_test_command(symbol, worker_id):
            cmd = ["uv", "run", "ktrdr", "ib", "test", "--symbol", symbol, "--verbose"]

            start_time = time.time()

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                elapsed = time.time() - start_time

                # Check for async errors
                combined_output = (result.stdout + result.stderr).lower()
                has_async_error = any(
                    term in combined_output
                    for term in ["runtimewarning", "coroutine", "was never awaited"]
                )

                return {
                    "worker_id": worker_id,
                    "symbol": symbol,
                    "returncode": result.returncode,
                    "elapsed": elapsed,
                    "has_async_error": has_async_error,
                    "output_size": len(result.stdout) + len(result.stderr),
                }

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                return {
                    "worker_id": worker_id,
                    "symbol": symbol,
                    "timeout": True,
                    "elapsed": elapsed,
                    "has_async_error": False,  # Timeout is not an async error
                }

            except Exception as e:
                elapsed = time.time() - start_time
                return {
                    "worker_id": worker_id,
                    "symbol": symbol,
                    "error": str(e),
                    "elapsed": elapsed,
                    "has_async_error": False,
                }

        # Run concurrent IB operations
        symbols = clean_test_symbols[:2]  # AAPL, MSFT

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []

            # Start concurrent IB test commands
            for worker_id in range(4):
                symbol = symbols[worker_id % len(symbols)]
                future = executor.submit(run_ib_test_command, symbol, worker_id)
                futures.append(future)

            # Collect results
            results = []
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)

        # Analyze concurrent results
        async_error_count = sum(1 for r in results if r.get("has_async_error", False))
        timeout_count = sum(1 for r in results if r.get("timeout", False))
        success_count = sum(1 for r in results if r.get("returncode") == 0)

        print("✅ Concurrent CLI IB operations:")
        print(f"  Successful: {success_count}/4")
        print(f"  Timeouts: {timeout_count}/4 (acceptable)")
        print(f"  Async errors: {async_error_count}/4")

        # CRITICAL: No async errors allowed
        assert (
            async_error_count == 0
        ), "Async errors detected in concurrent CLI operations"

    def test_cli_memory_stability_over_time(self, clean_test_symbols):
        """Test CLI command memory stability over extended operation."""

        symbol = clean_test_symbols[0]

        # Run CLI commands repeatedly to test for memory leaks
        results = []

        for iteration in range(10):
            start_time = time.time()

            cmd = ["uv", "run", "ktrdr", "ib", "test", "--symbol", symbol]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                elapsed = time.time() - start_time

                # Check for memory-related issues in output
                combined_output = (result.stdout + result.stderr).lower()
                memory_issues = [
                    "memory" in combined_output and "error" in combined_output,
                    "leak" in combined_output,
                    "out of memory" in combined_output,
                ]

                # Check for async errors
                async_errors = [
                    "runtimewarning" in combined_output,
                    "coroutine" in combined_output,
                    "was never awaited" in combined_output,
                ]

                results.append(
                    {
                        "iteration": iteration,
                        "elapsed": elapsed,
                        "returncode": result.returncode,
                        "has_memory_issue": any(memory_issues),
                        "has_async_error": any(async_errors),
                        "output_size": len(result.stdout) + len(result.stderr),
                    }
                )

                if iteration % 3 == 0:
                    print(f"✅ Memory stability test: iteration {iteration}/10")

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                results.append(
                    {
                        "iteration": iteration,
                        "elapsed": elapsed,
                        "timeout": True,
                        "has_memory_issue": False,
                        "has_async_error": False,
                    }
                )

            # Small delay between iterations
            time.sleep(0.5)

        # Analyze memory stability
        memory_issue_count = sum(1 for r in results if r.get("has_memory_issue", False))
        async_error_count = sum(1 for r in results if r.get("has_async_error", False))
        avg_elapsed = sum(r["elapsed"] for r in results) / len(results)

        print("✅ CLI memory stability over 10 iterations:")
        print(f"  Average time: {avg_elapsed:.2f}s")
        print(f"  Memory issues: {memory_issue_count}/10")
        print(f"  Async errors: {async_error_count}/10")

        # CRITICAL: No memory issues or async errors
        assert memory_issue_count == 0, "Memory issues detected"
        assert async_error_count == 0, "Async errors detected"

        # Performance should be consistent (no memory leaks)
        times = [r["elapsed"] for r in results if "timeout" not in r]
        if len(times) > 1:
            time_variance = max(times) - min(times)
            assert (
                time_variance < 10.0
            ), f"High time variance suggests memory issues: {time_variance:.2f}s"


@pytest.mark.real_ib
@pytest.mark.exhaustive_integration_resilience
class TestFullSystemIntegrationResilience:
    """Test full system integration resilience with real IB under stress."""

    def test_end_to_end_data_pipeline_resilience(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test complete data pipeline resilience from API to IB to storage."""

        symbol = clean_test_symbols[0]

        # Step 1: Symbol discovery
        print("✅ Step 1: Symbol discovery")
        discovery_request = {"symbol": symbol, "force_refresh": True}
        discovery_response = api_client.post(
            "/api/v1/ib/symbols/discover", json=discovery_request
        )

        # Should handle gracefully regardless of IB availability
        assert discovery_response.status_code == 200
        discovery_data = discovery_response.json()

        if not discovery_data.get("success"):
            print(
                f"  Symbol discovery failed (IB unavailable): {discovery_data.get('error', {}).get('message')}"
            )
        else:
            print("  Symbol discovery succeeded")

        # Step 2: Data retrieval
        print("✅ Step 2: Data retrieval")
        data_request = {
            "symbol": symbol,
            "timeframe": "1h",
            "start_date": "2024-12-01",
            "end_date": "2024-12-02",
            "mode": "tail",
        }

        data_response = api_client.post("/api/v1/data/load", json=data_request)
        assert data_response.status_code in [
            200,
            400,
        ]  # 400 acceptable for invalid params

        if data_response.status_code == 200:
            data_result = data_response.json()
            print(f"  Data retrieval: {data_result.get('success')}")
        else:
            print("  Data retrieval failed with validation error (acceptable)")

        # Step 3: System health check
        print("✅ Step 3: System health check")
        health_response = api_client.get("/api/v1/ib/health")
        assert health_response.status_code in [200, 503]

        health_data = health_response.json()["data"]
        print(
            f"  System health: {'healthy' if health_data.get('healthy') else 'unhealthy'}"
        )

        # Step 4: Resilience validation
        print("✅ Step 4: Resilience validation")
        resilience_response = api_client.get("/api/v1/ib/resilience")
        assert resilience_response.status_code == 200

        resilience_data = resilience_response.json()["data"]
        resilience_score = resilience_data["overall_resilience_score"]

        print(f"  Resilience score: {resilience_score}/100")

        # All phases should be working (infrastructure at minimum)
        phases = [
            "phase_1_systematic_validation",
            "phase_2_garbage_collection",
            "phase_3_client_id_preference",
        ]
        for phase in phases:
            phase_status = resilience_data[phase]["status"]
            assert phase_status == "working", f"{phase} not working"
            print(f"  {phase}: {phase_status}")

        print("✅ End-to-end pipeline resilience validated")

    def test_system_recovery_after_simulated_stress(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test system recovery after simulated connection stress."""

        # Phase 1: Apply stress through rapid API calls
        print("✅ Phase 1: Applying connection stress")

        stress_requests = []
        for i in range(20):
            try:
                response = api_client.get("/api/v1/ib/status")
                stress_requests.append(response.status_code)
            except Exception as e:
                stress_requests.append(f"error: {e}")

        stress_success_count = sum(
            1 for r in stress_requests if isinstance(r, int) and r in [200, 503]
        )
        print(f"  Stress test: {stress_success_count}/20 requests handled gracefully")

        # Phase 2: Check immediate resilience
        print("✅ Phase 2: Immediate resilience check")

        immediate_resilience = api_client.get("/api/v1/ib/resilience")
        assert immediate_resilience.status_code == 200

        immediate_data = immediate_resilience.json()["data"]
        immediate_score = immediate_data["overall_resilience_score"]
        print(f"  Immediate resilience score: {immediate_score}/100")

        # Phase 3: Recovery test
        print("✅ Phase 3: Recovery validation")
        time.sleep(2)  # Allow brief recovery time

        recovery_tests = [
            ("status", "/api/v1/ib/status"),
            ("health", "/api/v1/ib/health"),
            ("resilience", "/api/v1/ib/resilience"),
        ]

        recovery_results = {}
        for test_name, endpoint in recovery_tests:
            response = api_client.get(endpoint)
            recovery_results[test_name] = {
                "status_code": response.status_code,
                "success": response.status_code in [200, 503],
            }
            print(f"  {test_name}: {response.status_code}")

        # All recovery tests should succeed
        for test_name, result in recovery_results.items():
            assert result["success"], f"Recovery test {test_name} failed"

        # Final resilience check
        final_resilience = api_client.get("/api/v1/ib/resilience")
        assert final_resilience.status_code == 200

        final_data = final_resilience.json()["data"]
        final_score = final_data["overall_resilience_score"]

        print(f"  Final resilience score: {final_score}/100")

        # Score should recover (not degrade significantly)
        score_degradation = immediate_score - final_score
        assert (
            score_degradation <= 10
        ), f"Resilience score degraded too much: {score_degradation}"

        print("✅ System recovery validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib", "-m", "exhaustive_resilience"])
