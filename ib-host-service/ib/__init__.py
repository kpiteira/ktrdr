"""
IB (Interactive Brokers) integration package.

This package contains all IB Gateway connection code that was moved from ktrdr/ib/.
The code lives in the host service because it requires direct TCP access to IB Gateway,
which is not available from within Docker containers.

Package structure:
- connection.py: IB Gateway connection management
- pool.py: Connection pool for IB
- pool_manager.py: Pool lifecycle management
- data_fetcher.py: Historical data fetching from IB
- symbol_validator.py: Symbol validation with IB
- trading_hours_parser.py: Trading hours parsing
- pace_manager.py: Rate limiting for IB API
- error_classifier.py: IB error classification and handling

Import pattern:
    from ib import IbDataFetcher  # Local import within host service
    from ktrdr.logging import get_logger  # Shared utility via sys.path

Note: Backend (Docker) NEVER imports from this package. It uses HTTP to call
the host service endpoints instead.
"""
