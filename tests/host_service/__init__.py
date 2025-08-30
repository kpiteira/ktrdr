"""
Host service tests - require actual running services.

These tests are designed to run against real host services:
- IB Gateway/TWS (Interactive Brokers)
- Training services 
- Other external services that cannot be easily mocked

Usage:
    make test-host  # Run all host service tests
    
Requirements:
    - IB Gateway or TWS running with paper trading account
    - Training services running (if applicable)
    - Network connectivity to external services
    
Note: These tests are not run in CI/CD pipelines.
"""