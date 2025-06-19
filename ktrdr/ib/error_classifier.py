"""
IB Error Classifier

Accurate classification of Interactive Brokers API error codes based on official documentation:
- https://interactivebrokers.github.io/tws-api/message_codes.html
- https://interactivebrokers.github.io/tws-api/historical_limitations.html
- https://www.interactivebrokers.com/campus/ibkr-api-page/tws-api-error-codes/

This classifier is based on comprehensive research of official IB documentation
and real-world usage patterns.
"""

from typing import Tuple
from enum import Enum

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IbErrorType(Enum):
    """Classification of IB error types for appropriate handling"""

    FATAL = "fatal"  # No retry - permanent issues
    RETRYABLE = "retryable"  # Can retry after delay
    PACING_VIOLATION = "pacing"  # Specific pacing violation
    DATA_UNAVAILABLE = "data_unavail"  # Data not available but request was valid
    CONNECTION_ERROR = "connection"  # Connection/network issues
    PERMISSION_ERROR = "permission"  # Market data permissions required


class IbErrorClassifier:
    """
    Classify IB errors based on OFFICIAL IB documentation.

    Error classifications based on research of official sources:
    - Official TWS API documentation
    - Real-world usage patterns
    - Community findings and discussions
    """

    # Official error code classifications based on IB documentation
    ERROR_MAPPINGS = {
        # === PACING VIOLATIONS ===
        100: (
            "Max rate of messages per second has been exceeded",
            IbErrorType.PACING_VIOLATION,
            60.0,
        ),
        420: (
            "Invalid real-time query (pacing violation)",
            IbErrorType.PACING_VIOLATION,
            60.0,
        ),
        # === CONNECTION ERRORS (retryable) ===
        1100: (
            "Connectivity between IB and the TWS has been lost",
            IbErrorType.CONNECTION_ERROR,
            5.0,
        ),
        1101: (
            "Connectivity between IB and TWS has been restored",
            IbErrorType.CONNECTION_ERROR,
            0.0,
        ),
        1102: (
            "Connectivity between IB and TWS has been restored",
            IbErrorType.CONNECTION_ERROR,
            0.0,
        ),
        326: ("Client id is already in use", IbErrorType.CONNECTION_ERROR, 2.0),
        502: ("Couldn't connect to TWS", IbErrorType.CONNECTION_ERROR, 5.0),
        504: ("Not connected", IbErrorType.CONNECTION_ERROR, 2.0),
        507: ("Bad message length", IbErrorType.CONNECTION_ERROR, 1.0),
        # === MARKET DATA PERMISSIONS (fatal) ===
        200: (
            "No security definition has been found for the request",
            IbErrorType.FATAL,
            0.0,
        ),
        354: (
            "Requested market data is not subscribed",
            IbErrorType.PERMISSION_ERROR,
            0.0,
        ),
        10090: (
            "Part of requested market data is not subscribed",
            IbErrorType.PERMISSION_ERROR,
            0.0,
        ),
        10197: ("No market data permissions", IbErrorType.PERMISSION_ERROR, 0.0),
        # === HISTORICAL DATA ERRORS ===
        # Based on research: 162 and 165 are historical data service messages
        162: (
            "Historical Market Data Service error message",
            IbErrorType.DATA_UNAVAILABLE,
            0.0,
        ),
        165: (
            "Historical Market Data Service query message",
            IbErrorType.DATA_UNAVAILABLE,
            0.0,
        ),
        430: (
            "Fundamentals data for the security specified is not available",
            IbErrorType.DATA_UNAVAILABLE,
            0.0,
        ),
        # === CONNECTIVITY STATUS (informational) ===
        2103: (
            "Market data farm connection is broken",
            IbErrorType.CONNECTION_ERROR,
            2.0,
        ),
        2104: ("Market data farm connection is OK", IbErrorType.CONNECTION_ERROR, 0.0),
        2105: (
            "HMDS data farm connection is broken",
            IbErrorType.CONNECTION_ERROR,
            2.0,
        ),
        2106: ("HMDS data farm connection is OK", IbErrorType.CONNECTION_ERROR, 0.0),
        2107: (
            "HMDS data farm connection is inactive",
            IbErrorType.CONNECTION_ERROR,
            2.0,
        ),
        2108: (
            "Market data farm connection is inactive",
            IbErrorType.CONNECTION_ERROR,
            2.0,
        ),
        2119: ("Market data farm connection is OK", IbErrorType.CONNECTION_ERROR, 0.0),
        # === FATAL ERRORS (do not retry) ===
        154: (
            "Orders cannot be transmitted for a halted security",
            IbErrorType.FATAL,
            0.0,
        ),
        392: ("Invalid order: contract expired", IbErrorType.FATAL, 0.0),
    }

    # Transport-related error keywords (usually retryable)
    TRANSPORT_ERROR_KEYWORDS = [
        "handler is closed",
        "transport closed",
        "connection closed",
        "unable to perform operation",
        "socket",
        "tcp",
        "connection lost",
        "disconnected",
    ]

    # Market data permission keywords (usually fatal)
    PERMISSION_ERROR_KEYWORDS = [
        "not subscribed",
        "no market data permissions",
        "market data permission",
        "subscription required",
    ]

    @classmethod
    def classify(cls, error_code: int, error_message: str) -> Tuple[IbErrorType, float]:
        """
        Classify error and return (type, suggested_wait_seconds)

        Args:
            error_code: IB error code
            error_message: IB error message text

        Returns:
            Tuple of (error_type, suggested_wait_seconds)
        """
        logger.debug(
            f"Classifying IB error: code={error_code}, message='{error_message}'"
        )

        # Check explicit error code mappings first
        if error_code in cls.ERROR_MAPPINGS:
            description, error_type, wait_time = cls.ERROR_MAPPINGS[error_code]
            logger.debug(
                f"Found explicit mapping: {description} -> {error_type.value}, wait={wait_time}s"
            )
            return error_type, wait_time

        # Check message content for transport errors
        error_message_lower = error_message.lower()

        # Transport/connection errors (usually retryable)
        if any(
            keyword in error_message_lower for keyword in cls.TRANSPORT_ERROR_KEYWORDS
        ):
            logger.debug("Detected transport error from message keywords")
            return IbErrorType.CONNECTION_ERROR, 2.0

        # Permission errors (usually fatal)
        if any(
            keyword in error_message_lower for keyword in cls.PERMISSION_ERROR_KEYWORDS
        ):
            logger.debug("Detected permission error from message keywords")
            return IbErrorType.PERMISSION_ERROR, 0.0

        # Check for specific historical data messages
        if "historical" in error_message_lower and "data" in error_message_lower:
            if "pacing" in error_message_lower or "violation" in error_message_lower:
                logger.debug("Detected historical data pacing violation")
                return IbErrorType.PACING_VIOLATION, 60.0
            else:
                logger.debug("Detected historical data unavailable")
                return IbErrorType.DATA_UNAVAILABLE, 0.0

        # Default: assume retryable with moderate wait
        logger.debug("No specific classification found, defaulting to retryable")
        return IbErrorType.RETRYABLE, 5.0

    @classmethod
    def is_client_id_conflict(cls, error_message: str) -> bool:
        """Check if error is client ID conflict (error 326)"""
        return "326" in error_message or "already in use" in error_message.lower()

    @classmethod
    def should_retry(cls, error_type: IbErrorType) -> bool:
        """Determine if error should be retried"""
        return error_type in [
            IbErrorType.RETRYABLE,
            IbErrorType.PACING_VIOLATION,
            IbErrorType.CONNECTION_ERROR,
        ]

    @classmethod
    def is_fatal(cls, error_type: IbErrorType) -> bool:
        """Check if error is fatal (should not retry)"""
        return error_type in [IbErrorType.FATAL, IbErrorType.PERMISSION_ERROR]

    @classmethod
    def get_retry_delay(cls, error_type: IbErrorType, attempt_count: int = 1) -> float:
        """
        Get suggested retry delay with exponential backoff

        Args:
            error_type: Type of error
            attempt_count: Number of previous attempts (for backoff)

        Returns:
            Suggested delay in seconds
        """
        if cls.is_fatal(error_type):
            return 0.0  # No retry

        # Base delays by error type
        base_delays = {
            IbErrorType.CONNECTION_ERROR: 2.0,
            IbErrorType.PACING_VIOLATION: 60.0,
            IbErrorType.DATA_UNAVAILABLE: 0.0,
            IbErrorType.RETRYABLE: 5.0,
        }

        base_delay = base_delays.get(error_type, 5.0)

        # Apply exponential backoff, but cap at reasonable limits
        if error_type == IbErrorType.PACING_VIOLATION:
            # For pacing violations, don't use exponential backoff
            return base_delay
        else:
            # Exponential backoff with cap
            backoff_delay = base_delay * (2 ** (attempt_count - 1))
            return min(backoff_delay, 60.0)  # Cap at 1 minute

    @classmethod
    def format_error_info(cls, error_code: int, error_message: str) -> dict:
        """
        Format error information for logging and API responses

        Returns:
            Dictionary with error classification and details
        """
        error_type, wait_time = cls.classify(error_code, error_message)

        return {
            "error_code": error_code,
            "error_message": error_message,
            "error_type": error_type.value,
            "is_retryable": cls.should_retry(error_type),
            "is_fatal": cls.is_fatal(error_type),
            "suggested_wait_seconds": wait_time,
            "classification_source": "official_ib_documentation",
        }
