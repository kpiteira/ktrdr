"""
Real End-to-End Tests

These tests require actual IB Gateway connection and test the complete system
with real IB API interactions, not mocked components.

Prerequisites:
- IB Gateway or TWS running on localhost:4002 (or configured host/port)
- Valid IB account (paper trading recommended for tests)
- Network connectivity to IB servers

Usage:
    # Run all real E2E tests (requires IB Gateway)
    pytest tests/e2e_real/ -v --real-ib

    # Run specific test categories
    pytest tests/e2e_real/test_real_cli.py -v --real-ib
    pytest tests/e2e_real/test_real_api.py -v --real-ib

    # Skip real E2E tests (default behavior)
    pytest tests/e2e_real/ -v  # Will skip all tests
"""
