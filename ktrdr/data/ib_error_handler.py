"""
Interactive Brokers Error Handler

Centralized error classification, pace violation detection, and recovery logic.
Based on official IB API error codes and empirical testing.
"""

import time
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from ktrdr.logging import get_logger
from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class IbErrorType(Enum):
    """Classification of IB error types for appropriate handling."""

    PACING_VIOLATION = "pacing_violation"
    NO_DATA_AVAILABLE = "no_data_available"
    FUTURE_DATE_REQUEST = "future_date_request"  # NEW: Future date validation error
    HISTORICAL_DATA_LIMIT = (
        "historical_data_limit"  # NEW: Data not available for historical period
    )
    CONNECTION_ERROR = "connection_error"
    PERMISSION_ERROR = "permission_error"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    INFORMATIONAL = "informational"
    UNKNOWN = "unknown"


@dataclass
class IbErrorInfo:
    """Detailed information about an IB error."""

    error_code: int
    error_message: str
    error_type: IbErrorType
    is_retryable: bool
    suggested_wait_time: float  # seconds
    description: str


class IbErrorHandler:
    """
    Centralized IB error handling with pace violation detection and recovery.

    Based on official IB API documentation and community knowledge:
    - https://ibkrcampus.com/ibkr-api-page/trader-workstation-api/#error-codes
    - https://interactivebrokers.github.io/tws-api/message_codes.html
    """

    # Official IB error code classifications
    ERROR_CLASSIFICATIONS = {
        # GENUINE PACING VIOLATIONS (these require waiting)
        165: IbErrorInfo(
            error_code=165,
            error_message="Historical data request pacing violation",
            error_type=IbErrorType.PACING_VIOLATION,
            is_retryable=True,
            suggested_wait_time=60.0,
            description="Direct pacing violation message",
        ),
        200: IbErrorInfo(
            error_code=200,
            error_message="No security definition has been found",
            error_type=IbErrorType.INVALID_REQUEST,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Invalid contract - not a pacing issue",
        ),
        354: IbErrorInfo(
            error_code=354,
            error_message="Requested market data is not subscribed",
            error_type=IbErrorType.PERMISSION_ERROR,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Market data subscription required",
        ),
        # CONNECTION ISSUES (retryable)
        502: IbErrorInfo(
            error_code=502,
            error_message="Couldn't connect to TWS",
            error_type=IbErrorType.CONNECTION_ERROR,
            is_retryable=True,
            suggested_wait_time=5.0,
            description="Connection to TWS/Gateway failed",
        ),
        504: IbErrorInfo(
            error_code=504,
            error_message="Not connected",
            error_type=IbErrorType.CONNECTION_ERROR,
            is_retryable=True,
            suggested_wait_time=2.0,
            description="Client not connected to TWS/Gateway",
        ),
        # INFORMATIONAL (not errors)
        2106: IbErrorInfo(
            error_code=2106,
            error_message="HMDS data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Connection status update",
        ),
        2107: IbErrorInfo(
            error_code=2107,
            error_message="HMDS data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Historical data connection OK",
        ),
        2119: IbErrorInfo(
            error_code=2119,
            error_message="Market data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Market data connection OK",
        ),
    }

    def __init__(self):
        """Initialize the error handler with tracking state."""
        self.pace_violation_count = 0
        self.last_pace_violation_time = 0.0
        self.total_wait_time = 0.0
        self.last_request_context = {}  # Store context for better error classification

        # Proactive pace limiting state
        self.request_history = []  # List of (timestamp, request_type) tuples
        self.last_request_time = 0.0
        self.identical_request_cache = {}  # symbol+timeframe -> last_request_time

    def set_request_context(
        self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str
    ) -> None:
        """
        Set context for the current request to enable intelligent error classification.

        Args:
            symbol: Trading symbol being requested
            start_date: Start date of the request
            end_date: End date of the request
            timeframe: Timeframe being requested
        """
        self.last_request_context = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "is_future_request": end_date > TimestampManager.now_utc(),
            "request_time": TimestampManager.now_utc(),
        }

    def classify_error(
        self, error_code: int, error_message: str, use_context: bool = True
    ) -> IbErrorInfo:
        """
        Classify an IB error for appropriate handling with enhanced 162 classification.

        Args:
            error_code: IB error code
            error_message: Full error message from IB
            use_context: Whether to use request context for enhanced classification

        Returns:
            IbErrorInfo with classification and handling guidance
        """
        # Enhanced handling for error 162 - the most problematic one
        if error_code == 162:
            return self._classify_error_162(error_message, use_context)

        # Use predefined classification if available
        if error_code in self.ERROR_CLASSIFICATIONS:
            base_info = self.ERROR_CLASSIFICATIONS[error_code]
            # Update with actual message
            return IbErrorInfo(
                error_code=error_code,
                error_message=error_message,
                error_type=base_info.error_type,
                is_retryable=base_info.is_retryable,
                suggested_wait_time=base_info.suggested_wait_time,
                description=base_info.description,
            )

        # Unknown error - conservative handling
        return IbErrorInfo(
            error_code=error_code,
            error_message=error_message,
            error_type=IbErrorType.UNKNOWN,
            is_retryable=True,
            suggested_wait_time=30.0,
            description=f"Unknown error code {error_code}",
        )

    def _classify_error_162(self, error_message: str, use_context: bool) -> IbErrorInfo:
        """
        Enhanced classification for error 162 with head timestamp awareness.

        Error 162 can mean:
        1. Future date request (user error)
        2. Historical data limit reached (symbol limitation)
        3. Actual pacing violation (retry needed)
        4. Temporary server issue (retry needed)

        Now uses head timestamp data for much more accurate classification!

        Args:
            error_message: Full error message from IB
            use_context: Whether to use request context

        Returns:
            IbErrorInfo with specific 162 classification
        """
        message_lower = error_message.lower()

        # Check if we have request context for intelligent classification
        if use_context and self.last_request_context:
            context = self.last_request_context

            # 1. Future date request detection
            if context.get("is_future_request", False):
                logger.warning(
                    f"🔮 Error 162 for FUTURE DATE request: {context['end_date']} > now"
                )
                return IbErrorInfo(
                    error_code=162,
                    error_message=error_message,
                    error_type=IbErrorType.FUTURE_DATE_REQUEST,
                    is_retryable=False,
                    suggested_wait_time=0.0,
                    description="Cannot request data for future dates",
                )

            # 2. ENHANCED: Use head timestamp data to detect historical data limits
            symbol = context.get("symbol")
            start_date = context.get("start_date")

            if symbol and start_date:
                head_timestamp_result = self._check_against_head_timestamp(
                    symbol, start_date
                )
                if head_timestamp_result:
                    return head_timestamp_result

            # 3. Fallback: Very old historical data (likely symbol limitation)
            if start_date:
                days_ago = (TimestampManager.now_utc() - start_date).days
                if days_ago > 365 * 5:  # More than 5 years ago
                    logger.info(
                        f"📅 Error 162 for VERY OLD data: {days_ago} days ago for {context['symbol']}"
                    )
                    return IbErrorInfo(
                        error_code=162,
                        error_message=error_message,
                        error_type=IbErrorType.HISTORICAL_DATA_LIMIT,
                        is_retryable=False,
                        suggested_wait_time=0.0,
                        description=f"Historical data not available {days_ago} days ago for {context['symbol']}",
                    )

        # 4. Message-based classification (fallback when no context)
        if any(
            phrase in message_lower
            for phrase in ["no data", "no historical data", "insufficient data"]
        ):
            return IbErrorInfo(
                error_code=162,
                error_message=error_message,
                error_type=IbErrorType.NO_DATA_AVAILABLE,
                is_retryable=False,
                suggested_wait_time=0.0,
                description="No historical data available for requested period",
            )

        # 5. Assume pacing violation for other 162 errors (most common case)
        logger.warning(f"🚦 Assuming error 162 is PACING VIOLATION: {error_message}")
        return IbErrorInfo(
            error_code=162,
            error_message=error_message,
            error_type=IbErrorType.PACING_VIOLATION,
            is_retryable=True,
            suggested_wait_time=60.0,
            description="Assumed HMDS pacing violation based on error 162",
        )

    def _check_against_head_timestamp(
        self, symbol: str, start_date: datetime
    ) -> Optional[IbErrorInfo]:
        """
        Check if error 162 is due to requesting data before symbol's head timestamp.

        This provides much more accurate classification by comparing the request
        against the actual earliest available data for the symbol.

        Args:
            symbol: Symbol being requested
            start_date: Requested start date

        Returns:
            IbErrorInfo if this is a head timestamp violation, None otherwise
        """
        try:
            # Try to access the symbol validator to get head timestamp
            # This is a bit tricky since we don't have direct access, but we can try to import
            # and check if head timestamp data exists in the cache

            from pathlib import Path
            import json

            # Try to load from symbol discovery cache
            cache_file = None
            try:
                from ktrdr.config.settings import get_settings

                settings = get_settings()
                data_dir = (
                    Path(settings.data_dir)
                    if hasattr(settings, "data_dir")
                    else Path("data")
                )
                cache_file = data_dir / "symbol_discovery_cache.json"
            except:
                cache_file = Path("data") / "symbol_discovery_cache.json"

            if cache_file and cache_file.exists():
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)

                # Look for symbol in cache
                cached_symbols = cache_data.get("cache", {})
                if symbol in cached_symbols:
                    symbol_data = cached_symbols[symbol]
                    head_timestamp_str = symbol_data.get("head_timestamp")

                    if head_timestamp_str:
                        # Parse head timestamp
                        head_timestamp = datetime.fromisoformat(
                            head_timestamp_str.replace("Z", "+00:00")
                        )

                        # Compare with requested start date
                        if start_date < head_timestamp:
                            days_before = (head_timestamp - start_date).days

                            logger.warning(
                                f"📅 ERROR 162 CLASSIFICATION: {symbol} head timestamp is {head_timestamp.date()}"
                            )
                            logger.warning(
                                f"📅 Requested start {start_date.date()} is {days_before} days before head timestamp"
                            )

                            if days_before > 7:  # Significant gap
                                logger.error(
                                    f"📅 DEFINITIVE: Error 162 is HISTORICAL DATA LIMIT (not pace violation)"
                                )
                                return IbErrorInfo(
                                    error_code=162,
                                    error_message=f"Data for {symbol} only available from {head_timestamp.date()}, requested from {start_date.date()}",
                                    error_type=IbErrorType.HISTORICAL_DATA_LIMIT,
                                    is_retryable=False,
                                    suggested_wait_time=0.0,
                                    description=f"Historical data for {symbol} starts from {head_timestamp.date()}, requested {days_before} days earlier",
                                )
                            else:
                                logger.info(
                                    f"📅 Small gap ({days_before} days) - could be weekend/holiday, treating as pace violation"
                                )
                                return None
                        else:
                            logger.debug(
                                f"📅 Request {start_date.date()} is after head timestamp {head_timestamp.date()} - not a head timestamp issue"
                            )
                            return None
                    else:
                        logger.debug(
                            f"📅 No head timestamp data available for {symbol} in cache"
                        )
                        return None
                else:
                    logger.debug(f"📅 Symbol {symbol} not found in cache")
                    return None
            else:
                logger.debug(f"📅 Symbol discovery cache not found: {cache_file}")
                return None

        except Exception as e:
            logger.debug(f"📅 Error checking head timestamp for {symbol}: {e}")
            return None

    def handle_error(
        self, error_code: int, error_message: str, req_id: Optional[int] = None
    ) -> Tuple[bool, float]:
        """
        Handle an IB error with appropriate logging and recovery guidance.

        Args:
            error_code: IB error code
            error_message: Full error message from IB
            req_id: Request ID if available

        Returns:
            Tuple of (should_retry, wait_time_seconds)
        """
        error_info = self.classify_error(error_code, error_message)

        # Log based on error type
        if error_info.error_type == IbErrorType.INFORMATIONAL:
            logger.debug(f"IB Info {error_code}: {error_message}")
            return False, 0.0

        elif error_info.error_type == IbErrorType.NO_DATA_AVAILABLE:
            logger.info(f"IB: No data available for request (code {error_code})")
            return False, 0.0

        elif error_info.error_type == IbErrorType.FUTURE_DATE_REQUEST:
            logger.error(f"🔮 FUTURE DATE ERROR: {error_message}")
            logger.error(
                "⚠️  Cannot request data for future dates - check your date parameters!"
            )
            return False, 0.0

        elif error_info.error_type == IbErrorType.HISTORICAL_DATA_LIMIT:
            logger.warning(f"📅 HISTORICAL LIMIT: {error_message}")
            logger.warning(
                "💡 Try requesting more recent data or use a different data source for older periods"
            )
            return False, 0.0

        elif error_info.error_type == IbErrorType.PACING_VIOLATION:
            self.pace_violation_count += 1
            self.last_pace_violation_time = time.time()

            logger.warning(
                f"🚦 PACE VIOLATION #{self.pace_violation_count}: IB error {error_code}"
            )
            logger.warning(
                f"🚦 Will wait {error_info.suggested_wait_time}s before retry"
            )

            return True, error_info.suggested_wait_time

        elif error_info.error_type in [IbErrorType.CONNECTION_ERROR]:
            logger.warning(f"IB Connection Error {error_code}: {error_message}")
            return True, error_info.suggested_wait_time

        else:
            # Other errors
            if error_info.is_retryable:
                logger.warning(f"IB Error {error_code}: {error_message}")
            else:
                logger.error(f"IB Error {error_code}: {error_message}")
            return error_info.is_retryable, error_info.suggested_wait_time

    def wait_for_recovery(
        self, wait_time: float, cancellation_token: Optional[Any] = None
    ) -> None:
        """
        Wait for the specified time with progress logging and cancellation support.

        Args:
            wait_time: Time to wait in seconds
            cancellation_token: Optional cancellation token to check during wait
        """
        if wait_time <= 0:
            return

        logger.info(f"⏳ Waiting {wait_time}s for IB pace recovery...")
        self.total_wait_time += wait_time

        # Break wait into 15-second increments with cancellation checks
        remaining_time = wait_time
        increment = 15.0  # 15-second increments as requested

        while remaining_time > 0:
            # Check for cancellation before each sleep increment
            if cancellation_token:
                self._check_cancellation(cancellation_token)

            # Sleep for the smaller of remaining time or increment
            sleep_time = min(remaining_time, increment)
            time.sleep(sleep_time)
            remaining_time -= sleep_time

            # Log progress for longer waits
            if wait_time > 30 and remaining_time > 0:
                logger.debug(f"⏳ Still waiting... {remaining_time:.1f}s remaining")

        logger.info(f"✅ Wait complete, resuming IB requests")

    def _check_cancellation(self, cancellation_token: Any) -> None:
        """
        Check if cancellation has been requested.

        Args:
            cancellation_token: Token to check for cancellation

        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        # Check if token has cancellation method
        is_cancelled = False
        if hasattr(cancellation_token, "is_cancelled_requested"):
            is_cancelled = cancellation_token.is_cancelled_requested
        elif hasattr(cancellation_token, "is_set"):
            is_cancelled = cancellation_token.is_set()
        elif hasattr(cancellation_token, "cancelled"):
            is_cancelled = cancellation_token.cancelled()

        if is_cancelled:
            logger.info(f"🛑 Cancellation requested during IB error recovery wait")
            # Import here to avoid circular imports
            import asyncio

            raise asyncio.CancelledError(
                "Operation cancelled during error recovery wait"
            )

    def check_proactive_pace_limit(
        self, symbol: str, timeframe: str, cancellation_token: Optional[Any] = None
    ) -> None:
        """
        Proactively check and enforce IB pace limits before making a request.

        This method prevents pace violations by enforcing delays based on:
        1. Request frequency (max 60 requests per 10 minutes)
        2. Identical request cooldown (15+ seconds between identical requests)
        3. Burst limits (max 6 requests per 2 seconds)

        Args:
            symbol: Symbol being requested
            timeframe: Timeframe being requested
            cancellation_token: Optional cancellation token for wait operations

        Raises:
            asyncio.CancelledError: If operation was cancelled during wait
        """
        current_time = time.time()

        # 1. Clean old request history (keep only last 10 minutes)
        self._clean_request_history(current_time)

        # 2. Check overall request frequency (60 requests per 10 minutes)
        wait_for_frequency = self._check_frequency_limit(current_time)

        # 3. Check identical request cooldown (15 seconds between identical)
        # Create proper request key that includes date range for truly identical requests
        request_key = self._create_request_key(symbol, timeframe)
        wait_for_identical = self._check_identical_request_limit(
            request_key, current_time
        )

        # 4. Check burst limit (6 requests per 2 seconds)
        wait_for_burst = self._check_burst_limit(current_time)

        # 5. Minimum delay between any requests (2 seconds)
        wait_for_minimum = self._check_minimum_delay(current_time)

        # Take the maximum required wait time
        total_wait = max(
            wait_for_frequency, wait_for_identical, wait_for_burst, wait_for_minimum
        )

        # Enhanced debug logging to show current pace values
        logger.debug(f"🚦 PACE CHECK for {symbol}:{timeframe}")
        logger.debug(
            f"🚦 Request history: {len(self.request_history)} requests in last 10min"
        )
        logger.debug(
            f"🚦 Last request: {current_time - self.last_request_time:.1f}s ago"
        )
        logger.debug(
            f"🚦 Wait breakdown: freq={wait_for_frequency:.1f}s, identical={wait_for_identical:.1f}s, burst={wait_for_burst:.1f}s, min={wait_for_minimum:.1f}s"
        )

        if total_wait > 0:
            # Show which limit is causing the wait
            primary_reason = (
                "frequency"
                if wait_for_frequency == total_wait
                else (
                    "identical"
                    if wait_for_identical == total_wait
                    else "burst" if wait_for_burst == total_wait else "minimum"
                )
            )

            logger.warning(
                f"🚦 PROACTIVE PACE LIMITING: Waiting {total_wait:.1f}s before {symbol} {timeframe} request (reason: {primary_reason})"
            )
            logger.info(
                f"🚦 Wait breakdown: freq={wait_for_frequency:.1f}s, identical={wait_for_identical:.1f}s, burst={wait_for_burst:.1f}s, min={wait_for_minimum:.1f}s"
            )

            # Use the existing wait method with cancellation support
            self.wait_for_recovery(total_wait, cancellation_token)
        else:
            logger.debug(f"🚦 No pace limiting needed for {symbol}:{timeframe}")

        # 6. Record this request in history
        self._record_request(symbol, timeframe, current_time)

    def _clean_request_history(self, current_time: float) -> None:
        """Remove requests older than 10 minutes from history."""
        cutoff_time = (
            current_time - IbLimitsRegistry.PACING_LIMITS["rate_window_seconds"]
        )
        self.request_history = [
            req for req in self.request_history if req[0] > cutoff_time
        ]

    def _check_frequency_limit(self, current_time: float) -> float:
        """Check if we're approaching the 60 requests per 10 minutes limit."""
        max_requests = IbLimitsRegistry.PACING_LIMITS["max_requests_per_10min"]
        window_seconds = IbLimitsRegistry.PACING_LIMITS["rate_window_seconds"]

        # Count requests in the current window
        window_start = current_time - window_seconds
        requests_in_window = len(
            [req for req in self.request_history if req[0] > window_start]
        )

        # Use 80% of the limit as safety threshold (48 out of 60)
        safety_threshold = int(max_requests * 0.8)

        if requests_in_window >= safety_threshold:
            # Calculate when the oldest request in window will expire
            if self.request_history:
                oldest_in_window = min(
                    req[0] for req in self.request_history if req[0] > window_start
                )
                wait_time = (oldest_in_window + window_seconds) - current_time
                logger.warning(
                    f"🚦 FREQUENCY LIMIT: {requests_in_window}/{max_requests} requests in window, waiting {wait_time:.1f}s"
                )
                return max(0, wait_time)

        return 0.0

    def _check_identical_request_limit(
        self, request_key: str, current_time: float
    ) -> float:
        """Check cooldown for identical requests."""
        if request_key in self.identical_request_cache:
            last_time = self.identical_request_cache[request_key]
            cooldown = IbLimitsRegistry.SAFE_DELAYS["identical_requests"]
            time_since_last = current_time - last_time

            if time_since_last < cooldown:
                wait_time = cooldown - time_since_last
                logger.warning(
                    f"🚦 IDENTICAL REQUEST: {request_key} requested {time_since_last:.1f}s ago, waiting {wait_time:.1f}s"
                )
                return wait_time
            else:
                logger.debug(f"🔍 Cooldown period passed for {request_key}")
        else:
            logger.debug(f"🔍 No previous request found for {request_key}")

        return 0.0

    def _check_burst_limit(self, current_time: float) -> float:
        """Check burst limit (6 requests per 2 seconds)."""
        burst_window = IbLimitsRegistry.PACING_LIMITS["burst_window_seconds"]
        max_burst = IbLimitsRegistry.PACING_LIMITS["burst_limit"]

        # Count requests in the last 2 seconds
        burst_start = current_time - burst_window
        requests_in_burst = len(
            [req for req in self.request_history if req[0] > burst_start]
        )

        if requests_in_burst >= max_burst:
            # Wait for the burst window to clear
            if self.request_history:
                oldest_in_burst = min(
                    req[0] for req in self.request_history if req[0] > burst_start
                )
                wait_time = (oldest_in_burst + burst_window) - current_time
                logger.warning(
                    f"🚦 BURST LIMIT: {requests_in_burst}/{max_burst} requests in {burst_window}s, waiting {wait_time:.1f}s"
                )
                return max(0, wait_time)

        return 0.0

    def _check_minimum_delay(self, current_time: float) -> float:
        """Check minimum delay between any requests."""
        min_delay = IbLimitsRegistry.SAFE_DELAYS["between_requests"]
        time_since_last = current_time - self.last_request_time

        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.debug(
                f"🚦 MINIMUM DELAY: Last request {time_since_last:.1f}s ago, waiting {wait_time:.1f}s"
            )
            return wait_time

        return 0.0

    def _create_request_key(self, symbol: str, timeframe: str) -> str:
        """Create request key for pace tracking - includes date range for truly identical requests."""
        if (
            self.last_request_context
            and self.last_request_context.get("symbol") == symbol
            and self.last_request_context.get("timeframe") == timeframe
        ):
            # Include date range for truly identical request detection
            start_date = self.last_request_context["start_date"]
            end_date = self.last_request_context["end_date"]
            request_key = (
                f"{symbol}:{timeframe}:{start_date.isoformat()}:{end_date.isoformat()}"
            )
            logger.debug(f"🔍 FULL REQUEST KEY: {request_key}")
            return request_key
        else:
            # Fallback to symbol:timeframe if no context available
            request_key = f"{symbol}:{timeframe}"
            logger.warning(
                f"🔍 FALLBACK REQUEST KEY (no context available): {request_key}"
            )
            return request_key

    def _record_request(self, symbol: str, timeframe: str, current_time: float) -> None:
        """Record a request in the history for pace tracking."""
        request_key = self._create_request_key(symbol, timeframe)

        # Add to request history
        self.request_history.append((current_time, request_key))

        # Update identical request cache
        self.identical_request_cache[request_key] = current_time

        # Update last request time
        self.last_request_time = current_time

        logger.debug(
            f"🚦 RECORDED REQUEST: {request_key} at {current_time:.1f} (total history: {len(self.request_history)})"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        current_time = time.time()
        self._clean_request_history(current_time)

        # Calculate request rates
        window_10min = current_time - 600
        window_2sec = current_time - 2

        requests_10min = len(
            [req for req in self.request_history if req[0] > window_10min]
        )
        requests_2sec = len(
            [req for req in self.request_history if req[0] > window_2sec]
        )

        # Calculate what the next wait would be for a hypothetical request
        next_wait_freq = self._check_frequency_limit(current_time)
        next_wait_burst = self._check_burst_limit(current_time)
        next_wait_min = self._check_minimum_delay(current_time)

        return {
            "pace_violations": self.pace_violation_count,
            "last_pace_violation": self.last_pace_violation_time,
            "total_wait_time": self.total_wait_time,
            "time_since_last_violation": (
                time.time() - self.last_pace_violation_time
                if self.last_pace_violation_time > 0
                else 0
            ),
            "requests_in_10min": requests_10min,
            "requests_in_2sec": requests_2sec,
            "total_requests_tracked": len(self.request_history),
            "unique_request_types": len(self.identical_request_cache),
            "is_frequency_safe": requests_10min < 48,  # 80% of 60
            "is_burst_safe": requests_2sec < 6,
            "time_since_last_request": (
                current_time - self.last_request_time
                if self.last_request_time > 0
                else 0
            ),
            "next_wait_frequency": next_wait_freq,
            "next_wait_burst": next_wait_burst,
            "next_wait_minimum": next_wait_min,
            "configured_delays": {
                "between_requests": IbLimitsRegistry.SAFE_DELAYS["between_requests"],
                "identical_requests": IbLimitsRegistry.SAFE_DELAYS[
                    "identical_requests"
                ],
                "burst_recovery": IbLimitsRegistry.SAFE_DELAYS["burst_recovery"],
            },
        }

    def log_pace_status(self) -> None:
        """Log current pace limiting status for debugging."""
        stats = self.get_stats()
        logger.info(f"🚦 PACE STATUS:")
        logger.info(
            f"🚦   Requests in last 10min: {stats['requests_in_10min']}/60 ({stats['requests_in_10min']/60*100:.1f}%)"
        )
        logger.info(f"🚦   Requests in last 2sec: {stats['requests_in_2sec']}/6")
        logger.info(
            f"🚦   Time since last request: {stats['time_since_last_request']:.1f}s"
        )
        logger.info(f"🚦   Current configured delays:")
        logger.info(
            f"🚦     Between requests: {stats['configured_delays']['between_requests']}s"
        )
        logger.info(
            f"🚦     Identical requests: {stats['configured_delays']['identical_requests']}s"
        )
        logger.info(f"🚦   Next request would wait:")
        logger.info(f"🚦     Frequency: {stats['next_wait_frequency']:.1f}s")
        logger.info(f"🚦     Burst: {stats['next_wait_burst']:.1f}s")
        logger.info(f"🚦     Minimum: {stats['next_wait_minimum']:.1f}s")
