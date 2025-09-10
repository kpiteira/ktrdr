"""
Interactive Brokers API limits and constraints registry.

This module centralizes all IB API limits, pacing requirements, and timing constraints
to eliminate duplication across the codebase and provide a single source of truth.

Based on official IB API documentation and empirical testing.
"""

from datetime import timedelta


class IbLimitsRegistry:
    """Single source of truth for all IB API limits and constraints."""

    # =============================================================================
    # IB API OFFICIAL DURATION LIMITS
    # Based on: https://ibkrcampus.com/ibkr-api-page/trader-workstation-api/#tws-api-historical-data
    # =============================================================================

    DURATION_LIMITS = {
        # Short timeframes - limited by bar count (up to 2000 bars max)
        "1 sec": timedelta(seconds=1800),  # 30 minutes of 1-second bars
        "5 secs": timedelta(seconds=10000),  # ~2.8 hours of 5-second bars
        "10 secs": timedelta(seconds=20000),  # ~5.6 hours of 10-second bars
        "15 secs": timedelta(seconds=30000),  # ~8.3 hours of 15-second bars
        "30 secs": timedelta(hours=16),  # 16 hours of 30-second bars
        # Standard timeframes - commonly used
        "1 min": timedelta(days=1),  # 1 day of 1-minute bars
        "2 mins": timedelta(days=2),  # 2 days of 2-minute bars
        "3 mins": timedelta(days=3),  # 3 days of 3-minute bars
        "5 mins": timedelta(days=7),  # 1 week of 5-minute bars
        "10 mins": timedelta(days=14),  # 2 weeks of 10-minute bars
        "15 mins": timedelta(days=14),  # 2 weeks of 15-minute bars
        "20 mins": timedelta(days=20),  # 20 days of 20-minute bars
        "30 mins": timedelta(days=30),  # 30 days of 30-minute bars
        # Hourly and daily timeframes
        "1 hour": timedelta(days=30),  # 30 days of hourly bars
        "2 hours": timedelta(days=60),  # 60 days of 2-hour bars
        "3 hours": timedelta(days=90),  # 90 days of 3-hour bars
        "4 hours": timedelta(days=120),  # 120 days of 4-hour bars
        "8 hours": timedelta(days=240),  # 240 days of 8-hour bars
        # Daily and weekly timeframes
        "1 day": timedelta(days=365),  # 1 year of daily bars
        "1 week": timedelta(days=730),  # 2 years of weekly bars
        "1 month": timedelta(days=3650),  # 10 years of monthly bars
    }

    # Simplified aliases for common usage
    SIMPLE_DURATION_LIMITS = {
        "1m": timedelta(days=1),
        "5m": timedelta(days=7),
        "15m": timedelta(days=14),
        "30m": timedelta(days=30),
        "1h": timedelta(days=30),
        "4h": timedelta(days=120),
        "1d": timedelta(days=365),
        "1w": timedelta(days=730),
    }

    # =============================================================================
    # IB API PACING REQUIREMENTS
    # Based on: https://ibkrcampus.com/ibkr-api-page/trader-workstation-api/#tws-api-pacing-violations
    # =============================================================================

    PACING_LIMITS = {
        # Request frequency limits
        "max_requests_per_10min": 60,  # No more than 60 historical data requests in 10 minutes
        "identical_request_cooldown": 15,  # Wait 15 seconds between identical requests
        "burst_limit": 6,  # Max 6 requests per 2 seconds for same contract
        "bid_ask_multiplier": 2,  # BID_ASK requests count as 2 normal requests
        # Connection limits
        "max_client_connections": 32,  # Max 32 API client connections per IBKR account
        "max_market_data_lines": 100,  # Max 100 market data lines (varies by account)
        # Data limits
        "max_bars_per_request": 2000,  # IB returns max 2000 bars per request
        "head_timestamp_cache_ttl": 3600,  # Cache head timestamps for 1 hour
        # Rate limiting windows
        "rate_window_seconds": 600,  # 10-minute window for request counting
        "burst_window_seconds": 2,  # 2-second window for burst detection
    }

    # =============================================================================
    # SAFE DELAYS AND TIMING
    # Conservative timing to avoid pacing violations
    # =============================================================================

    SAFE_DELAYS = {
        # Request delays (conservative but reasonable)
        "between_requests": 1.0,  # 1 second between different requests (reasonable)
        "identical_requests": 15.0,  # 15 seconds between truly identical requests (IB recommendation)
        "burst_recovery": 3.0,  # 3 seconds after burst of requests
        "connection_delay": 1.0,  # 1 second after connection established
        # Progressive loading delays
        "progressive_chunk_delay": 2.0,  # 2 seconds between chunks in progressive loading
        "progressive_retry_delay": 10.0,  # 10 seconds before retrying failed chunk
        # Error recovery delays
        "pacing_violation_delay": 30.0,  # 30 seconds after pacing violation
        "connection_error_delay": 5.0,  # 5 seconds after connection error
        "data_error_delay": 2.0,  # 2 seconds after data error
    }

    # =============================================================================
    # GAP DETECTION THRESHOLDS
    # How long a gap must be before we consider it worth filling
    # =============================================================================

    GAP_THRESHOLDS = {
        # Threshold in hours - gaps smaller than this are ignored
        "1m": 0.5,  # 30 minutes for 1-minute bars
        "5m": 1.0,  # 1 hour for 5-minute bars
        "15m": 2.0,  # 2 hours for 15-minute bars
        "30m": 3.0,  # 3 hours for 30-minute bars
        "1h": 6.0,  # 6 hours for hourly bars
        "4h": 12.0,  # 12 hours for 4-hour bars
        "1d": 18.0,  # 18 hours (next trading day) for daily bars
        "1w": 7 * 24,  # 1 week for weekly bars
    }

    # =============================================================================
    # CLIENT ID ALLOCATION STRATEGY
    # Organized ranges for different use cases
    # =============================================================================

    CLIENT_ID_RANGES = {
        # Production API connections
        "api_singleton": list(
            range(1, 11)
        ),  # 1-10: Singleton connections (API, gap filler)
        "api_pool": list(range(11, 51)),  # 11-50: Connection pool for API requests
        # Background services
        "gap_filler": list(range(101, 111)),  # 101-110: Gap filling service
        "data_manager": list(range(111, 121)),  # 111-120: DataManager IB fallback
        "symbol_validation": list(
            range(121, 131)
        ),  # 121-130: Symbol validation service
        # Development and testing
        "cli_temporary": list(range(201, 251)),  # 201-250: CLI temporary connections
        "test_connections": list(range(251, 299)),  # 251-298: Test connections
        # Reserved
        "reserved": [299],  # 299: Reserved for special cases
    }

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    @classmethod
    def get_duration_limit(cls, timeframe: str) -> timedelta:
        """
        Get the maximum duration for a single IB request for given timeframe.

        Args:
            timeframe: Timeframe string (e.g., '1m', '1h', '1d', '1 min', '1 hour')

        Returns:
            Maximum timedelta for single request

        Raises:
            ValueError: If timeframe is not supported
        """
        # Try simple format first (1m, 1h, 1d)
        if timeframe in cls.SIMPLE_DURATION_LIMITS:
            return cls.SIMPLE_DURATION_LIMITS[timeframe]

        # Try full format (1 min, 1 hour, 1 day)
        if timeframe in cls.DURATION_LIMITS:
            return cls.DURATION_LIMITS[timeframe]

        # Common aliases
        aliases = {
            "minute": "1 min",
            "hour": "1 hour",
            "daily": "1 day",
            "day": "1 day",
            "week": "1 week",
            "weekly": "1 week",
        }

        if timeframe in aliases:
            return cls.DURATION_LIMITS[aliases[timeframe]]

        raise ValueError(
            f"Unsupported timeframe: {timeframe}. Supported: {list(cls.SIMPLE_DURATION_LIMITS.keys())}"
        )

    @classmethod
    def get_gap_threshold_hours(cls, timeframe: str) -> float:
        """
        Get gap detection threshold in hours for given timeframe.

        Args:
            timeframe: Timeframe string

        Returns:
            Threshold in hours
        """
        return cls.GAP_THRESHOLDS.get(timeframe, 6.0)  # Default to 6 hours

    @classmethod
    def get_safe_delay(cls, delay_type: str) -> float:
        """
        Get safe delay duration for given operation.

        Args:
            delay_type: Type of delay needed

        Returns:
            Delay in seconds
        """
        return cls.SAFE_DELAYS.get(delay_type, 2.0)  # Default to 2 seconds

    @classmethod
    def get_client_id_for_purpose(cls, purpose: str, index: int = 0) -> int:
        """
        Get appropriate client ID for given purpose.

        Args:
            purpose: Purpose category (e.g., 'api_singleton', 'gap_filler')
            index: Index within the range (0-based)

        Returns:
            Client ID to use

        Raises:
            ValueError: If purpose not found or index out of range
        """
        if purpose not in cls.CLIENT_ID_RANGES:
            raise ValueError(
                f"Unknown purpose: {purpose}. Available: {list(cls.CLIENT_ID_RANGES.keys())}"
            )

        range_list = cls.CLIENT_ID_RANGES[purpose]
        if index >= len(range_list):
            raise ValueError(
                f"Index {index} out of range for {purpose} (max: {len(range_list) - 1})"
            )

        return range_list[index]

    @classmethod
    def calculate_progressive_chunks(
        cls, timeframe: str, total_duration: timedelta
    ) -> int:
        """
        Calculate how many chunks needed for progressive loading.

        Args:
            timeframe: Timeframe string
            total_duration: Total time range to fetch

        Returns:
            Number of chunks needed
        """
        max_duration = cls.get_duration_limit(timeframe)

        if total_duration <= max_duration:
            return 1

        # Calculate chunks with small buffer for overlap
        chunks = int(
            (total_duration.total_seconds() / max_duration.total_seconds()) + 0.5
        )
        return max(1, chunks)

    @classmethod
    def is_pacing_safe(cls, requests_in_window: int, window_seconds: int = 600) -> bool:
        """
        Check if current request rate is within IB pacing limits.

        Args:
            requests_in_window: Number of requests made in time window
            window_seconds: Time window in seconds (default: 10 minutes)

        Returns:
            True if rate is safe, False if approaching limits
        """
        max_requests = cls.PACING_LIMITS["max_requests_per_10min"]

        # Scale limit based on actual window size
        scaled_limit = (max_requests * window_seconds) / 600  # 600 = 10 minutes

        # Use 80% of limit as safety threshold
        safety_threshold = scaled_limit * 0.8

        return requests_in_window < safety_threshold
