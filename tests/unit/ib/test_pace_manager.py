"""
Unit tests for IB Pace Manager

Tests the enforcement of official IB pacing rules.
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from ktrdr.ib.pace_manager import IbPaceManager, RequestInfo


class TestIbPaceManager(unittest.TestCase):
    """Test IB pace manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.pace_manager = IbPaceManager()

    def test_general_rate_limit_immediate(self):
        """Test that requests under 50/sec are allowed immediately."""
        # First request should be immediate
        can_proceed, wait_time = self.pace_manager.can_make_request()
        self.assertTrue(can_proceed)
        self.assertEqual(wait_time, 0.0)

        # Record a few requests
        for _ in range(10):
            self.pace_manager._record_request(time.time(), False, None, False)

        # Should still be immediate
        can_proceed, wait_time = self.pace_manager.can_make_request()
        self.assertTrue(can_proceed)
        self.assertEqual(wait_time, 0.0)

    def test_general_rate_limit_exceeded(self):
        """Test rate limiting when 50 requests/sec is exceeded."""
        now = time.time()

        # Fill up the request queue with recent requests
        for _i in range(50):
            self.pace_manager.request_times.append(now - 0.1)  # All within last 100ms

        # Next request should require waiting
        can_proceed, wait_time = self.pace_manager.can_make_request()
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 0.0)
        self.assertLess(wait_time, 1.0)  # Should be less than 1 second

    def test_historical_data_minimum_interval(self):
        """Test 2-second minimum between historical data requests."""
        # First historical request should be immediate
        can_proceed, wait_time = self.pace_manager.can_make_request(is_historical=True)
        self.assertTrue(can_proceed)
        self.assertEqual(wait_time, 0.0)

        # Record the request
        self.pace_manager._record_request(time.time(), True, "AAPL_1h_STK", False)

        # Immediate second request should require waiting
        can_proceed, wait_time = self.pace_manager.can_make_request(is_historical=True)
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 1.0)  # Should be close to 2 seconds
        self.assertLess(wait_time, 2.1)

    def test_historical_data_ten_minute_limit(self):
        """Test 60 requests per 10-minute window."""
        now = time.time()

        # Fill up with 60 requests in the last 10 minutes
        for _i in range(60):
            self.pace_manager.historical_requests.append(
                RequestInfo(
                    timestamp=now - 300,  # 5 minutes ago
                    request_type="historical",
                    contract_key="AAPL_1h_STK",
                    is_bid_ask=False,
                )
            )

        # Next request should require waiting
        can_proceed, wait_time = self.pace_manager.can_make_request(is_historical=True)
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 0.0)

    def test_bid_ask_double_counting(self):
        """Test that BID_ASK requests count double in 10-minute limit."""
        now = time.time()

        # Fill up with 30 BID_ASK requests (counts as 60)
        for _i in range(30):
            self.pace_manager.historical_requests.append(
                RequestInfo(
                    timestamp=now - 300,  # 5 minutes ago
                    request_type="historical",
                    contract_key="AAPL_1h_STK",
                    is_bid_ask=True,
                )
            )

        # Next BID_ASK request should require waiting (would be 62 total)
        can_proceed, wait_time = self.pace_manager.can_make_request(
            is_historical=True, is_bid_ask=True
        )
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 0.0)

    def test_contract_specific_limit(self):
        """Test 6 requests per contract per 2 seconds."""
        contract_key = "AAPL_1h_STK"
        now = time.time()

        # Fill up contract-specific requests
        for _i in range(6):
            self.pace_manager.contract_requests[contract_key].append(now - 0.1)

        # Next request for same contract should require waiting
        can_proceed, wait_time = self.pace_manager.can_make_request(
            is_historical=True, contract_key=contract_key
        )
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 0.0)
        self.assertLess(wait_time, 2.1)

    def test_identical_request_limit(self):
        """Test 15-second minimum between identical requests."""
        contract_key = "AAPL_1h_STK"
        now = time.time()

        # Record an identical request recently
        self.pace_manager.identical_requests[contract_key] = now - 5.0  # 5 seconds ago

        # Same request should require waiting
        can_proceed, wait_time = self.pace_manager.can_make_request(
            is_historical=True, contract_key=contract_key
        )
        self.assertFalse(can_proceed)
        self.assertGreater(wait_time, 9.0)  # Should be around 10 seconds
        self.assertLess(wait_time, 11.0)

    def test_wait_if_needed_general(self):
        """Test async wait functionality for general requests."""

        async def run_test():
            # Should not wait for first request
            start_time = time.time()
            await self.pace_manager.wait_if_needed()
            elapsed = time.time() - start_time
            self.assertLess(elapsed, 0.1)  # Should be nearly instant

        asyncio.run(run_test())

    def test_wait_if_needed_historical(self):
        """Test async wait functionality for historical requests."""

        async def run_test():
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # First request should be immediate
                await self.pace_manager.wait_if_needed(is_historical=True)
                mock_sleep.assert_not_called()

                # Second request should trigger sleep for historical rate limiting
                await self.pace_manager.wait_if_needed(is_historical=True)

                # Verify that sleep was called with approximately 2.0 seconds
                # (historical requests have 2-second minimum spacing)
                mock_sleep.assert_called_once()
                call_args = mock_sleep.call_args[0][
                    0
                ]  # Get the first argument (sleep duration)
                self.assertGreater(call_args, 1.9)  # Should wait close to 2 seconds
                self.assertLess(call_args, 2.1)

        asyncio.run(run_test())

    def test_get_stats(self):
        """Test statistics reporting."""
        # Record some requests
        now = time.time()
        self.pace_manager._record_request(now, False, None, False)  # General
        self.pace_manager._record_request(now, True, "AAPL_1h_STK", False)  # Historical
        self.pace_manager._record_request(now, True, "MSFT_1d_STK", True)  # BID_ASK

        stats = self.pace_manager.get_stats()

        expected_keys = {
            "general_requests_last_second",
            "historical_requests_last_10min",
            "seconds_since_last_historical",
            "tracked_contracts",
            "identical_request_cache_size",
        }
        self.assertEqual(set(stats.keys()), expected_keys)

        self.assertEqual(stats["general_requests_last_second"], 3)
        self.assertEqual(stats["historical_requests_last_10min"], 2)
        self.assertLess(stats["seconds_since_last_historical"], 1.0)
        self.assertEqual(stats["tracked_contracts"], 2)  # AAPL and MSFT
        self.assertEqual(stats["identical_request_cache_size"], 2)

    def test_reset_stats(self):
        """Test statistics reset."""
        # Record some requests
        now = time.time()
        self.pace_manager._record_request(now, True, "AAPL_1h_STK", False)

        # Verify stats exist
        stats = self.pace_manager.get_stats()
        self.assertGreater(stats["general_requests_last_second"], 0)

        # Reset and verify empty
        self.pace_manager.reset_stats()
        stats = self.pace_manager.get_stats()
        self.assertEqual(stats["general_requests_last_second"], 0)
        self.assertEqual(stats["historical_requests_last_10min"], 0)
        self.assertEqual(stats["tracked_contracts"], 0)
        self.assertEqual(stats["identical_request_cache_size"], 0)

    def test_cleanup_old_requests(self):
        """Test automatic cleanup of old requests."""
        now = time.time()

        # Add old historical requests (older than 10 minutes)
        for _i in range(5):
            self.pace_manager.historical_requests.append(
                RequestInfo(
                    timestamp=now - 700,  # More than 10 minutes ago
                    request_type="historical",
                    contract_key="OLD_REQUEST",
                    is_bid_ask=False,
                )
            )

        # Add recent request
        self.pace_manager.historical_requests.append(
            RequestInfo(
                timestamp=now - 60,  # 1 minute ago
                request_type="historical",
                contract_key="RECENT_REQUEST",
                is_bid_ask=False,
            )
        )

        # Check that can_make_request cleans up old requests
        can_proceed, wait_time = self.pace_manager.can_make_request(is_historical=True)

        stats = self.pace_manager.get_stats()
        # Should only have 1 recent request left
        self.assertEqual(stats["historical_requests_last_10min"], 1)

    def test_contract_request_cleanup(self):
        """Test cleanup of old contract-specific requests."""
        contract_key = "AAPL_1h_STK"
        now = time.time()

        # Add old contract requests (older than 2 seconds)
        for _i in range(3):
            self.pace_manager.contract_requests[contract_key].append(now - 5.0)

        # Add recent request
        self.pace_manager.contract_requests[contract_key].append(now - 0.5)

        # Check that cleanup happens during can_make_request
        can_proceed, wait_time = self.pace_manager.can_make_request(
            is_historical=True, contract_key=contract_key
        )

        # Should only have 1 recent request left
        recent_requests = [
            t
            for t in self.pace_manager.contract_requests[contract_key]
            if t >= now - 2.0
        ]
        self.assertEqual(len(recent_requests), 1)


if __name__ == "__main__":
    # Run async tests
    async def run_async_tests():
        test_instance = TestIbPaceManager()
        test_instance.setUp()

        await test_instance.test_wait_if_needed_general()
        await test_instance.test_wait_if_needed_historical()

        print("Async tests completed successfully")

    # Run sync tests
    unittest.main(exit=False)

    # Run async tests if in asyncio context
    try:
        asyncio.run(run_async_tests())
    except RuntimeError:
        print("Skipping async tests (not in async context)")
