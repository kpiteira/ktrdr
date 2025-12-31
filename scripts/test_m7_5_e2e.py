#!/usr/bin/env python3
"""
Real E2E Test for M7.5: Re-Registration Reliability

This script performs a real test of the M7.5 improvements:
1. Records initial workers
2. Restarts backend (graceful SIGTERM)
3. Measures time for workers to re-register
4. Validates fast re-registration (~5-15s vs old ~30-40s)

Usage:
    uv run python scripts/test_m7_5_e2e.py
"""

import subprocess
import sys
import time

import httpx

API_BASE_URL = "http://localhost:8000/api/v1"


def get_workers() -> list:
    """Get list of registered workers."""
    try:
        response = httpx.get(f"{API_BASE_URL}/workers", timeout=5.0)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def check_api_available() -> bool:
    """Check if API is available."""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_api(timeout: int = 60) -> bool:
    """Wait for API to become available."""
    start = time.time()
    while time.time() - start < timeout:
        if check_api_available():
            return True
        time.sleep(0.5)
    return False


def restart_backend() -> bool:
    """Restart the backend container using docker compose."""
    try:
        result = subprocess.run(
            ["docker", "compose", "restart", "backend"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to restart backend: {e}")
        return False


def main():
    print("=" * 60)
    print("M7.5 E2E Test: Fast Re-Registration After Graceful Restart")
    print("=" * 60)
    print()

    # Step 1: Check API is available
    print("Step 1: Checking API availability...")
    if not check_api_available():
        print("ERROR: API is not available. Start containers with: docker compose up -d")
        sys.exit(1)
    print("  ✓ API is available")

    # Step 2: Get initial workers
    print("\nStep 2: Recording initial workers...")
    initial_workers = get_workers()
    if not initial_workers:
        print("ERROR: No workers registered. Restart workers and try again.")
        sys.exit(1)

    initial_count = len(initial_workers)
    worker_ids = [w["worker_id"] for w in initial_workers]
    print(f"  ✓ Found {initial_count} workers:")
    for wid in worker_ids:
        print(f"    - {wid}")

    # Step 3: Restart backend (graceful - sends SIGTERM)
    print("\nStep 3: Restarting backend (graceful shutdown)...")
    restart_start = time.time()

    if not restart_backend():
        print("ERROR: Failed to restart backend")
        sys.exit(1)
    print("  ✓ Restart command sent")

    # Step 4: Wait for backend to become available
    print("\nStep 4: Waiting for backend to become available...")
    if not wait_for_api(timeout=30):
        print("ERROR: Backend failed to restart within 30 seconds")
        sys.exit(1)

    backend_ready_time = time.time() - restart_start
    print(f"  ✓ Backend ready after {backend_ready_time:.1f}s")

    # Step 5: Poll for workers to re-register
    print("\nStep 5: Waiting for workers to re-register...")
    reregistration_start = time.time()

    max_wait = 20  # Should be much faster than old 30-40s
    poll_interval = 0.5

    while time.time() - reregistration_start < max_wait:
        workers = get_workers()
        current_count = len(workers)
        elapsed = time.time() - reregistration_start

        print(f"  [{elapsed:5.1f}s] {current_count}/{initial_count} workers registered", end="\r")

        if current_count >= initial_count:
            break

        time.sleep(poll_interval)

    print()  # New line after progress

    # Step 6: Validate results
    reregistration_time = time.time() - reregistration_start
    final_workers = get_workers()
    final_count = len(final_workers)

    print(f"\n  ✓ {final_count} workers re-registered in {reregistration_time:.1f}s")

    # Check which workers re-registered
    registered_ids = [w["worker_id"] for w in final_workers]
    missing = [wid for wid in worker_ids if wid not in registered_ids]

    if missing:
        print(f"\n  ⚠ Missing workers: {missing}")

    # Step 7: Final verdict
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    total_time = time.time() - restart_start

    print(f"  Total restart time:      {total_time:.1f}s")
    print(f"  Backend ready time:      {backend_ready_time:.1f}s")
    print(f"  Re-registration time:    {reregistration_time:.1f}s")
    print(f"  Workers registered:      {final_count}/{initial_count}")

    # Determine pass/fail
    # M7.5 target: < 15s for re-registration (was ~30-40s before)
    if reregistration_time < 15 and final_count >= initial_count:
        print("\n✅ TEST PASSED!")
        print(f"   Workers re-registered in {reregistration_time:.1f}s (target: <15s)")
        return 0
    elif reregistration_time < 20 and final_count >= initial_count:
        print("\n⚠️  TEST MARGINAL")
        print(f"   Workers re-registered in {reregistration_time:.1f}s (target: <15s, max: 20s)")
        return 0
    else:
        print("\n❌ TEST FAILED!")
        if reregistration_time >= 20:
            print(f"   Re-registration took {reregistration_time:.1f}s (expected <15s)")
        if final_count < initial_count:
            print(f"   Only {final_count}/{initial_count} workers re-registered")
        return 1


if __name__ == "__main__":
    sys.exit(main())
